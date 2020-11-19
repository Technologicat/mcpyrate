# -*- coding: utf-8; -*-
from mcpyrate.multiphase import macros, phase
from mcpyrate.debug import macros, step_expansion  # noqa: F811
# from mcpyrate.debug import macros, step_phases  # uncomment this line to see the multiphase compilation

with phase[2]:
    from mcpyrate.quotes import macros, q, a, h  # noqa: F811, F401

    from ast import arg

    from mcpyrate import parametricmacro

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

        # Create the lambda, injecting the parameters with an oldschool AST edit.
        # Note we can't really put any sensible placeholder there, since parameter names must be literals,
        # and "..." - which would best suggest we're going to replace it - is not a valid name in Python.
        lam = q[lambda: a[tree]]
        lam.args.args = [arg(arg=x) for x in names]

        # Using a[] with a list of expression AST nodes splices that list into the surrounding context.
        # We splice `values` into positional arguments of the `Call`.
        return q[a[lam](a[values])]


with phase[1]:
    from __self__ import macros, let  # noqa: F811, F401

    @parametricmacro
    def letseq(tree, *, args, syntax, **kw):
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
        body = letseq(tree, args=rest, syntax=syntax)
        return q[h[let][a[first]][a[body]]]

        # We could as well call `let` as a function, to expand it immediately.
        # let(body, args=[first, ], syntax=syntax)


from __self__ import macros, letseq  # noqa: F811, F401

def demo():
    with step_expansion:
        assert let[[x, 2], [y, 3]][x * y] == 6  # noqa: F821, `x` and `y` are defined by the `let`.
    with step_expansion:
        assert letseq[[x, 21], [x, 2 * x]][x] == 42  # noqa: F821

if __name__ == '__main__':
    demo()
