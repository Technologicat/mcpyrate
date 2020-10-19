# -*- coding: utf-8 -*-

from ..quotes import (macros, q, u, n, a, s, h,
                      expand, expand1, expandq, expand1q)
from .macros import (macros, test_q, test_hq,  # noqa: F401, F811
                     first, second, third)

import ast

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

    # n[]: string -> identifier
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

    # a[]: AST literal
    nam = ast.Name(id=nom)
    qa = q[a[nam]]
    assert type(qa) is ast.Name
    assert qa.id == nom

    # s[]: list of ASTs -> ast.List
    lst = [ast.Name(id=x) for x in ("a", "b", "c")]
    qs = q[s[lst]]
    assert type(qs) is ast.List
    assert qs.elts is lst

    # classic and hygienic unquoting
    assert test_q == "f from macro use site"
    assert test_hq == "f from macro definition site"

    # --------------------------------------------------------------------------------
    # unparse(): render approximate source code that corresponds to an AST

    # A quoted expression can be unparsed into a source code representation.
    assert unparse(q[first[42]]) == "first[42]"

    # TODO: Python 3.8: remove ast.Num
    assert unparse(q[q[42]]) in ("mcpyrate.quotes.ast.Num(n=42)",
                                 "mcpyrate.quotes.ast.Constant(value=42)")
    assert unparse(expand1q[h[q][42]]) in ("mcpyrate.quotes.ast.Num(n=42)",
                                           "mcpyrate.quotes.ast.Constant(value=42)")

    # Macro names can be hygienically captured, too. It inserts a uniqified macro binding
    # into a global table for the current process. The name becomes "originalname_uuid".
    assert unparse(q[h[first][42]]).startswith("first_")
    assert unparse(q[h[q][42]]).startswith("q_")

    # Unparsed source code can usually be eval'd (unless it has AST markers).
    # Doing that is discouraged, though.
    result = eval(unparse(q[f"Cat is \"{cat}\",\ndog is '{dog}'."]),  # noqa: F821
                  {"cat": "tabby", "dog": "terrier"})
    assert result == "Cat is \"tabby\",\ndog is 'terrier'."

    # --------------------------------------------------------------------------------
    # expand macros in quoted code (returns quoted result)

    # expand1[...] expands once
    assert first[21] == 2 * 21
    assert unparse(q[first[21]]) == "first[21]"
    assert unparse(expand1[q[first[21]]]) == "second[21]"
    assert unparse(expand1[expand1[q[first[21]]]]) == "third[21]"
    assert unparse(expand1[expand1[expand1[q[first[21]]]]]) == "(2 * 21)"
    assert unparse(expand1[expand1[expand1[expand1q[first[21]]]]]) == "(2 * 21)"  # once no more macros, no-op.

    # expand[...] expands until no macros left.
    assert unparse(expand[q[first[21]]]) == "(2 * 21)"

    # expand1q[...] is shorthand for expand1[q[...]]
    assert unparse(expand1q[first[21]]) == "second[21]"
    assert unparse(expand1[expand1q[first[21]]]) == "third[21]"
    assert unparse(expand1[expand1[expand1q[first[21]]]]) == "(2 * 21)"
    assert unparse(expand1[expand1[expand1[expand1q[first[21]]]]]) == "(2 * 21)"

    # expandq[...] is shorthand for expand[q[...]]
    assert unparse(expandq[first[21]]) == "(2 * 21)"

    # Whatever the original macro expands to is *not* hygienically treated.
    #
    # This is a *feature*; if you want a macro to invoke other macros hygienically
    # in its output, the original macro must do that explicitly (i.e. use `q[h[]]`
    # in its output).
    assert unparse(expand1[q[h[first][21]]]) == "second[21]"
    assert unparse(expand[q[h[first][21]]]) == "(2 * 21)"

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
