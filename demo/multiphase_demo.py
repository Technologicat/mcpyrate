# -*- coding: utf-8; -*-
"""Multi-phase compiler demo.

Multi-phase compilation allows using macros in the same module where they
are defined.
"""

# Enable the multi-phase compiler for this module.
from mcpyrate.multiphase import macros, phase

# Enable debug mode for multi-phase compiler.
# Debug mode prints unparsed source code for the AST of each phase, before macro expansion.
from mcpyrate.debug import macros, step_phases  # noqa: F401, F811


with phase[1]:  # The phase number must be a positive integer literal.
    # Macro-imports may appear at the top level of a phase.
    # The macro-imports are lifted into the next phase, too.
    from mcpyrate.debug import macros, step_expansion  # noqa: F811
    from mcpyrate.quotes import macros, q, a  # noqa: F811

    def f(x):
        print(f"Hello! {x}")

    def block(tree, *, syntax, **kw):
        if syntax != "block":
            raise SyntaxError("`block` is a block macro only")
        f("Expanding macro `block` defined in phase 1.")
        with step_expansion:
            with q as quoted:
                #print("block expanded!")
                with a:
                    tree
        return quoted

# To import macros from any higher phase of this module itself, use a *self-macro-import*.
# It's just like any macro-import, but using the magic __self__ for the module name:
from __self__ import macros, block  # noqa: F401, F811

with block:
    # To use a run-time definition made in an earlier phase, just use it.
    # The same definition is made in the current phase, too, so there's
    # no need to import anything. Indeed, the temporary module from which
    # the original instance of the definition could theoretically be imported,
    # no longer even exists.
    f("Running the block body during phase 0.")
