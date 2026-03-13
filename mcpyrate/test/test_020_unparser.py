# -*- coding: utf-8 -*-
"""Tests for the unparser — one test per AST node type family.

This is essentially a grammar exhaustion test. Each handler in unparser.py
corresponds to an AST node type; we feed it source code that exercises each
one and verify round-tripping through parse→unparse→parse.
"""

import ast
import sys

from ..unparser import unparse, unparse_with_fallbacks, UnparserError
from ..markers import ASTMarker


def _roundtrip(source, mode="exec"):
    """Parse source, unparse, re-parse, unparse again.

    The first unparse normalizes formatting; the second should be
    identical — that's our stability invariant.

    Return (unparsed_code, re_parsed_tree) where unparsed_code is
    the stabilized (second) unparse.
    """
    tree = ast.parse(source, mode=mode)
    code1 = unparse(tree)
    tree2 = ast.parse(code1, mode=mode)
    code2 = unparse(tree2)
    assert code1 == code2, f"unparse not stable:\n  first:  {code1!r}\n  second: {code2!r}"
    return code2, tree2


def _unparse(source, mode="exec", **kwargs):
    """Parse source and unparse. Return the unparsed code string."""
    tree = ast.parse(source, mode=mode)
    return unparse(tree, **kwargs)


def runtests():
    # -- Top-level nodes --

    def test_module():
        code, _ = _roundtrip("x = 1")
        assert "x" in code
    test_module()

    def test_interactive():
        tree = ast.parse("x = 1", mode="single")
        code = unparse(tree)
        assert "x" in code
    test_interactive()

    def test_expression():
        code, _ = _roundtrip("42", mode="eval")
        assert "42" in code
    test_expression()

    def test_expression_debug():
        tree = ast.parse("42", mode="eval")
        code = unparse(tree, debug=True)
        assert "$Expression" in code
        assert "42" in code
    test_expression_debug()

    # -- Statements --

    def test_expr_stmt():
        code = _unparse("print('hello')")
        assert "print" in code
    test_expr_stmt()

    def test_expr_debug():
        code = _unparse("42", debug=True)
        assert "$Expr" in code
    test_expr_debug()

    def test_import():
        code, _ = _roundtrip("import os")
        assert "import" in code and "os" in code
    test_import()

    def test_import_from():
        code, _ = _roundtrip("from os import path")
        assert "from" in code and "os" in code and "path" in code
    test_import_from()

    def test_import_as():
        code, _ = _roundtrip("import os as operating_system")
        assert "as" in code and "operating_system" in code
    test_import_as()

    def test_assign():
        code, _ = _roundtrip("x = 1")
        assert "x" in code and "1" in code
    test_assign()

    def test_ann_assign():
        code, _ = _roundtrip("x: int = 1")
        assert "int" in code
    test_ann_assign()

    def test_ann_assign_complex():
        code, _ = _roundtrip("(x): int")
        assert "int" in code
    test_ann_assign_complex()

    def test_aug_assign():
        code, _ = _roundtrip("x = 0\nx += 1")
        assert "+=" in code
    test_aug_assign()

    def test_return():
        code, _ = _roundtrip("def f():\n return 42")
        assert "return" in code
    test_return()

    def test_pass():
        code, _ = _roundtrip("pass")
        assert "pass" in code
    test_pass()

    def test_break():
        code, _ = _roundtrip("while True:\n break")
        assert "break" in code
    test_break()

    def test_continue():
        code, _ = _roundtrip("while True:\n continue")
        assert "continue" in code
    test_continue()

    def test_delete():
        code, _ = _roundtrip("del x")
        assert "del" in code
    test_delete()

    def test_assert():
        code, _ = _roundtrip("assert True")
        assert "assert" in code
    test_assert()

    def test_assert_with_msg():
        code, _ = _roundtrip("assert True, 'msg'")
        assert "msg" in code
    test_assert_with_msg()

    def test_global():
        code, _ = _roundtrip("def f():\n global x")
        assert "global" in code
    test_global()

    def test_nonlocal():
        code, _ = _roundtrip("def f():\n x = 1\n def g():\n  nonlocal x")
        assert "nonlocal" in code
    test_nonlocal()

    def test_raise():
        code, _ = _roundtrip("raise")
        assert "raise" in code
    test_raise()

    def test_raise_with_cause():
        code, _ = _roundtrip("raise ValueError('x') from RuntimeError('y')")
        assert "from" in code
    test_raise_with_cause()

    # -- Control flow --

    def test_if_elif_else():
        source = "if x:\n pass\nelif y:\n pass\nelse:\n pass"
        code, _ = _roundtrip(source)
        assert "if" in code and "elif" in code and "else" in code
    test_if_elif_else()

    def test_while_else():
        source = "while True:\n pass\nelse:\n pass"
        code, _ = _roundtrip(source)
        assert "while" in code and "else" in code
    test_while_else()

    def test_for():
        code, _ = _roundtrip("for x in y:\n pass")
        assert "for" in code and "in" in code
    test_for()

    def test_for_else():
        source = "for x in y:\n pass\nelse:\n pass"
        code, _ = _roundtrip(source)
        assert "else" in code
    test_for_else()

    def test_async_for():
        source = "async def f():\n async for x in y:\n  pass"
        code, _ = _roundtrip(source)
        assert "async for" in code
    test_async_for()

    def test_with():
        code, _ = _roundtrip("with open('f') as f:\n pass")
        assert "with" in code and "as" in code
    test_with()

    def test_async_with():
        source = "async def f():\n async with ctx() as c:\n  pass"
        code, _ = _roundtrip(source)
        assert "async with" in code
    test_async_with()

    # -- Try / Except --

    def test_try_except():
        source = "try:\n pass\nexcept Exception as e:\n pass"
        code, _ = _roundtrip(source)
        assert "try" in code and "except" in code and "as" in code
    test_try_except()

    def test_try_except_else_finally():
        source = "try:\n pass\nexcept:\n pass\nelse:\n pass\nfinally:\n pass"
        code, _ = _roundtrip(source)
        assert "else" in code and "finally" in code
    test_try_except_else_finally()

    if sys.version_info >= (3, 11):
        def test_try_star():
            source = "try:\n pass\nexcept* ValueError as e:\n pass"
            code, _ = _roundtrip(source)
            assert "except*" in code
        test_try_star()

    # -- Functions --

    def test_function_def():
        code, _ = _roundtrip("def f(x, y=1):\n pass")
        assert "def" in code
    test_function_def()

    def test_function_return_annotation():
        code, _ = _roundtrip("def f() -> int:\n pass")
        assert "->" in code
    test_function_return_annotation()

    def test_async_function_def():
        code, _ = _roundtrip("async def f():\n pass")
        assert "async def" in code
    test_async_function_def()

    def test_function_decorators():
        code, _ = _roundtrip("@deco\ndef f():\n pass")
        assert "@" in code and "deco" in code
    test_function_decorators()

    def test_function_decorators_colored():
        tree = ast.parse("@deco\ndef f():\n pass")
        code = unparse(tree, color=True)
        assert "@" in code and "deco" in code
        assert "\x1b[" in code
    test_function_decorators_colored()

    def test_function_posonly_args():
        code, _ = _roundtrip("def f(x, /, y):\n pass")
        assert "/" in code
    test_function_posonly_args()

    def test_function_varargs():
        code, _ = _roundtrip("def f(*args):\n pass")
        assert "*args" in code
    test_function_varargs()

    def test_function_varargs_annotated():
        code, _ = _roundtrip("def f(*args: int):\n pass")
        assert "*args" in code and "int" in code
    test_function_varargs_annotated()

    def test_function_kwonly_args():
        code, _ = _roundtrip("def f(*, x, y=1):\n pass")
        assert "x" in code
    test_function_kwonly_args()

    def test_function_kwargs():
        code, _ = _roundtrip("def f(**kw):\n pass")
        assert "**kw" in code
    test_function_kwargs()

    def test_function_kwargs_annotated():
        code, _ = _roundtrip("def f(**kw: int):\n pass")
        assert "**kw" in code and "int" in code
    test_function_kwargs_annotated()

    def test_function_arg_annotation():
        code, _ = _roundtrip("def f(x: int):\n pass")
        assert "int" in code
    test_function_arg_annotation()

    # -- Classes --

    def test_class_def():
        code, _ = _roundtrip("class C:\n pass")
        assert "class" in code
    test_class_def()

    def test_class_bases():
        code, _ = _roundtrip("class C(A, B):\n pass")
        assert "A" in code and "B" in code
    test_class_bases()

    def test_class_keywords():
        code, _ = _roundtrip("class C(metaclass=M):\n pass")
        assert "metaclass" in code
    test_class_keywords()

    def test_class_decorators():
        code, _ = _roundtrip("@deco\nclass C:\n pass")
        assert "@" in code and "deco" in code
    test_class_decorators()

    def test_class_decorators_colored():
        tree = ast.parse("@deco\nclass C:\n pass")
        code = unparse(tree, color=True)
        assert "\x1b[" in code
    test_class_decorators_colored()

    # -- Expressions --

    def test_lambda():
        code, _ = _roundtrip("f = lambda x, y: x + y")
        assert "lambda" in code
    test_lambda()

    def test_lambda_no_args():
        code, _ = _roundtrip("f = lambda: 42")
        assert "lambda" in code
    test_lambda_no_args()

    def test_named_expr():
        code, _ = _roundtrip("if (x := 10):\n pass")
        assert ":=" in code
    test_named_expr()

    def test_await():
        source = "async def f():\n await g()"
        code, _ = _roundtrip(source)
        assert "await" in code
    test_await()

    def test_yield():
        source = "def f():\n yield 1"
        code, _ = _roundtrip(source)
        assert "yield" in code
    test_yield()

    def test_yield_from():
        source = "def f():\n yield from g()"
        code, _ = _roundtrip(source)
        assert "yield from" in code
    test_yield_from()

    # -- Literals and constants --

    def test_constant_int():
        code = _unparse("42", mode="eval")
        assert "42" in code
    test_constant_int()

    def test_constant_float():
        code = _unparse("3.14", mode="eval")
        assert "3.14" in code
    test_constant_float()

    def test_constant_complex():
        code = _unparse("1+2j", mode="eval")
        assert "2j" in code
    test_constant_complex()

    def test_constant_string():
        code = _unparse("'hello'", mode="eval")
        assert "hello" in code
    test_constant_string()

    def test_constant_bytes():
        code = _unparse("b'hello'", mode="eval")
        assert "hello" in code
    test_constant_bytes()

    def test_constant_true():
        code = _unparse("True", mode="eval")
        assert "True" in code
    test_constant_true()

    def test_constant_none():
        code = _unparse("None", mode="eval")
        assert "None" in code
    test_constant_none()

    def test_constant_ellipsis():
        code = _unparse("...", mode="eval")
        assert "..." in code
    test_constant_ellipsis()

    def test_constant_colored():
        tree = ast.parse("42", mode="eval")
        code = unparse(tree, color=True)
        assert "\x1b[" in code
    test_constant_colored()

    # -- Container expressions --

    def test_list():
        code, _ = _roundtrip("x = [1, 2, 3]")
        assert "[" in code
    test_list()

    def test_tuple():
        code, _ = _roundtrip("x = (1, 2, 3)")
        assert "1" in code and "2" in code
    test_tuple()

    def test_tuple_single():
        code, _ = _roundtrip("x = (1,)")
        assert "," in code  # trailing comma for single-element tuple
    test_tuple_single()

    def test_set():
        code, _ = _roundtrip("x = {1, 2, 3}")
        assert "{" in code
    test_set()

    def test_dict():
        code, _ = _roundtrip("x = {'a': 1, 'b': 2}")
        assert ":" in code
    test_dict()

    # -- Comprehensions --

    def test_list_comp():
        code, _ = _roundtrip("x = [i for i in range(10)]")
        assert "for" in code and "in" in code
    test_list_comp()

    def test_generator_exp():
        code, _ = _roundtrip("x = sum(i for i in range(10))")
        assert "for" in code
    test_generator_exp()

    def test_set_comp():
        code, _ = _roundtrip("x = {i for i in range(10)}")
        assert "for" in code
    test_set_comp()

    def test_dict_comp():
        code, _ = _roundtrip("x = {k: v for k, v in items}")
        assert "for" in code and ":" in code
    test_dict_comp()

    def test_comp_with_if():
        code, _ = _roundtrip("x = [i for i in range(10) if i > 5]")
        assert "if" in code
    test_comp_with_if()

    def test_async_comp():
        source = "async def f():\n x = [i async for i in aiter]"
        code, _ = _roundtrip(source)
        assert "async for" in code
    test_async_comp()

    # -- Operators --

    def test_unary_op_not():
        code, _ = _roundtrip("x = not True")
        assert "not" in code
    test_unary_op_not()

    def test_unary_op_symbols():
        code, _ = _roundtrip("x = -1\ny = +1\nz = ~1")
        assert "-" in code and "+" in code and "~" in code
    test_unary_op_symbols()

    def test_bin_op():
        code, _ = _roundtrip("x = 1 + 2 * 3")
        assert "+" in code and "*" in code
    test_bin_op()

    def test_compare():
        code, _ = _roundtrip("x = 1 < 2 <= 3")
        assert "<" in code and "<=" in code
    test_compare()

    def test_compare_keyword_ops():
        code, _ = _roundtrip("x = a is b\ny = a is not b\nz = a in b\nw = a not in b")
        assert "is" in code and "is not" in code
        assert " in " in code and "not in" in code
    test_compare_keyword_ops()

    def test_bool_op():
        code, _ = _roundtrip("x = a and b or c")
        assert "and" in code and "or" in code
    test_bool_op()

    def test_if_exp():
        code, _ = _roundtrip("x = a if cond else b")
        assert "if" in code and "else" in code
    test_if_exp()

    # -- Attribute, Call, Subscript --

    def test_attribute():
        code, _ = _roundtrip("x = obj.attr")
        assert ".attr" in code
    test_attribute()

    def test_attribute_int_literal():
        """3.__abs__() needs special handling (space before dot)."""
        code = _unparse("(3).__abs__()", mode="eval")
        assert "abs" in code
    test_attribute_int_literal()

    def test_call():
        code, _ = _roundtrip("f(a, b, c=1, **kw)")
        assert "f(" in code and "**kw" in code
    test_call()

    def test_subscript():
        code, _ = _roundtrip("x = a[1]")
        assert "[" in code
    test_subscript()

    def test_subscript_tuple():
        code, _ = _roundtrip("x = a[1, 2]")
        assert "1" in code and "2" in code
    test_subscript_tuple()

    def test_starred():
        code, _ = _roundtrip("a, *b = [1, 2, 3]")
        assert "*" in code
    test_starred()

    # -- Slices --

    def test_slice_full():
        code, _ = _roundtrip("x = a[1:2:3]")
        assert ":" in code
    test_slice_full()

    def test_slice_partial():
        code, _ = _roundtrip("x = a[:5]")
        assert ":" in code
    test_slice_partial()

    # -- F-strings --

    def test_fstring():
        code, _ = _roundtrip("x = f'hello {name}'")
        assert "f'" in code
    test_fstring()

    def test_fstring_conversion():
        code, _ = _roundtrip("x = f'{val!r}'")
        assert "!r" in code
    test_fstring_conversion()

    def test_fstring_conversion_s():
        code, _ = _roundtrip("x = f'{val!s}'")
        assert "!s" in code
    test_fstring_conversion_s()

    def test_fstring_conversion_a():
        code, _ = _roundtrip("x = f'{val!a}'")
        assert "!a" in code
    test_fstring_conversion_a()

    def test_fstring_format_spec():
        code, _ = _roundtrip("x = f'{val:.2f}'")
        assert ":" in code
    test_fstring_format_spec()

    def test_fstring_standalone_formatted_value():
        """A FormattedValue outside a JoinedStr."""
        tree = ast.parse("f'{x}'", mode="eval")
        code = unparse(tree)
        assert "x" in code
    test_fstring_standalone_formatted_value()

    # -- Name coloring --

    def test_name_builtin_exception():
        code = _unparse("ValueError", mode="eval", color=True)
        assert "\x1b[" in code and "ValueError" in code
    test_name_builtin_exception()

    def test_name_builtin_other():
        code = _unparse("print", mode="eval", color=True)
        assert "\x1b[" in code and "print" in code
    test_name_builtin_other()

    # -- match/case (Python 3.10+) --

    def test_match_basic():
        source = "match x:\n case 1:\n  pass\n case _:\n  pass"
        code, _ = _roundtrip(source)
        assert "match" in code and "case" in code
    test_match_basic()

    def test_match_value():
        source = "match x:\n case 42:\n  pass"
        code, _ = _roundtrip(source)
        assert "42" in code
    test_match_value()

    def test_match_singleton():
        source = "match x:\n case None:\n  pass\n case True:\n  pass"
        code, _ = _roundtrip(source)
        assert "None" in code and "True" in code
    test_match_singleton()

    def test_match_sequence():
        source = "match x:\n case [1, 2, 3]:\n  pass"
        code, _ = _roundtrip(source)
        assert "[" in code
    test_match_sequence()

    def test_match_star():
        source = "match x:\n case [1, *rest]:\n  pass"
        code, _ = _roundtrip(source)
        assert "*rest" in code
    test_match_star()

    def test_match_star_wildcard():
        source = "match x:\n case [1, *_]:\n  pass"
        code, _ = _roundtrip(source)
        assert "*" in code
    test_match_star_wildcard()

    def test_match_mapping():
        source = "match x:\n case {'key': val, **rest}:\n  pass"
        code, _ = _roundtrip(source)
        assert "key" in code and "**rest" in code
    test_match_mapping()

    def test_match_class():
        source = "match x:\n case Point(x=1, y=2):\n  pass"
        code, _ = _roundtrip(source)
        assert "Point" in code
    test_match_class()

    def test_match_class_positional():
        source = "match x:\n case Point(1, 2):\n  pass"
        code, _ = _roundtrip(source)
        assert "Point" in code
    test_match_class_positional()

    def test_match_class_mixed():
        source = "match x:\n case Point(1, y=2):\n  pass"
        code, _ = _roundtrip(source)
        assert "Point" in code
    test_match_class_mixed()

    def test_match_as():
        source = "match x:\n case 1 as y:\n  pass"
        code, _ = _roundtrip(source)
        assert "as" in code
    test_match_as()

    def test_match_capture():
        source = "match x:\n case name:\n  pass"
        code, _ = _roundtrip(source)
        assert "name" in code
    test_match_capture()

    def test_match_or():
        source = "match x:\n case 1 | 2 | 3:\n  pass"
        code, _ = _roundtrip(source)
        assert "|" in code
    test_match_or()

    def test_match_or_with_guard():
        source = "match x:\n case 1 | 2 if x > 0:\n  pass"
        code, _ = _roundtrip(source)
        assert "|" in code and "if" in code
    test_match_or_with_guard()

    def test_match_or_as():
        source = "match x:\n case (1 | 2) as y:\n  pass"
        code, _ = _roundtrip(source)
        assert "|" in code and "as" in code
    test_match_or_as()

    def test_match_guard():
        source = "match x:\n case y if y > 0:\n  pass"
        code, _ = _roundtrip(source)
        assert "if" in code
    test_match_guard()

    # -- type statement (Python 3.12+) --

    if sys.version_info >= (3, 12):
        def test_type_alias():
            source = "type Vector = list[float]"
            code, _ = _roundtrip(source)
            assert "type" in code and "Vector" in code
        test_type_alias()

        def test_type_alias_params():
            source = "type Vector[T] = list[T]"
            code, _ = _roundtrip(source)
            assert "[T]" in code or "T" in code
        test_type_alias_params()

        def test_type_var_bound():
            source = "type Num[T: int] = T"
            code, _ = _roundtrip(source)
            assert "int" in code
        test_type_var_bound()

        def test_param_spec():
            source = "type Callback[**P] = Callable[P, None]"
            code, _ = _roundtrip(source)
            assert "**P" in code
        test_param_spec()

        def test_type_var_tuple():
            source = "type Shape[*Ts] = tuple[*Ts]"
            code, _ = _roundtrip(source)
            assert "*Ts" in code
        test_type_var_tuple()

    # -- Debug mode --

    def test_debug_module():
        code = _unparse("x = 1", debug=True)
        assert "$Module" in code
    test_debug_module()

    def test_debug_invisible_nodes():
        code = _unparse("x = 1", debug=True)
        assert "$Expr" not in code  # x = 1 is an Assign, not an Expr
    test_debug_invisible_nodes()

    def test_debug_lineno():
        code = _unparse("x = 1", debug=True)
        assert "L" in code
    test_debug_lineno()

    # -- Color mode --

    def test_color_basic():
        code = _unparse("x = 1", color=True)
        assert "\x1b[" in code
    test_color_basic()

    def test_color_keywords():
        code = _unparse("def f():\n return 42", color=True)
        assert "\x1b[" in code and "def" in code
    test_color_keywords()

    # -- ASTMarker rendering --

    def test_astmarker_expr():
        """ASTMarker wrapping an expression."""
        inner = ast.Constant(value=42)
        marker = ASTMarker(body=inner)
        code = unparse(marker, debug=True)
        assert "$ASTMarker" in code
        assert "42" in code
    test_astmarker_expr()

    def test_astmarker_stmt():
        """ASTMarker wrapping a statement."""
        inner = ast.parse("x = 1").body[0]
        marker = ASTMarker(body=inner)
        code = unparse(marker, debug=True)
        assert "$ASTMarker" in code
    test_astmarker_stmt()

    def test_astmarker_suite():
        """ASTMarker wrapping a statement suite (list)."""
        suite = ast.parse("x = 1\ny = 2").body
        marker = ASTMarker(body=suite)
        code = unparse(marker, debug=True)
        assert "$ASTMarker" in code
    test_astmarker_suite()

    def test_astmarker_multi_field():
        """ASTMarker subclass with multiple fields (expression mode)."""
        class Tagged(ASTMarker):
            _fields = ("body", "tag")
            def __init__(self, body, tag):
                super().__init__(body=body)
                self.tag = tag
        marker = Tagged(body=ast.Constant(value=1), tag="hello")
        code = unparse(marker, debug=True)
        assert "$ASTMarker" in code
        assert "hello" in code
    test_astmarker_multi_field()

    def test_astmarker_multi_field_stmt():
        """Multi-field ASTMarker wrapping a statement."""
        class Tagged(ASTMarker):
            _fields = ("body", "tag")
            def __init__(self, body, tag):
                super().__init__(body=body)
                self.tag = tag
        stmt = ast.parse("x = 1").body[0]
        marker = Tagged(body=stmt, tag="meta")
        code = unparse(marker, debug=True)
        assert "meta" in code
    test_astmarker_multi_field_stmt()

    # -- Error handling --

    def test_unparse_error():
        """Unparsing a completely unknown node type should raise."""
        class FakeNode(ast.AST):
            _fields = ()
        try:
            unparse(FakeNode())
        except UnparserError:
            pass
        else:
            assert False, "should raise UnparserError"
    test_unparse_error()

    def test_unparse_with_fallbacks_error():
        """unparse_with_fallbacks returns error string instead of raising."""
        class FakeNode(ast.AST):
            _fields = ()
        result = unparse_with_fallbacks(FakeNode())
        assert "unparse failed" in result or "Internal error" in result
    test_unparse_with_fallbacks_error()

    def test_unparse_with_fallbacks_non_ast():
        """Totally non-AST input goes through the repr fallback chain."""
        result = unparse_with_fallbacks("not an AST at all")
        assert "unparse failed" in result.lower() or "internal error" in result.lower() or "str" in result.lower()
    test_unparse_with_fallbacks_non_ast()

    # -- Statement suite (list) input --

    def test_unparse_list():
        stmts = ast.parse("x = 1\ny = 2").body
        code = unparse(stmts)
        assert "x" in code and "y" in code
    test_unparse_list()

    # -- Keyword argument in call --

    def test_keyword_double_star():
        code, _ = _roundtrip("f(**kw)")
        assert "**" in code
    test_keyword_double_star()

    # -- Edge cases we can hit on any Python version --

    def test_class_keyword_comma():
        """Class with both bases and keyword args."""
        code, _ = _roundtrip("class C(A, metaclass=M):\n pass")
        assert "A" in code and "metaclass" in code
    test_class_keyword_comma()

    def test_lambda_posonly():
        """Lambda with positional-only args (Python 3.8+)."""
        # Construct manually — `lambda x, /: x` is a syntax error in source,
        # but the AST supports it.
        tree = ast.parse("f = lambda x: x")
        lam = tree.body[0].value
        lam.args.posonlyargs = lam.args.args[:]
        lam.args.args = []
        code = unparse(tree)
        assert "lambda" in code and "/" in code
    test_lambda_posonly()

    def test_function_kwonly_first():
        """Keyword-only args with no regular args (bare *)."""
        code, _ = _roundtrip("def f(*, x):\n pass")
        assert "*" in code and "x" in code
    test_function_kwonly_first()

    def test_standalone_formatted_value():
        """A standalone FormattedValue node (outside JoinedStr)."""
        # Construct manually — this doesn't arise from source directly.
        fv = ast.FormattedValue(value=ast.Name(id="x"), conversion=-1, format_spec=None)
        code = unparse(fv)
        assert "x" in code
    test_standalone_formatted_value()

    def test_unparse_with_fallbacks_internal_error():
        """Trigger the internal error catch-all in unparse_with_fallbacks."""
        # Monkey-patch unparse to raise a non-UnparserError
        import mcpyrate.unparser as _unparser_mod
        _orig = _unparser_mod.unparse
        def _boom(*a, **kw):
            raise RuntimeError("synthetic boom")
        _unparser_mod.unparse = _boom
        try:
            result = unparse_with_fallbacks(ast.parse("x = 1"))
            assert "Internal error" in result
            assert "synthetic boom" in result
        finally:
            _unparser_mod.unparse = _orig
    test_unparse_with_fallbacks_internal_error()


if __name__ == '__main__':
    runtests()
