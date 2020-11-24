# -*- coding: utf-8; -*-
"""Alternative file layout for the anaphoric if example. Macro definitions.

Now we don't need to multi-phase compile this module, and `it` both becomes
simpler and can properly prevent all incorrect uses.
"""

__all__ = ["aif", "it"]

from mcpyrate.quotes import macros, q, n, a, h  # noqa: F811, F401

from let import macros, let  # noqa: F811, F401

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
    macro_bindings = extract_bindings(expander.bindings, it)
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
        let_bindings = q[[n[name_of_it], a[test]]]
        let_body = q[a[then] if a[expanded_it] else a[otherwise]]
        return q[h[let][a[let_bindings]][a[let_body]]]

@namemacro
def it(tree, *, syntax, **kw):
    """[syntax, name] The `it` of an anaphoric if.

    Inside an `aif` body, evaluates to the value of the test result.
    Anywhere else, is considered a syntax error.
    """
    if syntax != "name":
        raise SyntaxError("`it` is a name macro only")
    if _aif_level.value < 1:
        raise SyntaxError("`it` may only appear within an `aif[...]`")
    return tree
