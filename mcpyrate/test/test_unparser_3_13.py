# -*- coding: utf-8 -*-
"""Unparser round-trip tests for Python 3.13+ syntax.

Requires Python 3.13+ (the source itself won't parse on older versions).
"""

import ast

from ..unparser import unparse


def runtests():
    def test_typevar_default():
        """Type parameter default (PEP 696)."""
        src = "type Response[T = str] = dict[str, T]"
        tree = ast.parse(src)
        result = unparse(tree)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_typevar_default()

    def test_typevar_bound_and_default():
        src = "type Callback[T: int = bool] = Callable[[T], None]"
        tree = ast.parse(src)
        result = unparse(tree)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_typevar_bound_and_default()

    def test_paramspec_default():
        src = "type Decorator[**P = [int, str]] = Callable[P, None]"
        tree = ast.parse(src)
        result = unparse(tree)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_paramspec_default()

    def test_typevartuple_default():
        src = "type Batch[*Ts = *tuple[int, ...]] = tuple[*Ts]"
        # Our unparser adds a trailing comma for single-element starred tuple in subscript;
        # `tuple[*Ts,]` is semantically equivalent.
        expected = "type Batch[*Ts = *tuple[int, ...]] = tuple[*Ts,]"
        tree = ast.parse(src)
        result = unparse(tree)
        assert result == expected, f"Expected {expected!r}, got {result!r}"
    test_typevartuple_default()
