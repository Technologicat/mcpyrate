# -*- coding: utf-8; -*-
#
# Run as `macropython demo/anaphoric_if.py`.

from mcpyrate.multiphase import macros, phase
from mcpyrate.debug import macros, step_expansion  # noqa: F811

with phase[1]:
    from mcpyrate.quotes import macros, q, n, a, h  # noqa: F811, F401

    from let import macros, let  # noqa: F811, F401

    from ast import Load

    from mcpyrate import namemacro
    from mcpyrate.expander import MacroExpander
    from mcpyrate.utils import extract_bindings, NestingLevelTracker

    _aif_level = NestingLevelTracker()

    def aif(tree, *, syntax, expander, **kw):
        """[syntax, expr] Anaphoric if. The test result is `it`.

        Usage::

            aif[test, then, otherwise]

        Expands to a `let` and an if-expr::

            let[[it, test]][then if it else otherwise]

        The name `it` is literally exactly that. The variable `it` is available
        in the `then` and `otherwise` parts, and refers to the test result.
        """
        if syntax != "expr":
            raise SyntaxError("`aif` is an expr macro only")

        # Detect the name(s) of `it` at the use site (this accounts for as-imports)
        bindings = extract_bindings(expander.bindings, it_macro)
        if not bindings:
            raise SyntaxError("The use site of `aif` must macro-import `it`, too.")

        with _aif_level.changed_by(+1):
            # expand any `it` inside the `aif` (thus confirming those uses are valid)
            def expand_it(tree):
                return MacroExpander(bindings, expander.filename).visit(tree)

            name_of_it = list(bindings.keys())[0]
            expanded_it = expand_it(q[n[name_of_it]])

            tree = expand_it(tree)
            test, then, otherwise = tree.elts
            # Our `let` takes in a bare `Name`, which it lifts into a function parameter,
            # so in `let_bindings`, we *must not* expand the `it`.
            let_bindings = q[[n[name_of_it], a[test]]]
            # But in the test for the `if`, we must use an *expanded* `it`;
            # if we leave it to the expander to handle later, our context
            # will have exited and it'll error out.
            let_body = q[a[then] if a[expanded_it] else a[otherwise]]
            return q[h[let][a[let_bindings]][a[let_body]]]

    def it_macro(tree, *, syntax, **kw):
        """[syntax, name] The `it` of an anaphoric if.

        Inside an `aif` body, evaluates to the value of the test result.
        Anywhere else, is considered a syntax error.
        """
        if syntax != "name":
            raise SyntaxError("`it` is a name macro only")
        # Accept `it` in any non-load context, so that we can below define the macro `it`.
        # TODO: Only an issue if we define this with multi-phase compilation?
        # The phase-1 `it` is in the macro expander when the lifted phase-0 definition is being run.
        if hasattr(tree, "ctx") and type(tree.ctx) is not Load:
            return tree
        if _aif_level.value < 1:
            raise SyntaxError("`it` may only appear within an `aif[...]`")
        # Check passed, go ahead and use this `it` as a regular run-time name.
        return tree
    it = namemacro(it_macro)


from __self__ import macros, aif, it  # noqa: F811, F401

def demo():
    with step_expansion:
        assert aif[2 * 21,
                   f"it is {it}",
                   "it is False"] == "it is 42"

if __name__ == '__main__':
    demo()
