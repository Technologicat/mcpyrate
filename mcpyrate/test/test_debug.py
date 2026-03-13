# -*- coding: utf-8 -*-
"""Tests for debug utilities."""

import ast

from ..debug import SourceLocationInfoValidator, format_bindings
from ..expander import MacroExpander


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

    print("    test_debug: all passed")
