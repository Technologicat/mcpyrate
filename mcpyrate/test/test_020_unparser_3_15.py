# -*- coding: utf-8 -*-
"""Unparser round-trip tests for Python 3.15+ syntax.

Requires Python 3.15+ (the source itself won't parse on older versions).

Covers the two syntax additions that changed the AST: PEP 810 lazy imports, which
added the `is_lazy` field to `Import`/`ImportFrom`, and PEP 798 unpacking in
comprehensions, which made `DictComp.value` optional and allows a `Starred` as the
element of the other three comprehension forms.
"""

import ast

from ..unparser import unparse


def runtests():
    def roundtrip(src):
        """Parse and unparse `src` in `"exec"` mode, and return the result."""
        return unparse(ast.parse(src)).strip()

    # --- PEP 810: lazy imports ---

    def test_lazy_import():
        src = "lazy import json"
        result = roundtrip(src)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_lazy_import()

    def test_lazy_import_from():
        src = "lazy from pathlib import Path"
        result = roundtrip(src)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_lazy_import_from()

    def test_lazy_import_multiple_names():
        src = "lazy from os.path import join, split"
        result = roundtrip(src)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_lazy_import_multiple_names()

    def test_eager_import_unaffected():
        """The modifier must not leak onto ordinary imports."""
        for src in ("import json", "from pathlib import Path"):
            result = roundtrip(src)
            assert result == src, f"Expected {src!r}, got {result!r}"
    test_eager_import_unaffected()

    def test_relative_import_still_has_its_dots():
        """`level` shares a line with the lazy modifier, so check it did not get lost."""
        for src in ("from . import thing", "from ...pkg import thing"):
            result = roundtrip(src)
            assert result == src, f"Expected {src!r}, got {result!r}"
    test_relative_import_still_has_its_dots()

    # --- PEP 798: unpacking in comprehensions ---

    def test_dict_unpacking_comprehension():
        """`DictComp.value` is None here; `key` holds the whole mapping expression."""
        src = "{**d for d in dicts}"
        result = roundtrip(src)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_dict_unpacking_comprehension()

    def test_ordinary_dict_comprehension_unaffected():
        """Control: the `k: v` form still goes through the `value` branch."""
        src = "{k: f(k) for k in keys}"
        result = roundtrip(src)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_ordinary_dict_comprehension_unaffected()

    def test_starred_list_comprehension():
        src = "[*L for L in lists]"
        result = roundtrip(src)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_starred_list_comprehension()

    def test_starred_set_comprehension():
        src = "{*s for s in sets}"
        result = roundtrip(src)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_starred_set_comprehension()

    def test_starred_generator_expression():
        src = "(*L for L in lists)"
        result = roundtrip(src)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_starred_generator_expression()

    def test_starred_async_generator_expression():
        """Async comprehensions only parse inside an `async def`."""
        src = "async def f():\n    return (*a async for a in agen())"
        result = roundtrip(src)
        assert result == src, f"Expected {src!r}, got {result!r}"
    test_starred_async_generator_expression()

    # --- Nodes built by hand, where the optional fields are `None` ---

    def test_handbuilt_import_without_is_lazy():
        """A macro building an `Import` will not set `is_lazy`; it must unparse eagerly."""
        tree = ast.Module(body=[ast.Import(names=[ast.alias(name="json")])], type_ignores=[])
        result = unparse(tree).strip()
        assert result == "import json", f"Expected 'import json', got {result!r}"
    test_handbuilt_import_without_is_lazy()

    def test_handbuilt_importfrom_without_level():
        """`level` is optional too, and `'.' * None` would raise."""
        tree = ast.Module(body=[ast.ImportFrom(module="mypkg",
                                               names=[ast.alias(name="thing")])],
                          type_ignores=[])
        result = unparse(tree).strip()
        assert result == "from mypkg import thing", f"Expected 'from mypkg import thing', got {result!r}"
    test_handbuilt_importfrom_without_level()


if __name__ == '__main__':
    runtests()
