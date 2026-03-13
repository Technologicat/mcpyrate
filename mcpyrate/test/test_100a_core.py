# -*- coding: utf-8 -*-
"""Tests for the expander core (core.py)."""

import ast

from ..core import (MacroExpansionError, MacroApplicationError,
                    MacroExpanderMarker, Done,
                    BaseMacroExpander,
                    global_postprocess, global_postprocessors,
                    add_postprocessor, remove_postprocessor,
                    global_bindings)
from ..expander import MacroExpander, namemacro, parametricmacro
from ..markers import ASTMarker
from ..unparser import unparse_with_fallbacks


def runtests():
    # -- Exception hierarchy --

    def test_exception_hierarchy():
        assert issubclass(MacroExpansionError, Exception)
        assert issubclass(MacroApplicationError, MacroExpansionError)
        err = MacroApplicationError("test")
        assert isinstance(err, MacroExpansionError)
    test_exception_hierarchy()

    # -- Marker hierarchy --

    def test_marker_hierarchy():
        assert issubclass(MacroExpanderMarker, ASTMarker)
        assert issubclass(Done, MacroExpanderMarker)
        d = Done(ast.Constant(value=1))
        assert isinstance(d, ASTMarker)
    test_marker_hierarchy()

    # -- BaseMacroExpander.visit edge cases --

    def _make_expander(bindings=None):
        if bindings is None:
            bindings = {}
        return MacroExpander(bindings, "<test>")

    def test_visit_no_bindings():
        expander = _make_expander()
        tree = ast.parse("x = 1")
        result = expander.visit(tree)
        assert result is tree  # no-op
    test_visit_no_bindings()

    def test_visit_done_tree():
        def m(tree, **kw): return tree
        expander = _make_expander({"m": m})
        tree = Done(ast.parse("x = 1"))
        result = expander.visit(tree)
        assert result is tree  # skip Done
    test_visit_done_tree()

    def test_visit_none():
        def m(tree, **kw): return tree
        expander = _make_expander({"m": m})
        result = expander.visit(None)
        assert result is None
    test_visit_none()

    def test_visit_empty_list():
        """Visiting an empty list should return None."""
        def m(tree, **kw): return tree
        expander = _make_expander({"m": m})
        result = expander.visit([])
        assert result is None
    test_visit_empty_list()

    def test_visit_list_all_none():
        """Visiting a list where every element is None → empty after flatten → None."""
        def m(tree, **kw): return tree
        expander = _make_expander({"m": m})
        result = expander.visit([None, None])
        assert result is None
    test_visit_list_all_none()

    # -- visit_recursively / visit_once --

    def test_visit_recursively():
        counter = [0]
        def counting_macro(tree, *, syntax, **kw):
            counter[0] += 1
            return tree
        expander = _make_expander({"cm": counting_macro})
        tree = ast.parse("cm[x]")
        expander.visit_recursively(tree)
        # Should have been called at least once
        assert counter[0] >= 1
    test_visit_recursively()

    def test_visit_once():
        counter = [0]
        def counting_macro(tree, *, syntax, **kw):
            counter[0] += 1
            return tree
        expander = _make_expander({"cm": counting_macro})
        tree = ast.parse("cm[x]")
        result = expander.visit_once(tree)
        assert isinstance(result, Done)
        assert counter[0] == 1
    test_visit_once()

    # -- _recursive_mode --

    def test_recursive_mode_context():
        expander = _make_expander()
        assert expander.recursive is True
        with expander._recursive_mode(False):
            assert expander.recursive is False
        assert expander.recursive is True
    test_recursive_mode_context()

    # -- debughook --

    def test_debughook():
        hook_calls = []
        def my_hook(oldid, oldtree, newtree, macroname, macro):
            hook_calls.append((macroname, oldid))
        def identity(tree, *, syntax, **kw):
            return tree
        expander = _make_expander({"ident": identity})
        tree = ast.parse("ident[x]")
        with expander.debughook(my_hook):
            assert expander._debughook is my_hook
            expander.visit_once(tree)
        assert expander._debughook is None
        assert len(hook_calls) == 1
        assert hook_calls[0][0] == "ident"
    test_debughook()

    def test_debughook_restores_old():
        def hook_a(*a): pass
        def hook_b(*a): pass
        def identity(tree, *, syntax, **kw): return tree
        expander = _make_expander({"ident": identity})
        with expander.debughook(hook_a):
            assert expander._debughook is hook_a
            with expander.debughook(hook_b):
                assert expander._debughook is hook_b
            assert expander._debughook is hook_a
        assert expander._debughook is None
    test_debughook_restores_old()

    # -- expand: macro returning bad type --

    def test_expand_bad_return_type():
        """Macro returning a non-AST, non-iterable value should raise."""
        def bad_macro(tree, *, syntax, **kw):
            return 42  # not AST, not iterable
        expander = _make_expander({"bad": bad_macro})
        tree = ast.parse("bad[x]")
        try:
            expander.visit_recursively(tree)
        except MacroApplicationError as e:
            assert "bad" in str(e)
        else:
            assert False, "Expected MacroApplicationError"
    test_expand_bad_return_type()

    def test_expand_bad_list_elements():
        """Macro returning a list with non-AST elements should raise."""
        def bad_macro(tree, *, syntax, **kw):
            return [42, "not an AST"]
        expander = _make_expander({"bad": bad_macro})
        tree = ast.parse("bad[x]")
        try:
            expander.visit_recursively(tree)
        except MacroApplicationError as e:
            assert "bad" in str(e)
        else:
            assert False, "Expected MacroApplicationError"
    test_expand_bad_list_elements()

    # -- expand: exception in macro function → MacroApplicationError --

    def test_expand_exception_wrapping():
        """Exception raised inside a macro gets wrapped in MacroApplicationError."""
        def exploding_macro(tree, *, syntax, **kw):
            raise ValueError("boom")
        expander = _make_expander({"boom": exploding_macro})
        tree = ast.parse("boom[x]")
        try:
            expander.visit_recursively(tree)
        except MacroApplicationError as e:
            assert "boom" in str(e)
            assert isinstance(e.__cause__, ValueError)
        else:
            assert False, "Expected MacroApplicationError"
    test_expand_exception_wrapping()

    # -- expand: telescoped error messages for nested macro invocations --

    def test_expand_telescoped_errors():
        """Nested macro invocations telescope error messages."""
        # inner macro raises → gets wrapped → outer macro re-raises → telescopes
        def inner_macro(tree, *, syntax, **kw):
            raise ValueError("inner boom")

        def outer_macro(tree, *, syntax, expander, **kw):
            return expander.visit(tree)

        expander = _make_expander({"outer": outer_macro, "inner": inner_macro})
        tree = ast.parse("outer[inner[x]]")
        try:
            expander.visit_recursively(tree)
        except MacroApplicationError as e:
            msg = str(e)
            assert "outer" in msg
            assert "inner" in msg
            assert "most recent macro application last" in msg
            # The ultimate cause should be the ValueError
            cause = e.__cause__
            while isinstance(cause, MacroApplicationError) and cause.__cause__:
                cause = cause.__cause__
            assert isinstance(cause, ValueError)
        else:
            assert False, "Expected MacroApplicationError"
    test_expand_telescoped_errors()

    def test_expand_deeply_telescoped_errors():
        """Three levels of nesting — exercises hint-stripping in telescope."""
        def deepest(tree, *, syntax, **kw):
            raise ValueError("deep boom")

        def middle(tree, *, syntax, expander, **kw):
            return expander.visit(tree)

        def outermost(tree, *, syntax, expander, **kw):
            return expander.visit(tree)

        expander = _make_expander({"a": outermost, "b": middle, "c": deepest})
        tree = ast.parse("a[b[c[x]]]")
        try:
            expander.visit_recursively(tree)
        except MacroApplicationError as e:
            msg = str(e)
            # All three macro names should appear in the telescoped report
            assert "a" in msg and "b" in msg and "c" in msg
            assert "most recent macro application last" in msg
        else:
            assert False, "Expected MacroApplicationError"
    test_expand_deeply_telescoped_errors()

    # -- global_postprocess --

    def test_global_postprocess_cleans_done():
        tree = ast.parse("x = 1")
        tree.body[0] = Done(tree.body[0])
        result = global_postprocess(tree)
        # Done markers should be removed
        assert not any(isinstance(n, Done) for n in ast.walk(result))
    test_global_postprocess_cleans_done()

    # -- add_postprocessor / remove_postprocessor --

    def test_add_remove_postprocessor():
        calls = []
        def my_processor(tree):
            calls.append(True)
            return tree

        # Save and restore global state
        original = list(global_postprocessors)
        try:
            add_postprocessor(my_processor)
            assert my_processor in global_postprocessors

            # Adding again should be idempotent
            add_postprocessor(my_processor)
            assert global_postprocessors.count(my_processor) == 1

            # global_postprocess should call it
            tree = ast.parse("x = 1")
            global_postprocess(tree)
            assert len(calls) == 1

            # Remove it
            remove_postprocessor(my_processor)
            assert my_processor not in global_postprocessors

            # Removing again should be a no-op
            remove_postprocessor(my_processor)
        finally:
            global_postprocessors[:] = original
    test_add_remove_postprocessor()

    # -- isbound --

    def test_isbound():
        def m(tree, **kw): return tree
        expander = _make_expander({"m": m})
        assert expander.isbound("m") is m
        assert expander.isbound("nonexistent") is False
    test_isbound()

    def test_isbound_global():
        """Global bindings are visible through isbound."""
        def global_m(tree, **kw): return tree
        original = dict(global_bindings)
        try:
            global_bindings["global_m"] = global_m
            expander = _make_expander()
            assert expander.isbound("global_m") is global_m
            assert expander.isbound("global_m", global_only=True) is global_m
            # Local bindings not visible with global_only
            def local_m(tree, **kw): return tree
            expander2 = _make_expander({"local_m": local_m})
            assert expander2.isbound("local_m") is local_m
            assert expander2.isbound("local_m", global_only=True) is False
        finally:
            global_bindings.clear()
            global_bindings.update(original)
    test_isbound_global()

    # -- _visit_expansion --

    def test_visit_expansion_none():
        """_visit_expansion with None returns None."""
        expander = _make_expander()
        result = expander._visit_expansion(None, ast.parse("x = 1"))
        assert result is None
    test_visit_expansion_none()


if __name__ == '__main__':
    runtests()
