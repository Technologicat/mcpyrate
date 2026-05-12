# -*- coding: utf-8 -*-
"""Tests for general utilities."""

import ast

from ..utils import (gensym, scrub_uuid, flatten, rename, extract_bindings,
                     getdocstring, get_lineno, get_end_lineno, format_location,
                     format_macrofunction, format_context, NestingLevelTracker)
from ..markers import ASTMarker


def runtests():
    # -- gensym --

    def test_gensym_default():
        s = gensym()
        assert s.startswith("gensym_")
        assert len(s) == len("gensym_") + 32  # uuid is 32 hex chars
    test_gensym_default()

    def test_gensym_with_basename():
        s = gensym("kitty")
        assert s.startswith("kitty_")
    test_gensym_with_basename()

    def test_gensym_empty_basename():
        s = gensym("")
        # No prefix, just the uuid
        assert "_" not in s
        assert len(s) == 32
    test_gensym_empty_basename()

    def test_gensym_uniqueness():
        syms = {gensym("x") for _ in range(100)}
        assert len(syms) == 100
    test_gensym_uniqueness()

    def test_gensym_type_error():
        try:
            gensym(42)
        except TypeError:
            pass
        else:
            assert False, "gensym with non-str basename should raise TypeError"
    test_gensym_type_error()

    # -- scrub_uuid --

    def test_scrub_uuid_strips_suffix():
        name = gensym("hello")
        assert scrub_uuid(name) == "hello"
    test_scrub_uuid_strips_suffix()

    def test_scrub_uuid_noop_no_uuid():
        assert scrub_uuid("plain_name") == "plain_name"
    test_scrub_uuid_noop_no_uuid()

    def test_scrub_uuid_noop_no_underscore():
        assert scrub_uuid("nounderscore") == "nounderscore"
    test_scrub_uuid_noop_no_underscore()

    def test_scrub_uuid_not_hex():
        # Suffix is 32 chars but not valid hex
        name = "prefix_" + "g" * 32
        assert scrub_uuid(name) == name
    test_scrub_uuid_not_hex()

    def test_scrub_uuid_wrong_length():
        # Suffix after last _ is not 32 chars
        assert scrub_uuid("prefix_short") == "prefix_short"
    test_scrub_uuid_wrong_length()

    # -- flatten --

    def test_flatten_simple():
        assert flatten([1, [2, 3], [4, [5, 6]]]) == [1, 2, 3, 4, 5, 6]
    test_flatten_simple()

    def test_flatten_removes_none():
        assert flatten([1, None, 2]) == [1, 2]
    test_flatten_removes_none()

    def test_flatten_non_recursive():
        assert flatten([1, [2, [3, 4]]], recursive=False) == [1, 2, [3, 4]]
    test_flatten_non_recursive()

    def test_flatten_empty():
        assert flatten([]) == []
    test_flatten_empty()

    # -- rename --

    def test_rename_name_node():
        tree = ast.parse("x = x + 1")
        rename("x", "y", tree)
        code = ast.unparse(tree)
        assert "y" in code
        assert "x" not in code
    test_rename_name_node()

    def test_rename_attribute():
        tree = ast.parse("obj.x")
        rename("x", "y", tree)
        code = ast.unparse(tree)
        assert "obj.y" in code
    test_rename_attribute()

    def test_rename_function_def():
        tree = ast.parse("def foo(): pass")
        rename("foo", "bar", tree)
        code = ast.unparse(tree)
        assert "def bar" in code
    test_rename_function_def()

    def test_rename_async_function_def():
        tree = ast.parse("async def foo(): pass")
        rename("foo", "bar", tree)
        code = ast.unparse(tree)
        assert "bar" in code
    test_rename_async_function_def()

    def test_rename_class_def():
        tree = ast.parse("class Foo: pass")
        rename("Foo", "Bar", tree)
        code = ast.unparse(tree)
        assert "class Bar" in code
    test_rename_class_def()

    def test_rename_function_parameter():
        tree = ast.parse("def f(x): return x")
        rename("x", "y", tree)
        code = ast.unparse(tree)
        assert "y" in code
    test_rename_function_parameter()

    def test_rename_keyword_argument():
        tree = ast.parse("f(x=1)")
        rename("x", "y", tree)
        code = ast.unparse(tree)
        assert "y=1" in code
    test_rename_keyword_argument()

    def test_rename_import_from():
        tree = ast.parse("from mymod import thing")
        rename("mymod", "newmod", tree)
        code = ast.unparse(tree)
        assert "newmod" in code
    test_rename_import_from()

    def test_rename_alias():
        tree = ast.parse("import foo as bar")
        rename("bar", "baz", tree)
        code = ast.unparse(tree)
        assert "baz" in code
    test_rename_alias()

    def test_rename_alias_name():
        tree = ast.parse("import foo")
        rename("foo", "bar", tree)
        code = ast.unparse(tree)
        assert "bar" in code
    test_rename_alias_name()

    def test_rename_except_handler():
        tree = ast.parse("try:\n pass\nexcept Exception as e:\n pass")
        rename("e", "err", tree)
        code = ast.unparse(tree)
        assert "err" in code
    test_rename_except_handler()

    def test_rename_global():
        tree = ast.parse("def f():\n global x\n x = 1")
        rename("x", "y", tree)
        code = ast.unparse(tree)
        assert "global y" in code
    test_rename_global()

    def test_rename_nonlocal():
        tree = ast.parse("def f():\n x = 1\n def g():\n  nonlocal x")
        rename("x", "y", tree)
        code = ast.unparse(tree)
        assert "nonlocal y" in code
    test_rename_nonlocal()

    def test_rename_match_as():
        tree = ast.parse("match x:\n case y:\n  pass")
        rename("y", "z", tree)
        code = ast.unparse(tree)
        assert "z" in code
    test_rename_match_as()

    # -- extract_bindings --

    def test_extract_bindings():
        def macro_a(tree, **kw): return tree
        def macro_b(tree, **kw): return tree
        def macro_c(tree, **kw): return tree
        bindings = {"a": macro_a, "b": macro_b, "c": macro_c, "alias_a": macro_a}
        result = extract_bindings(bindings, macro_a, macro_c)
        assert "a" in result
        assert "alias_a" in result
        assert "c" in result
        assert "b" not in result
    test_extract_bindings()

    # -- getdocstring --

    def test_getdocstring_present():
        tree = ast.parse('"hello world"\nx = 1')
        assert getdocstring(tree.body) == "hello world"
    test_getdocstring_present()

    def test_getdocstring_absent():
        tree = ast.parse("x = 1")
        assert getdocstring(tree.body) is None
    test_getdocstring_absent()

    def test_getdocstring_none_body():
        assert getdocstring(None) is None
    test_getdocstring_none_body()

    def test_getdocstring_empty_body():
        assert getdocstring([]) is None
    test_getdocstring_empty_body()

    def test_getdocstring_type_error():
        try:
            getdocstring("not a list")
        except TypeError:
            pass
        else:
            assert False, "getdocstring with non-list should raise TypeError"
    test_getdocstring_type_error()

    # -- get_lineno --

    def test_get_lineno_direct():
        node = ast.Constant(value=42, lineno=10, col_offset=0)
        assert get_lineno(node) == 10
    test_get_lineno_direct()

    def test_get_lineno_nested():
        tree = ast.parse("x = 1")
        lineno = get_lineno(tree)  # Module has no lineno; should find it in children
        assert lineno == 1
    test_get_lineno_nested()

    def test_get_lineno_list():
        stmts = ast.parse("x = 1\ny = 2").body
        assert get_lineno(stmts) == 1
    test_get_lineno_list()

    def test_get_lineno_none():
        node = ast.Constant(value=42)  # no lineno
        assert get_lineno(node) is None
    test_get_lineno_none()

    def test_get_lineno_marker():
        inner = ast.Constant(value=42, lineno=7, col_offset=0)
        marker = ASTMarker(body=inner)
        assert get_lineno(marker) == 7
    test_get_lineno_marker()

    # -- get_end_lineno --

    def test_get_end_lineno_direct():
        node = ast.Constant(value=42, lineno=10, col_offset=0,
                            end_lineno=10, end_col_offset=2)
        assert get_end_lineno(node) == 10
    test_get_end_lineno_direct()

    def test_get_end_lineno_nested():
        tree = ast.parse("x = 1\ny = 2")
        # The Module itself has no end_lineno, but its children do.
        # Recursive search returns the first non-None value found depth-first.
        assert get_end_lineno(tree) is not None
    test_get_end_lineno_nested()

    def test_get_end_lineno_none():
        node = ast.Constant(value=42, lineno=10, col_offset=0)  # no end_*
        assert get_end_lineno(node) is None
    test_get_end_lineno_none()

    def test_get_end_lineno_marker():
        inner = ast.Constant(value=42, lineno=7, col_offset=0,
                             end_lineno=7, end_col_offset=2)
        marker = ASTMarker(body=inner)
        assert get_end_lineno(marker) == 7
    test_get_end_lineno_marker()

    # -- format_location --

    def test_format_location_single_line():
        node = ast.Constant(value=42, lineno=10, col_offset=0)
        result = format_location("/test.py", node, "x = 42")
        assert "10" in result
        assert "x = 42" in result
    test_format_location_single_line()

    def test_format_location_multiline():
        node = ast.Constant(value=42, lineno=10, col_offset=0)
        result = format_location("/test.py", node, "if True:\n    pass")
        assert "\n" in result
    test_format_location_multiline()

    def test_format_location_no_source():
        node = ast.Constant(value=42, lineno=10, col_offset=0)
        result = format_location("/test.py", node, None)
        assert "10" in result
    test_format_location_no_source()

    # -- format_macrofunction --

    def test_format_macrofunction_normal():
        def my_macro(tree, **kw): return tree
        result = format_macrofunction(my_macro)
        assert "my_macro" in result
    test_format_macrofunction_normal()

    def test_format_macrofunction_broken_binding():
        # An object without __module__ or __qualname__
        result = format_macrofunction(42)
        assert "42" in result
    test_format_macrofunction_broken_binding()

    def test_format_macrofunction_no_module():
        """Macros defined in the REPL have __module__=None."""
        def repl_macro(tree, **kw): return tree
        repl_macro.__module__ = None
        result = format_macrofunction(repl_macro)
        assert "repl_macro" in result
        assert "None." not in result
    test_format_macrofunction_no_module()

    # -- format_context --

    def test_format_context_short():
        tree = ast.parse("x = 1")
        result = format_context(tree)
        assert "x" in result
    test_format_context_short()

    def test_format_context_truncation():
        source = "\n".join(f"x{i} = {i}" for i in range(20))
        tree = ast.parse(source)
        result = format_context(tree, n=3)
        assert "..." in result
    test_format_context_truncation()

    # -- NestingLevelTracker --

    def test_nesting_level_default():
        t = NestingLevelTracker()
        assert t.value == 0
    test_nesting_level_default()

    def test_nesting_level_set_to():
        t = NestingLevelTracker()
        with t.set_to(42):
            assert t.value == 42
        assert t.value == 0
    test_nesting_level_set_to()

    def test_nesting_level_changed_by():
        t = NestingLevelTracker()
        with t.changed_by(+10):
            assert t.value == 10
            with t.changed_by(+5):
                assert t.value == 15
            assert t.value == 10
        assert t.value == 0
    test_nesting_level_changed_by()

    def test_nesting_level_set_to_type_error():
        t = NestingLevelTracker()
        try:
            with t.set_to("not an int"):
                pass
        except TypeError:
            pass
        else:
            assert False, "set_to with non-int should raise TypeError"
    test_nesting_level_set_to_type_error()

    def test_nesting_level_set_to_negative():
        t = NestingLevelTracker()
        try:
            with t.set_to(-1):
                pass
        except ValueError:
            pass
        else:
            assert False, "set_to with negative value should raise ValueError"
    test_nesting_level_set_to_negative()

    def test_nesting_level_custom_start():
        t = NestingLevelTracker(start=5)
        assert t.value == 5
    test_nesting_level_custom_start()


if __name__ == '__main__':
    runtests()
