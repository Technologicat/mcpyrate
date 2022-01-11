# -*- coding: utf-8; -*-
"""Importer (finder/loader) customizations, to inject the dialect and macro expanders."""

__all__ = ["source_to_xcode", "path_xstats", "path_stats"]

import ast
import distutils.sysconfig
from importlib.machinery import SourceFileLoader
import importlib.util
import os
import pickle
import sys
import tokenize

from . import compiler
from .coreutils import resolve_package, ismacroimport
from .multiphase import iswithphase
from .unparser import unparse_with_fallbacks
from .utils import format_location


def source_to_xcode(self, data, path, *, _optimize=-1):
    """[mcpyrate] Import hook for the source to bytecode transformation.

    This function is monkey-patched into `importlib.machinery.SourceFileLoader`.
    """
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
    """[mcpyrate] Import hook to compute mtime, accounting for macro-imports.

    This function is monkey-patched into `importlib.machinery.SourceFileLoader`.
    For direct use as an API function, use `mcpyrate.importer.path_stats`.

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
    return path_stats(path)


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


def path_stats(path, _stats_cache=None):
    """[mcpyrate] Compute a `.py` source file's mtime, accounting for macro-imports.

    This is a public API function for direct use, if you have a `.py` file and
    you want to know its macro-enabled mtime.

    Beside the source file `path` itself, we look at any macro definition files
    the source file imports macros from, recursively, in a `make`-like fashion.
    Dialect-imports, if any, are treated the same way.

    `_stats_cache` is used internally to speed up the computation, in case the
    dependency graph hits the same source file multiple times.
    """
    if _stats_cache is None:
        _stats_cache = {}
    if path in _stats_cache:
        return _stats_cache[path]

    stat_result = os.stat(path)

    # Try for cached macro-import statements for `path` to avoid the parse cost.
    #
    # This is a single node in the dependency graph; the result depends only
    # on the content of the source file `path` itself. So we invalidate the
    # macro-import statement cache file for `path` based on the mtime of `path` only.
    #
    # For a given source file `path`, the `.pyc` sometimes becomes newer than
    # the macro-import statement cache. This is normal. Unlike the bytecode, the
    # macro-import statement cache only needs to be refreshed when the text of the
    # source file `path` changes.
    #
    # So if some of the macro-dependency source files have changed (so `path`
    # must be re-expanded and recompiled), but `path` itself hasn't, the text
    # of the source file `path` will still have the same macro-imports it did
    # last time.
    #
    pyc_path = importlib.util.cache_from_source(path)
    if pyc_path.endswith(".pyc"):
        pyc_path = pyc_path[:-4]
    macroimport_cache_path = pyc_path + ".mcpyrate.pickle"
    try:
        macroimport_cache_valid = False
        with open(macroimport_cache_path, "rb") as importcachefile:
            data = pickle.load(importcachefile)
        if data["st_mtime_ns"] == stat_result.st_mtime_ns:
            macroimport_cache_valid = True
    except Exception:
        pass

    if macroimport_cache_valid:
        macro_and_dialect_imports = data["macroimports"] + data["dialectimports"]
        has_relative_macroimports = data["has_relative_macroimports"]
    else:
        # This can be slow, the point of `.pyc` is to avoid the parse-and-compile cost.
        # We do save the macro-expansion cost, though, and that's likely much more expensive.
        #
        # TODO: Dialects may inject macro-imports in the template that the dialect transformer itself
        # TODO: doesn't need. How to detect those? Regex-search the source text?
        # TODO: Or just document it, that the dialect definition module *must* macro-import those macros
        # TODO: even if it just injects them in the template?
        with tokenize.open(path) as sourcefile:
            tree = ast.parse(sourcefile.read(), filename=path)

        macroimports = []
        dialectimports = []
        def scan(tree):
            for stmt in tree.body:
                if ismacroimport(stmt):
                    macroimports.append(stmt)
                elif ismacroimport(stmt, magicname="dialects"):
                    dialectimports.append(stmt)
                elif iswithphase(stmt, filename=path):  # for multi-phase compilation: scan also inside top-level `with phase`
                    scan(stmt)
        scan(tree)

        macro_and_dialect_imports = macroimports + dialectimports
        has_relative_macroimports = any(macroimport.level for macroimport in macro_and_dialect_imports)

        # macro-import statement cache goes with the .pyc
        if not sys.dont_write_bytecode:
            data = {"st_mtime_ns": stat_result.st_mtime_ns,
                    "macroimports": macroimports,
                    "dialectimports": dialectimports,
                    "has_relative_macroimports": has_relative_macroimports}
            try:
                with open(macroimport_cache_path, "wb") as importcachefile:
                    pickle.dump(data, importcachefile)
            except Exception:
                pass

    # The rest of the lookup process depends on the configuration of the currently
    # running Python, particularly its `sys.path`, so we do it dynamically.
    #
    # TODO: some duplication with code in mcpyrate.coreutils.get_macros, including the error messages.
    package_absname = None
    if has_relative_macroimports:
        try:
            package_absname = resolve_package(path)
        except (ValueError, ImportError) as err:
            raise ImportError(f"while resolving absolute package name of {path}, which uses relative macro-imports") from err

    mtimes = []
    for macroimport in macro_and_dialect_imports:
        if macroimport.module is None:
            approx_sourcecode = unparse_with_fallbacks(macroimport, debug=True, color=True)
            loc = format_location(path, macroimport, approx_sourcecode)
            raise SyntaxError(f"{loc}\nmissing module name in macro-import")
        module_absname = importlib.util.resolve_name('.' * macroimport.level + macroimport.module, package_absname)

        spec = importlib.util.find_spec(module_absname)
        if spec:  # self-macro-imports have no `spec`, and that's fine.
            origin = spec.origin
            stats = path_stats(origin, _stats_cache)
            mtimes.append(stats["mtime"])

    mtime = stat_result.st_mtime_ns * 1e-9
    # size = stat_result.st_size
    mtimes.append(mtime)

    result = {"mtime": max(mtimes)}  # and sum(sizes)? OTOH, as of Python 3.8, only 'mtime' is mandatory.
    if sys.version_info >= (3, 7, 0):
        # Docs say `size` is optional, and this is correct in 3.6 (and in PyPy3 7.3.0):
        # https://docs.python.org/3/library/importlib.html#importlib.abc.SourceLoader.path_stats
        #
        # but in 3.7 and later, the implementation is expecting at least a `None` there,
        # if the `size` is not used. See `get_code` in:
        # https://github.com/python/cpython/blob/master/Lib/importlib/_bootstrap_external.py
        result["size"] = None
    _stats_cache[path] = result
    return result
