# -*- coding: utf-8 -*-
"""Tests for macro expander utilities."""

import ast
import os
import sys

from ..coreutils import (resolve_package, relativize, match_syspath,
                         ismacroimport, get_macros,
                         isfutureimport, split_futureimports,
                         inject_after_futureimports,
                         _mcpyrate_attr)
from ..unparser import unparse_with_fallbacks


def runtests():
    # -- resolve_package / relativize / match_syspath --

    def test_match_syspath():
        """A file under a sys.path entry should resolve to that entry."""
        # mcpyrate itself is under some sys.path entry.
        import mcpyrate
        mcpyrate_init = mcpyrate.__file__
        root = match_syspath(mcpyrate_init)
        assert str(mcpyrate_init).startswith(str(root))
    test_match_syspath()

    def test_match_syspath_not_found():
        try:
            match_syspath("/nonexistent/path/to/file.py")
        except ValueError:
            pass
        else:
            assert False, "should raise ValueError for file not in sys.path"
    test_match_syspath_not_found()

    def test_relativize():
        import mcpyrate
        mcpyrate_init = mcpyrate.__file__
        root, relpath = relativize(mcpyrate_init)
        assert relpath  # should be non-empty (mcpyrate is in a package)
        assert "mcpyrate" in relpath
    test_relativize()

    def test_resolve_package():
        import mcpyrate
        mcpyrate_init = mcpyrate.__file__
        pkg = resolve_package(mcpyrate_init)
        assert "mcpyrate" in pkg
    test_resolve_package()

    def test_resolve_package_at_root():
        """A file at the root of a sys.path entry has no package."""
        # Create a temporary scenario by using a file at the sys.path root.
        # We know runtests.py is at the project root, which is on sys.path.
        root_path = str(match_syspath(os.path.abspath("runtests.py")))
        test_file = os.path.join(root_path, "runtests.py")
        try:
            resolve_package(test_file)
        except ImportError:
            pass
        else:
            assert False, "should raise ImportError for file at sys.path root"
    test_resolve_package_at_root()

    # -- ismacroimport --

    def test_ismacroimport_true():
        tree = ast.parse("from mymodule import macros, mymacro").body[0]
        assert ismacroimport(tree)
    test_ismacroimport_true()

    def test_ismacroimport_false_regular():
        tree = ast.parse("from mymodule import something").body[0]
        assert not ismacroimport(tree)
    test_ismacroimport_false_regular()

    def test_ismacroimport_false_import():
        tree = ast.parse("import mymodule").body[0]
        assert not ismacroimport(tree)
    test_ismacroimport_false_import()

    def test_ismacroimport_custom_magicname():
        tree = ast.parse("from mymodule import dialects, mydialect").body[0]
        assert ismacroimport(tree, magicname="dialects")
        assert not ismacroimport(tree, magicname="macros")
    test_ismacroimport_custom_magicname()

    def test_ismacroimport_with_asname():
        """'from x import macros as m, ...' is NOT a macro-import (asname on 'macros')."""
        tree = ast.parse("from mymodule import macros as m, mymacro").body[0]
        assert not ismacroimport(tree)
    test_ismacroimport_with_asname()

    # -- get_macros --

    def test_get_macros_basic():
        """Import macros from a real module (mcpyrate.debug has some)."""
        tree = ast.parse("from mcpyrate.debug import macros, step_expansion").body[0]
        absname, bindings = get_macros(tree, filename="<test>")
        assert absname == "mcpyrate.debug"
        assert "step_expansion" in bindings
        assert callable(bindings["step_expansion"])
    test_get_macros_basic()

    def test_get_macros_no_module_name():
        """Macro-import with missing module name should raise SyntaxError."""
        imp = ast.ImportFrom(module=None, names=[ast.alias(name="macros"), ast.alias(name="foo")], level=0)
        ast.fix_missing_locations(imp)
        try:
            get_macros(imp, filename="<test>")
        except SyntaxError:
            pass
        else:
            assert False, "should raise SyntaxError for missing module"
    test_get_macros_no_module_name()

    def test_get_macros_module_not_found():
        """Macro-import from nonexistent module should raise ModuleNotFoundError."""
        tree = ast.parse("from nonexistent_module_xyz import macros, foo").body[0]
        try:
            get_macros(tree, filename="<test>")
        except ModuleNotFoundError:
            pass
        else:
            assert False, "should raise ModuleNotFoundError"
    test_get_macros_module_not_found()

    def test_get_macros_name_not_found():
        """Macro-import of nonexistent name should raise ImportError."""
        tree = ast.parse("from mcpyrate.debug import macros, no_such_macro_xyz").body[0]
        try:
            get_macros(tree, filename="<test>")
        except ImportError:
            pass
        else:
            assert False, "should raise ImportError for nonexistent macro name"
    test_get_macros_name_not_found()

    def test_get_macros_not_callable():
        """Importing a non-callable as a macro should raise ImportError."""
        tree = ast.parse("from mcpyrate.debug import macros, __all__").body[0]
        try:
            get_macros(tree, filename="<test>")
        except ImportError as e:
            assert "not a callable" in str(e)
        else:
            assert False, "should raise ImportError for non-callable"
    test_get_macros_not_callable()

    def test_get_macros_disallow_asname():
        tree = ast.parse("from mcpyrate.debug import macros, step_expansion as se").body[0]
        try:
            get_macros(tree, filename="<test>", allow_asname=False)
        except ImportError as e:
            assert "as-naming" in str(e)
        else:
            assert False, "should raise ImportError when as-naming is disallowed"
    test_get_macros_disallow_asname()

    def test_get_macros_self_import_relative():
        """Self-macro-import cannot be relative."""
        imp = ast.ImportFrom(module="__self__",
                             names=[ast.alias(name="macros"), ast.alias(name="foo")],
                             level=1)
        ast.fix_missing_locations(imp)
        try:
            get_macros(imp, filename="<test>")
        except SyntaxError as e:
            assert "cannot be relative" in str(e)
        else:
            assert False, "should raise SyntaxError for relative self-macro-import"
    test_get_macros_self_import_relative()

    def test_get_macros_self_import_not_found():
        """Self-macro-import for a module not in sys.modules should raise ModuleNotFoundError."""
        imp = ast.ImportFrom(module="__self__",
                             names=[ast.alias(name="macros"), ast.alias(name="foo")],
                             level=0)
        ast.fix_missing_locations(imp)
        try:
            get_macros(imp, filename="<test>", self_module="__nonexistent_self_module_xyz__")
        except ModuleNotFoundError:
            pass
        else:
            assert False, "should raise ModuleNotFoundError for missing self module"
    test_get_macros_self_import_not_found()

    # -- _mcpyrate_attr --

    def test_mcpyrate_attr_simple():
        """Simple dotted name without submodule."""
        tree = _mcpyrate_attr("dump")
        code = unparse_with_fallbacks(tree)
        assert "mcpyrate" in code
        assert "dump" in code
    test_mcpyrate_attr_simple()

    def test_mcpyrate_attr_dotted():
        """Dotted name with submodule."""
        tree = _mcpyrate_attr("quotes.lookup_value")
        code = unparse_with_fallbacks(tree)
        assert "mcpyrate" in code
        assert "quotes" in code
        assert "lookup_value" in code
    test_mcpyrate_attr_dotted()

    def test_mcpyrate_attr_force_import():
        """force_import should use __import__ instead of bare Name."""
        tree = _mcpyrate_attr("dump", force_import=True)
        code = unparse_with_fallbacks(tree)
        assert "__import__" in code
    test_mcpyrate_attr_force_import()

    def test_mcpyrate_attr_force_import_dotted():
        tree = _mcpyrate_attr("quotes.lookup_value", force_import=True)
        code = unparse_with_fallbacks(tree)
        assert "__import__" in code
        assert "mcpyrate.quotes" in code
    test_mcpyrate_attr_force_import_dotted()

    def test_mcpyrate_attr_type_error():
        try:
            _mcpyrate_attr(42)
        except TypeError:
            pass
        else:
            assert False, "should raise TypeError for non-str"
    test_mcpyrate_attr_type_error()

    # -- isfutureimport --

    def test_isfutureimport_true():
        tree = ast.parse("from __future__ import annotations").body[0]
        assert isfutureimport(tree)
    test_isfutureimport_true()

    def test_isfutureimport_false():
        tree = ast.parse("from os import path").body[0]
        assert not isfutureimport(tree)
    test_isfutureimport_false()

    # -- split_futureimports --

    def test_split_futureimports_basic():
        body = ast.parse("from __future__ import annotations\nx = 1").body
        doc, future, rest = split_futureimports(body)
        assert doc == []
        assert len(future) == 1
        assert len(rest) == 1
    test_split_futureimports_basic()

    def test_split_futureimports_with_docstring():
        body = ast.parse("'docstring'\nfrom __future__ import annotations\nx = 1").body
        doc, future, rest = split_futureimports(body)
        assert len(doc) == 1
        assert len(future) == 1
        assert len(rest) == 1
    test_split_futureimports_with_docstring()

    def test_split_futureimports_no_future():
        body = ast.parse("x = 1\ny = 2").body
        doc, future, rest = split_futureimports(body)
        assert doc == []
        assert future == []
        assert len(rest) == 2
    test_split_futureimports_no_future()

    def test_split_futureimports_empty():
        doc, future, rest = split_futureimports([])
        assert doc == [] and future == [] and rest == []
    test_split_futureimports_empty()

    # -- inject_after_futureimports --

    def test_inject_after_futureimports_basic():
        body = ast.parse("from __future__ import annotations\nx = 1").body
        stmt = ast.parse("y = 2").body[0]
        result = inject_after_futureimports(stmt, body)
        # Should be: future import, y = 2, x = 1
        assert len(result) == 3
    test_inject_after_futureimports_basic()

    def test_inject_after_futureimports_list():
        body = ast.parse("x = 1").body
        stmts = ast.parse("y = 2\nz = 3").body
        result = inject_after_futureimports(stmts, body)
        assert len(result) == 3
    test_inject_after_futureimports_list()

    def test_inject_after_futureimports_type_error_body():
        try:
            inject_after_futureimports(ast.parse("x = 1").body[0], "not a list")
        except TypeError:
            pass
        else:
            assert False, "should raise TypeError for non-list body"
    test_inject_after_futureimports_type_error_body()

    def test_inject_after_futureimports_type_error_stmts():
        try:
            inject_after_futureimports(42, [])
        except TypeError:
            pass
        else:
            assert False, "should raise TypeError for non-stmt stmts"
    test_inject_after_futureimports_type_error_stmts()


if __name__ == '__main__':
    runtests()
