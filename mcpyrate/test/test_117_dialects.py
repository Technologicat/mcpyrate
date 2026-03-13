# -*- coding: utf-8 -*-
"""Tests for the dialect expander error handling and debug mode."""

import ast
import io
import sys

from ..dialects import Dialect, DialectExpander, StepExpansion


# Test dialect classes for error path testing
class GoodDialect(Dialect):
    def transform_source(self, text):
        return text

    def transform_ast(self, tree):
        return tree

    def postprocess_ast(self, tree):
        return tree


class EmptyResultDialect(Dialect):
    def transform_ast(self, tree):
        return []  # falsy but not NotImplemented


class ExplodingInitDialect(Dialect):
    def __init__(self, expander):
        raise RuntimeError("boom in __init__")


class ExplodingTransformDialect(Dialect):
    def transform_ast(self, tree):
        raise RuntimeError("boom in transform")


class ExplodingPostprocessDialect(Dialect):
    def postprocess_ast(self, tree):
        raise RuntimeError("boom in postprocess")


class EmptyPostprocessDialect(Dialect):
    def postprocess_ast(self, tree):
        return []  # falsy


def _make_dialect_import(module_name, *dialect_names):
    """Build a dialect-import AST: `from module_name import dialects, D1, D2, ...`"""
    names = [ast.alias(name="dialects")] + [ast.alias(name=n) for n in dialect_names]
    return ast.ImportFrom(module=module_name, names=names, level=0,
                          lineno=1, col_offset=0)


