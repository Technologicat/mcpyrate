# -*- coding: utf-8; -*-
"""Importer (finder/loader) customizations, to inject the dialect and macro expanders."""

__all__ = ["source_to_xcode", "path_xstats"]

import distutils.sysconfig
from importlib.machinery import SourceFileLoader
import os

from . import compiler


def source_to_xcode(self, data, path, *, _optimize=-1):
    """[mcpyrate] Import hook for the source to bytecode transformation."""
    # `self.name` is absolute dotted module name, see `importlib.machinery.FileLoader`.
    return compiler.compile(data, filename=path, self_module=self.name)


# TODO: Support PEP552 (Deterministic pycs). Need to intercept source file hashing, too.
# TODO: https://www.python.org/dev/peps/pep-0552/
#
# Note about caching. Look at:
#   https://github.com/python/cpython/blob/master/Lib/importlib/__init__.py
#   https://github.com/python/cpython/blob/master/Lib/importlib/_bootstrap.py
#   https://github.com/python/cpython/blob/master/Lib/importlib/_bootstrap_external.py
#
# As of Python 3.9:
#   - The function `importlib.reload` (from `__init__.py`) eventually calls `_bootstrap._exec`.
#   - `_bootstrap._exec` takes the loader from the spec, and calls its `exec_module` method.
#   - `SourceFileLoader` defaults to the implementation of `_bootstrap_external._LoaderBasics.exec_module`,
#     which calls the `get_code` method of the actual loader class.
#   - `SourceFileLoader` inherits its `get_code` method from `SourceLoader`, which inherits from `_LoaderBasics`.
#   - `SourceLoader.get_code` calls `path_stats` (hence our `path_xstats`,
#     which replaces that), which returns the relevant timestamp; it then
#     validates the bytecode cache against that timestamp (if in timestamp mode).
#
# The conclusion is, the timestamp we return from `path_xstats` determines
# whether `reload` even attempts to actually reload the module!
#
# To compute the relevant timestamp, we must examine not only the target file,
# but also its macro-dependencies (recursively). The easy thing to do - to
# facilitate reloading for REPL use - is to not keep a global timestamp cache,
# but only cache the timestamps during a single call of `path_xstats`, so if
# the same dependency appears again at another place in the graph, we can get
# its timestamp from the timestamp cache.
#
_stdlib_path_stats = SourceFileLoader.path_stats
def path_xstats(self, path):
    """[mcpyrate] Import hook that overrides mtime computation, accounting for macro-imports.

    The mtime is the latest of those of `path` and its macro-dependencies,
    considered recursively, so that if any macro definition anywhere in the
    macro-dependency tree of `path` is changed, Python will treat the source
    file `path` as "changed", thus re-expanding and recompiling `path` (hence,
    updating the corresponding `.pyc`).

    If `path` does not end in `.py`, or alternatively, if it points to a `.py` file that
    is part of Python's standard library, we delegate to the standard implementation of
    `SourceFileLoader.path_stats`.
    """
    # Ignore stdlib, it's big and doesn't use macros. Allows faster error
    # exits, because an uncaught exception causes Python to load a ton of
    # .py based stdlib modules. Also makes `macropython -i` start faster.
    if path in _stdlib_sourcefile_paths or not path.endswith(".py"):
        return _stdlib_path_stats(self, path)
    return compiler.path_stats(path)


def _detect_stdlib_sourcefile_paths():
    """Return a set of full paths of `.py` files that are part of Python's standard library."""
    # Adapted from StackOverflow answer by Adam Spiers, https://stackoverflow.com/a/8992937
    # Note we don't want to get module names, but full paths to `.py` files.
    stdlib_dir = distutils.sysconfig.get_python_lib(standard_lib=True)
    paths = set()
    for root, dirs, files in os.walk(stdlib_dir):
        for filename in files:
            if filename[-3:] == ".py":
                paths.add(os.path.join(root, filename))
    return paths
_stdlib_sourcefile_paths = _detect_stdlib_sourcefile_paths()
