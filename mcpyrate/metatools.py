# -*- coding: utf-8; -*-
"""Macros that expand macros.

Less silly than it sounds; these are convenient when working with quasiquoted
code, and with run-time AST values in general. Run-time AST values are exactly
the kind of thing macros operate on: the macro expansion time of the use site
is the run time of the macro implementation itself.

Also, if you have a quasiquoted tree, run-time expansion also has the benefit
that any unquoted values will have been spliced in. Unquotes operate partly
at run time of the use site of `q`. They must; the only context that has the
user-provided names (where the unquoted data comes from) in scope is each
particular use site of `q`, at its run time. The quasiquoted tree is only
fully ready at run time of the use site of `q`.

The suffixes `1srq` mean:

 - `1`: once. Expand one layer of macros only.
 - `s`: statically, i.e. at macro expansion time.
 - `r`: dynamically, i.e. at run time.
 - `q`: quote first. Apply `q` first, then the expander.

You'll most likely want `expandr` or `expand1r`.

**When to use**:

If you want to expand a tree using the macro bindings *from your macro's use
site*, you should use `expander.visit` and its sisters (`visit_once`,
`visit_recursively`).

If you want to expand a tree using the macro bindings *from your macro's
definition site*, you should use the `expand` family of macros.
"""

__all__ = ['expand1sq', 'expandsq',
           'expand1s', 'expands',
           'expand1rq', 'expandrq',
           'expand1r', 'expandr']

import ast

# Note we import `q` as a regular function. We just want its syntax transformer.
from .expander import MacroExpander
from .quotes import q, unastify, capture_value


def _mcpyrate_metatools_attr(attr):
    """Create an AST that, when compiled and run, looks up `mcpyrate.metatools.attr` in `Load` context."""
    mcpyrate_metatools_module = ast.Attribute(value=ast.Name(id="mcpyrate"), attr="metatools")
    return ast.Attribute(value=mcpyrate_metatools_module, attr=attr)

# --------------------------------------------------------------------------------

def runtime_expand1(bindings, filename, tree):
    """Macro-expand an AST value `tree` at run time, once. Run-time part of `expand1r`.

    `bindings` and `filename` are as in `mcpyrate.core.BaseMacroExpander`.

    Convenient for experimenting with quoted code in the REPL.
    """
    expander = MacroExpander(bindings, filename)
    return expander.visit_once(tree).body  # Done(body=...) -> ...


def runtime_expand(bindings, filename, tree):
    """Macro-expand an AST value `tree` at run time, until no macros remain. Run-time part of `expandr`.

    `bindings` and `filename` are as in `mcpyrate.core.BaseMacroExpander`.

    Convenient for experimenting with quoted code in the REPL.
    """
    expander = MacroExpander(bindings, filename)
    return expander.visit_recursively(tree)

# --------------------------------------------------------------------------------

def expand1sq(tree, *, syntax, **kw):
    '''[syntax, expr/block] quote-then-expand-once.

    Quasiquote `tree`, then expand one layer of macros in it. Return the result
    quasiquoted.

    Because the expansion runs at macro expansion time, unquoted values are not
    available. If you need to expand also in those, see `expand1rq`.

    `expand1sq[...]` is shorthand for `expand1s[q[...]]`.

    `with expand1sq as quoted` has the corresponding effect on a block.
    but does not factor into `q` and `expand1s`, because the quote is
    applied first, but with the expander outside of it.

    If your tree is quasiquoted, use `expands1` instead.
    '''
    if syntax not in ("expr", "block"):
        raise SyntaxError("`expand1sq` is an expr and block macro only")
    tree = q(tree, syntax=syntax, **kw)
    kw = dict(kw)
    if "optional_vars" in kw:  # the asname was meant for `q`, `expand1s` doesn't take it.
        kw["optional_vars"] = None
    return expand1s(tree, syntax=syntax, **kw)


def expandsq(tree, *, syntax, **kw):
    '''[syntax, expr/block] quote-then-expand.

    Quasiquote `tree`, then expand it until no macros remain. Return the result
    quasiquoted.

    Because the expansion runs at macro expansion time, unquoted values are not
    available. If you need to expand also in those, see `expandrq`.

    `expandsq[...]` is shorthand for `expands[q[...]]`.

    `with expandsq as quoted` has the corresponding effect on a block.
    but does not factor into `q` and `expands`, because the quote is
    applied first, with the expander outside of it.

    If your tree is quasiquoted, use `expands` instead.

    This operator should produce results closest to those of `macropy`'s `q`.
    '''
    if syntax not in ("expr", "block"):
        raise SyntaxError("`expandsq` is an expr and block macro only")
    tree = q(tree, syntax=syntax, **kw)
    kw = dict(kw)
    if "optional_vars" in kw:
        kw["optional_vars"] = None
    return expands(tree, syntax=syntax, **kw)


