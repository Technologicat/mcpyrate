# -*- coding: utf-8; -*-
"""Macro debugging utilities."""

import ast
from sys import stderr
from .expander import MacroCollector
from .unparser import unparse

# TODO: indent the output, to support nested `step_expansion` invocations properly.
def step_expansion(tree, *, syntax, expander, **kw):
    """[syntax, expr/block] Macroexpand `tree`, showing source code at each step of the expansion."""
    if syntax not in ("expr", "block"):
        raise SyntaxError("step_expansion is an expr/block macro only")
    tag = id(tree)
    print(f"****Tree 0x{tag:x} before macroexpansion:", file=stderr)
    print(unparse(tree), file=stderr)
    mc = MacroCollector(expander)
    mc.visit(tree)
    step = 0
    while mc.collected:
        step += 1
        tree = expander.visit_once(tree)  # -> Done(body=...)
        tree = tree.body
        print(f"****Tree 0x{tag:x} after step {step}:", file=stderr)
        print(unparse(tree), file=stderr)
        mc.clear()
        mc.visit(tree)
    plural = "s" if step != 1 else ""
    print(f"****Tree 0x{tag:x} macroexpansion complete after {step} step{plural}.", file=stderr)
    return tree

def show_bindings(tree, *, syntax, expander, **kw):
    """[syntax, name] Show all bindings of the macro expander.

    For each binding, this lists the macro name, and the fully qualified name
    of the corresponding macro function.

    Any bindings that have an uuid as part of the name are hygienically
    unquoted macros. These make a per-session global binding across all modules.
    """
    if syntax != "name":
        raise SyntaxError("show_bindings is an identifier macro only")
    print(f"Macro expander bindings for module {expander.filename} (at expansion time):", file=stderr)
    for k, v in sorted(expander.bindings.items()):
        print(f"    {k}: {v.__module__}.{v.__qualname__}", file=stderr)
    return ast.Constant(value=None)  # can't just delete the node (return None) if it's in an Expr(value=...)
