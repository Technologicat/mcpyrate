# -*- coding: utf-8 -*-

import ast

from ..quotes import macros, q  # noqa: F401

from ..compiler import temporary_module, run
from ..markers import ASTMarker
from ..splicing import splice_expression, splice_statements, splice_dialect


def runtests():
    # -- splice_expression edge cases (pure AST, no quasiquotes) --

    def test_splice_expression_empty_template():
        """Empty template returns expr itself."""
        expr = ast.parse("x", mode="eval").body
        result = splice_expression(expr, [])
        assert result is expr
    test_splice_expression_empty_template()

    def test_splice_expression_marker():
        """Splice an ASTMarker wrapping an expression."""
        inner = ast.parse("x", mode="eval").body
        marker = ASTMarker(inner)
        template = ast.parse("f(__paste_here__)", mode="eval").body
        result = splice_expression(marker, template)
        assert result.args[0] is marker
    test_splice_expression_marker()

    def test_splice_expression_bad_expr():
        """Non-expression raises TypeError."""
        stmt = ast.parse("x = 1").body[0]
        template = ast.parse("f(__paste_here__)", mode="eval").body
        try:
            splice_expression(stmt, template)
        except TypeError as e:
            assert "expression" in str(e).lower()
        else:
            assert False, "Expected TypeError"
    test_splice_expression_bad_expr()

    def test_splice_expression_bad_template():
        """Non-AST/list template raises TypeError."""
        expr = ast.parse("x", mode="eval").body
        try:
            splice_expression(expr, "not an AST")
        except TypeError as e:
            assert "template" in str(e).lower()
        else:
            assert False, "Expected TypeError"
    test_splice_expression_bad_template()

    # -- splice_statements edge cases --

    def test_splice_statements_single_ast_body():
        """Body as single AST node gets wrapped in list."""
        body = ast.parse("x = 1").body[0]
        template = ast.parse("__paste_here__").body
        result = splice_statements(body, template)
        assert isinstance(result, list)
    test_splice_statements_single_ast_body()

    def test_splice_statements_single_ast_template():
        """Template as single AST node gets wrapped in list."""
        body = ast.parse("x = 1").body
        template = ast.parse("__paste_here__").body[0]
        result = splice_statements(body, template)
        assert isinstance(result, list)
    test_splice_statements_single_ast_template()

    def test_splice_statements_empty_body():
        """Empty body raises ValueError."""
        try:
            splice_statements([], ast.parse("__paste_here__").body)
        except ValueError as e:
            assert "at least one" in str(e)
        else:
            assert False, "Expected ValueError"
    test_splice_statements_empty_body()

    def test_splice_statements_empty_template():
        """Empty template returns body."""
        body = ast.parse("x = 1").body
        result = splice_statements(body, [])
        assert result is body
    test_splice_statements_empty_template()

    # -- splice_dialect edge cases --

    def test_splice_dialect_single_ast():
        """Body/template as single AST node."""
        body = ast.parse("x = 1").body[0]
        template = ast.parse("__paste_here__").body[0]
        result = splice_dialect(body, template)
        assert isinstance(result, list)
    test_splice_dialect_single_ast()

    def test_splice_dialect_empty_body():
        """Empty body raises ValueError."""
        try:
            splice_dialect([], ast.parse("__paste_here__").body)
        except ValueError as e:
            assert "at least one" in str(e)
        else:
            assert False, "Expected ValueError"
    test_splice_dialect_empty_body()

    def test_splice_dialect_empty_template():
        """Empty template returns body."""
        body = ast.parse("x = 1").body
        result = splice_dialect(body, [])
        assert result is body
    test_splice_dialect_empty_template()

    def test_splice_dialect_with_lineno():
        """Template location info from explicit lineno/col_offset."""
        body = ast.parse("x = 1").body
        template = ast.parse("y = 2\n__paste_here__").body
        result = splice_dialect(body, template, lineno=10, col_offset=0)
        assert isinstance(result, list)
    test_splice_dialect_with_lineno()

    def test_splice_dialect_docstrings():
        """Both body and template have docstrings → concatenated."""
        body = ast.parse('"User module."\nx = 1').body
        template = ast.parse('"Template module."\n__paste_here__').body
        result = splice_dialect(body, template)
        first = result[0]
        assert isinstance(first, ast.Expr)
        doc = first.value.value
        assert "User module." in doc
        assert "Template module." in doc
    test_splice_dialect_docstrings()

    def test_splice_dialect_future_imports():
        """Future imports gathered at the top."""
        body = ast.parse("from __future__ import annotations\nx = 1").body
        template = ast.parse("__paste_here__").body
        result = splice_dialect(body, template)
        first_import = next((s for s in result if isinstance(s, ast.ImportFrom)), None)
        assert first_import is not None
        assert first_import.module == "__future__"
    test_splice_dialect_future_imports()

    def test_splice_dialect_magic_all():
        """__all__ from body is preserved."""
        body = ast.parse("__all__ = ['x']\nx = 1").body
        template = ast.parse("__paste_here__").body
        result = splice_dialect(body, template)
        all_assigns = [s for s in result if isinstance(s, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "__all__"
                               for t in s.targets)]
        assert len(all_assigns) == 1
    test_splice_dialect_magic_all()

    # -- splice_expression/statements with quasiquotes --

    def test_splice_expression_1():
        with q as quoted:
            a = __paste_here__  # noqa: F821, F841; `a` used in surrounding context; `__paste_here__` is a marker
        splice_expression(q[42], quoted)
        with temporary_module() as module:
            run(quoted, module)
            assert module.a == 42
    test_splice_expression_1()

    def test_splice_expression_2():
        with q as quoted:
            results = []
            def write_result(x):
                results.append(x)
            # Here the `__paste_here__` appears inside the insidious, invisible `ast.Expr` node.
            # `splice_expression` should only replace the expression inside it.
            __paste_here__  # noqa: F821, marker.
        splice_expression(q[write_result(42)], quoted)
        with temporary_module() as module:
            run(quoted, module)
            assert len(module.results) == 1 and module.results[0] == 42
    test_splice_expression_2()

    def test_splice_expression_multiple():
        with q as quoted:
            a = __paste_here__ + __paste_here__  # noqa: F821, F841
        splice_expression(q[21], quoted)
        with temporary_module() as module:
            run(quoted, module)
            assert module.a == 42
    test_splice_expression_multiple()

    def test_splice_statements():
        with q as code:
            # `splice_statements` should replace the invisible `ast.Expr` node, too.
            __paste_here__  # noqa: F821
            a += 1  # noqa: F821, `a` will be defined once the replacement is pasted in.
        with q as replacement:
            a = 41  # noqa: F841, `a` will be used inside `template` once pasted.
        splice_statements(replacement, code)
        with temporary_module() as module:
            run(code, module)
            assert module.a == 42
    test_splice_statements()

    def test_splice_statements_multiple():
        with q as code:
            a = 40  # noqa: F841, `a` is used after the paste completes.
            __paste_here__  # noqa: F821, marker
            __paste_here__  # noqa: F821, marker
        with q as replacement:
            a += 1
        splice_statements(replacement, code)
        with temporary_module() as module:
            run(code, module)
            assert module.a == 42
    test_splice_statements_multiple()

    # splice_dialect is system-tested by the dialect tests and by
    # `unpythonic.dialects` in our sister project.

    print("    test_splicing: all passed")

if __name__ == '__main__':
    runtests()
