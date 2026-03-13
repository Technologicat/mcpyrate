# -*- coding: utf-8 -*-
"""Tests for multi-phase compilation utilities."""

import ast

from ..multiphase import (iswithphase, extract_phase, phase, step_phases,
                          ismultiphase, detect_highest_phase, isdebug)


def _make_with_phase(n):
    """Build a `with phase[n]: pass` AST node."""
    return ast.With(
        items=[ast.withitem(
            context_expr=ast.Subscript(
                value=ast.Name(id="phase"),
                slice=ast.Constant(value=n)),
            optional_vars=None)],
        body=[ast.Pass()])


def _make_module(*stmts):
    """Build an ast.Module with the given statements."""
    return ast.Module(body=list(stmts), type_ignores=[])


def runtests():
    # -- iswithphase: acceptance --

    def test_iswithphase_valid():
        stmt = _make_with_phase(1)
        assert iswithphase(stmt, filename="<test>") == 1
    test_iswithphase_valid()

    def test_iswithphase_higher_phase():
        stmt = _make_with_phase(3)
        assert iswithphase(stmt, filename="<test>") == 3
    test_iswithphase_higher_phase()

    # -- iswithphase: rejection branches --

    def test_iswithphase_not_with():
        assert iswithphase(ast.Pass(), filename="<test>") is False
    test_iswithphase_not_with()

    def test_iswithphase_multiple_items():
        stmt = ast.With(
            items=[ast.withitem(context_expr=ast.Name(id="a"), optional_vars=None),
                   ast.withitem(context_expr=ast.Name(id="b"), optional_vars=None)],
            body=[ast.Pass()])
        assert iswithphase(stmt, filename="<test>") is False
    test_iswithphase_multiple_items()

    def test_iswithphase_has_as_part():
        stmt = ast.With(
            items=[ast.withitem(
                context_expr=ast.Subscript(
                    value=ast.Name(id="phase"),
                    slice=ast.Constant(value=1)),
                optional_vars=ast.Name(id="result"))],
            body=[ast.Pass()])
        assert iswithphase(stmt, filename="<test>") is False
    test_iswithphase_has_as_part()

    def test_iswithphase_not_subscript():
        stmt = ast.With(
            items=[ast.withitem(
                context_expr=ast.Name(id="phase"),
                optional_vars=None)],
            body=[ast.Pass()])
        assert iswithphase(stmt, filename="<test>") is False
    test_iswithphase_not_subscript()

    def test_iswithphase_wrong_name():
        stmt = ast.With(
            items=[ast.withitem(
                context_expr=ast.Subscript(
                    value=ast.Name(id="notphase"),
                    slice=ast.Constant(value=1)),
                optional_vars=None)],
            body=[ast.Pass()])
        assert iswithphase(stmt, filename="<test>") is False
    test_iswithphase_wrong_name()

    def test_iswithphase_no_args():
        # phase without subscript arg → destructure_candidate returns no args
        stmt = ast.With(
            items=[ast.withitem(
                context_expr=ast.Subscript(
                    value=ast.Name(id="phase"),
                    slice=ast.Tuple(elts=[ast.Constant(value=1),
                                          ast.Constant(value=2)])),
                optional_vars=None)],
            body=[ast.Pass()])
        assert iswithphase(stmt, filename="<test>") is False
    test_iswithphase_no_args()

    def test_iswithphase_non_constant_arg():
        stmt = ast.With(
            items=[ast.withitem(
                context_expr=ast.Subscript(
                    value=ast.Name(id="phase"),
                    slice=ast.Name(id="n")),
                optional_vars=None)],
            body=[ast.Pass()])
        assert iswithphase(stmt, filename="<test>") is False
    test_iswithphase_non_constant_arg()

    def test_iswithphase_non_int():
        stmt = _make_with_phase("not_an_int")
        assert iswithphase(stmt, filename="<test>") is False
    test_iswithphase_non_int()

    def test_iswithphase_zero():
        stmt = _make_with_phase(0)
        assert iswithphase(stmt, filename="<test>") is False
    test_iswithphase_zero()

    def test_iswithphase_negative():
        stmt = _make_with_phase(-1)
        assert iswithphase(stmt, filename="<test>") is False
    test_iswithphase_negative()

    # -- extract_phase --

    def test_extract_phase_bad_type():
        try:
            extract_phase(_make_module(), filename="<test>", phase="1")
        except TypeError as e:
            assert "int" in str(e)
        else:
            assert False, "should reject non-int phase"
    test_extract_phase_bad_type()

    def test_extract_phase_negative():
        try:
            extract_phase(_make_module(), filename="<test>", phase=-1)
        except ValueError as e:
            assert "positive" in str(e)
        else:
            assert False, "should reject negative phase"
    test_extract_phase_negative()

    def test_extract_phase_zero():
        """Phase 0 returns tree as-is."""
        tree = _make_module(ast.Pass())
        result = extract_phase(tree, filename="<test>", phase=0)
        assert result is tree
    test_extract_phase_zero()

    def test_extract_phase_basic():
        """Split phase-1 code from phase-0 code."""
        phase1_body = [ast.Expr(value=ast.Constant(value="phase1"))]
        phase0_stmt = ast.Expr(value=ast.Constant(value="phase0"))
        tree = _make_module(_make_with_phase(1), phase0_stmt)
        # Put body into the with-phase
        tree.body[0].body = phase1_body

        result = extract_phase(tree, filename="<test>", phase=1)
        # result should contain the phase-1 body
        assert any(isinstance(s, ast.Expr) and
                   getattr(s.value, 'value', None) == "phase1"
                   for s in result.body)
    test_extract_phase_basic()

    def test_extract_phase_lift_higher():
        """Phase > 1 should decrease the phase number by 1."""
        # Create with phase[2] containing a statement
        phase2_stmt = ast.Expr(value=ast.Constant(value="phase2"))
        with_phase_2 = _make_with_phase(2)
        with_phase_2.body = [phase2_stmt]
        # Add line numbers for the SyntaxError check
        with_phase_2.lineno = 1
        with_phase_2.col_offset = 0

        tree = _make_module(with_phase_2)
        result = extract_phase(tree, filename="<test>", phase=2)
        assert any(isinstance(s, ast.Expr) and
                   getattr(s.value, 'value', None) == "phase2"
                   for s in result.body)
        # The remaining tree should have with phase[1] (decremented)
        remaining_withs = [s for s in tree.body if iswithphase(s, filename="<test>")]
        assert len(remaining_withs) == 1
        assert iswithphase(remaining_withs[0], filename="<test>") == 1
    test_extract_phase_lift_higher()

    # -- phase macro: misplaced invocations --

    def test_phase_non_block():
        try:
            phase(ast.Name(id="x"), syntax="expr")
        except SyntaxError as e:
            assert "block macro only" in str(e)
        else:
            assert False, "should reject non-block syntax"
    test_phase_non_block()

    def test_phase_misplaced():
        try:
            phase([ast.Pass()], syntax="block")
        except SyntaxError as e:
            assert "Misplaced" in str(e)
        else:
            assert False, "should raise for misplaced phase"
    test_phase_misplaced()

    # -- step_phases: misplaced invocation --

    def test_step_phases_misplaced():
        try:
            step_phases(ast.Name(id="x"), syntax="name", expander=None)
        except SyntaxError as e:
            assert "compiler flag" in str(e)
        else:
            assert False, "should raise for misplaced step_phases"
    test_step_phases_misplaced()

    # -- ismultiphase --

    def test_ismultiphase_true():
        tree = ast.parse("from mcpyrate.multiphase import macros, phase")
        assert ismultiphase(tree) is True
    test_ismultiphase_true()

    def test_ismultiphase_false():
        tree = ast.parse("x = 1")
        assert ismultiphase(tree) is False
    test_ismultiphase_false()

    # -- isdebug --

    def test_isdebug_true():
        tree = ast.parse("from mcpyrate.debug import macros, step_phases")
        assert isdebug(tree) is True
    test_isdebug_true()

    def test_isdebug_false():
        tree = ast.parse("x = 1")
        assert isdebug(tree) is False
    test_isdebug_false()

    def test_isdebug_wrong_module():
        tree = ast.parse("from mcpyrate.quotes import macros, q")
        assert isdebug(tree) is False
    test_isdebug_wrong_module()

    # -- detect_highest_phase --

    def test_detect_highest_phase_none():
        tree = _make_module(ast.Pass())
        result = detect_highest_phase(tree, filename="<test>")
        assert not result  # False (from iswithphase) when no phases found
    test_detect_highest_phase_none()

    def test_detect_highest_phase_finds_max():
        tree = _make_module(_make_with_phase(1), ast.Pass(), _make_with_phase(3))
        assert detect_highest_phase(tree, filename="<test>") == 3
    test_detect_highest_phase_finds_max()

    print("    test_multiphase: all passed")


if __name__ == '__main__':
    runtests()
