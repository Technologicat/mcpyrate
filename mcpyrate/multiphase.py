# -*- coding: utf-8; -*-
"""Multi-phase compiler, to allow a module to use macros defined in that module itself.

See the `with phase[n]` construct.

Note `__main__` is a module, too, so if `app.py` uses `with phase`,
running as `macropython app.py` is fine.
"""

__all__ = ["phase", "ismultiphase", "detect_highest_phase", "multiphase_expand"]

import ast
from copy import copy, deepcopy
import sys
from types import ModuleType

from .coreutils import ismacroimport
from .expander import find_macros, expand_macros, destructure_candidate, global_postprocess
from .markers import check_no_markers_remaining

# --------------------------------------------------------------------------------

def iswithphase(stmt):
    """Detect `with phase[n]`, where `n >= 1` is an integer.

    Return `n`, or `False`.
    """
    if type(stmt) is not ast.With:
        return False
    if len(stmt.items) != 1:
        return False

    item = stmt.items[0]
    if item.optional_vars is not None:  # no as-part allowed
        return False

    candidate = item.context_expr
    if type(candidate) is not ast.Subscript:
        return False

    macroname, macroargs = destructure_candidate(candidate)
    if macroname != "phase":
        return False
    if not macroargs or len(macroargs) != 1:  # exactly one macro-argument
        return False

    arg = macroargs[0]
    if type(arg) is ast.Constant:
        n = arg.value
    elif type(arg) is ast.Num:  # TODO: remove ast.Num once we bump minimum language version to Python 3.8
        n = arg.n
    else:
        return False

    if not isinstance(n, int) or n < 1:
        return False

    return n


def split_multiphase_module_ast(tree, *, phase=0):
    """Split `ast.Module` `tree` into given phase and remaining parts.

    The statements belonging to this phase are returned as a new `ast.Module`,
    and the `body` attribute of the original `tree` is overwritten with the
    remaining statements.
    """
    if not isinstance(phase, int):
        raise TypeError  # TODO: proper error message
    if phase < 0:
        raise ValueError  # TODO: proper error message
    if phase == 0:
        return tree
    remaining = []
    thisphase = []
    for stmt in tree.body:
        if iswithphase(stmt) == phase:
            thisphase.extend(stmt.body)
        else:
            remaining.append(stmt)
    tree.body[:] = remaining
    out = copy(tree)
    out.body = thisphase
    return out

# --------------------------------------------------------------------------------

def phase(tree, syntax, **kw):
    """[syntax, block] Control multi-phase compilation.

    Allows a module to use macros defined in that module itself.

    Phases count down from whatever is the highest declared, down to an
    implicit final phase 0. Once the phase-0 code has been macro-expanded
    and compiled, the module is sent to the regular import machinery.

    All code from phase `k + 1` is lifted to phase `k`. The chain continues
    until `k = 0`. This means e.g. that any macros or functions defined in
    **any** phase will be available in the final compiled module.

    Mutations of state, however, will not; each phase starts as a new module.

    Usage::

        with phase[1]:
            # macro definitions here

        # everything not inside a `with phase` is implicitly phase 0

        # use the magic module name __self__ to import macros from a higher phase
        from __self__ import macros, ...

        # then just code as usual

    To run, `macropython app.py`.

    The phase number must be a positive integer literal.

    The `with phase` construct may only appear at the top level of the module.

    The syntax `from __self__ import macros, ...` is a *self-macro-import*,
    which imports macros from any higher-numbered phase of the same module
    it appears in.

    Self-macro-imports vanish during macro expansion (leaving just a coverage
    dummy node), because a module does not need to really import itself. This
    is just a macropythonic syntax to register macro bindings.

    If you need to write helper macros to define your phase 1 macros::

        with phase[2]:
            # define macros used by phase 1 here

        with phase[1]:
            # macro-imports (also self-macro-imports) may appear
            # at the top level of a `with phase`.
            from __self__ import macros, ...

            # define macros used by phase 0 here

        # everything not inside a `with phase` is implicitly phase 0

        # you can import macros from any higher phase, not just phase 1
        from __self__ import macros, ...

        # then just code as usual

    **NOTE**: Strictly speaking, multi-phase compilation is not a macro;
    it is actually a feature of the `mcpyrate` importer.

    **NOTE**: This is a sloppy pythonification of Racket's phase level tower:

        https://docs.racket-lang.org/guide/phases.html

    but there are differences. Particularly, racketeers should note that in
    `mcpyrate`, phase separation is not strict; code from **all** phases will
    be available in the final phase-0 module. This is a design decision; it's
    more pythonic that macros don't "disappear" from the final module just
    because they were defined in a higher phase.

    This makes the phase level into a module initialization detail that is
    local to each module. Other modules don't need to care in which phase
    a thing was defined when they import that thing.
    """
    # This is actually an importer feature; all correctly placed invocations
    # will be gone before the code is macro-expanded. So if we get here, the
    # importer didn't handle this invocation.
    if syntax != "block":
        raise SyntaxError("`with phase` is a block macro only")
    raise SyntaxError("Misplaced `with phase`; must appear at the module top level only.")


