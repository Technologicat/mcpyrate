# -*- coding: utf-8 -*-

from ..quotes import macros, q, u, n, a, s, t, h  # noqa: F811
from .macros import (macros, first, second, test_hq,  # noqa: F401, F811
                     test_q, third)
from ..metatools import (macros, expand1r, expand1rq, expand1s,  # noqa: F401, F811
                         expand1sq, expandr, expandrq, expands, expandsq)

import ast

from ..compiler import temporary_module, run, expand
from ..quotes import unastify, is_captured_value, lookup_value, is_captured_macro
from ..unparser import unparse
from ..walkers import ASTVisitor


def f():
    return "f from macro use site"


def runtests():
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
    #
    # Because we're not in a macro (that could just return `tree` to the
    # importer), we have to compile and exec `tree`. For this use case,
    # we have `mcpyrate.compiler.run`.
    with temporary_module() as module:
        with q as quoted:
            n[nom] = 42
        run(quoted, module)
        assert hasattr(module, "x")
        assert module.x == 42

        # `n[]` can also appear in a `del`:
        assert hasattr(module, "x")
        with q as quoted:
            del n[nom]
        run(quoted, module)
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

    # Inner quotes are preserved literally
    assert unparse(q[q[42]]) == "q[42]"

    # Quote level is tracked, interpolation occurs when it hits zero
    x = "hi"
    assert unparse(q[u[x]]) == "'hi'"
    assert unparse(q[q[u[x]]]) == "q[u[x]]"
    assert unparse(q[q[u[u[x]]]]) == "q[u['hi']]"

    # TODO: This is testing, beside what we want, an implementation detail;
    # TODO: is there a better way?
    # TODO: Python 3.8: remove ast.Num
    assert unparse(expand1rq[h[q][42]]) in (f"mcpyrate.quotes.splice_ast_literals(mcpyrate.quotes.ast.Num(n=42), '{__file__}')",
                                            f"mcpyrate.quotes.splice_ast_literals(mcpyrate.quotes.ast.Constant(value=42), '{__file__}')",
                                            f"mcpyrate.quotes.splice_ast_literals(mcpyrate.quotes.ast.Constant(value=42, kind=None), '{__file__}')")

    # Macro names can be hygienically captured, too. The name becomes "originalname_uuid".
    assert unparse(q[h[first][42]]).startswith("first_")
    assert unparse(q[h[q][42]]).startswith("q_")

    # Unparsed source code can usually be eval'd (unless it has AST markers).
    # Doing that is discouraged, though. See `mcpyrate.compiler.run` instead.
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
    #
    # Note the `unastify` runs at run time; so for this test to work,
    # we must expand the inner `q` manually, and then quote the result
    # (because a nested quote won't expand automatically).
    assert unparse(unastify(expand1rq[q[foo(a, b=c, *lst, **dic)]])) == "foo(a, *lst, b=c, **dic)"  # noqa: F821

    # This should have the same result.
    assert unparse(q[foo(a, b=c, *lst, **dic)]) == "foo(a, *lst, b=c, **dic)"  # noqa: F821

    # --------------------------------------------------------------------------------
    # Advanced macrology: detecting hygienic captures

    quoted = q[print]
    assert not is_captured_value(quoted)

    quoted = q[h[print]]
    key = is_captured_value(quoted)
    assert key
    assert lookup_value(key) is print  # *our* binding for `print`, since we're the use site of `q`.

    quoted = q[h[first][21]]
    assert type(quoted) is ast.Subscript  # represents a macro invocation
    assert type(quoted.value) is ast.Name and quoted.value.id.startswith("first")  # uniqified name already injected

    # Testing `is_captured_macro` is trickier, because `lookup_macro` disappears when
    # the use site of `q` reaches run time. So let's use a quoted block and `expand` it manually.
    #
    # The node to detect is then somewhere inside the expanded AST. In order to not bother
    # hardcoding its expected location, let's scan the output and see if there is exactly
    # one matching node.
    #
    def count_matching_nodes(matcher, tree):  # matcher: AST -> bool
        class DetectoCounter3000(ASTVisitor):
            def examine(self, tree):
                if matcher(tree):
                    self.state.count += 1
                self.generic_visit(tree)
        counter = DetectoCounter3000(count=0)
        counter.visit(tree)
        return counter.state.count

    with q as quoted:
        # It doesn't matter what macro we `h[...]`, as long as it can be imported from here.
        # Let's use `n` for the test. (The target macro must be imported, so that it will be
        # in the expander's bindings when the `h[]` sees it. Otherwise a regular run-time value
        # capture will occur.)
        from mcpyrate.quotes import macros, q, h, n  # noqa: F401, F811, this is in a new module.
        quoted2 = q[h[n]["catfood"]]  # noqa: F841, we're not going to use it, this snippet is just for analysis.
    quoted = expand(quoted, "fake filename for testing by test_quotes")
    assert count_matching_nodes(is_captured_macro, quoted) == 1
    assert count_matching_nodes(is_captured_value, quoted) == 0

    # If h[]'ing something that's not in the expander's bindings, the result is a run-time value capture.
    with q as quoted:
        from mcpyrate.quotes import macros, q, h  # noqa: F401, F811, this is in a new module.
        quoted2 = q[h[n]["catfood"]]  # noqa: F841, we're not going to use it, this snippet is just for analysis.
    quoted = expand(quoted, "fake filename for testing by test_quotes")
    assert count_matching_nodes(is_captured_macro, quoted) == 0
    assert count_matching_nodes(is_captured_value, quoted) == 1

if __name__ == '__main__':
    runtests()
