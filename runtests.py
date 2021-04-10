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


# "some/dir", "mod.py" --> "some.dir.mod"
def filename_to_modulename(path, filename):
    modpath = re.sub(os.path.sep, r".", path)
    themod = re.sub(r"\.py$", r"", filename)
    return ".".join([modpath, themod])

# "some/dir", ["mod1.py", "mod2.py", ...] --> ["some.dir.mod1", "some.dir.mod2", ...]
def filenames_to_modulenames(path, filenames):
    return list(sorted(filename_to_modulename(path, fn) for fn in filenames))


# In the `mcpyrate` codebase, tests follow the naming pattern "test_*.py".
def listtestfiles(path, prefix="test_", suffix=".py"):
    return [fn for fn in os.listdir(path) if fn.startswith(prefix) and fn.endswith(suffix)]

# In the `mcpyrate` codebase, a demo is either:
#  - A directory with a main script "demo.py" and a bunch of auxiliary files
#    (where the auxiliary files are not meant to be called by the runner).
#    - Some demos may have a `run.py` for running with bare `python3`; doesn't matter here.
#  - A single .py file, possibly in the same directory with other single-file demos.
def listdemofiles(path):
    if os.path.isfile(os.path.join(path, "demo.py")):
        return ["demo.py"]
    return [fn for fn in os.listdir(path) if fn.endswith(".py")]


def listalldemofiles(demoroot):
    out = []
    for path, dirs, files in os.walk(demoroot):
        demos = listdemofiles(path)
        if demos:
            out.extend(os.path.join(path, filename) for filename in demos)
    return list(sorted(out))

# def listalldemomodules(demoroot):
#     out = []
#     for path, dirs, files in os.walk(demoroot):
#         demos = filenames_to_modulenames(path, listdemofiles(path))
#         if demos:
#             out.extend(demos)
#     return out


def runtests():
    print(colorize("Testing started.", ColorScheme.TESTHEADING), file=sys.stderr)
    errors = 0
    # Each submodule of `mcpyrate` should have an entry here, regardless of if it currently has tests or not.
    testsets = (("main", os.path.join("mcpyrate", "test")),
                ("repl", os.path.join("mcpyrate", "repl", "test")))
    for testsetname, path in testsets:
        if not os.path.isdir(path):  # skip empty testsets
            continue
        modnames = filenames_to_modulenames(path, listtestfiles(path))
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
# def rundemos():
#     print(colorize("Demos started.", ColorScheme.TESTHEADING), file=sys.stderr)
#     errors = 0
#     demomodules = listalldemomodules("demo")
#     deletepycachedirs("demo")
#     for m in demomodules:
#         print(colorize(f"  Running '{m}'...", ColorScheme.TESTHEADING),
#               file=sys.stderr)
#         mod = import_module(m)
#     print(colorize("Demos finished.", ColorScheme.TESTHEADING), file=sys.stderr)
#     all_passed = (errors == 0)
#     return all_passed

# UGH! We can't currently import demos as modules, since they may depend on other modules
# in their containing directory. So let's run them like a shell script would.
def rundemos():
    print(colorize("Demos started.", ColorScheme.TESTHEADING), file=sys.stderr)
    errors = 0
    demofiles = listalldemofiles("demo")
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
    if not (runtests() and rundemos()):
        sys.exit(1)  # pragma: no cover, this only runs when the tests fail.
