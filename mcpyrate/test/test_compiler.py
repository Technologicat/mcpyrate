# -*- coding: utf-8 -*-
"""Test the compiler; mainly the handling of dynamically created modules.

Contains some advanced usage examples.
"""

# TODO: Testing some features of the compiler is a chicken-and-egg problem.
#
# We need quasiquotes for the test, but on the other hand, testing all features
# of the quasiquote system needs the dynamic module features of the compiler.
#
# One way to break that dependency might be to not use quotes here; we could
# instead start from source code. But then the code path that starts from AST
# would remain untested.

from ..quotes import macros, q, u  # noqa: F401

import copy
from textwrap import dedent

# `expand` and `compile` aren't tested separately, but `run` is built on them, so meh.
from ..compiler import run, create_module
from ..utils import gensym, rename

def test():
    def test_create_module():
        # `create_module` with custom dotted names obeys Python's package semantics.
        try:
            flop = create_module("flip.flop")
        except ModuleNotFoundError:  # parent module does not exist in `sys.modules`
            pass
        else:
            assert False

        flip = create_module("flip")
        flop = create_module("flip.flop")
        assert flip.__package__ is None
        assert flop.__package__ == "flip"
        assert flip.flop is flop  # submodule is added to the package namespace
    test_create_module()

    def test_dynamicmodule_from_source():
        module = run("x = 21")
        assert module.x == 21

        run("x = 2 * x", module)
        assert module.x == 42

        run("x = 2 * x", module)
        assert module.x == 84
    test_dynamicmodule_from_source()

    def test_dynamicmodule_from_ast():
        # The module acts essentially as a namespace.
        with q as quoted:
            x = 21  # noqa: F841, it's used in the surrounding context.
        module = run(quoted)
        assert module.x == 21

        with q as quoted:
            x = 2 * x
        run(quoted, module)
        assert module.x == 42

        run(quoted, module)
        assert module.x == 84
    test_dynamicmodule_from_ast()

    def test_dynamicmodule_customname():
        mymodule = create_module("mymod", filename="<my module>")
        with q as quoted:
            assert __name__ == "mymod"
            assert __file__ == "<my module>"
        run(quoted, mymodule)
    test_dynamicmodule_customname()

    # using the same temporary module for lots of runs
    def test_dynamicmodule_reuse_1():
        tempmodule = create_module(gensym("temporary_module"))
        name = tempmodule.__name__

        with q as quoted:
            # Test we're running in the expected module.
            #
            # The `u` belongs to the top-level quote, so we're splicing in
            # the value of `name` from the surrounding context; it then
            # becomes a static string against which we will assert __name__
            # when the code actually runs.
            assert __name__ == u[name]
            x = 0
        run(quoted, tempmodule)

        with q as quoted:
            assert __name__ == u[name]
            x = x + 1
        for _ in range(500):
            run(quoted, tempmodule)
        assert tempmodule.x == 500
    test_dynamicmodule_reuse_1()

    # how to reset such a shared temporary module between runs
    def test_dynamicmodule_reuse_2():
        tempmodule = create_module(gensym("temporary_module"))
        name = tempmodule.__name__
        metadata = copy.copy(tempmodule.__dict__)
        def reset():
            tempmodule.__dict__.clear()
            tempmodule.__dict__.update(metadata)

        with q as quoted:
            assert __name__ == u[name]
            x = 0
        run(quoted, tempmodule)

        with q as quoted:
            assert __name__ == u[name]
            try:
                x
            except NameError:
                pass
            else:
                assert False
            x = 42
        for _ in range(500):
            reset()  # `x` goes poof when we reset tempmodule's namespace
            run(quoted, tempmodule)
        assert tempmodule.x == 42  # from the final run
    test_dynamicmodule_reuse_2()

    def test_dynamicmodule_docstring():
        with q as quoted:
            """This becomes the module docstring in `run`."""
            x = 42  # important thing is whether the code ran.  # noqa: F841
        module = run(quoted)
        assert module.x == 42
        assert module.__doc__ == """This becomes the module docstring in `run`."""

        source = dedent("""
        '''This becomes the module docstring in `run`.'''
        x = 42
        """)
        module = run(source)
        assert module.x == 42
        assert module.__doc__ == """This becomes the module docstring in `run`."""
    test_dynamicmodule_docstring()

    # defining macros in a dynamically created module and then importing them later
    def test_dynamicmodule_macros_1():
        mymacros = create_module("mymacros")
        with q as quoted:
            # Important to import this here to use it below. This is effectively a
            # module top level, so `mcpyrate` (for `mcpyrate.quotes`, used by the
            # run-time part of `q`) won't be defined at run time in this code if
            # this import is missing.
            from mcpyrate.quotes import macros, q  # noqa: F811, F401

            def testmacro(tree, **kw):
                return q["success"]
        run(quoted, mymacros)

        with q as quoted:
            from mymacros import macros, testmacro  # noqa: F811, F401
            assert testmacro["blah"] == "success"
        module = run(quoted)  # noqa: F841, we don't need `module` here, but having it reminds what the return value is.
    test_dynamicmodule_macros_1()

    # how to avoid module name conflicts in the above scenario
    def test_dynamicmodule_macros_2():
        modname = gensym("mymacros")
        mymacros = create_module(modname)
        with q as quoted:
            from mcpyrate.quotes import macros, q  # noqa: F811, F401
            def testmacro(tree, **kw):
                return q["success"]
        run(quoted, mymacros)

        with q as quoted:
            from _xxx_ import macros, testmacro  # noqa: F811, F401
            assert testmacro["blah"] == "success"
        rename("_xxx_", modname, quoted)
        module = run(quoted)  # noqa: F841
    test_dynamicmodule_macros_2()

    def test_dynamicmodule_multiphase():
        with q as quoted:
            # This is a module top level for `run`, so...
            from mcpyrate.multiphase import macros, phase  # noqa: F811
            # from mcpyrate.debug import macros, step_phases  # uncomment if you want to see the phases

            with phase[1]:
                from mcpyrate.quotes import macros, q  # noqa: F811, F401

                def testmacro(tree, **kw):
                    return q["success"]

            # Here __self__ refers to the higher-phase temporary module
            # for the dynamically generated module.
            from __self__ import macros, testmacro  # noqa: F811, F401
            assert testmacro["blah"] == "success"

        from ..compiler import _fill_dummy_location_info
        _fill_dummy_location_info(quoted)
        module = run(quoted)  # noqa: F841

        # TODO: improve the compiler so we don't need to fill in dummy locations here
        #
        # The problem here is that during `multiphase_expand`, the temporary modules
        # for the higher phases are compiled directly with the built-in `compile`,
        # whereas the dummy location filler is in `mcpyrate.compiler._compile`.
        #
        # Technically that's almost a drop-in replacement, but using `_compile`
        # there leads to allowing `with phase` in positions where it's not
        # understood by other parts of `mcpyrate` (particularly `path_stats`
        # in the importer). In the long run that seems the right direction,
        # but we should first think about the implications.
        #
        # Also, filling useless dummy locations is stupid. But the AST only has
        # `lineno` and `col_offset`. It has no `filename`, so it assumes that:
        #
        #   1. an AST comes from a single source file
        #
        # `types.CodeType` only has `co_filename`, `co_firstlineno`, `co_lnotab`,
        # so it might additionally assume that:
        #
        #   2. the source code is in one contiguous block
        #
        # (There's `co_lnotab`, which isn't documented that well, so it may be
        #  it doesn't make that additional assumption.)
        #
        # Python's support for source location info just doesn't lend itself
        # well to a use scenario where an AST is assembled from pieces defined
        # in several locations, then passed around, and finally compiled and
        # run at a yet another location.
        #
        #   https://greentreesnakes.readthedocs.io/en/latest/tofrom.html#fix-locations
        #   https://docs.python.org/3/library/types.html#types.CodeType
        #   https://docs.python.org/3/library/inspect.html#types-and-members
        #
        # As long as there is only one location that defines the whole snippet
        # in one go, and the `run` appears in that same file, we could add a mode
        # to `q` to fill in `lineno` and `col_offset` from the use site of `q`.
        #
        # (Note that for regular use of `q`, for constructing output ASTs in
        #  macros, we must not do that, precisely because the AST will be used
        #  somewhere else - namely at the use site *for the macro that used `q`*.
        #  For that use case, the right solution is the current one - leave out
        #  the source location info, and let the expander auto-fill it.)
        #
        # But even that runs into practical problems, because we have also
        # `mcpyrate.quotes.unastify`, and especially hygienic macro capture
        # is essentially a one-way operation (so passing around the original
        # source location for that may be difficult so that it survives an
        # astify-unastify-astify roundtrip).
        #
        # So, practically, perhaps we should just move to use `_compile`
        # in `multiphase_expand`, hunt down and resolve the implications,
        # and leave the source location issue unresolved for now.
    test_dynamicmodule_multiphase()

    print("All tests PASSED")

if __name__ == '__main__':
    test()
