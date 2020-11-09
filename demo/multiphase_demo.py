# Multi-phase compilation demo.
#
# Multi-phase compilation, a.k.a. `with phase`, is a convenience feature
# that allows defining macros in the same module where they are used.
#
# Actually `with phase` is an importer feature, not really a regular macro,
# but we need a place to put the docstring, and it's nice if `flake8` is happy.
# So there's a `phase` "macro" in `mcpyrate.multiphase`. Macro-importing it
# enables the multi-phase compiler for this module.
#
from mcpyrate.multiphase import macros, phase

# `with phase` is only recognized at the top level of a module. It is basically
# just data for the importer that the importer compiles away; it takes effect
# before the macro expander runs.
#
# Thus, currently macros cannot inject `with phase` invocations.
#
# Phases count down, regular run time is phase 0. Run time of phase `k + 1`
# is the macro-expansion time of phase `k`.
#
# Phase 0 is defined implicitly. All code that is **not** inside any
# `with phase` block belongs to phase 0.
#
# Phases are a module initialization detail, local to each module. Once a module
# finishes importing, it has reached phase 0.
#
# During module initialization, for `k >= 1`, each phase `k` is reified into a
# temporary module, placed in `sys.modules`, with the same absolute dotted name
# as the final one. This allows the next phase to import macros from it.
#
# When the macro expander and bytecode compiler are done with phase `k`, that
# phase is reified, completely overwriting the module from phase `k + 1`.
#
# Once phase 0 has been compiled, the temporary module is removed from
# `sys.modules`, and the module is handed over to Python's regular import
# machinery. Thus Python's import machinery will perform any remaining steps of
# initialization, such as placing the final module into `sys.modules` (the
# important point is, it may need to do something else, too, and the absence
# from `sys.modules` may act as a trigger).
#
# All definitions from phase `k + 1` are automatically lifted into the
# code for phase `k`. Phase `k` then lifts them to phase `k - 1`, and the
# chain continues all the way down to the implicit phase 0.
#
# This means e.g. that another module that wants to import macros from this one
# doesn't need to care which phase the macros were defined in here. They'll be
# present in the final phase-0 module. The phase is important only for invoking
# those macros inside this module itself.
#
# TODO: Order preservation is not yet implemented. Code will be pasted in phase-descending order.
#     Original ordering of the code blocks is preserved. Once a phase is compiled,
#     the body of its `with phase` block (after macro expansion) is spliced into
#     the surrounding context. Thus, like a receding tide, each phase will "reveal"
#     increasing subsets of the original source file, until (at the implicit phase
#     0) all of the file is processed.
#
# Mutable state, if any, is **not** preserved between phases, because each
# phase starts as a new module instance. There is currently no way to transmit
# information to a future phase, except by encoding it in macro output (so it
# becomes part of the next phase's AST, before that phase reaches run time).
# If you're really desperate, you could define a `@namemacro` that expands
# into an AST for the data you want to transmit. (Then maybe use `q[h[...]]`
# or `q[u[...]]` in its implementation, to generate the expansion.)
#
# Each phase may import macros from any earlier phase, by using the magic
# *self-macro-import* syntax `from __self__ import macros, ...`. It doesn't
# matter which phase the macro is defined in, as long as it is in *some*
# earlier (higher-number) phase.

# **NOTE**: This is a sloppy pythonification of Racket's phase level tower:
#
#     https://docs.racket-lang.org/guide/phases.html
#
# but there are differences. Particularly, racketeers should note that in
# `mcpyrate`, phase separation is not strict; code from **all** phases will
# be available in the final phase-0 module. This is a design decision; it's
# more pythonic that macros don't "disappear" from the final module just
# because they were defined in a higher phase.
#
# This makes the phase level into a module initialization detail that is
# local to each module. Other modules don't need to care in which phase
# a thing was defined when they import that thing.
#
with phase[1]:  # The phase number must be a positive integer literal.
    # Macro-imports may appear at the top level of a phase.
    # The macro-imports are lifted into the next phase, too.
    from mcpyrate.debug import macros, step_expansion  # noqa: F811
    from mcpyrate.quotes import macros, q, a  # noqa: F811

    def f(x):
        print(f"Hello! {x}")

    def block(tree, *, syntax, **kw):
        if syntax != "block":
            raise SyntaxError("sorry, block macro only")
        f("Expanding macro `block` defined in phase 1.")
        with step_expansion:
            with q as quoted:
                #print("block expanded!")
                with a:
                    tree
        return quoted

# To import macros from any higher phase of this module itself, use a *self-macro-import*.
# It is a macro-import, with the module name the magic __self__:
from __self__ import macros, block  # noqa: F401, F811

with block:
    # To use a run-time definition made in an earlier phase, just use it.
    # The same definition was made in the current phase, too, so there's
    # no need to import anything. Indeed, the temporary module from which
    # the original instance of the definition could theoretically be imported,
    # no longer even exists.
    f("Running the block body during phase 0.")
