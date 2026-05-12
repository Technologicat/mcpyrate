# -*- coding: utf-8 -*-
"""Tests for the dialect expander error handling and debug mode."""

import ast
import io
import sys

from ..dialects import Dialect, DialectExpander, StepExpansion, split_at_dialectimport


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
                                                    1, 0, 1, 10),
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
                                                    1, 0, 1, 10),
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
                                                    1, 0, 1, 10),
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
                                                    1, 0, 1, 10),
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
                return ("fake.module", {"Good": GoodDialect}, 1, 0, 1, 10)
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

    # -- find_dialectimport_*: source-location field propagation --

    def test_find_dialectimport_source_returns_end_fields():
        """Text-based finder returns end_lineno (= lineno) and end_col_offset (= statement length)."""
        # Stick to a real, importable dialect so the module-level get_macros call succeeds.
        text = "from mcpyrate.dialects import dialects, StepExpansion\n"
        dexpander = DialectExpander(filename="<test>")
        result = dexpander.find_dialectimport_source(text)
        assert result is not None
        module_absname, bindings, lineno, col_offset, end_lineno, end_col_offset = result
        assert lineno == 1
        assert col_offset == 0
        # Single-line statement, so end_lineno matches lineno; end_col_offset is the
        # column one past the last char of the stripped statement.
        assert end_lineno == 1
        assert end_col_offset == len(text.strip())
    test_find_dialectimport_source_returns_end_fields()

    def test_find_dialectimport_ast_returns_end_fields():
        """AST-based finder picks up end_lineno/end_col_offset from the import node."""
        tree = ast.parse("from mcpyrate.dialects import dialects, StepExpansion\n")
        dexpander = DialectExpander(filename="<test>")
        result = dexpander.find_dialectimport_ast(tree)
        assert result is not None
        module_absname, bindings, lineno, col_offset, end_lineno, end_col_offset = result
        # Real ast.ImportFrom carries all four fields on Python 3.8+.
        assert lineno == 1
        assert col_offset == 0
        assert end_lineno == 1
        assert end_col_offset is not None and end_col_offset > 0

    test_find_dialectimport_ast_returns_end_fields()

    def test_dialect_instance_receives_end_fields():
        """DialectExpander threads end_lineno/end_col_offset onto the dialect instance."""
        captured = {}

        class CaptureDialect(Dialect):
            def transform_ast(self, tree):
                captured["lineno"] = self.lineno
                captured["col_offset"] = self.col_offset
                captured["end_lineno"] = self.end_lineno
                captured["end_col_offset"] = self.end_col_offset
                return tree

        dexpander = DialectExpander(filename="<test>")
        call_count = [0]
        def find_once(content):
            if call_count[0] == 0:
                call_count[0] += 1
                return ("fake.module", {"Capture": CaptureDialect}, 7, 0, 7, 35)
            return None

        dexpander._transform(
            ast.parse("x = 1"), kind="AST",
            find_dialectimport=find_once,
            transform="transform_ast",
            format_for_display=str)

        assert captured == {"lineno": 7, "col_offset": 0,
                            "end_lineno": 7, "end_col_offset": 35}
    test_dialect_instance_receives_end_fields()

    def test_dialect_instance_receives_location_ref():
        """DialectExpander synthesizes a `location_ref` AST node bundling the four fields."""
        captured = {}

        class CaptureDialect(Dialect):
            def transform_ast(self, tree):
                captured["location_ref"] = self.location_ref
                return tree

        dexpander = DialectExpander(filename="<test>")
        call_count = [0]
        def find_once(content):
            if call_count[0] == 0:
                call_count[0] += 1
                return ("fake.module", {"Capture": CaptureDialect}, 7, 0, 7, 35)
            return None

        dexpander._transform(
            ast.parse("x = 1"), kind="AST",
            find_dialectimport=find_once,
            transform="transform_ast",
            format_for_display=str)

        ref = captured["location_ref"]
        assert isinstance(ref, ast.AST)
        assert ref.lineno == 7
        assert ref.col_offset == 0
        assert ref.end_lineno == 7
        assert ref.end_col_offset == 35
    test_dialect_instance_receives_location_ref()

    # -- split_at_dialectimport --

    def test_split_single_dialect():
        """Single dialect-import, single binding: import line disappears, body preserved."""
        text = "from x import dialects, BF\n+++.\n"
        prologue, other, body = split_at_dialectimport(text, "BF", 1)
        assert prologue == ""
        assert body == "+++.\n"
        assert other == []
    test_split_single_dialect()

    def test_split_preserves_prologue():
        """Text before the dialect-import line goes into `prologue`."""
        text = "# encoding comment\n'''docstring'''\nfrom x import dialects, BF\nbody\n"
        prologue, other, body = split_at_dialectimport(text, "BF", 3)
        assert prologue == "# encoding comment\n'''docstring'''\n"
        assert body == "body\n"
        assert other == []
    test_split_preserves_prologue()

    def test_split_strips_own_dialect_from_shared_line():
        """Two dialects on one line: target's name is stripped, line re-emitted in `other`."""
        text = "from x import dialects, BF, Opt\n+++.\n"
        prologue, other, body = split_at_dialectimport(text, "BF", 1)
        assert prologue == ""
        assert body == "+++.\n"
        assert other == ["from x import dialects, Opt\n"]
    test_split_strips_own_dialect_from_shared_line()

    def test_split_preserves_other_dialect_on_separate_line():
        """Separate dialect-imports: the non-target one is pulled out into `other`."""
        text = "from x import dialects, BF\nfrom y import dialects, Opt\n+++.\n"
        prologue, other, body = split_at_dialectimport(text, "BF", 1)
        assert prologue == ""
        assert body == "+++.\n"
        assert other == ["from y import dialects, Opt\n"]
    test_split_preserves_other_dialect_on_separate_line()

    def test_split_stale_lineno_falls_back_to_name():
        """A lineno that no longer points to the dialect-import still finds it by name."""
        text = "from x import dialects, BF\n+++.\n"
        # lineno 99 doesn't exist in the text; helper falls back to name search.
        prologue, other, body = split_at_dialectimport(text, "BF", 99)
        assert prologue == ""
        assert body == "+++.\n"
        assert other == []
    test_split_stale_lineno_falls_back_to_name()

    def test_split_no_matching_dialect():
        """Returns None when no dialect-import with the given name is present."""
        text = "from x import dialects, Other\n+++.\n"
        assert split_at_dialectimport(text, "BF") is None
    test_split_no_matching_dialect()

    def test_split_no_dialect_import_at_all():
        """Returns None when there's no dialect-import anywhere in the text."""
        assert split_at_dialectimport("x = 1\n", "BF") is None
    test_split_no_dialect_import_at_all()

    def test_split_tolerates_trailing_comment_on_import_line():
        """A `# noqa`-style trailing comment on the import line is handled."""
        text = "from x import dialects, BF  # noqa: F401\n+++.\n"
        prologue, other, body = split_at_dialectimport(text, "BF")
        assert prologue == ""
        assert body == "+++.\n"
        assert other == []
    test_split_tolerates_trailing_comment_on_import_line()


if __name__ == '__main__':
    runtests()
