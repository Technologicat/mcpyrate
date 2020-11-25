# -*- coding: utf-8; -*-
"""Alternative file layout for the let example. Macro definitions.

We also make another change to the first example, to demonstrate a useful
technique: hygienic macro recursion. Now we don't need multi-phase compilation.
"""

__all__ = ["let", "letseq"]

from mcpyrate.quotes import macros, q, a, t  # noqa: F811, F401

from ast import arg

from mcpyrate import parametricmacro
from mcpyrate.quotes import capture_as_macro


@parametricmacro
def let(tree, *, args, syntax, **kw):
    """[syntax, expr] Bind expression-local variables.

    Usage::

        let[[k0, v0], ...][expr]

    `let` expands into a `lambda`::

        let[[x, 1], [y, 2]][print(x, y)]
        # --> (lambda x, y: print(x, y))(1, 2)
    """
    if syntax != "expr":
        raise SyntaxError("`let` is an expr macro only")  # pragma: no cover
    if not args:
        raise SyntaxError("expected at least one binding")  # pragma: no cover

    # args: `list` of `ast.List`. Each sublist is [ast.Name, expr].
    names = [k.id for k, _ in (a.elts for a in args)]
    values = [v for _, v in (a.elts for a in args)]
    if len(set(names)) < len(names):
        raise SyntaxError("binding names must be unique in the same `let`")  # pragma: no cover

    lam = q[lambda: a[tree]]
    lam.args.args = [arg(arg=x) for x in names]
    return q[a[lam](a[values])]


@parametricmacro
def letseq(tree, *, args, syntax, expander, **kw):
    """[syntax, expr] Sequential let, like `let*` in Scheme.

    Usage::

        letseq[[k0, v0], ...][expr]

    The difference to `let` is that in `letseq`, on the RHS
    of each new binding, the previous bindings are in scope.

    Expands to a sequence of nested `let`.

    Example::

        letseq[[x, 21], [x, 2 * x]][x]  # --> 42
    """
    if syntax != "expr":
        raise SyntaxError("`letseq` is an expr macro only")  # pragma: no cover
    if not args:
        return tree
    first, *rest = args
    body = q[a[our_letseq][t[rest]][a[tree]]]
    return q[a[our_let][a[first]][a[body]]]


our_let = capture_as_macro(let)
our_letseq = capture_as_macro(letseq)
