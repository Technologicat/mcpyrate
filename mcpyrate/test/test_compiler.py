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
import sys
from textwrap import dedent

# `expand` and `compile` aren't tested separately, but `run` is built on them, so meh.
from ..compiler import create_module, temporary_module, run
from ..utils import gensym, rename


def runtests():
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

        # We must clean up so that the second-pass test works too.
        try:
            del sys.modules["flip.flop"]
            del sys.modules["flip"]
        except KeyError:
            pass
    test_create_module()

    # `temporary_module` is like `create_module`, except it destroys the module when the context exits.
    def test_temporary_module():
        with temporary_module("flip") as flip:
            with temporary_module("flip.flop") as flop:
                assert flip.__package__ is None
                assert flop.__package__ == "flip"
                assert flip.flop is flop  # submodule is added to the package namespace
                assert "flip.flop" in sys.modules
            assert "flip.flop" not in sys.modules  # auto-deletion
            assert not hasattr(flip, "flop")  # auto-removed from package namespace, too
            assert "flip" in sys.modules
        assert "flip" not in sys.modules
    test_temporary_module()

    def test_dynamicmodule_from_source():
        with temporary_module() as module:
            run("x = 21", module)
            assert module.x == 21

            run("x = 2 * x", module)
            assert module.x == 42

            run("x = 2 * x", module)
            assert module.x == 84
    test_dynamicmodule_from_source()

    def test_dynamicmodule_from_ast():
        # The module acts essentially as a namespace.
        with temporary_module() as module:
            with q as quoted:
                x = 21  # noqa: F841, it's used in the surrounding context.
            run(quoted, module)
            assert module.x == 21

            with q as quoted:
                x = 2 * x
            run(quoted, module)
            assert module.x == 42

            run(quoted, module)
            assert module.x == 84
    test_dynamicmodule_from_ast()

    def test_dynamicmodule_customname():
        with temporary_module("mymod", filename="<my module>") as mymodule:
            with q as quoted:
                assert __name__ == "mymod"
                assert __file__ == "<my module>"
            run(quoted, mymodule)
    test_dynamicmodule_customname()

    # using the same temporary module for lots of runs
    def test_dynamicmodule_reuse_1():
        with temporary_module(gensym("temporary_module")) as tempmodule:
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
        with temporary_module(gensym("temporary_module")) as tempmodule:
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
        with temporary_module() as module:
            with q as quoted:
                """This becomes the module docstring in `run`."""
                x = 42  # important thing is whether the code ran.  # noqa: F841
            run(quoted, module)
            assert module.x == 42
            assert module.__doc__ == """This becomes the module docstring in `run`."""

        with temporary_module() as module:
            source = dedent("""
            '''This becomes the module docstring in `run`.'''
            x = 42
            """)
            run(source, module)
            assert module.x == 42
            assert module.__doc__ == """This becomes the module docstring in `run`."""
    test_dynamicmodule_docstring()

    # defining macros in a dynamically created module and then importing them later
    def test_dynamicmodule_macros_1():
        try:
            mymacros = create_module("mymacros")
            with q as quoted:
                # Important to import this here to use it below. This is quoted code,
                # so the `q` in `testmacro` below isn't expanded in the surrounding context.
                from mcpyrate.quotes import macros, q  # noqa: F811, F401

                def testmacro(tree, **kw):
                    return q["success"]
            run(quoted, mymacros)

            with q as quoted:
                from mymacros import macros, testmacro  # noqa: F811, F401
                assert testmacro["blah"] == "success"
            module = run(quoted)  # noqa: F841, we don't need `module` here, but having it reminds what the return value is.
        finally:
            try:
                del sys.modules[mymacros.__name__]
                del sys.modules[module.__name__]
            except KeyError:
                pass
    test_dynamicmodule_macros_1()

    # how to avoid module name conflicts in the above scenario
    def test_dynamicmodule_macros_2():
        try:
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
        finally:
            try:
                del sys.modules[mymacros.__name__]
                del sys.modules[module.__name__]
            except KeyError:
                pass
    test_dynamicmodule_macros_2()

    def test_dynamicmodule_multiphase():
        try:
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
            module = run(quoted)  # noqa: F841
        finally:
            try:
                del sys.modules[module.__name__]
            except KeyError:
                pass
    test_dynamicmodule_multiphase()

    def test_futureimports_multiphase_nodocstring():
        try:
            source = dedent("""
            from __future__ import annotations
            from mcpyrate.multiphase import macros, phase
            with phase[1]:
                x = 42
            """)
            module = run(source)
        finally:
            try:
                del sys.modules[module.__name__]
            except KeyError:
                pass
    test_futureimports_multiphase_nodocstring()

    def test_futureimports_multiphase_withdocstring():
        try:
            source = dedent("""
            '''Works with a module docstring, too.'''
            from __future__ import annotations
            from mcpyrate.multiphase import macros, phase
            with phase[1]:
                x = 42
            """)
            module = run(source)
        finally:
            try:
                del sys.modules[module.__name__]
            except KeyError:
                pass
    test_futureimports_multiphase_withdocstring()

if __name__ == '__main__':
    runtests()
