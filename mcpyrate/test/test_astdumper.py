# -*- coding: utf-8 -*-
"""Tests for the AST pretty-printer."""

import ast

from ..astdumper import dump


def runtests():
    def test_simple_node():
        tree = ast.Constant(value=42)
        result = dump(tree)
        assert "Constant" in result
        assert "42" in result
    test_simple_node()

    def test_multiline_vs_oneline():
        tree = ast.parse("x = 1").body[0]
        multi = dump(tree, multiline=True)
        one = dump(tree, multiline=False)
        assert "\n" in multi
        assert "\n" not in one
    test_multiline_vs_oneline()

    def test_include_attributes():
        tree = ast.parse("x = 1").body[0]
        without = dump(tree, include_attributes=False)
        with_attrs = dump(tree, include_attributes=True)
        assert "lineno" not in without
        assert "lineno" in with_attrs
    test_include_attributes()

    def test_color():
        tree = ast.Constant(value=42)
        colored = dump(tree, color=True)
        plain = dump(tree, color=False)
        # Colored output should contain ANSI escapes
        assert "\x1b[" in colored
        assert "\x1b[" not in plain
    test_color()

    def test_color_value_types():
        """Exercise maybe_colorize_value with different types."""
        for val in (42, 3.14, 1+2j, "hello", b"bytes", True, None):
            tree = ast.Constant(value=val)
            result = dump(tree, color=True)
            assert "Constant" in result
    test_color_value_types()

    def test_color_nonliteral_value():
        """Non-literal field values go through the str() fallback."""
        # ast.alias has a non-literal 'name' field (string, but used as identifier)
        tree = ast.parse("import os").body[0]
        result = dump(tree, color=True)
        assert "Import" in result
    test_color_nonliteral_value()

    def test_list_of_nodes():
        """dump accepts a statement suite (list of AST nodes)."""
        suite = ast.parse("x = 1\ny = 2").body
        result = dump(suite)
        assert "Assign" in result
    test_list_of_nodes()

    def test_empty_list():
        """Empty body list should render as []."""
        tree = ast.parse("def f(): pass").body[0]
        result = dump(tree)
        # decorator_list is always [], so [] should appear
        assert "[]" in result
    test_empty_list()

    def test_invalid_input():
        try:
            dump("not an AST")
        except TypeError:
            pass
        else:
            assert False, "dump with non-AST should raise TypeError"
    test_invalid_input()

    def test_nested_structure():
        """Nested AST should produce indented output."""
        tree = ast.parse("f(x, y)").body[0]
        result = dump(tree, multiline=True)
        lines = result.strip().split("\n")
        assert len(lines) > 1
        # Deeper lines should be indented
        assert any(line.startswith(" ") for line in lines[1:])
    test_nested_structure()

    print("    test_astdumper: all passed")


if __name__ == '__main__':
    runtests()
