# -*- coding: utf-8; -*-
"""Macro debugging utilities."""

__all__ = ["step_expansion", "StepExpansion",
           "show_bindings", "format_bindings",
           "SourceLocationInfoValidator"]

import ast
import functools
import io
from sys import stderr
import textwrap

from .astdumper import dump
from .colorizer import setcolor, colorize, ColorScheme
from .dialects import StepExpansion  # re-export for discoverability, it's a debug feature
from .expander import MacroCollector, namemacro, parametricmacro
from .unparser import unparse_with_fallbacks
from .utils import NestingLevelTracker, format_macrofunction
from .walker import Walker


_step_expansion_level = NestingLevelTracker()

@parametricmacro
def step_expansion(tree, *, args, syntax, expander, **kw):
    """[syntax, expr/block] Macroexpand `tree`, showing each step of the expansion.

    Syntax::

        step_expansion[...]
        step_expansion[mode][...]
        with step_expansion:
            ...
        with step_expansion[mode]:
            ...

    This calls `expander.visit_once` in a loop, discarding the `Done` markers,
    and showing the AST at each step (by printing to `sys.stderr`).

    A step is defined as when `expander.visit_once` returns control to the
    expander core. If your macro does `expander.visit(subtree)`, that will
    expand by one step; if it does `expander.visit_recursively(subtree)`,
    then that subtree will be expanded, in a single step, until no macros remain.

    Since this is a debugging utility, the source code is rendered in the debug
    mode of `unparse`, which prints also invisible nodes such as `Module` and
    `Expr` in a Python-like pseudocode notation.

    The optional macro argument `mode`, if present, sets the renderer mode.
    It must be one of the strings `"unparse"` (default) or `"dump"`.
    If `"unparse"`, then at each step, the AST will be shown as source code.
    If `"dump"`, then at each step, the AST will be shown as a raw AST dump.
    """
    if syntax not in ("expr", "block"):
        raise SyntaxError("`step_expansion` is an expr and block macro only")

    formatter = functools.partial(unparse_with_fallbacks, debug=True, color=True,
                                  expander=expander)
    if args:
        if len(args) != 1:
            raise SyntaxError("expected `step_expansion` or `step_expansion['mode_str']`")
        arg = args[0]
        if type(arg) is ast.Constant:
            mode = arg.value
        elif type(arg) is ast.Str:  # up to Python 3.7
            mode = arg.s
        else:
            raise TypeError(f"expected mode_str, got {repr(arg)} {unparse_with_fallbacks(arg)}")
        if mode not in ("unparse", "dump"):
            raise ValueError(f"expected mode_str either 'unparse' or 'dump', got {repr(mode)}")
        if mode == "dump":
            formatter = functools.partial(dump, include_attributes=True, color=True)

    c, CS = setcolor, ColorScheme

    with _step_expansion_level.changed_by(+1):
        indent = 2 * _step_expansion_level.value
        stars = indent * '*'
        codeindent = indent
        tag = id(tree)
        print(f"{c(CS.HEADING)}{stars}Tree {c(CS.TREEID)}0x{tag:x} {c(CS.HEADING)}before macro expansion:{c(CS._RESET)}",
              file=stderr)
        print(textwrap.indent(formatter(tree), codeindent * ' '), file=stderr)
        mc = MacroCollector(expander)
        mc.visit(tree)
        step = 0
        while mc.collected:
            step += 1
            tree = expander.visit_once(tree)  # -> Done(body=...)
            tree = tree.body
            print(f"{c(CS.HEADING)}{stars}Tree {c(CS.TREEID)}0x{tag:x} {c(CS.HEADING)}after step {step}:{c(CS._RESET)}",
                  file=stderr)
            print(textwrap.indent(formatter(tree), codeindent * ' '), file=stderr)
            mc.clear()
            mc.visit(tree)
        plural = "s" if step != 1 else ""
        print(f"{c(CS.HEADING)}{stars}Tree {c(CS.TREEID)}0x{tag:x} {c(CS.HEADING)}macro expansion complete after {step} step{plural}.{c(CS._RESET)}",
              file=stderr)
    return tree


