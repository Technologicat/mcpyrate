# -*- coding: utf-8; -*-
"""Hygienic macro recursion."""

from mcpyrate.multiphase import macros, phase
from mcpyrate.debug import macros, step_expansion  # noqa: F811

with phase[1]:
    from mcpyrate.quotes import macros, q, u, a  # noqa: F811, F401

    import ast

    from mcpyrate.quotes import capture_as_macro

    def even(tree, **kw):
        if type(tree) is ast.Constant:
            v = tree.value

        if v == 0:
            return q[True]
        return q[a[our_odd][u[v - 1]]]

    def odd(tree, **kw):
        if type(tree) is ast.Constant:
            v = tree.value

        if v == 0:
            return q[False]
        return q[a[our_even][u[v - 1]]]

    # This is the important part: capture macro functions manually to make hygienic
    # references, without caring about macro-imports at the use site.
    #
    # We can't simply `q[h[...]]`, because these macros aren't bound in *our* expander.
    # This is where the `capture_as_macro` function comes in. It registers the macro
    # in the global bindings table for the current process, and returns an AST snippet
    # that refers to that macro hygienically.
    our_even = capture_as_macro(even)
    our_odd = capture_as_macro(odd)


from __self__ import macros, even, odd  # noqa: F811, F401

def demo():
    with step_expansion:
        assert even[4]

    with step_expansion:
        assert not odd[4]

if __name__ == '__main__':
    demo()
