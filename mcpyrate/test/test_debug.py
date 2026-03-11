# -*- coding: utf-8 -*-
"""Tests for debug utilities, particularly SourceLocationInfoValidator."""

import ast

from ..debug import SourceLocationInfoValidator


def runtests():
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

    print("    test_debug: all passed")
