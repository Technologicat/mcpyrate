# -*- coding: utf-8; -*-
"""Macro debugging utilities."""

import ast
import functools
from sys import stderr
import textwrap

from .astdumper import dump
from .expander import MacroCollector, namemacro, parametricmacro
from .unparser import unparse
from .utilities import NestingLevelTracker, format_macrofunction


_step_expansion_level = NestingLevelTracker()

@parametricmacro
def step_expansion(tree, *, args, syntax, expander, **kw):
    """[syntax, expr/block] Macroexpand `tree`, showing source code at each step of the expansion.

    Since this is a debugging utility, the source code is shown in the debug
    mode of `unparse`, which prints also invisible nodes such as `Module` and
    `Expr`.
    """
    if syntax not in ("expr", "block"):
        raise SyntaxError("`step_expansion` is an expr and block macro only")

    formatter = functools.partial(unparse, debug=True)
    if args:
        if len(args) != 1:
            raise SyntaxError("expected `step_expansion['mode_str']`")
        arg = args[0]
        if type(arg) is ast.Constant:
            mode = arg.value
        elif type(arg) is ast.Str:  # up to Python 3.7
            mode = arg.s
        else:
            raise TypeError(f"expected mode str, got {repr(arg)} {unparse(arg)}")
        if mode not in ("unparse", "dump"):
            raise ValueError(f"expected mode either 'unparse' or 'dump', got {repr(mode)}")
        if mode == "dump":
            formatter = dump

    with _step_expansion_level.changed_by(+1):
        indent = 2 * _step_expansion_level.value
        stars = indent * '*'
        moreindent = indent
        tag = id(tree)
        print(f"{stars}Tree 0x{tag:x} before macro expansion:", file=stderr)
        print(textwrap.indent(formatter(tree), moreindent * ' '), file=stderr)
        mc = MacroCollector(expander)
        mc.visit(tree)
        step = 0
        while mc.collected:
            step += 1
            tree = expander.visit_once(tree)  # -> Done(body=...)
            tree = tree.body
            print(f"{stars}Tree 0x{tag:x} after step {step}:", file=stderr)
            print(textwrap.indent(formatter(tree), moreindent * ' '), file=stderr)
            mc.clear()
            mc.visit(tree)
        plural = "s" if step != 1 else ""
        print(f"{stars}Tree 0x{tag:x} macro expansion complete after {step} step{plural}.", file=stderr)
    return tree

@namemacro
def show_bindings(tree, *, syntax, expander, **kw):
    """[syntax, name] Show all bindings of the macro expander.

    For each binding, this lists the macro name, and the fully qualified name
    of the corresponding macro function.

    Any bindings that have an uuid as part of the name are hygienically
    unquoted macros. These make a per-process global binding across all modules.
    """
    if syntax != "name":
        raise SyntaxError("`show_bindings` is an identifier macro only")
    print(f"Macro expander bindings for module {expander.filename} (at expansion time):", file=stderr)
    for k, v in sorted(expander.bindings.items()):
        print(f"    {k}: {format_macrofunction(v)}", file=stderr)
    return ast.Constant(value=None)  # can't just delete the node (return None) if it's in an Expr(value=...)
