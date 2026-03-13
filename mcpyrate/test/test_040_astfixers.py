# -*- coding: utf-8 -*-
"""Tests for astfixers: ctx fixing and source location fixing."""

import ast
import sys

from ..astfixers import fix_ctx, fix_locations


def runtests():
    # -- fix_ctx --

    def test_fix_ctx_basic():
        """Assign targets get Store, values get Load."""
        tree = ast.parse("x = y")
        # Mangle the ctx to verify fix_ctx actually fixes it
        tree.body[0].targets[0].ctx = ast.Load()
        fix_ctx(tree, copy_seen_nodes=False)
        assert isinstance(tree.body[0].targets[0].ctx, ast.Store)
        assert isinstance(tree.body[0].value.ctx, ast.Load)
    test_fix_ctx_basic()

    def test_fix_ctx_ann_assign():
        """Annotated assignment: target=Store, annotation=Load, value=Load."""
        tree = ast.parse("x: int = 1")
        fix_ctx(tree, copy_seen_nodes=False)
        stmt = tree.body[0]
        assert isinstance(stmt.target.ctx, ast.Store)
        assert isinstance(stmt.annotation.ctx, ast.Load)
    test_fix_ctx_ann_assign()

    def test_fix_ctx_ann_assign_no_value():
        """Annotated assignment without value: just target and annotation."""
        tree = ast.parse("x: int")
        fix_ctx(tree, copy_seen_nodes=False)
        stmt = tree.body[0]
        assert isinstance(stmt.target.ctx, ast.Store)
        assert isinstance(stmt.annotation.ctx, ast.Load)
    test_fix_ctx_ann_assign_no_value()

    def test_fix_ctx_named_expr():
        """Walrus operator: target=Store, value=Load."""
        tree = ast.parse("(x := y)")
        fix_ctx(tree, copy_seen_nodes=False)
        walrus = tree.body[0].value
        assert isinstance(walrus.target.ctx, ast.Store)
        assert isinstance(walrus.value.ctx, ast.Load)
    test_fix_ctx_named_expr()

    def test_fix_ctx_type_alias():
        """type X = int: name gets Store. (PEP 695, Python 3.12+)"""
        if sys.version_info < (3, 12):
            print("    skipped test_fix_ctx_type_alias (needs Python 3.12+)", file=sys.stderr)
            return
        tree = ast.parse("type X = int")
        fix_ctx(tree, copy_seen_nodes=False)
        stmt = tree.body[0]
        assert isinstance(stmt.name.ctx, ast.Store)
    test_fix_ctx_type_alias()

    def test_fix_ctx_copy_seen_nodes():
        """Same node in two positions gets shallow-copied."""
        # Build an AST where the same Name node appears in two places
        shared = ast.Name(id="x", ctx=ast.Load())
        tree = ast.Module(body=[
            ast.Assign(
                targets=[shared],  # needs Store
                value=shared,      # needs Load
                lineno=1, col_offset=0, end_lineno=1, end_col_offset=5,
            )
        ], type_ignores=[])
        ast.fix_missing_locations(tree)
        fix_ctx(tree, copy_seen_nodes=True)
        # One of them should have been copied
        assert tree.body[0].targets[0] is not tree.body[0].value
    test_fix_ctx_copy_seen_nodes()

    def test_fix_ctx_delete():
        """Delete targets get Del context."""
        tree = ast.parse("del x")
        fix_ctx(tree, copy_seen_nodes=False)
        assert isinstance(tree.body[0].targets[0].ctx, ast.Del)
    test_fix_ctx_delete()

    def test_fix_ctx_for():
        """For loop: target=Store, iter=Load."""
        tree = ast.parse("for x in y: pass")
        fix_ctx(tree, copy_seen_nodes=False)
        assert isinstance(tree.body[0].target.ctx, ast.Store)
        assert isinstance(tree.body[0].iter.ctx, ast.Load)
    test_fix_ctx_for()

    def test_fix_ctx_comprehension():
        """Comprehension: target=Store, iter=Load, ifs=Load."""
        tree = ast.parse("[x for x in y if z]")
        fix_ctx(tree, copy_seen_nodes=False)
        comp = tree.body[0].value.generators[0]
        assert isinstance(comp.target.ctx, ast.Store)
        assert isinstance(comp.iter.ctx, ast.Load)
    test_fix_ctx_comprehension()

    def test_fix_ctx_subscript():
        """Subscript: value=Load, slice=Load."""
        tree = ast.parse("x[y]")
        fix_ctx(tree, copy_seen_nodes=False)
        sub = tree.body[0].value
        assert isinstance(sub.value.ctx, ast.Load)
        assert isinstance(sub.slice.ctx, ast.Load)
    test_fix_ctx_subscript()

    def test_fix_ctx_attribute():
        """Attribute: value always Load."""
        tree = ast.parse("x.y")
        fix_ctx(tree, copy_seen_nodes=False)
        attr = tree.body[0].value
        assert isinstance(attr.value.ctx, ast.Load)
    test_fix_ctx_attribute()

    def test_fix_ctx_aug_assign():
        """Augmented assignment: target=Store, value=Load."""
        tree = ast.parse("x += y")
        fix_ctx(tree, copy_seen_nodes=False)
        assert isinstance(tree.body[0].target.ctx, ast.Store)
        assert isinstance(tree.body[0].value.ctx, ast.Load)
    test_fix_ctx_aug_assign()

    def test_fix_ctx_with():
        """With statement: context_expr=Load, optional_vars=Store."""
        tree = ast.parse("with manager as x: pass")
        fix_ctx(tree, copy_seen_nodes=False)
        item = tree.body[0].items[0]
        assert isinstance(item.context_expr.ctx, ast.Load)
        assert isinstance(item.optional_vars.ctx, ast.Store)
    test_fix_ctx_with()

    # -- fix_locations --

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

    def test_fix_locations_none_tree():
        """fix_locations with tree=None returns immediately."""
        ref = ast.Constant(value=42, lineno=10, col_offset=5, end_lineno=10, end_col_offset=7)
        result = fix_locations(None, ref, mode="reference")
        assert result is None
    test_fix_locations_none_tree()

    def test_fix_locations_list_tree():
        """fix_locations with a list of nodes."""
        ref = ast.Constant(value=42, lineno=10, col_offset=5, end_lineno=10, end_col_offset=7)
        nodes = [ast.Constant(value=1), ast.Constant(value=2)]
        fix_locations(nodes, ref, mode="reference")
        for node in nodes:
            assert node.lineno == 10
            assert node.col_offset == 5
    test_fix_locations_list_tree()

    def test_fix_locations_update_col_offset():
        """In update mode, child inherits parent's col_offset when missing."""
        ref = ast.Constant(value=42, lineno=1, col_offset=0, end_lineno=1, end_col_offset=2)
        # Parent has col_offset, child doesn't
        child = ast.Constant(value=99)
        parent = ast.Expr(value=child)
        parent.lineno = 5
        parent.col_offset = 10
        parent.end_lineno = 5
        parent.end_col_offset = 15
        fix_locations(parent, ref, mode="update")
        # Child should get parent's col_offset since parent's was set
        assert child.col_offset == 10
    test_fix_locations_update_col_offset()