def expand1s(tree, *, syntax, expander, **kw):
    '''[syntax, expr/block] expand one layer of macros in quasiquoted `tree`.

    The result remains in quasiquoted form.

    Like calling `expander.visit_once(tree)`, but for a quasiquoted `tree`,
    already at macro expansion time (of the use site of `expand1s`).

    Because the expansion runs at macro expansion time, unquoted values are not
    available. If you need to expand also in those, see `expand1r`.

    `tree` must be an "astified" AST; i.e. output from, or an invocation of,
    `q`, `expand1sq`, `expandsq`, `expand1s`, or `expands`. Passing any other
    AST as `tree` raises `TypeError`.

    If your `tree` is not quasiquoted, use `expand1sq` instead.
    '''
    if syntax not in ("expr", "block"):
        raise SyntaxError("`expand1s` is an expr and block macro only")
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("`expand1s` (block mode) does not take an asname")
    # We first invert the quasiquote operation, then use the garden variety
    # `expander` on the result, and then re-quote the expanded AST.
    #
    # The first `visit_once` makes any quote invocations inside this macro invocation expand first.
    # If the input `tree` is an already expanded `q`, it will do nothing, because any macro invocations
    # are then in a quoted form, which don't look like macro invocations to the expander.
    # If the input `tree` is a `Done`, it will likewise do nothing.
    tree = expander.visit_once(tree)  # -> Done(body=...)
    tree = expander.visit_once(unastify(tree.body))  # On wrong kind of input, `unastify` will `TypeError` for us.
    # The final piece of the magic, why this works in the expander's recursive mode,
    # without wrapping the result with `Done`, is that after `q` has finished, the output
    # will be a **quoted** AST, so macro invocations in it don't look like macro invocations.
    # Hence upon looping on the output, the expander finds no more macros.
    return q(tree.body, syntax=syntax, expander=expander, **kw)


def expands(tree, *, syntax, expander, **kw):
    '''[syntax, expr/block] expand quasiquoted `tree` until no macros remain.

    The result remains in quasiquoted form.

    Like calling `expander.visit_recursively(tree)`, but for a quasiquoted `tree`,
    already at macro expansion time (of the use site of `expands`).

    Because the expansion runs at macro expansion time, unquoted values are not
    available. If you need to expand also in those, see `expandr`.

    `tree` must be an "astified" AST; i.e. output from, or an invocation of,
    `q`, `expand1sq`, `expandsq`, `expand1s`, or `expands`. Passing any other
    AST as `tree` raises `TypeError`.

    If your `tree` is not quasiquoted, use `expandsq` instead.
    '''
    if syntax not in ("expr", "block"):
        raise SyntaxError("`expands` is an expr and block macro only")
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("`expands` (block mode) does not take an asname")
    tree = expander.visit_once(tree)  # make the quotes inside this invocation expand first; -> Done(body=...)
    # Always use recursive mode, because `expand[...]` may appear inside
    # another macro invocation that uses `visit_once` (which sets the expander
    # mode to non-recursive for the dynamic extent of the `visit_once`).
    tree = expander.visit_recursively(unastify(tree.body))  # On wrong kind of input, `unastify` will `TypeError` for us.
    return q(tree, syntax=syntax, expander=expander, **kw)

# --------------------------------------------------------------------------------

def expand1rq(tree, *, syntax, **kw):
    '''[syntax, expr/block] quote-then-expand-once-at-runtime.

    Quasiquote `tree`, then set it up to have one layer of macros expanded
    at run time. At run time, return the resulting AST.

    Convenient for interactive experimentation in the REPL.

    Because the expansion runs at run time (of the use site of `expand1rq`),
    unquoted values have been spliced in by the time the expansion is performed.

    `expand1rq[...]` is shorthand for `expand1r[q[...]]`.

    `with expand1rq as quoted` has the corresponding effect on a block, but
    does not factor into `q` and `expand1r`, because the quote is to be applied
    first, but with the expander outside of it. Also, block mode `q` generates
    an `ast.Assign`. The call to the expander is spliced in around its RHS.

    If your tree is quasiquoted, use `expand1r` instead.
    '''
    if syntax not in ("expr", "block"):
        raise SyntaxError("`expand1rq` is an expr and block macro only")
    tree = q(tree, syntax=syntax, **kw)
    if syntax == "expr":
        return expand1r(tree, syntax=syntax, **kw)
    else:
        assert syntax == "block"
        assert type(tree) is ast.Assign
        kw = dict(kw)
        kw["optional_vars"] = None  # the asname was meant for `q`, `expand1r` doesn't take it.
        tree.value = expand1r(tree.value, syntax=syntax, **kw)
        return tree


