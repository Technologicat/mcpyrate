# -*- coding: utf-8 -*-
"""Tests for AST markers (markers.py)."""

import ast

from ..markers import ASTMarker, get_markers, delete_markers, check_no_markers_remaining
from ..core import MacroExpansionError


def runtests():
    # -- ASTMarker basics --

    def test_marker_fields():
        m = ASTMarker(ast.Constant(value=1))
        assert m.body.value == 1
        assert "body" in m._fields
        # _fields is a per-instance list
        assert isinstance(m._fields, list)
    test_marker_fields()

    def test_marker_default_none():
        """Default body is None (needed for copy/deepcopy)."""
        m = ASTMarker()
        assert m.body is None
    test_marker_default_none()

    def test_marker_subclass_fields():
        class Tagged(ASTMarker):
            _fields = ["body", "tag"]
            def __init__(self, body, tag):
                super().__init__(body)
                self.tag = tag
        t = Tagged(ast.Constant(value=1), "mytag")
        assert t.tag == "mytag"
        assert "tag" in t._fields
        assert "body" in t._fields
        # Subclass fields don't leak to base
        base = ASTMarker(ast.Constant(value=2))
        assert "tag" not in base._fields
    test_marker_subclass_fields()

    def test_marker_per_instance_fields():
        """_fields is per-instance; mutating one doesn't affect others."""
        a = ASTMarker(ast.Constant(value=1))
        b = ASTMarker(ast.Constant(value=2))
        a._fields.append("extra")
        assert "extra" not in b._fields
        assert "extra" not in ASTMarker._fields
    test_marker_per_instance_fields()

    # -- get_markers --

    def test_get_markers():
        tree = ast.parse("x = 1")
        tree.body[0] = ASTMarker(tree.body[0])
        markers = get_markers(tree)
        assert len(markers) == 1
        assert isinstance(markers[0], ASTMarker)
    test_get_markers()

    def test_get_markers_none():
        tree = ast.parse("x = 1")
        markers = get_markers(tree)
        assert markers == []
    test_get_markers_none()

    def test_get_markers_subclass_filter():
        """get_markers can filter by subclass."""
        class MyMarker(ASTMarker):
            pass
        tree = ast.parse("x = 1\ny = 2")
        tree.body[0] = ASTMarker(tree.body[0])
        tree.body[1] = MyMarker(tree.body[1])
        # All markers
        all_markers = get_markers(tree)
        assert len(all_markers) == 2
        # Only MyMarker
        my_markers = get_markers(tree, cls=MyMarker)
        assert len(my_markers) == 1
        assert isinstance(my_markers[0], MyMarker)
    test_get_markers_subclass_filter()

    # -- delete_markers --

    def test_delete_markers():
        tree = ast.parse("x = 1")
        original_assign = tree.body[0]
        tree.body[0] = ASTMarker(tree.body[0])
        result = delete_markers(tree)
        # Marker is gone, original node restored
        assert not any(isinstance(n, ASTMarker) for n in ast.walk(result))
        assert result.body[0] is original_assign
    test_delete_markers()

    def test_delete_markers_subclass():
        """delete_markers with cls only deletes that subclass."""
        class MyMarker(ASTMarker):
            pass
        tree = ast.parse("x = 1\ny = 2")
        tree.body[0] = ASTMarker(tree.body[0])
        tree.body[1] = MyMarker(tree.body[1])
        result = delete_markers(tree, cls=MyMarker)
        # MyMarker gone, base ASTMarker still present
        markers = get_markers(result)
        assert len(markers) == 1
        assert type(markers[0]) is ASTMarker
    test_delete_markers_subclass()

    # -- check_no_markers_remaining --

    def test_check_no_markers_clean():
        """No markers → no error."""
        tree = ast.parse("x = 1")
        check_no_markers_remaining(tree, filename="<test>")  # should not raise
    test_check_no_markers_clean()

    def test_check_no_markers_raises():
        """Markers present → MacroExpansionError."""
        tree = ast.parse("x = 1")
        marker = ASTMarker(tree.body[0])
        # Give the marker location info for error reporting
        marker.lineno = 1
        marker.col_offset = 0
        marker.end_lineno = 1
        marker.end_col_offset = 5
        tree.body[0] = marker
        try:
            check_no_markers_remaining(tree, filename="<test>")
        except MacroExpansionError as e:
            assert "<test>" in str(e)
            assert "AST markers remaining" in str(e)
        else:
            assert False, "Expected MacroExpansionError"
    test_check_no_markers_raises()

    def test_check_no_markers_cls_filter():
        """With cls filter, only matching markers trigger error."""
        class MyMarker(ASTMarker):
            pass
        tree = ast.parse("x = 1\ny = 2")
        tree.body[0] = ASTMarker(tree.body[0])
        tree.body[1] = MyMarker(tree.body[1])
        # Only check for MyMarker — should raise
        try:
            check_no_markers_remaining(tree, filename="<test>", cls=MyMarker)
        except MacroExpansionError:
            pass
        else:
            assert False, "Expected MacroExpansionError for MyMarker"
    test_check_no_markers_cls_filter()

    print("    test_markers: all passed")


if __name__ == '__main__':
    runtests()
