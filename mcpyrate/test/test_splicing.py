# -*- coding: utf-8 -*-

from ..quotes import macros, q  # noqa: F401

from ..compiler import temporary_module, run
from ..splicing import splice_expression, splice_statements


def runtests():
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

    # TODO: Test splice_dialect (or maybe test it along with the dialect system, technically it's part of that)
    # TODO: For now, `unpythonic.dialects` in our sister project `unpythonic` system-tests it.

if __name__ == '__main__':
    runtests()
