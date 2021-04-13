# -*- coding: utf-8 -*-
"""Run all tests for `mcpyrate`."""

import os
import re
import subprocess
import sys
import traceback
from importlib import import_module

from mcpyrate.colorizer import ColorScheme, colorize
from mcpyrate.pycachecleaner import deletepycachedirs

import mcpyrate.activate  # noqa: F401, this enables the macro expander.

# --------------------------------------------------------------------------------

def filename_to_modulename(path, filename):
    """Convert .py filename to module name.

    Example::
        "some/dir", "mod.py" --> "some.dir.mod"
    """
    modpath = re.sub(os.path.sep, r".", path)
    themod = re.sub(r"\.py$", r"", filename)
    return ".".join([modpath, themod])

def filenames_to_modulenames(path, filenames):
    """Convert .py filenames to module names.

    Example::
        "some/dir", ["mod1.py", "mod2.py", ...] --> ["some.dir.mod1", "some.dir.mod2", ...]
    """
    return list(sorted(filename_to_modulename(path, fn) for fn in filenames))

# --------------------------------------------------------------------------------
# In the `mcpyrate` codebase, test modules are placed in "test/" subfolders,
# and follow the naming pattern "test_*.py".

def discovertestdirectories(root):
    pattern = f"{os.path.sep}test"
    out = []
    for path, dirs, files in os.walk(root):
        if path.endswith(pattern):
            out.append(path)
    return list(sorted(out))

def discovertestfiles_in(path):
    return [fn for fn in os.listdir(path) if fn.startswith("test_") and fn.endswith(".py")]

# --------------------------------------------------------------------------------
# In the `mcpyrate` codebase, demos live in the "demo/" subfolder of the project top level.
#
# Each demo is either:
#  - A directory with a main script "demo.py" and a bunch of auxiliary files
#    (where the auxiliary files are not meant to be called by the runner).
#    - Some demos may have a `run.py` for running with bare `python3`; doesn't matter here.
#  - A single .py file, possibly in the same directory with other single-file demos.

def discoverdemofiles(root):
    out = []
    for path, dirs, files in os.walk(root):
        demos = discoverdemofiles_in(path)
        if demos:
            relpath = os.path.relpath(path)
            out.extend(os.path.join(relpath, filename) for filename in demos)
        # don't descend into internal subdirectories of individual demos
        if "demo.py" in files:
            dirs.clear()
    return list(sorted(out))

# def discoverdemomodules(root):
#     out = []
#     for path, dirs, files in os.walk(root):
#         demos = filenames_to_modulenames(os.path.relpath(path), discoverdemofiles_in(path))
#         if demos:
#             out.extend(demos)
#     return out

def discoverdemofiles_in(path):
    if os.path.isfile(os.path.join(path, "demo.py")):
        return ["demo.py"]
    return [fn for fn in os.listdir(path) if fn.endswith(".py")]

# --------------------------------------------------------------------------------

def runtests(clear_bytecode_cache=True):
    cache_note = "Bytecode cache will be cleared." if clear_bytecode_cache else "Using existing bytecode."
    print(colorize(f"Testing started. {cache_note}", ColorScheme.TESTHEADING), file=sys.stderr)
    errors = 0
    for path in discovertestdirectories("."):
        modnames = filenames_to_modulenames(os.path.relpath(path), discovertestfiles_in(path))
        if clear_bytecode_cache:
            deletepycachedirs(path)
        for m in modnames:
            try:
                # TODO: We're not inside a package, so we can't use a relative import.
                # TODO: We just hope this resolves to the local `mcpyrate` source code,
                # TODO: not to an installed copy of the library.
                print(colorize(f"  Running module '{m}'...", ColorScheme.TESTHEADING),
                      file=sys.stderr)
                mod = import_module(m)
                mod.runtests()
                print(colorize(f"    PASS '{m}'", ColorScheme.TESTPASS), file=sys.stderr)
            except ImportError:
                print(colorize(f"    ERROR '{m}': import failed", ColorScheme.TESTERROR),
                      file=sys.stderr)
                traceback.print_exc()
                errors += 1
            except AssertionError:
                print(colorize(f"    FAIL '{m}': at least one test failed",
                               ColorScheme.TESTFAIL),
                      file=sys.stderr)
                traceback.print_exc()
                errors += 1
            except Exception:
                print(colorize(f"    ERROR '{m}': unexpected exception", ColorScheme.TESTERROR),
                      file=sys.stderr)
                traceback.print_exc()
                errors += 1
    print(colorize("Testing finished.", ColorScheme.TESTHEADING), file=sys.stderr)
    all_passed = (errors == 0)
    return all_passed


# This just checks that all the demos run without crashing on the version being tested,
# so that they are likely to be up to date.
# def rundemos(clear_bytecode_cache=True):
#     cache_note = "Bytecode cache will be cleared." if clear_bytecode_cache else "Using existing bytecode."
#     print(colorize(f"Demos started. {cache_note}", ColorScheme.TESTHEADING), file=sys.stderr)
#     errors = 0
#     demomodules = discoverdemomodules("demo")
#     if clear_bytecode_cache:
#         deletepycachedirs("demo")
#     for m in demomodules:
#         print(colorize(f"  Running '{m}'...", ColorScheme.TESTHEADING),
#               file=sys.stderr)
#         mod = import_module(m)
#     print(colorize("Demos finished.", ColorScheme.TESTHEADING), file=sys.stderr)
#     all_passed = (errors == 0)
#     return all_passed

# UGH! We can't currently import demos as modules, since they may depend on other modules
# in their containing directory. So let's run them like a shell script would.
# (Alternatively, we could tweak `sys.path`.)
def rundemos(clear_bytecode_cache=True):
    cache_note = "Bytecode cache will be cleared." if clear_bytecode_cache else "Using existing bytecode."
    print(colorize(f"Demos started. {cache_note}", ColorScheme.TESTHEADING), file=sys.stderr)
    errors = 0
    demofiles = discoverdemofiles("demo")
    if clear_bytecode_cache:
        deletepycachedirs("demo")
    for fn in demofiles:
        print(colorize(f"  Running file '{fn}'...", ColorScheme.TESTHEADING),
              file=sys.stderr)
        cmd = ['/usr/bin/env',
               'python3',
               '-m', 'mcpyrate.repl.macropython',
               fn]
        try:
            subprocess.run(cmd, check=True,
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(colorize(f"    PASS '{fn}'", ColorScheme.TESTPASS), file=sys.stderr)
        except subprocess.CalledProcessError as err:
            print(colorize(f"    FAIL '{fn}': subprocess returned non-zero exit status",
                           ColorScheme.TESTFAIL),
                  file=sys.stderr)
            traceback.print_exc()
            print(err.stderr.decode("utf-8"), file=sys.stderr)
            errors += 1
    print(colorize("Demos finished.", ColorScheme.TESTHEADING), file=sys.stderr)
    all_passed = (errors == 0)
    return all_passed

if __name__ == '__main__':
    t1 = runtests(True)
    t2 = runtests(False)
    t3 = rundemos(True)
    t4 = rundemos(False)
    if not (t1 and t2 and t3 and t4):
        sys.exit(1)  # pragma: no cover, this only runs when the tests fail.
