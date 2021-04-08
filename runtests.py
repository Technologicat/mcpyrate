# -*- coding: utf-8 -*-
"""Run all tests for `mcpyrate`."""

import os
import re
import sys
import traceback
from importlib import import_module

from mcpyrate.colorizer import ColorScheme, colorize
from mcpyrate.pycachecleaner import deletepycachedirs

import mcpyrate.activate  # noqa: F401, this enables the macro expander.


def listtestmodules(path):
    testfiles = listtestfiles(path)
    testmodules = [modname(path, fn) for fn in testfiles]
    return list(sorted(testmodules))

def listtestfiles(path, prefix="test_", suffix=".py"):
    return [fn for fn in os.listdir(path) if fn.startswith(prefix) and fn.endswith(suffix)]

def modname(path, filename):  # some/dir/mod.py --> some.dir.mod
    modpath = re.sub(os.path.sep, r".", path)
    themod = re.sub(r"\.py$", r"", filename)
    return ".".join([modpath, themod])

def main():
    errors = 0
    testsets = (("main", os.path.join("mcpyrate", "test")),
                ("repl", os.path.join("mcpyrate", "repl", "test")))
    for tsname, path in testsets:
        if not os.path.isdir(path):
            continue
        modnames = listtestmodules(path)
        deletepycachedirs(path)
        for m in modnames:
            try:
                # TODO: We're not inside a package, so we currently can't use a relative import.
                # TODO: So we just hope this resolves to the local `mcpyrate` source code,
                # TODO: not to an installed copy of the library.
                print(colorize(f"Testing '{m}'...", ColorScheme.TESTHEADING),
                      file=sys.stderr)
                mod = import_module(m)
                mod.runtests()
            except ImportError:
                print(colorize(f"ERROR: failed to load '{m}'", ColorScheme.TESTERROR),
                      file=sys.stderr)
                traceback.print_exc()
                errors += 1
            except AssertionError:
                print(colorize(f"ERROR: at least one test failed in '{m}'", ColorScheme.TESTFAIL),
                      file=sys.stderr)
                traceback.print_exc()
                errors += 1
    print(colorize("Testing finished.", ColorScheme.TESTHEADING))
    all_passed = (errors == 0)
    return all_passed

if __name__ == '__main__':
    if not main():
        sys.exit(1)  # pragma: no cover, this only runs when the tests fail.
