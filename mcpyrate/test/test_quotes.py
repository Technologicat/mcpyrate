# -*- coding: utf-8 -*-

from ..metatools import (macros, expands, expand1s, expandsq, expand1sq,  # noqa: F811
                         expandr, expand1r, expandrq, expand1rq)
from ..quotes import macros, q, u, n, a, s, t, h  # noqa: F811
from .macros import (macros, test_q, test_hq,  # noqa: F401, F811
                     first, second, third)

import ast

from ..compiler import run, create_module
from ..quotes import unastify
from ..unparser import unparse


def f():
    return "f from macro use site"


def test():
    # q: quasiquote (has both expr and block modes)

    # expr mode: expression -> AST
    qx = q[x]  # noqa: F821, only quoted
    assert type(qx) is ast.Name
    assert qx.id == "x"

    # literals
    assert type(q[[1, 2, 3]]) is ast.List
    assert type(q[(1, 2, 3)]) is ast.Tuple
    assert type(q[{1, 2, 3}]) is ast.Set
    assert type(q[{1: 'a', 2: 'b', 3: 'c'}]) is ast.Dict

    # block mode: statements -> AST; assigns a list of AST nodes to the as-variable.
    with q as quoted:
        number = 42  # noqa: F841, only quoted
    assert type(quoted[0]) is ast.Assign
    assert len(quoted[0].targets) == 1
    assert type(quoted[0].targets[0]) is ast.Name
    assert quoted[0].targets[0].id == "number"
    assert type(quoted[0].value) in (ast.Constant, ast.Num)  # TODO: Python 3.8: remove ast.Num
    if type(quoted[0].value) is ast.Constant:
        assert quoted[0].value.value == 42
    else:  # ast.Num
        assert quoted[0].value.n == 42

    # u[]: simple value
    v = 42
    quv = q[u[v]]
    assert type(quv) is ast.Constant
    assert quv.value == v

    # n[]: parse and evaluate Python code (e.g. string -> lexical identifier)
    qnx = q[n["x"]]  # same as q[x], the point of n[] is that the argument may be a variable.
    assert type(qnx) is ast.Name
    assert qnx.id == "x"

    nom = "x"
    qns = q[n[nom]]
    assert type(qns) is ast.Name
    assert qns.id == nom

    qnss = q[n[nom + nom]]  # expressions that evaluate to a string are ok, too.
    assert type(qnss) is ast.Name
    assert qnss.id == nom + nom

    # Thanks to the ctx fixer, `n[]` can also appear on the LHS of an assignment.
    # (Indeed, any unquote can, if the end result makes sense syntactically.)
    with q as quoted:
        n[nom] = 42
    # Because we're not in a macro (that could just return `tree` to the
    # importer), we have to compile and exec `tree`. For this use case,
    # we have `mcpyrate.compiler.run`.
    module = run(quoted)  # create new module, run the code in it
    assert hasattr(module, "x")
    assert module.x == 42

    # create_module obeys Python's package semantics when used with custom dotted names.
    # TODO: compiler tests should be in their own test module.
    try:
        flop = create_module("flip.flop")
    except ModuleNotFoundError:  # parent module does not exist in `sys.modules`
        pass
    else:
        assert False

    flip = create_module("flip")
    flop = create_module("flip.flop")
    assert flop.__package__ == "flip"
    assert flip.flop is flop  # submodule is added to the package namespace

    # `n[]` can also appear in a `del`:
    assert hasattr(module, "x")
    with q as quoted:
        del n[nom]
    run(quoted, module)  # run in existing module
    assert not hasattr(module, "x")

    # a[]: AST literal
    nam = ast.Name(id=nom)
    qa = q[a[nam]]
    assert type(qa) is ast.Name
    assert qa.id == nom

    # s[]: list of ASTs -> ast.List
    thenames = ["a", "b", "c"]
    lst = [ast.Name(id=x) for x in thenames]
    qs = q[s[lst]]
    assert type(qs) is ast.List
    assert [node.id for node in qs.elts] == thenames

    # t[]: list of ASTs -> ast.Tuple
    thenames = ["a", "b", "c"]
    lst = [ast.Name(id=x) for x in thenames]
    qs = q[t[lst]]
    assert type(qs) is ast.Tuple
    assert [node.id for node in qs.elts] == thenames

    # classic and hygienic unquoting
    assert test_q == "f from macro use site"
    assert test_hq == "f from macro definition site"

    # --------------------------------------------------------------------------------
    # unparse(): render approximate source code that corresponds to an AST

    # A quoted expression can be unparsed into a source code representation.
    assert unparse(q[first[42]]) == "first[42]"

    # TODO: This is testing, beside what we want, an implementation detail;
    # TODO: is there a better way?
    # TODO: Python 3.8: remove ast.Num
    assert unparse(q[q[42]]) in (f"mcpyrate.quotes.splice_ast_literals(mcpyrate.quotes.ast.Num(n=42), '{__file__}')",
                                 f"mcpyrate.quotes.splice_ast_literals(mcpyrate.quotes.ast.Constant(value=42), '{__file__}')")
    assert unparse(expand1rq[h[q][42]]) in (f"mcpyrate.quotes.splice_ast_literals(mcpyrate.quotes.ast.Num(n=42), '{__file__}')",
                                            "mcpyrate.quotes.splice_ast_literals(mcpyrate.quotes.ast.Constant(value=42), '{__file__}')")

    # Macro names can be hygienically captured, too. The name becomes "originalname_uuid".
    assert unparse(q[h[first][42]]).startswith("first_")
    assert unparse(q[h[q][42]]).startswith("q_")

    # Unparsed source code can usually be eval'd (unless it has AST markers).
    # Doing that is discouraged, though.
    result = eval(unparse(q[f"Cat is \"{cat}\",\ndog is '{dog}'."]),  # noqa: F821
                  {"cat": "tabby", "dog": "terrier"})
    assert result == "Cat is \"tabby\",\ndog is 'terrier'."

    # --------------------------------------------------------------------------------
    # expand macros in quoted code (returns quoted result)

    # The `s` variants operate at macro expansion time.

    # expand1s[...] expands once
    assert first[21] == 2 * 21
    assert unparse(q[first[21]]) == "first[21]"
    assert unparse(expand1s[q[first[21]]]) == "second[21]"
    assert unparse(expand1s[expand1s[q[first[21]]]]) == "third[21]"
    assert unparse(expand1s[expand1s[expand1s[q[first[21]]]]]) == "(2 * 21)"
    assert unparse(expand1s[expand1s[expand1s[expand1sq[first[21]]]]]) == "(2 * 21)"  # once no more macros, no-op.

    # expands[...] expands until no macros left.
    assert unparse(expands[q[first[21]]]) == "(2 * 21)"

    # expand1sq[...] is shorthand for expand1s[q[...]]
    assert unparse(expand1sq[first[21]]) == "second[21]"
    assert unparse(expand1s[expand1sq[first[21]]]) == "third[21]"
    assert unparse(expand1s[expand1s[expand1sq[first[21]]]]) == "(2 * 21)"
    assert unparse(expand1s[expand1s[expand1s[expand1sq[first[21]]]]]) == "(2 * 21)"

    # expandsq[...] is shorthand for expand[q[...]]
    assert unparse(expandsq[first[21]]) == "(2 * 21)"

    # Whatever the original macro expands to is *not* hygienically treated.
    #
    # This is a *feature*; if you want a macro to invoke other macros hygienically
    # in its output, the original macro must do that explicitly (i.e. use `q[h[]]`
    # in its output).
    #
    # Here we use the `r` variants of the `expand` macros, so that they'll perform
    # the expansion at run time of their use site, thus allowing the expander to see
    # unquoted values (which are only available at run time). Note that applies to
    # the hygienic unquote, too.
    #
    # Though hygienically unquoting a macro name performs the actual capture at macro
    # expansion time, the `s` variants of the `expand` macros won't expand the captured
    # macro, because due to technical reasons, the unquote is internally converted back
    # into a capture command. See `unastify` if curious. (This solution also treats all
    # unquote types consistently.)
    #
    # The `r` variants are generally useful for expanding macros in any
    # run-time AST value. They capture the macro bindings from their use site,
    # at macro expansion time.
    assert unparse(expand1r[q[h[first][21]]]) == "second[21]"
    assert unparse(expandr[q[h[first][21]]]) == "(2 * 21)"
    assert unparse(expand1rq[h[first][21]]) == "second[21]"
    assert unparse(expandrq[h[first][21]]) == "(2 * 21)"

    # --------------------------------------------------------------------------------
    # unastify(): the inverse of the quote operator
    #
    # Rarely needed. It's not an unquote - unquotes interpolate stuff, which
    # then becomes quoted. Unastify inverts the quoting process itself.

    # Note the extra q[], this code is inside two levels of quoting.
    # We undo one level by `unastify`, so we're left with an AST.
    assert unparse(unastify(q[q[foo(a, b=c, *lst, **dic)]])) == "foo(a, *lst, b=c, **dic)"  # noqa: F821

    # This should have the same result.
    assert unparse(q[foo(a, b=c, *lst, **dic)]) == "foo(a, *lst, b=c, **dic)"  # noqa: F821

    print("All tests PASSED")

if __name__ == '__main__':
    test()
