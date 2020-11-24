# -*- coding: utf-8; -*-
"""Advanced tricks, part 2. Building an anaphoric if, with a context-sensitive `it`.

Run as `macropython demo/anaphoric_if.py`.
"""

__all__ = ["aif", "it"]

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
        macro_bindings = extract_bindings(expander.bindings, it_function)
        if not macro_bindings:
            raise SyntaxError("The use site of `aif` must macro-import `it`, too.")

        with _aif_level.changed_by(+1):
            # expand any `it` inside the `aif` (thus confirming those uses are valid)
            def expand_it(tree):
                return MacroExpander(macro_bindings, expander.filename).visit(tree)

            name_of_it = list(macro_bindings.keys())[0]
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

            # Which unquote to use to inject the `let` bindings depends on the data:
            #  - One binding, like we have: `a[let_bindings]`
            #  - Two or more bindings, defined as `q[[k1, v1], [k2, v2]]`: still `a[let_bindings]`,
            #    because that quoted code represents an `ast.Tuple` (which contains two `ast.List`s
            #    as its elements).
            #  - Two or more bindings, defined as `[q[[k1, v1]], q[[k2, v2]]]`: then `t[let_bindings]`,
            #    to convert that run-time `list` wrapper into an `ast.Tuple` node.
            # (Keep in mind multiple macroargs are always fed in as an `ast.Tuple`. The `let` macro
            #  takes in one or more args, each of which is a two-element `ast.List`.)
            return q[h[let][a[let_bindings]][a[let_body]]]

            # The temporary variables above are only for readability. This works, too:
            # return q[h[let][[n[name_of_it], a[test]]][a[then] if a[expanded_it] else a[otherwise]]]

    # If this was in a separate file, we could name the function `it` directly,
    # but due to multi-phase compilation, the macro binding established in phase 1
    # would prevent us from referring to the macro function `it` during the compilation
    # of phase 0. (This is because all code from phase 1 is lifted to appear also in phase 0,
    # so that other modules can import things from it).
    #
    # So we give the function a different name, to separate the concepts of
    # "the macro function `it`" and "the name macro `it`".
    def it_function(tree, *, syntax, **kw):
        """[syntax, name] The `it` of an anaphoric if.

        Inside an `aif` body, evaluates to the value of the test result.
        Anywhere else, is considered a syntax error.
        """
        if syntax != "name":
            raise SyntaxError("`it` is a name macro only")

        # Accept `it` in any non-load context, so that we can below define the macro `it`.
        #
        # This is only an issue, because this example uses multi-phase compilation.
        # The phase-1 `it` is in the macro expander - preventing us from referring to
        # the name `it` - when the lifted phase-0 definition is being run. During phase 0,
        # that makes the line `it = namemacro(...)` below into a macro-expansion-time
        # syntax error, because that `it` is not inside an `aif`.
        #
        # We hack around it, by allowing `it` anywhere as long as the context is not a `Load`.
        if hasattr(tree, "ctx") and type(tree.ctx) is not Load:
            return tree

        if _aif_level.value < 1:
            raise SyntaxError("`it` may only appear within an `aif[...]`")
        # Check passed, go ahead and use this `it` as a regular run-time name.
        return tree
    it = namemacro(it_function)


from __self__ import macros, aif, it  # noqa: F811, F401

def demo():
    with step_expansion:
        assert aif[2 * 21,
                   f"it is {it}",
                   "it is False"] == "it is 42"

if __name__ == '__main__':
    demo()
