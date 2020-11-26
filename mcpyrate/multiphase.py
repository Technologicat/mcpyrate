# -*- coding: utf-8; -*-
"""Multi-phase compiler, to allow a module to use macros defined in that module itself.

See the `with phase[n]` construct.

Note `__main__` is a module, too, so if `app.py` uses `with phase`,
running as `macropython app.py` is fine.

As a user, see the macros `phase` and `step_phases`. The latter is actually
part of the public API of `mcpyrate.debug`, because it's a debugging utility.

As a developer, see `ismultiphase` and `multiphase_expand`; the rest are
implementation details. We provide `isdebug` and `detect_highest_phase`
for convenient introspection.
"""

__all__ = ["phase", "ismultiphase", "detect_highest_phase", "isdebug", "multiphase_expand"]

import ast
from copy import copy, deepcopy
import sys
from types import ModuleType

from .colorizer import setcolor, ColorScheme
from .coreutils import ismacroimport
from .expander import find_macros, expand_macros, destructure_candidate, namemacro, parametricmacro
from .markers import check_no_markers_remaining
from .unparser import unparse_with_fallbacks

# --------------------------------------------------------------------------------
# Private utilities.

def iswithphase(stmt):
    """Check if AST node `stmt` is a `with phase[n]`, where `n >= 1` is an integer.

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
    elif type(arg) is ast.Num:  # TODO: Python 3.8: remove ast.Num
        n = arg.n
    else:
        return False

    if not isinstance(n, int) or n < 1:
        return False

    return n


def extract_phase(tree, *, phase=0):
    """Split `tree` into given `phase` and remaining parts.

    Primarily meant to be called with `tree` the AST of a module that
    uses macros, but works with any `tree` that has a `body` attribute,
    where that `body` is a `list` of statement AST nodes.

    If `phase == 0`, just return `tree` as-is.

    If `phase >= 1`, return the statements belonging to this phase as a new
    `ast.Module`, and overwrite the `body` attribute of the original `tree`
    with the code for `phase - 1`, also performing code lifting from `phase`
    to `phase - 1`.

    The lifted AST is deep-copied to minimize confusion, since it may get
    edited by macros during macro expansion. (This guarantees that
    macro-expanding it, in either phase, gives the same result.)
    """
    if not isinstance(phase, int):
        raise TypeError(f"`phase` must be `int`, got {type(phase)} with value {repr(phase)}")
    if phase < 0:
        raise ValueError(f"`phase` must be a positive integer, got {repr(phase)}")
    if phase == 0:
        return tree

    remaining = []
    def lift(withphase):  # Lift a `with phase[n]` code block to phase `n - 1`.
        original_phase = iswithphase(withphase)
        assert original_phase
        if original_phase == 1:
            # Lifting to phase 0. Drop the `with phase` wrapper.
            remaining.extend(deepcopy(withphase.body))
        else:
            # Lifting to phase >= 1. Decrease the `n` in `with phase[n]`
            # by one, so the block gets processed again in the next phase.
            macroarg = withphase.items[0].context_expr.slice.value
            if type(macroarg) is ast.Constant:
                macroarg.value -= 1
            elif type(macroarg) is ast.Num:  # TODO: Python 3.8: remove ast.Num
                macroarg.n -= 1
            remaining.append(deepcopy(withphase))

    thisphase = []
    for stmt in tree.body:
        if iswithphase(stmt) == phase:
            thisphase.extend(stmt.body)
            lift(stmt)
        else:
            remaining.append(stmt)
    tree.body[:] = remaining

    newmodule = copy(tree)
    newmodule.body = thisphase
    return newmodule

# --------------------------------------------------------------------------------
# Public utilities.

@parametricmacro
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
    # will be gone before the macro expander runs. So if we get here, the
    # importer didn't compile away this invocation.
    if syntax != "block":
        raise SyntaxError("`with phase` is a block macro only")
    raise SyntaxError("Misplaced `with phase`; must appear at the module top level only.")


def ismultiphase(tree):
    """Scan a module body to determine whether it requests multi-phase compilation.

    Primarily meant to be called with `tree` the AST of a module that
    uses macros, but works with any `tree` that has a `body` attribute,
    where that `body` is a `list` of statement AST nodes.

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
    uses macros, but works with any `tree` that has a `body` attribute,
    where that `body` is a `list` of statement AST nodes.

    Used for initializing the phase countdown in multi-phase compilation.
    """
    maxn = None
    for stmt in tree.body:
        n = iswithphase(stmt)
        if maxn is None or (n is not None and n > maxn):
            maxn = n
    return maxn


# This is actually part of the public API of `mcpyrate.debug`. We make this a name macro
# so it will error out on any mention of the name (except the macro-import, which is compiled away).
@namemacro
def step_phases(tree, **kw):
    """[syntax, special] Enable the multi-phase compiler's debug mode.

    Usage::

        from mcpyrate.debug import macros, step_phases

    Strictly speaking, `step_phases` is not a macro, but a flag that enables the
    debug mode of the multi-phase compiler for the module where that macro-import
    appears in. `step_phases` may only appear in its macro-import.

    `step_phases` only has an effect if also the `phase` macro from
    `mcpyrate.multiphase` is imported (thus enabling multi-phase compilation).

    When in debug mode, the unparsed source code for the AST of each phase,
    before macro expansion, is printed to stderr, with syntax highlighting.
    Note the macro expander is not yet running when this happens, so macro
    names will not be highlighted.

    The macro expansion itself will **not** be stepped; this debug tool is
    orthogonal to that. For that, use the `step_expansion` macro, as usual.
    """
    raise SyntaxError("`step_phases` is a compiler flag; it may only appear in its macro-import.")


def isdebug(tree):
    """Scan a module body to determine whether it requests debug mode for multi-phase compilation.

    Primarily meant to be called with `tree` the AST of a module that
    uses macros, but works with any `tree` that has a `body` attribute,
    where that `body` is a `list` of statement AST nodes.

    To request debug mode for multi-phase compilation, place this macro-import
    somewhere in the top level of the module body::

        from mcpyrate.debug import macros, step_phases

    `step_phases` only has an effect if also the `phase` macro from
    `mcpyrate.multiphase` is imported (thus enabling multi-phase compilation).
    """
    for stmt in tree.body:
        if not (ismacroimport(stmt) and stmt.module == "mcpyrate.debug" and stmt.level == 0):
            continue
        for name in stmt.names[1:]:
            if name.name == "step_phases":
                return True
    return False

# --------------------------------------------------------------------------------
# The multi-phase compiler.

def multiphase_expand(tree, dexpander, *, filename, self_module, _optimize=-1):
    """Macro-expand an AST in multiple phases, controlled by `with phase[n]`.

    Primarily meant to be called with `tree` the AST of a module that
    uses macros, but works with any `tree` that has a `body` attribute,
    where that `body` is a `list` of statement AST nodes.

    At each phase `k >= 1`, we inject a temporary module into `sys.modules`, so that
    the next phase can import macros from it, using the self-macro-import syntax.

    Once phase `k = 0` is reached and the code has been macro-expanded, the temporary
    entry is deleted from `sys.modules`.

    `dexpander`:        The `DialectExpander` instance to use for dialect AST transforms.

    `filename`:         Full path to the `.py` file being compiled.

    `self_module`:      Absolute dotted module name of the module being compiled.
                        Will be used to temporarily inject the temporary,
                        higher-phase modules into `sys.modules`.

    `_optimize`:        Passed on to Python's built-in `compile` function, when compiling
                        the temporary higher-phase modules. Has no effect on the final result.

    Return value is the final phase-0 `tree`, after macro expansion.
    """
    n = detect_highest_phase(tree)
    debug = isdebug(tree)
    c, CS = setcolor, ColorScheme

    # If this module is already in `sys.modules` (e.g. created by Python's
    # import system as a blank module instance, to be filled in by an exec
    # after compilation is done), record the original module object, so we
    # can reinstate it once we're done.
    if self_module in sys.modules:
        original_module = sys.modules[self_module]
    else:
        original_module = None

    if debug:
        print(f"{c(CS.HEADING)}**Multi-phase compiling module {c(CS.TREEID)}'{self_module}' ({c(CS.SOURCEFILENAME)}{filename}{c(CS.TREEID)}){c()}", file=sys.stderr)

    for k in range(n, -1, -1):  # phase 0 is what a regular compile would do
        if debug:
            print(f"{c(CS.HEADING)}**AST for {c(CS.ATTENTION)}PHASE {k}{c(CS.HEADING)} of module {c(CS.TREEID)}'{self_module}' ({c(CS.SOURCEFILENAME)}{filename}{c(CS.TREEID)}){c()}", file=sys.stderr)

        phase_k_tree = extract_phase(tree, phase=k)
        if phase_k_tree.body:
            # inject `__phase__ = k` for introspection
            tgt = ast.Name(id="__phase__", ctx=ast.Store(), lineno=1, col_offset=1)
            val = ast.Constant(value=k, lineno=1, col_offset=13)
            assignment = ast.Assign(targets=[tgt], value=val, lineno=1, col_offset=1)
            # TODO: remove ast.Str once we bump minimum language version to Python 3.8
            if type(phase_k_tree.body[0]) is ast.Expr and type(phase_k_tree.body[0].value) in (ast.Constant, ast.Str):
                docstring, *body = phase_k_tree.body
                phase_k_tree.body = [docstring, assignment] + body
            else:  # no docstring
                phase_k_tree.body = [assignment] + phase_k_tree.body

            if debug:
                print(unparse_with_fallbacks(phase_k_tree, debug=True, color=True), file=sys.stderr)

            phase_k_tree, dialect_instances = dexpander.transform_ast(phase_k_tree)
            module_macro_bindings = find_macros(phase_k_tree, filename=filename, self_module=self_module)
            expansion = expand_macros(phase_k_tree, bindings=module_macro_bindings, filename=filename)
            expansion = dexpander.postprocess_ast(expansion, dialect_instances)
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

    # restore `sys.modules` to how it was before we began the multi-phase compile for this module
    if original_module:
        sys.modules[self_module] = original_module
    else:
        try:
            del sys.modules[self_module]
        except KeyError:
            pass

    return expansion
