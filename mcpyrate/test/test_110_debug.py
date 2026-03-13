# -*- coding: utf-8 -*-
"""Tests for debug utilities."""

import ast
import io
import sys

from ..debug import (SourceLocationInfoValidator, format_bindings,
                     step_expansion, show_bindings)
from ..expander import MacroExpander


def _identity_macro(tree, *, syntax, **kw):
    """A trivial macro that returns its input unchanged."""
    return tree


def runtests():
    # -- SourceLocationInfoValidator --

    def test_validator_detects_valid_location():
        """A node with lineno and col_offset should not be collected."""
        node = ast.Constant(value=42, lineno=10, col_offset=5)
        v = SourceLocationInfoValidator()
        v.visit(node)
        assert len(v.collected) == 0
    test_validator_detects_valid_location()

    def test_validator_detects_none_as_missing():
        """lineno=None should be flagged as missing.

        In Python 3.13, omitted optional AST fields are set to None
        instead of being absent. The validator must treat None as
        'not meaningfully present'.
        """
        node = ast.Constant(value=42)
        node.lineno = None
        node.col_offset = 5
        v = SourceLocationInfoValidator()
        v.visit(node)
        assert len(v.collected) == 1
        _tree, _code, missing = v.collected[0]
        assert "lineno" in missing
        assert "col_offset" not in missing
    test_validator_detects_none_as_missing()

    def test_validator_detects_absent_as_missing():
        """A node without lineno at all should be flagged."""
        node = ast.Constant(value=42)
        # Don't set lineno or col_offset at all
        v = SourceLocationInfoValidator()
        v.visit(node)
        assert len(v.collected) == 1
        _tree, _code, missing = v.collected[0]
        assert "lineno" in missing
        assert "col_offset" in missing
    test_validator_detects_absent_as_missing()

    def test_validator_ignores_specified_nodes():
        """Nodes in the ignore set should not be collected."""
        node = ast.Constant(value=42)  # no location info
        v = SourceLocationInfoValidator(ignore={node})
        v.visit(node)
        assert len(v.collected) == 0
    test_validator_ignores_specified_nodes()

    def test_validator_custom_check_fields():
        """Validator can check arbitrary fields, not just source location."""
        node = ast.Constant(value=42, lineno=1, col_offset=0)
        v = SourceLocationInfoValidator(check_fields=["end_lineno"])
        v.visit(node)
        assert len(v.collected) == 1
        _, _, missing = v.collected[0]
        assert "end_lineno" in missing
    test_validator_custom_check_fields()

    def test_validator_nested_tree():
        """Validator walks into child nodes."""
        tree = ast.parse("x = 1")
        v = SourceLocationInfoValidator()
        v.visit(tree)
        # Module and ctx nodes (Store, Load) lack lineno — they should be collected.
        assert len(v.collected) > 0
        collected_types = {type(t).__name__ for t, _, _ in v.collected}
        assert "Module" in collected_types or "Store" in collected_types
    test_validator_nested_tree()

    # -- format_bindings --

    def _make_expander(bindings=None):
        """Create a MacroExpander with the given bindings for testing."""
        if bindings is None:
            bindings = {}
        return MacroExpander(bindings, "<test>")

    def test_format_bindings_empty():
        """Empty bindings should show '<no bindings>'."""
        expander = _make_expander()
        result = format_bindings(expander)
        assert "<no bindings>" in result
        assert "<test>" in result
    test_format_bindings_empty()

    def test_format_bindings_with_entries():
        """Bindings should list macro names and their functions."""
        def my_macro(tree, **kw):
            return tree
        expander = _make_expander({"my_macro": my_macro})
        result = format_bindings(expander)
        assert "my_macro" in result
        assert "<no bindings>" not in result
    test_format_bindings_with_entries()

    def test_format_bindings_color():
        """Colored output should contain ANSI escapes."""
        expander = _make_expander()
        colored = format_bindings(expander, color=True)
        plain = format_bindings(expander, color=False)
        assert "\x1b[" in colored
        assert "\x1b[" not in plain
    test_format_bindings_color()

    def test_format_bindings_color_with_entries():
        """Colored output with actual bindings."""
        def my_macro(tree, **kw):
            return tree
        expander = _make_expander({"my_macro": my_macro})
        result = format_bindings(expander, color=True)
        assert "my_macro" in result
        assert "\x1b[" in result
    test_format_bindings_color_with_entries()

    def test_format_bindings_sorted():
        """Bindings should appear in sorted order."""
        def m1(tree, **kw): return tree
        def m2(tree, **kw): return tree
        def m3(tree, **kw): return tree
        expander = _make_expander({"zebra": m1, "alpha": m2, "middle": m3})
        result = format_bindings(expander)
        alpha_pos = result.index("alpha")
        middle_pos = result.index("middle")
        zebra_pos = result.index("zebra")
        assert alpha_pos < middle_pos < zebra_pos
    test_format_bindings_sorted()

    # -- show_bindings --

    def test_show_bindings_wrong_syntax():
        """show_bindings rejects non-name syntax."""
        expander = _make_expander()
        try:
            show_bindings(ast.Name(id="x"), syntax="expr", expander=expander)
        except SyntaxError as e:
            assert "identifier macro only" in str(e)
        else:
            assert False, "should raise SyntaxError for non-name syntax"
    test_show_bindings_wrong_syntax()

    def test_show_bindings_prints_and_returns_none():
        """show_bindings prints bindings to stderr and evaluates to None."""
        def my_macro(tree, **kw):
            return tree
        expander = _make_expander({"my_macro": my_macro})
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = expander_result = show_bindings(  # noqa: F841, documents API return
                ast.Name(id="show_bindings"), syntax="name", expander=expander)
            output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr
        assert result is None
        assert "my_macro" in output
    test_show_bindings_prints_and_returns_none()

    # -- step_expansion: error paths --

    def test_step_expansion_wrong_syntax():
        """step_expansion rejects non-expr/block syntax."""
        expander = _make_expander()
        try:
            step_expansion(ast.Name(id="x"), args=[], syntax="name",
                           expander=expander)
        except SyntaxError as e:
            assert "expr and block macro only" in str(e)
        else:
            assert False, "should raise SyntaxError for name syntax"
    test_step_expansion_wrong_syntax()

    def test_step_expansion_bad_arg_type():
        """step_expansion rejects non-Constant arguments."""
        expander = _make_expander()
        try:
            step_expansion(ast.parse("x = 1"), args=[ast.Name(id="bad")],
                           syntax="expr", expander=expander)
        except TypeError as e:
            assert "expected str argument" in str(e)
        else:
            assert False, "should raise TypeError for non-Constant arg"
    test_step_expansion_bad_arg_type()

    def test_step_expansion_unknown_arg():
        """step_expansion rejects unknown argument values."""
        expander = _make_expander()
        try:
            step_expansion(ast.parse("x = 1"),
                           args=[ast.Constant(value="bogus")],
                           syntax="expr", expander=expander)
        except ValueError as e:
            assert "unknown argument" in str(e)
        else:
            assert False, "should raise ValueError for unknown arg"
    test_step_expansion_unknown_arg()

    # -- step_expansion: happy paths --

    def _make_macro_invocation_tree():
        """Build `im[42]` as AST, where `im` is a macro name.

        This is a Subscript node: im[42], which the expander recognizes
        as an expr-macro invocation when `im` is bound.
        """
        tree = ast.Subscript(
            value=ast.Name(id="im", ctx=ast.Load(),
                           lineno=1, col_offset=0, end_lineno=1, end_col_offset=2),
            slice=ast.Constant(value=42, lineno=1, col_offset=3,
                               end_lineno=1, end_col_offset=5),
            ctx=ast.Load(),
            lineno=1, col_offset=0, end_lineno=1, end_col_offset=6)
        return ast.fix_missing_locations(ast.Module(body=[ast.Expr(value=tree)],
                                                    type_ignores=[]))

    def test_step_expansion_no_macros():
        """step_expansion with no macro invocations just prints before/complete."""
        expander = _make_expander()
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = step_expansion(ast.parse("x = 1"), args=[],  # noqa: F841, documents API return
                                    syntax="expr", expander=expander)
            output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr
        assert "before macro expansion" in output
        assert "macro expansion complete" in output
        assert "0 steps" in output
    test_step_expansion_no_macros()

    def test_step_expansion_with_macro():
        """step_expansion expands a macro and prints step output."""
        expander = _make_expander({"im": _identity_macro})
        tree = _make_macro_invocation_tree()
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = step_expansion(tree, args=[], syntax="expr",  # noqa: F841, documents API return
                                    expander=expander)
            output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr
        assert "before macro expansion" in output
        assert "after step 1" in output
        assert "macro expansion complete" in output
        assert "1 step." in output  # singular
    test_step_expansion_with_macro()

    def test_step_expansion_dump_mode():
        """step_expansion with 'dump' arg uses AST dump renderer."""
        expander = _make_expander()
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            step_expansion(ast.parse("x = 1"),
                           args=[ast.Constant(value="dump")],
                           syntax="expr", expander=expander)
            output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr
        # dump mode shows AST node types
        assert "Module" in output
    test_step_expansion_dump_mode()

    def test_step_expansion_detailed_mode():
        """step_expansion with 'detailed' prints per-expansion details."""
        expander = _make_expander({"im": _identity_macro})
        tree = _make_macro_invocation_tree()
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            step_expansion(tree,
                           args=[ast.Constant(value="detailed")],
                           syntax="expr", expander=expander)
            output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr
        assert "Applying" in output
        assert "im" in output
        assert "Result" in output
    test_step_expansion_detailed_mode()

    print("    test_debug: all passed")