@namemacro
def show_bindings(tree, *, syntax, expander, **kw):
    """[syntax, name] Show all bindings of the macro expander.

    Syntax::

        show_bindings

    This can appear in any expression position, and at run-time evaluates to `None`.

    At macro expansion time, when the macro expander reaches the `show_bindings`
    expression, bindings *that are in effect at that point in time* are shown.

    (That disclaimer is important, because hygienically unquoted macros may add
     new bindings as those expressions are reached, and true to the dynamic nature
     of Python, when a macro runs, it is allowed to edit the expander's bindings.)

    For each macro binding, we print to `sys.stderr` the macro name, and the
    fully qualified name of the corresponding macro function.

    Any bindings that have an uuid as part of the name are hygienically
    unquoted macros. Those bindings are global across all modules and
    all expander instances.
    """
    if syntax != "name":
        raise SyntaxError("`show_bindings` is an identifier macro only")
    print(format_bindings(expander, globals_too=False, color=True), file=stderr)
    return None


def format_bindings(expander, *, globals_too=False, color=False):
    """Return a human-readable report of the macro bindings currently seen by `expander`.

    If `globals_too=True`, global bindings (across all expanders) are also included.

    If `color=True`, colorize the output for printing into a terminal.

    If you want to access them programmatically, just access `expander.bindings` directly.
    """
    def maybe_setcolor(*colors):
        if not color:
            return ""
        return setcolor(*colors)
    def maybe_colorize(text, *colors):
        if not color:
            return text
        return colorize(text, *colors)

    c, CS = maybe_setcolor, ColorScheme

    bindings = expander.bindings if globals_too else expander.local_bindings
    with io.StringIO() as output:
        output.write(f"{c(CS.HEADING)}Macro bindings for {c(CS.SOURCEFILENAME)}{expander.filename}{c(CS.HEADING)}:{c(CS._RESET)}\n")
        if not bindings:
            output.write(maybe_colorize("    <no bindings>\n",
                                        ColorScheme.GREYEDOUT))
        else:
            for k, v in sorted(bindings.items()):
                k = maybe_colorize(k, ColorScheme.MACROBINDING)
                output.write(f"    {k}: {format_macrofunction(v)}\n")
        return output.getvalue()


class SourceLocationInfoValidator(Walker):
    """Collect nodes that are missing `lineno` and/or `col_offset`.

    Usage::

        v = SourceLocationInfoValidator()
        v.visit(tree)
        print(v.collected)

    It's a rather common occurrence when developing macros to have the source
    location info missing somewhere, but when we `compile`, Python won't tell us
    *which* nodes are missing them.

    This can also be used to debug whether the problem is what Python claims it is.
    Python's `compile` is notorious for yelling about a missing source location
    when the actual problem is that is got a bare value in a position where an
    AST node was expected.

    The macro expander *should* fill in missing source location info when it expands
    a macro, so this utility will be needed only rarely.

    After `visit(tree)`, `self.collected` becomes a `list` of items in the format
    `(subtree, sourcecode, missing_field_names)`. Each `sourcecode` is truncated
    if too long.
    """
    def __init__(self, ignore={}, n=5, check_fields=['lineno', 'col_offset']):
        """Constructor.

        Parameters:

            `ignore={tree0, ...}` to ignore given subtrees (such as if you have
            a top-level `Module` node; those don't need source location info).
            Subtrees are detected by their `id`.

            `n`: maximum number of source lines to show for each collected item.

            `check_fields`: which fields are considered mandatory for every node
            in `tree`. Defaults to checking source location info.
        """
        self.ignore = ignore
        self.n = n
        self.check_fields = check_fields
        super().__init__()

    def transform(self, tree):
        if tree not in self.ignore:
            present = [hasattr(tree, x) for x in self.check_fields]
            if not all(present):
                code_lines = unparse_with_fallbacks(tree).split("\n")
                code = "\n".join(code_lines[:self.n])
                if len(code_lines) > self.n:
                    code += "\n..."

                self.collect((tree,
                              code,
                              [fieldname for fieldname, p in zip(self.check_fields, present) if not p]))
        return self.generic_visit(tree)
