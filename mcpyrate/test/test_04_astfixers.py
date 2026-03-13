# -*- coding: utf-8 -*-
"""Tests for astfixers, particularly the hasattr→getattr migration for Python 3.13 compat."""

import ast

from ..astfixers import fix_locations


def runtests():
    def test_fix_locations_fills_missing():
        """Nodes with no location info get it from the reference node."""
        ref = ast.Constant(value=42, lineno=10, col_offset=5, end_lineno=10, end_col_offset=7)
        node = ast.Constant(value=99)
        fix_locations(node, ref, mode="reference")
        assert node.lineno == 10
        assert node.col_offset == 5
    test_fix_locations_fills_missing()

    def test_fix_locations_none_treated_as_missing():
        """lineno=None should be treated as 'not set' and get overwritten.

        In Python 3.13, omitted optional AST fields are set to None
        instead of being absent. The fix_locations logic must treat
        None the same as absent.
        """
        ref = ast.Constant(value=42, lineno=10, col_offset=5, end_lineno=10, end_col_offset=7)
        node = ast.Constant(value=99)
        node.lineno = None
        node.col_offset = None
        fix_locations(node, ref, mode="reference")
        assert node.lineno == 10
        assert node.col_offset == 5
    test_fix_locations_none_treated_as_missing()

    def test_fix_locations_preserves_existing():
        """Nodes with valid location info keep it in 'reference' mode."""
        ref = ast.Constant(value=42, lineno=10, col_offset=5, end_lineno=10, end_col_offset=7)
        node = ast.Constant(value=99, lineno=20, col_offset=3, end_lineno=20, end_col_offset=5)
        fix_locations(node, ref, mode="reference")
        assert node.lineno == 20
        assert node.col_offset == 3
    test_fix_locations_preserves_existing()

    def test_fix_locations_overwrite_mode():
        """In 'overwrite' mode, existing location info gets replaced."""
        ref = ast.Constant(value=42, lineno=10, col_offset=5, end_lineno=10, end_col_offset=7)
        node = ast.Constant(value=99, lineno=20, col_offset=3, end_lineno=20, end_col_offset=5)
        fix_locations(node, ref, mode="overwrite")
        assert node.lineno == 10
        assert node.col_offset == 5
    test_fix_locations_overwrite_mode()

    def test_fix_locations_update_mode():
        """In 'update' mode, child nodes pick up location from their parent."""
        ref = ast.Constant(value=42, lineno=10, col_offset=5, end_lineno=10, end_col_offset=7)
        parent = ast.Expr(value=ast.Constant(value=99))
        parent.lineno = 20
        parent.col_offset = 3
        parent.end_lineno = 20
        parent.end_col_offset = 5
        fix_locations(parent, ref, mode="update")
        # Parent keeps its own info
        assert parent.lineno == 20
        # Child gets parent's info
        assert parent.value.lineno == 20
        assert parent.value.col_offset == 3
    test_fix_locations_update_mode()

    def test_fix_locations_end_lineno_propagation():
        """end_lineno and end_col_offset propagate correctly."""
        ref = ast.Constant(value=42, lineno=10, col_offset=5, end_lineno=10, end_col_offset=7)
        node = ast.Constant(value=99)
        fix_locations(node, ref, mode="reference")
        assert node.end_lineno == 10
        assert node.end_col_offset == 7
    test_fix_locations_end_lineno_propagation()

    def test_fix_locations_noop_without_reference():
        """If reference_node has no location info, fix_locations is a no-op."""
        ref = ast.Constant(value=42)  # no lineno/col_offset
        node = ast.Constant(value=99)
        result = fix_locations(node, ref, mode="reference")
        assert result is node  # returned unchanged
    test_fix_locations_noop_without_reference()

    print("    test_astfixers: all passed")
