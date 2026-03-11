# -*- coding: utf-8 -*-
"""Unparser round-trip tests for Python 3.14+ syntax.

Requires Python 3.14+ (the source itself won't parse on older versions).
"""

import ast

from ..unparser import unparse


def runtests():
    def test_tstring_simple():
        src = "t'hello {name}'"
        tree = ast.parse(src, mode="eval")
        result = unparse(tree)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_tstring_simple()

    def test_tstring_conversion_and_format():
        src = "t'{value!r:>10}'"
        tree = ast.parse(src, mode="eval")
        result = unparse(tree)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_tstring_conversion_and_format()

    def test_tstring_multiple_interpolations():
        src = "t'{x} + {y} = {x + y}'"
        tree = ast.parse(src, mode="eval")
        result = unparse(tree)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_tstring_multiple_interpolations()

    def test_tstring_no_interpolation():
        src = "t'just a template'"
        tree = ast.parse(src, mode="eval")
        result = unparse(tree)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_tstring_no_interpolation()
