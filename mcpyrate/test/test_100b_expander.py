# -*- coding: utf-8 -*-
"""Tests for the macro expander machinery."""

import ast

from ..astdumper import dump as ast_dump
from ..expander import (namemacro, isnamemacro, parametricmacro, isparametricmacro,
                        destructure_candidate,
                        MacroExpander, MacroCollector,
                        expand_macros, find_macros,
                        _insert_coverage_dummy_stmt, _make_coverage_dummy_expr)
from ..core import Done
from ..unparser import unparse_with_fallbacks


def runtests():
    # -- Decorator markers --

    def test_namemacro_decorator():
        @namemacro
        def mymacro(tree, **kw):
            return tree
        assert isnamemacro(mymacro)
        assert not isparametricmacro(mymacro)
    test_namemacro_decorator()

    def test_parametricmacro_decorator():
        @parametricmacro
        def mymacro(tree, **kw):
            return tree
        assert isparametricmacro(mymacro)
        assert not isnamemacro(mymacro)
    test_parametricmacro_decorator()

    def test_both_decorators():
        @namemacro
        @parametricmacro
        def mymacro(tree, **kw):
            return tree
        assert isnamemacro(mymacro)
        assert isparametricmacro(mymacro)
    test_both_decorators()

    # -- destructure_candidate --

    def test_destructure_name():
        tree = ast.parse("macroname", mode="eval").body
        name, args = destructure_candidate(tree, filename="<test>")
        assert name == "macroname"
        assert args == []
    test_destructure_name()

    def test_destructure_subscript_single_arg():
        tree = ast.parse("macroname[x]", mode="eval").body
        name, args = destructure_candidate(tree, filename="<test>")
        assert name == "macroname"
        assert len(args) == 1
    test_destructure_subscript_single_arg()

    def test_destructure_subscript_multiple_args():
        tree = ast.parse("macroname[x, y, z]", mode="eval").body
        name, args = destructure_candidate(tree, filename="<test>")
        assert name == "macroname"
        assert len(args) == 3
    test_destructure_subscript_multiple_args()

    def test_destructure_call_syntax():
        tree = ast.parse("macroname(x, y)", mode="eval").body
        name, args = destructure_candidate(tree, filename="<test>")
        assert name == "macroname"
        assert len(args) == 2
    test_destructure_call_syntax()

    def test_destructure_call_empty_args():
        tree = ast.parse("macroname()", mode="eval").body
        try:
            destructure_candidate(tree, filename="<test>")
        except SyntaxError as e:
            assert "at least one argument" in str(e)
        else:
            assert False, "empty call args should raise SyntaxError"
    test_destructure_call_empty_args()

    def test_destructure_call_starred():
        tree = ast.parse("macroname(*args)", mode="eval").body
        try:
            destructure_candidate(tree, filename="<test>")
        except SyntaxError as e:
            assert "unpacking" in str(e).lower() or "splatting" in str(e).lower()
        else:
            assert False, "starred arg should raise SyntaxError"
    test_destructure_call_starred()

    def test_destructure_call_no_validation():
        """With _validate_call_syntax=False, no errors on empty args."""
        tree = ast.parse("macroname()", mode="eval").body
        name, args = destructure_candidate(tree, filename="<test>",
                                           _validate_call_syntax=False)
        assert name == "macroname"
    test_destructure_call_no_validation()

    def test_destructure_not_a_macro():
        tree = ast.parse("1 + 2", mode="eval").body
        name, args = destructure_candidate(tree, filename="<test>")
        assert name is None and args is None
    test_destructure_not_a_macro()

    # -- MacroExpander.ismacrocall --

    def _make_expander(bindings=None):
        if bindings is None:
            bindings = {}
        return MacroExpander(bindings, "<test>")

    def test_ismacrocall_unbound():
        expander = _make_expander()
        assert not expander.ismacrocall("foo", [], "expr")
    test_ismacrocall_unbound()

    def test_ismacrocall_expr():
        def mymacro(tree, **kw): return tree
        expander = _make_expander({"mymacro": mymacro})
        assert expander.ismacrocall("mymacro", [], "expr")
    test_ismacrocall_expr()

    def test_ismacrocall_parametric_expr():
        @parametricmacro
        def mymacro(tree, **kw): return tree
        expander = _make_expander({"mymacro": mymacro})
        # With args, only parametric macros qualify.
        assert expander.ismacrocall("mymacro", [ast.Constant(value=1)], "expr")
    test_ismacrocall_parametric_expr()

    def test_ismacrocall_nonparametric_with_args():
        def mymacro(tree, **kw): return tree
        expander = _make_expander({"mymacro": mymacro})
        # Non-parametric macro with args → not a macro call.
        assert not expander.ismacrocall("mymacro", [ast.Constant(value=1)], "expr")
    test_ismacrocall_nonparametric_with_args()

    def test_ismacrocall_name():
        @namemacro
        def mymacro(tree, **kw): return tree
        expander = _make_expander({"mymacro": mymacro})
        assert expander.ismacrocall("mymacro", None, "name")
    test_ismacrocall_name()

    def test_ismacrocall_name_not_namemacro():
        def mymacro(tree, **kw): return tree
        expander = _make_expander({"mymacro": mymacro})
        assert not expander.ismacrocall("mymacro", None, "name")
    test_ismacrocall_name_not_namemacro()

    # -- MacroCollector --

    def test_collector_no_bindings():
        expander = _make_expander()
        mc = MacroCollector(expander)
        tree = ast.parse("x = 1")
        mc.visit(tree)
        assert mc.collected == []
    test_collector_no_bindings()

    def test_collector_none():
        expander = _make_expander({"m": lambda t, **kw: t})
        mc = MacroCollector(expander)
        mc.visit(None)
        assert mc.collected == []
    test_collector_none()

    def test_collector_done():
        expander = _make_expander({"m": lambda t, **kw: t})
        mc = MacroCollector(expander)
        mc.visit(Done(ast.parse("x = 1")))
        assert mc.collected == []
    test_collector_done()

    def test_collector_list():
        expander = _make_expander({"m": lambda t, **kw: t})
        mc = MacroCollector(expander)
        stmts = ast.parse("x = 1\ny = 2").body
        mc.visit(stmts)
        assert mc.collected == []
    test_collector_list()

    def test_collector_expr_macro():
        def mymacro(tree, **kw): return tree
        expander = _make_expander({"mymacro": mymacro})
        mc = MacroCollector(expander)
        tree = ast.parse("mymacro[x]")
        mc.visit(tree)
        assert ("mymacro", "expr") in mc.collected
    test_collector_expr_macro()

    def test_collector_name_macro():
        @namemacro
        def mymacro(tree, **kw): return tree
        expander = _make_expander({"mymacro": mymacro})
        mc = MacroCollector(expander)
        tree = ast.parse("mymacro")
        mc.visit(tree)
        assert ("mymacro", "name") in mc.collected
    test_collector_name_macro()

    def test_collector_decorator_macro():
        def mymacro(tree, **kw): return tree
        expander = _make_expander({"mymacro": mymacro})
        mc = MacroCollector(expander)
        tree = ast.parse("@mymacro\ndef f(): pass")
        mc.visit(tree)
        assert ("mymacro", "decorator") in mc.collected
    test_collector_decorator_macro()

    def test_collector_decorator_macro_on_class():
        def mymacro(tree, **kw): return tree
        expander = _make_expander({"mymacro": mymacro})
        mc = MacroCollector(expander)
        tree = ast.parse("@mymacro\nclass C: pass")
        mc.visit(tree)
        assert ("mymacro", "decorator") in mc.collected
    test_collector_decorator_macro_on_class()

    def test_collector_block_macro():
        def mymacro(tree, **kw): return tree
        expander = _make_expander({"mymacro": mymacro})
        mc = MacroCollector(expander)
        tree = ast.parse("with mymacro:\n pass")
        mc.visit(tree)
        assert ("mymacro", "block") in mc.collected
    test_collector_block_macro()

    def test_collector_clear():
        def mymacro(tree, **kw): return tree
        expander = _make_expander({"mymacro": mymacro})
        mc = MacroCollector(expander)
        tree = ast.parse("mymacro[x]")
        mc.visit(tree)
        assert len(mc.collected) > 0
        mc.clear()
        assert mc.collected == []
    test_collector_clear()

    def test_collector_deduplication():
        """Same macro invoked twice should only appear once in collected."""
        def mymacro(tree, **kw): return tree
        expander = _make_expander({"mymacro": mymacro})
        mc = MacroCollector(expander)
        tree = ast.parse("mymacro[x]\nmymacro[y]")
        mc.visit(tree)
        assert mc.collected.count(("mymacro", "expr")) == 1
    test_collector_deduplication()

    # -- Coverage dummies --

    def test_coverage_dummy_stmt():
        node = ast.Constant(value=42, lineno=10, col_offset=0,
                            end_lineno=10, end_col_offset=2)
        result = _insert_coverage_dummy_stmt(None, node, "mymacro", "<test>")
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Done)
    test_coverage_dummy_stmt()

    def test_coverage_dummy_stmt_no_location():
        """If macronode has no location info, return tree as-is."""
        node = ast.Constant(value=42)
        result = _insert_coverage_dummy_stmt([ast.Pass()], node, "mymacro", "<test>")
        # Should be returned unchanged (no injection)
        assert len(result) == 1
    test_coverage_dummy_stmt_no_location()

    def test_coverage_dummy_expr():
        node = ast.Constant(value=42, lineno=10, col_offset=0,
                            end_lineno=10, end_col_offset=2)
        result = _make_coverage_dummy_expr(node)
        assert isinstance(result, Done)
    test_coverage_dummy_expr()

    # -- expand_macros --

    def test_expand_macros_no_bindings():
        """With no bindings, tree passes through unchanged."""
        tree = ast.parse("x = 1")
        result = expand_macros(tree, {}, filename="<test>")
        assert ast.dump(result) == ast.dump(tree)
    test_expand_macros_no_bindings()

    def test_expand_macros_simple():
        """A simple expr macro that transforms its subtree."""
        def to_constant(tree, *, syntax, **kw):
            return ast.Constant(value=42)
        tree = ast.parse("to_constant[x]")
        result = expand_macros(tree, {"to_constant": to_constant}, filename="<test>")
        code = unparse_with_fallbacks(result)
        assert "42" in code
    test_expand_macros_simple()

    # -- find_macros --

    def test_find_macros_basic():
        tree = ast.parse("from mcpyrate.debug import macros, step_expansion\nx = 1")
        bindings = find_macros(tree, filename="<test>")
        assert "step_expansion" in bindings
        # The macro-import should have been transformed into a regular import.
        assert not any(isinstance(s, ast.ImportFrom) and
                       s.names[0].name == "macros"
                       for s in tree.body)
    test_find_macros_basic()

    def test_find_macros_no_transform():
        tree = ast.parse("from mcpyrate.debug import macros, step_expansion\nx = 1")
        bindings = find_macros(tree, filename="<test>", transform=False)
        assert "step_expansion" in bindings
        # With transform=False, the original import statement stays.
        assert any(isinstance(s, ast.ImportFrom) for s in tree.body)
    test_find_macros_no_transform()

    print("    test_expander: all passed")


if __name__ == '__main__':
    runtests()
