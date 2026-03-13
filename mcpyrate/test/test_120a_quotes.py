# -*- coding: utf-8 -*-

from ..quotes import macros, q, u, n, a, s, t, h  # noqa: F811
from .macros import (macros, first, second, test_hq,  # noqa: F401, F811
                     test_q, third)
from ..metatools import (macros, expand1r, expand1rq, expand1s,  # noqa: F401, F811
                         expand1sq, expandr, expandrq, expands, expandsq,
                         expand_first)

import ast

from ..compiler import temporary_module, run, expand
from ..core import Done
from ..markers import ASTMarker
from ..quotes import (unastify, astify, is_captured_value, lookup_value,
                      is_captured_macro, capture_macro,
                      capture_as_macro, lift_sourcecode,
                      ast_literal, splice_ast_literals, SpliceNodes,
                      _typecheck, _flatten_and_typecheck_iterable)
from ..unparser import unparse
from ..walkers import ASTVisitor


def f():
    return "f from macro use site"


def _dummy_macro(tree, **kw):
    """Module-level dummy macro for capture_as_macro test (must be picklable)."""
    return tree


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
    assert type(quoted[0].value) is ast.Constant
    assert quoted[0].value.value == 42

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
    assert unparse(expand1rq[h[q][42]]) in (f"mcpyrate.quotes.splice_ast_literals(mcpyrate.quotes.ast.Constant(value=42), '{__file__}')",
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

    # --------------------------------------------------------------------------------
    # expand_first: in a block, force given macros to expand before others

    # Here we test by expanding just one step; this expands the `expand_first`,
    # which causes (recursive) expansion of the given macros only.

    with expand1rq as quoted:
        with expand_first[second]:  # only the macro `second` gets expanded in the first step
            third[second[42]]
    assert unparse(quoted) == "third[third[42]]"  # second[...] -> third[...]

    with expand1rq as quoted:
        with expand_first[third]:  # only the macro `third` gets expanded in the first step
            third[second[42]]
    assert unparse(quoted) == "(2 * second[42])"  # third[...] -> (2 * ...)

    # Hygienic macro captures are also accepted.
    # Note here we are inside one level of quoting from the `expand1rq`.
    with expand1rq as quoted:
        with expand_first[h[second]]:
            third[h[second][42]]
    assert unparse(quoted) == "third[third[42]]"

    # --------------------------------------------------------------------------------
    # Block mode for quote-then-expand-at-runtime macros

    # expandrq block mode: quote-then-expand-at-runtime, as a block.
    with expandrq as quoted:
        h[first][21]
    assert unparse(quoted) == "(2 * 21)"

    # expand1sq block mode: quote-then-expand-once, as a block.
    with expand1sq as quoted:
        first[21]
    assert len(quoted) == 1
    assert unparse(quoted) == "second[21]"

    # expandsq block mode: quote-then-expand-all, as a block.
    with expandsq as quoted:
        first[21]
    assert len(quoted) == 1
    assert unparse(quoted) == "(2 * 21)"

    # --------------------------------------------------------------------------------
    # Direct function tests for coverage of quotes.py internals

    # -- lift_sourcecode: type validation --
    try:
        lift_sourcecode(42)
    except TypeError as e:
        assert "n[]" in str(e)
    else:
        assert False, "lift_sourcecode should reject non-str"

    # -- _typecheck: marker with list body, marker with single body, type mismatch --
    class TestMarker(ASTMarker):
        pass

    # Marker containing a list of stmts
    _typecheck(TestMarker(body=[ast.Pass(), ast.Pass()]), ast.stmt, "test")

    # Marker containing a single node
    _typecheck(TestMarker(body=ast.Pass()), ast.stmt, "test")

    # Type mismatch
    try:
        _typecheck(ast.Constant(value=42), ast.stmt, "test")
    except TypeError as e:
        assert "test" in str(e)
    else:
        assert False, "_typecheck should reject wrong type"

    # -- _flatten_and_typecheck_iterable: non-iterable --
    try:
        _flatten_and_typecheck_iterable(42, ast.expr, "test")
    except TypeError as e:
        assert "iterable" in str(e)
    else:
        assert False, "should reject non-iterable"

    # -- ast_literal: invalid syntax, block mode, expr mode with list --
    try:
        ast_literal(ast.Name(id="x"), "name")
    except ValueError as e:
        assert "expr" in str(e) or "block" in str(e)
    else:
        assert False, "ast_literal should reject invalid syntax"

    # expr mode with iterable of exprs
    result = ast_literal([ast.Name(id="x"), ast.Name(id="y")], "expr")
    assert isinstance(result, SpliceNodes)

    # block mode
    result = ast_literal([ast.Pass(), ast.Pass()], "block")
    assert isinstance(result, SpliceNodes)

    # -- splice_ast_literals: SpliceNodes remaining → error --
    # A SpliceNodes in a non-list context can't be consumed by the splicer.
    bad_expr = ast.Expr(value=SpliceNodes(body=[ast.Pass()]))
    bad_tree = ast.Module(body=[bad_expr], type_ignores=[])
    try:
        splice_ast_literals(bad_tree, "<test>")
    except RuntimeError as e:
        assert "SpliceNodes" in str(e)
    else:
        assert False, "splice_ast_literals should error on remaining SpliceNodes"

    # splice_ast_literals: Global/Nonlocal passthrough (line 232)
    global_node = ast.Global(names=["x"])
    mod = ast.Module(body=[global_node], type_ignores=[])
    splice_ast_literals(mod, "<test>")  # should not raise

    # splice_ast_literals: non-AST non-list → TypeError (line 238)
    # The doit() function is called recursively; feed it a non-AST directly.
    try:
        splice_ast_literals(42, "<test>")
    except TypeError as e:
        assert "Expected" in str(e)
    else:
        assert False, "splice_ast_literals should reject non-AST, non-list"

    # -- capture_macro: non-callable → TypeError --
    try:
        capture_macro(42, "notafunc")
    except TypeError as e:
        assert "callable" in str(e)
    else:
        assert False, "capture_macro should reject non-callable"

    # -- capture_as_macro: non-callable → TypeError --
    try:
        capture_as_macro(42)
    except TypeError as e:
        assert "callable" in str(e)
    else:
        assert False, "capture_as_macro should reject non-callable"

    # -- capture_as_macro: valid callable --
    result = capture_as_macro(_dummy_macro)
    assert isinstance(result, ast.Name)
    assert result.id.startswith("_dummy_macro")

    # -- lookup_value: unfrozen key → ValueError --
    try:
        lookup_value(("somename", None))
    except ValueError as e:
        assert "does not (yet) point to a value" in str(e)
    else:
        assert False, "lookup_value should reject unfrozen key"

    # -- astify: tuple, dict, set, Done, ASTMarker error --
    # tuple
    result = astify((1, 2, 3))
    assert isinstance(result, ast.Tuple)
    assert len(result.elts) == 3

    # dict
    result = astify({"a": 1})
    assert isinstance(result, ast.Dict)

    # set
    result = astify({1, 2})
    assert isinstance(result, ast.Set)

    # Done marker
    result = astify(Done(body=ast.Constant(value=42)))
    assert isinstance(result, ast.Call)

    # ASTMarker (non-Done) should raise
    try:
        astify(TestMarker(body=ast.Constant(value=42)))
    except TypeError as e:
        assert "Cannot astify" in str(e)
    else:
        assert False, "astify should reject non-Done ASTMarkers"

    # Unknown type should raise
    try:
        astify(object())
    except TypeError as e:
        assert "Don't know how to astify" in str(e)
    else:
        assert False, "astify should reject unknown types"

    # -- unastify: tuple, dict, set --
    assert unastify(astify((1, 2))) == (1, 2)
    assert unastify(astify({"k": "v"})) == {"k": "v"}
    assert unastify(astify({1, 2})) == {1, 2}

    # unastify: lookup_thing error paths
    try:
        # Non-mcpyrate.quotes dotted name
        bad = ast.Call(func=ast.Attribute(value=ast.Name(id="other_module"),
                                          attr="something"),
                       args=[], keywords=[])
        unastify(bad)
    except (TypeError, NotImplementedError):
        pass  # expected

    # unastify: unknown node type → TypeError (line 931)
    try:
        unastify(ast.Name(id="x"))
    except TypeError as e:
        assert "Don't know how to unastify" in str(e)
    else:
        assert False, "unastify should reject unknown node types"

    # -- Nested quasiquotes: quote level tracking --
    # q[q[u[u[x]]]] — inner u splices at level 0, outer u is preserved
    x = 42
    inner = q[q[u[u[x]]]]
    assert unparse(inner) == "q[u[42]]"

    # q[q[n[n[nom]]]] — inner n evaluates nom→"y", then n["y"]→Name(id='y');
    # outer n is preserved as-is because quote level > 0.
    nom = "y"
    inner = q[q[n[n[nom]]]]
    assert unparse(inner) == "q[n[y]]"

    # -- Block mode q: missing asname --
    # If you write `with q:` without `as`, the macro expander passes
    # optional_vars=None and q raises SyntaxError (wrapped in MacroApplicationError).
    from ..core import MacroApplicationError
    try:
        run("from mcpyrate.quotes import macros, q\nwith q:\n    x = 1\n")
    except MacroApplicationError:
        pass  # expected: SyntaxError about missing asname
    else:
        assert False, "block mode q without asname should raise"

    # -- Block mode a inside q: splice statements --
    with q as part1:
        x = 1  # noqa: F841
    with q as part2:
        y = 2  # noqa: F841
    parts = part1 + part2
    with q as quoted:
        with a:
            parts
    # The block macro expansion inserts a coverage dummy (Done node), plus our 2 stmts.
    assigns = [stmt for stmt in quoted if isinstance(stmt, ast.Assign)]
    assert len(assigns) == 2

    # -- unastify round-trips: markers for each unquote operator --
    # When we expand1s a quote, the unquote markers are compiled into function
    # calls by astify. unastify should convert them back to markers.
    from ..quotes import (Unquote, LiftSourcecode, ASTLiteral,
                          ASTList, ASTTuple, Capture)

    # The expand1s macro round-trips quote→unquote→re-quote. When we unastify
    # the result, we get markers back for each unquote operator. This exercises
    # all the unastify branches that reconstruct markers from compiled calls.
    #
    # expand1rq quotes, then expands at run time — so unquoted values (v, nom,
    # nam, lst, f) are available. We can then manually unastify the result.
    v = 42
    nom = "y"
    nam = ast.Name(id="x")
    lst = [ast.Name(id="a")]

    # u[] round-trip
    tree = expand1rq[q[u[v]]]
    result = unastify(tree)
    assert isinstance(result, Unquote)

    # n[] round-trip
    tree = expand1rq[q[n[nom]]]
    result = unastify(tree)
    assert isinstance(result, LiftSourcecode)

    # a[] (expr) round-trip
    tree = expand1rq[q[a[nam]]]
    result = unastify(tree)
    assert isinstance(result, ASTLiteral)

    # s[] round-trip
    tree = expand1rq[q[s[lst]]]
    result = unastify(tree)
    assert isinstance(result, ASTList)

    # t[] round-trip
    tree = expand1rq[q[t[lst]]]
    result = unastify(tree)
    assert isinstance(result, ASTTuple)

    # h[] (value) round-trip
    tree = expand1rq[q[h[f]]]
    result = unastify(tree)
    assert isinstance(result, Capture)

    # h[] (macro) round-trip: unastify of lookup_macro → Capture
    tree = expand1rq[q[h[first][42]]]
    result = unastify(tree)
    # The subscript's value should have been uncompiled to a Capture
    assert isinstance(result.value, Capture)

    # -- Unquote operators outside q: quotelevel < 1 errors --
    # These test the SyntaxError branches for each unquote when used without q.
    # We run them through the compiler since the macro expander needs to be active.
    for op_name in ("u", "n", "s", "t", "h"):
        try:
            run(f"from mcpyrate.quotes import macros, {op_name}\n{op_name}[x]\n")
        except MacroApplicationError:
            pass  # expected: quotelevel < 1
        else:
            assert False, f"`{op_name}` outside q should raise"

    # `a` outside q (both expr and block)
    try:
        run("from mcpyrate.quotes import macros, a\na[x]\n")
    except MacroApplicationError:
        pass
    else:
        assert False, "`a` (expr) outside q should raise"

    try:
        run("from mcpyrate.quotes import macros, a\nwith a:\n    x\n")
    except MacroApplicationError:
        pass
    else:
        assert False, "`a` (block) outside q should raise"

    # -- Block mode q: tuple/list asname --
    try:
        run("from mcpyrate.quotes import macros, q\nwith q as (a, b):\n    x = 1\n")
    except MacroApplicationError:
        pass
    else:
        assert False, "block mode q with tuple asname should raise"

    # -- is_captured_value: post-capture detection via expand1s --
    # After expansion, the h[f] has been captured → lookup_value form.
    tree = expand1s[q[h[f]]]
    key = is_captured_value(tree)
    assert key is not False
    name, frozen = key
    assert name == "f"
    assert isinstance(frozen, bytes)  # post-capture: value has been frozen
    assert lookup_value(key) is f  # round-trip: recovered value is the same object

    print("    test_quotes: all passed")

if __name__ == '__main__':
    runtests()
