# -*- coding: utf-8 -*-
"""Tests for metatools — macros that expand macros."""

import ast

from ..expander import MacroExpander, namemacro, parametricmacro
from ..metatools import (macro_bindings,
                         fill_location,
                         expand1sq, expandsq,
                         expand1s, expands,
                         expand1rq, expandrq,
                         expand1r, expandr,
                         stepr,
                         expand_first,
                         runtime_expand1, runtime_expand,
                         _expandr_impl)
from ..quotes import q
from ..unparser import unparse_with_fallbacks


def _make_expander(bindings=None, filename="<test>"):
    if bindings is None:
        bindings = {}
    return MacroExpander(bindings, filename)


def runtests():
    # -- runtime_expand1 / runtime_expand --

    def test_runtime_expand1_no_macros():
        """With no macro bindings, tree passes through."""
        tree = ast.parse("x = 1")
        result = runtime_expand1({}, "<test>", tree)
        assert isinstance(result, ast.Module)
    test_runtime_expand1_no_macros()

    def test_runtime_expand_no_macros():
        """With no macro bindings, tree passes through."""
        tree = ast.parse("x = 1")
        result = runtime_expand({}, "<test>", tree)
        assert isinstance(result, ast.Module)
    test_runtime_expand_no_macros()

    # -- macro_bindings: syntax errors --

    def test_macro_bindings_wrong_syntax():
        expander = _make_expander()
        try:
            macro_bindings(ast.parse("x"), syntax="expr", expander=expander)
        except SyntaxError as e:
            assert "name macro only" in str(e)
        else:
            assert False, "should raise SyntaxError for non-name syntax"
    test_macro_bindings_wrong_syntax()

    # -- fill_location: syntax errors --

    def test_fill_location_wrong_syntax():
        invocation = ast.Constant(value=None, lineno=1, col_offset=0)
        try:
            fill_location(ast.parse("x", mode="eval").body,
                          syntax="block", invocation=invocation)
        except SyntaxError as e:
            assert "expr macro only" in str(e)
        else:
            assert False, "should raise SyntaxError for non-expr syntax"
    test_fill_location_wrong_syntax()

    def test_fill_location_missing_location():
        invocation = ast.Constant(value=None)  # no lineno/col_offset
        try:
            fill_location(ast.parse("x", mode="eval").body,
                          syntax="expr", invocation=invocation)
        except SyntaxError as e:
            assert "missing source location" in str(e)
        else:
            assert False, "should raise SyntaxError when invocation has no location"
    test_fill_location_missing_location()

    def test_fill_location_expr():
        """fill_location in expr mode produces a Call to fix_locations."""
        invocation = ast.Constant(value=None, lineno=5, col_offset=10,
                                  end_lineno=5, end_col_offset=30)
        tree = ast.parse("x", mode="eval").body
        result = fill_location(tree, syntax="expr", invocation=invocation)
        assert isinstance(result, ast.Call)
    test_fill_location_expr()

    # -- expand1sq / expandsq: syntax errors --

    def test_expand1sq_wrong_syntax():
        expander = _make_expander()
        try:
            expand1sq(ast.Name(id="x"), syntax="name", expander=expander)
        except SyntaxError as e:
            assert "expr and block" in str(e)
        else:
            assert False, "should raise SyntaxError for name syntax"
    test_expand1sq_wrong_syntax()

    def test_expandsq_wrong_syntax():
        expander = _make_expander()
        try:
            expandsq(ast.Name(id="x"), syntax="name", expander=expander)
        except SyntaxError as e:
            assert "expr and block" in str(e)
        else:
            assert False, "should raise SyntaxError for name syntax"
    test_expandsq_wrong_syntax()

    # -- expand1s / expands: syntax errors --

    def test_expand1s_wrong_syntax():
        expander = _make_expander()
        try:
            expand1s(ast.Name(id="x"), syntax="name", expander=expander,
                     optional_vars=None)
        except SyntaxError as e:
            assert "expr and block" in str(e)
        else:
            assert False, "should raise SyntaxError for name syntax"
    test_expand1s_wrong_syntax()

    def test_expand1s_block_with_asname():
        expander = _make_expander()
        try:
            expand1s(ast.Name(id="x"), syntax="block", expander=expander,
                     optional_vars=ast.Name(id="result"))
        except SyntaxError as e:
            assert "does not take an asname" in str(e)
        else:
            assert False, "should raise SyntaxError for block with asname"
    test_expand1s_block_with_asname()

    def test_expands_wrong_syntax():
        expander = _make_expander()
        try:
            expands(ast.Name(id="x"), syntax="name", expander=expander,
                    optional_vars=None)
        except SyntaxError as e:
            assert "expr and block" in str(e)
        else:
            assert False, "should raise SyntaxError for name syntax"
    test_expands_wrong_syntax()

    def test_expands_block_with_asname():
        expander = _make_expander()
        try:
            expands(ast.Name(id="x"), syntax="block", expander=expander,
                    optional_vars=ast.Name(id="result"))
        except SyntaxError as e:
            assert "does not take an asname" in str(e)
        else:
            assert False, "should raise SyntaxError for block with asname"
    test_expands_block_with_asname()

    # -- expand1rq / expandrq: syntax errors --

    def test_expand1rq_wrong_syntax():
        expander = _make_expander()
        try:
            expand1rq(ast.Name(id="x"), syntax="name", expander=expander)
        except SyntaxError as e:
            assert "expr and block" in str(e)
        else:
            assert False, "should raise SyntaxError for name syntax"
    test_expand1rq_wrong_syntax()

    def test_expandrq_wrong_syntax():
        expander = _make_expander()
        try:
            expandrq(ast.Name(id="x"), syntax="name", expander=expander)
        except SyntaxError as e:
            assert "expr and block" in str(e)
        else:
            assert False, "should raise SyntaxError for name syntax"
    test_expandrq_wrong_syntax()

    # -- expand1r / expandr: syntax errors --

    def test_expand1r_block_with_asname():
        expander = _make_expander()
        try:
            expand1r(ast.Name(id="x"), syntax="block", expander=expander,
                     optional_vars=ast.Name(id="result"))
        except SyntaxError as e:
            assert "does not take an asname" in str(e)
        else:
            assert False, "should raise SyntaxError for block with asname"
    test_expand1r_block_with_asname()

    def test_expandr_block_with_asname():
        expander = _make_expander()
        try:
            expandr(ast.Name(id="x"), syntax="block", expander=expander,
                    optional_vars=ast.Name(id="result"))
        except SyntaxError as e:
            assert "does not take an asname" in str(e)
        else:
            assert False, "should raise SyntaxError for block with asname"
    test_expandr_block_with_asname()

    # -- _expandr_impl: wrong syntax and unknown macroname --

    def test_expandr_impl_wrong_syntax():
        try:
            _expandr_impl(ast.Name(id="x"), "name",
                          _make_expander(), macroname="expandr")
        except SyntaxError as e:
            assert "expr and block" in str(e)
        else:
            assert False, "should raise SyntaxError for name syntax"
    test_expandr_impl_wrong_syntax()

    def test_expandr_impl_unknown_macroname():
        try:
            _expandr_impl(ast.Name(id="x"), "expr",
                          _make_expander(), macroname="bogus")
        except ValueError as e:
            assert "Unknown macroname" in str(e)
        else:
            assert False, "should raise ValueError for unknown macroname"
    test_expandr_impl_unknown_macroname()

    # -- stepr: syntax errors --

    def test_stepr_wrong_syntax():
        expander = _make_expander()
        try:
            stepr(ast.Name(id="x"), args=[], syntax="block",
                  expander=expander, optional_vars=None)
        except SyntaxError as e:
            assert "expr macro only" in str(e)
        else:
            assert False, "should raise SyntaxError for non-expr syntax"
    test_stepr_wrong_syntax()

    def test_stepr_expr():
        """stepr in expr mode produces a Call node."""
        expander = _make_expander()
        result = stepr(ast.Name(id="x"), args=[], syntax="expr",
                       expander=expander)
        assert isinstance(result, ast.Call)
    test_stepr_expr()

    # -- expand_first: syntax errors --

    def test_expand_first_no_args():
        expander = _make_expander()
        try:
            expand_first(ast.parse("x = 1").body, args=[],
                         syntax="block", expander=expander,
                         optional_vars=None)
        except SyntaxError as e:
            assert "no macro arguments were given" in str(e)
        else:
            assert False, "should raise SyntaxError for no args"
    test_expand_first_no_args()

    def test_expand_first_invalid_arg_type():
        """Non-Name nodes in args should raise SyntaxError."""
        def mymacro(tree, **kw):
            return tree
        expander = _make_expander({"mymacro": mymacro})
        try:
            expand_first(ast.parse("x = 1").body,
                         args=[ast.Constant(value=42)],
                         syntax="block", expander=expander,
                         optional_vars=None)
        except SyntaxError as e:
            assert "invalid args" in str(e)
        else:
            assert False, "should raise SyntaxError for non-Name args"
    test_expand_first_invalid_arg_type()

    def test_expand_first_unbound_macro():
        """Macro name not in expander bindings should raise SyntaxError."""
        expander = _make_expander()
        try:
            expand_first(ast.parse("x = 1").body,
                         args=[ast.Name(id="no_such_macro")],
                         syntax="block", expander=expander,
                         optional_vars=None)
        except SyntaxError as e:
            assert "must be bound" in str(e)
        else:
            assert False, "should raise SyntaxError for unbound macro name"
    test_expand_first_unbound_macro()

    def test_expand_first_valid():
        """With a valid macro name, expand_first should not raise."""
        def mymacro(tree, *, syntax, **kw):
            return tree
        expander = _make_expander({"mymacro": mymacro})
        tree = ast.parse("x = 1").body
        result = expand_first(tree, args=[ast.Name(id="mymacro")],
                              syntax="block", expander=expander,
                              optional_vars=None)
        assert result is not None
    test_expand_first_valid()

    print("    test_metatools: all passed")


if __name__ == '__main__':
    runtests()