def runtests():
    # -- DialectExpander: debug mode output --

    def test_debug_mode_source():
        """Debug mode prints before/after/completed messages for source transforms."""
        dexpander = DialectExpander(filename="<test>")
        dexpander.debugmode = True

        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = dexpander.transform_source("x = 1\n")
            output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr

        assert "before dialect" in output
        assert "source" in output
        assert result == "x = 1\n"
    test_debug_mode_source()

    def test_debug_mode_ast():
        """Debug mode prints messages for AST transforms."""
        dexpander = DialectExpander(filename="<test>")
        dexpander.debugmode = True

        tree = ast.parse("x = 1")
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result, instances = dexpander.transform_ast(tree)
            output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr

        assert "before dialect" in output
        assert "AST" in output
    test_debug_mode_ast()

    def test_debug_mode_postprocess():
        """Debug mode prints messages for AST postprocessors."""
        dexpander = DialectExpander(filename="<test>")
        dexpander.debugmode = True

        tree = ast.parse("x = 1")
        dialect = GoodDialect(expander=dexpander)

        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = dexpander.postprocess_ast(tree, [dialect])  # noqa: F841, documents API return
            output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr

        assert "before dialect" in output
        assert "postprocessor" in output.lower()
    test_debug_mode_postprocess()

    def test_debug_mode_postprocess_with_step():
        """Debug mode prints 'after' and 'completed' when a postprocessor takes a step."""
        dexpander = DialectExpander(filename="<test>")
        dexpander.debugmode = True

        tree = ast.parse("x = 1")
        dialect = GoodDialect(expander=dexpander)

        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = dexpander.postprocess_ast(tree, [dialect])  # noqa: F841, documents API return
            output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr

        assert "after" in output
        assert "completed" in output
    test_debug_mode_postprocess_with_step()

    # -- DialectExpander._transform: error branches --
    # These are tested via the internal _transform method, using crafted
    # dialect classes that exercise the error paths.

    def test_non_dialect_class():
        """Non-Dialect class in bindings should raise TypeError."""
        dexpander = DialectExpander(filename="<test>")
        try:
            dexpander._transform(
                ast.parse("x = 1"), kind="AST",
                find_dialectimport=lambda content: ("fake.module",
                                                    {"BadDialect": int},
                                                    1, 0),
                transform="transform_ast",
                format_for_display=str)
        except TypeError as e:
            assert "not a `Dialect`" in str(e)
        else:
            assert False, "should raise TypeError for non-Dialect"
    test_non_dialect_class()

    def test_exploding_init():
        """Exception in dialect __init__ should raise ImportError."""
        dexpander = DialectExpander(filename="<test>")
        try:
            dexpander._transform(
                ast.parse("x = 1"), kind="AST",
                find_dialectimport=lambda content: ("fake.module",
                                                    {"Bad": ExplodingInitDialect},
                                                    1, 0),
                transform="transform_ast",
                format_for_display=str)
        except ImportError as e:
            assert "instantiating" in str(e)
        else:
            assert False, "should raise ImportError for __init__ failure"
    test_exploding_init()

    def test_exploding_transform():
        """Exception in transformer should raise ImportError."""
        dexpander = DialectExpander(filename="<test>")
        try:
            dexpander._transform(
                ast.parse("x = 1"), kind="AST",
                find_dialectimport=lambda content: ("fake.module",
                                                    {"Bad": ExplodingTransformDialect},
                                                    1, 0),
                transform="transform_ast",
                format_for_display=str)
        except ImportError as e:
            assert "Unexpected exception" in str(e)
        else:
            assert False, "should raise ImportError for transformer exception"
    test_exploding_transform()

    def test_empty_result():
        """Empty (falsy) result from transformer should raise ImportError."""
        dexpander = DialectExpander(filename="<test>")
        try:
            dexpander._transform(
                ast.parse("x = 1"), kind="AST",
                find_dialectimport=lambda content: ("fake.module",
                                                    {"Bad": EmptyResultDialect},
                                                    1, 0),
                transform="transform_ast",
                format_for_display=str)
        except ImportError as e:
            assert "empty result" in str(e)
        else:
            assert False, "should raise ImportError for empty result"
    test_empty_result()

    # -- postprocess_ast error branches --

    def test_postprocess_exploding():
        """Exception in postprocess_ast should raise ImportError."""
        dexpander = DialectExpander(filename="<test>")
        tree = ast.parse("x = 1")
        dialect = ExplodingPostprocessDialect(expander=dexpander)
        try:
            dexpander.postprocess_ast(tree, [dialect])
        except ImportError as e:
            assert "Unexpected exception" in str(e)
        else:
            assert False, "should raise ImportError for postprocess exception"
    test_postprocess_exploding()

    def test_postprocess_empty_result():
        """Empty result from postprocess_ast should raise ImportError."""
        dexpander = DialectExpander(filename="<test>")
        tree = ast.parse("x = 1")
        dialect = EmptyPostprocessDialect(expander=dexpander)
        try:
            dexpander.postprocess_ast(tree, [dialect])
        except ImportError as e:
            assert "empty result" in str(e)
        else:
            assert False, "should raise ImportError for empty postprocess result"
    test_postprocess_empty_result()

    # -- _transform: debug mode with actual step --

    def test_debug_mode_transform_step():
        """Debug mode prints 'after' message when a transformer takes a step."""
        dexpander = DialectExpander(filename="<test>")
        dexpander.debugmode = True

        call_count = [0]
        def find_once(content):
            if call_count[0] == 0:
                call_count[0] += 1
                return ("fake.module", {"Good": GoodDialect}, 1, 0)
            return None

        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            dexpander._transform(
                ast.parse("x = 1"), kind="AST",
                find_dialectimport=find_once,
                transform="transform_ast",
                format_for_display=lambda t: str(t))
            output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr

        assert "after" in output
        assert "completed" in output
    test_debug_mode_transform_step()

    # -- StepExpansion dialect --

    def test_step_expansion_source():
        """StepExpansion.transform_source enables debug mode and returns text."""
        dexpander = DialectExpander(filename="<test>")
        assert not dexpander.debugmode
        dialect = StepExpansion(expander=dexpander)

        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = dialect.transform_source("x = 1\n")
        finally:
            sys.stderr = old_stderr

        assert result == "x = 1\n"
        assert dexpander.debugmode is True
    test_step_expansion_source()

    def test_step_expansion_ast_enables_debug():
        """StepExpansion.transform_ast enables debug mode if not already on."""
        dexpander = DialectExpander(filename="<test>")
        assert not dexpander.debugmode
        dialect = StepExpansion(expander=dexpander)

        tree = ast.parse("x = 1")
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = dialect.transform_ast(tree)
        finally:
            sys.stderr = old_stderr

        assert result is tree
        assert dexpander.debugmode is True
    test_step_expansion_ast_enables_debug()

    def test_step_expansion_ast_already_debug():
        """StepExpansion.transform_ast returns NotImplemented if debug already on."""
        dexpander = DialectExpander(filename="<test>")
        dexpander.debugmode = True  # already on
        dialect = StepExpansion(expander=dexpander)

        result = dialect.transform_ast(ast.parse("x = 1"))
        assert result is NotImplemented
    test_step_expansion_ast_already_debug()


if __name__ == '__main__':
    runtests()