def ismultiphase(tree):
    """Scan a module body to determine whether it requests multi-phase compilation.

    Primarily meant to be called with `tree` the AST of a module that
    uses macros, but works with any `tree` that has a `body` attribute.

    To request multi-phase compilation, place this macro-import somewhere in the
    top level of the module body::

        from mcpyrate.multiphase import macros, phase
    """
    for stmt in tree.body:
        if not (ismacroimport(stmt) and stmt.module == "mcpyrate.multiphase" and stmt.level == 0):
            continue
        for name in stmt.names[1:]:
            if name.name == "phase":
                return True
    return False


def detect_highest_phase(tree):
    """Scan a module body for `with phase[n]` statements and return highest `n`, or `None`.

    Primarily meant to be called with `tree` the AST of a module that
    uses macros, but works with any `tree` that has a `body` attribute.

    Used for initializing the phase countdown in multi-phase compilation.
    """
    maxn = None
    for stmt in tree.body:
        n = iswithphase(stmt)
        if maxn is None or (n is not None and n > maxn):
            maxn = n
    return maxn


def multiphase_expand(tree, *, filename, self_module, start_from_phase=None, _optimize=-1):
    """Macro-expand an AST in multiple phases, controlled by `with phase[n]`.

    Primarily meant to be called with `tree` the AST of a module that
    uses macros, but works with any `tree` that has a `body` attribute.

    At each phase `k >= 1`, we inject a temporary module into `sys.modules`, so that
    the next phase can import macros from it, using the self-macro-import syntax.

    Once phase `k = 0` is reached and the code has been macro-expanded, the temporary
    entry is deleted from `sys.modules`.

    `filename`:         Full path to the `.py` file being compiled.

    `self_module`:      Absolute dotted module name of the module being compiled.
                        Will be used to temporarily inject the temporary,
                        higher-phase modules into `sys.modules`.

    `start_from_phase`: Optional int, >= 0. If `None`, will be scanned automatically
                        from `tree`, using `detect_highest_phase`.

                        This parameter exists only so that if you have already scanned
                        `tree` to determine the highest phase, you can provide the value,
                        so this function doesn't need to scan `tree` again.

    `_optimize`:        Passed on to Python's built-in `compile` function, when compiling
                        the temporary higher-phase modules. Has no effect on the final result.

    Return value is the final phase-0 `tree`, after macro expansion.
    """
    n = start_from_phase if start_from_phase is not None else detect_highest_phase(tree)
    if not isinstance(n, int):
        raise TypeError  # TODO: proper error message
    if n < 0:
        raise ValueError  # TODO: proper error message

    # TODO: preserve ordering of code in the file. Currently we just paste in phase-descending order.
    for k in range(n, -1, -1):  # phase 0 is what a regular compile would do
        print(f"***** PHASE {k} for '{self_module}' ({filename})")  # TODO: add proper debug tools
        phase_k_tree = split_multiphase_module_ast(tree, phase=k)
        if phase_k_tree:
            # Establish macro bindings, but don't transform macro-imports yet; we need to
            # keep them in the code to be spliced into the next phase.
            module_macro_bindings = find_macros(phase_k_tree, filename=filename,
                                                self_module=self_module, transform=False)

            # Expand macros as usual.
            expansion = expand_macros(phase_k_tree, bindings=module_macro_bindings, filename=filename)

            # # TODO: add proper debug tools to the multi-phase compiler
            # from .unparser import unparse
            # print(unparse(expansion.body, debug=True, color=True))

            # Lift macro-expanded code from phase `k` into phase `k - 1`.
            if k > 0:
                tree.body[:] = deepcopy(expansion.body) + tree.body

            # Transform the macro-imports in the code we actually intend to run at phase k.
            find_macros(expansion, filename=filename, self_module=self_module, transform=True)

            # We must postprocess again, because we transformed the macro-imports *after*
            # `expand_macros` (which postprocesses), and self-macro-imports insert dummy
            # coverage nodes (which have a `Done` marker around them).
            expansion = global_postprocess(expansion)

            check_no_markers_remaining(expansion, filename=filename)

            # Once we hit the final phase, no more temporary modules - let the import system take over.
            if k == 0:
                break

            # Compile temporary module, and inject it into `sys.modules`, so we can compile the next phase.
            #
            # We don't bother with hifi stuff, such as attributes usually set by the importer,
            # or even the module docstring. We essentially just want the macro functions,
            # so that the next phase can bind to them.
            temporary_code = compile(expansion, filename, "exec", dont_inherit=True, optimize=_optimize)
            temporary_module = ModuleType(self_module)
            sys.modules[self_module] = temporary_module
            exec(temporary_code, temporary_module.__dict__)

    # delete temporary module
    if self_module in sys.modules:
        del sys.modules[self_module]

    return expansion