def expandrq(tree, *, syntax, **kw):
    '''[syntax, expr/block] quote-then-expand-at-runtime.

    Quasiquote `tree`, then set it up to have it expanded, at run time,
    until no macros remain. At run time, return the resulting AST.

    Convenient for interactive experimentation in the REPL.

    Because the expansion runs at run time (of the use site of `expandrq`),
    unquoted values have been spliced in by the time the expansion is performed.

    `expandrq[...]` is shorthand for `expandr[q[...]]`.

    `with expandrq as quoted` has the corresponding effect on a block, but
    does not factor into `q` and `expandr`, because the quote is to be applied
    first, but with the expander outside of it. Also, block mode `q` generates
    an `ast.Assign`. The call to the expander is spliced in around its RHS.

    If your tree is already quasiquoted, use `expandr` instead.

    The results from this operator resemble those from `macropy`'s `q`,
    except macro expansion is applied inside any unquoted AST snippets, too.
    '''
    if syntax not in ("expr", "block"):
        raise SyntaxError("`expandrq` is an expr and block macro only")
    tree = q(tree, syntax=syntax, **kw)
    if syntax == "expr":
        return expandr(tree, syntax=syntax, **kw)
    else:
        assert syntax == "block"
        assert type(tree) is ast.Assign
        kw = dict(kw)
        kw["optional_vars"] = None
        tree.value = expandr(tree.value, syntax=syntax, **kw)
        return tree


def expand1r(tree, *, syntax, expander, **kw):
    """[syntax, expr/block] Expand macros at run time, once.

    Convenient for interactive experimentation on quoted code in the REPL.

    Because the expansion runs at run time (of the use site of `expand1r`),
    unquoted values have been spliced in by the time the expansion is performed.

    If you want to quote some code to produce `tree` and then immediately expand it,
    use `expand1rq` instead.
    """
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("`expand1r` (block mode) does not take an asname")
    return _expandr_impl(tree, syntax, expander, macroname="expand1r")


def expandr(tree, *, syntax, expander, **kw):
    """[syntax, expr/block] Expand macros at run time, until no macros remain.

    Convenient for interactive experimentation on quoted code in the REPL.

    Because the expansion runs at run time (of the use site of `expandr`),
    unquoted values have been spliced in by the time the expansion is performed.

    If you want to quote some code to produce `tree` and then immediately expand it,
    use `expandrq` instead.
    """
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("`expandr` (block mode) does not take an asname")
    return _expandr_impl(tree, syntax, expander, macroname="expandr")


def _expandr_impl(tree, syntax, expander, macroname):
    if syntax not in ("expr", "block"):
        raise SyntaxError(f"`{macroname}` is an expr and block macro only")

    # We must snapshot the macro expander's current bindings, and transmit them
    # from macro expansion time to run time. This is exactly the kind of thing
    # the hygienic capture system was designed to do.
    #
    # To keep the macro names as-is (which is important because that's how
    # they'll appear in `tree`), we skip `astify`, and capture the macro
    # functions manually as regular run-time values. As a bonus, this also
    # avoids polluting the global bindings table.
    keys = list(ast.Constant(value=k) for k in expander.bindings.keys())
    values = list(capture_value(v, k) for k, v in expander.bindings.items())

    if macroname == "expandr":
        runtime_operator = "runtime_expand"
    elif macroname == "expand1r":
        runtime_operator = "runtime_expand1"
    else:
        raise ValueError(f"Unknown macroname '{macroname}'; valid: 'expandr', 'expand1r'")

    # Pass args by name to improve human-readability of the expanded output.
    return ast.Call(_mcpyrate_metatools_attr(runtime_operator),
                    [],
                    [ast.keyword("bindings", ast.Dict(keys=keys, values=values)),
                     ast.keyword("filename", ast.Constant(value=expander.filename)),
                     ast.keyword("tree", tree)])