# -*- coding: utf-8; -*-
'''Importer (finder/loader) customizations, to inject the macro expander.'''

__all__ = ['source_to_xcode', 'path_xstats', 'invalidate_xcaches']

import ast
import importlib.util
from importlib.machinery import FileFinder, SourceFileLoader
import tokenize
import os
import pickle
import sys

from .core import MacroExpansionError
from .dialects import expand_dialects
from .expander import find_macros, expand_macros
from .coreutils import resolve_package, ismacroimport
from .markers import get_markers
from .unparser import unparse_with_fallbacks
from .utils import format_location


def source_to_xcode(self, data, path, *, _optimize=-1):
    '''[mcpyrate] Expand dialects, then expand macros, then compile.

    Intercepts the source to bytecode transformation.
    '''
    tree = expand_dialects(data, filename=path)

    module_macro_bindings = find_macros(tree, filename=path)
    expansion = expand_macros(tree, bindings=module_macro_bindings, filename=path)

    remaining_markers = get_markers(expansion)
    if remaining_markers:
        raise MacroExpansionError("{path}: AST markers remaining after expansion: {remaining_markers}")

    return compile(expansion, path, 'exec', dont_inherit=True, optimize=_optimize)


# TODO: Support PEP552 (Deterministic pycs). Need to intercept source file hashing, too.
# TODO: https://www.python.org/dev/peps/pep-0552/
_path_stats = SourceFileLoader.path_stats
_xstats_cache = {}
def path_xstats(self, path):
    '''[mcpyrate] Compute a `.py` source file's mtime, accounting for macro-imports.

    Beside the source file `path` itself, we look at any macro definition files
    the source file imports macros from, recursively, in a `make`-like fashion.

    The mtime is the latest of those of `path` and its macro-dependencies,
    considered recursively, so that if any macro definition anywhere in the
    macro-dependency tree of `path` is changed, Python will treat the source
    file `path` as "changed", thus re-expanding and recompiling `path` (hence,
    updating the corresponding `.pyc`).

    If `path` does not end in `.py`, delegate to the standard implementation
    of `SourceFileLoader.path_stats`.
    '''
    if not path.endswith(".py"):
        return _path_stats(path)
    if path in _xstats_cache:
        return _xstats_cache[path]

    stat_result = os.stat(path)

    # Try for cached macro-import statements for `path` to avoid the parse cost.
    #
    # This is a single node in the dependency graph; the result depends only
    # on the content of the source file `path` itself. So we invalidate the
    # macro-import statement cache for `path` based on the mtime of `path` only.
    #
    # For a given source file `path`, the `.pyc` sometimes becomes newer than
    # the macro-dependency cache. This is normal. Unlike the bytecode, the
    # macro-dependency cache only needs to be refreshed when the text of the
    # source file `path` changes.
    #
    # So if some of the macro-dependency source files have changed (so `path`
    # must be re-expanded and recompiled), but `path` itself hasn't, the text
    # of the source file `path` will still have the same macro-imports it did
    # last time.
    #
    pycpath = importlib.util.cache_from_source(path)
    if pycpath.endswith(".pyc"):
        pycpath = pycpath[:-4]
    importcachepath = pycpath + ".mcpyrate.pickle"
    try:
        cache_valid = False
        with open(importcachepath, "rb") as importcachefile:
            data = pickle.load(importcachefile)
        if data["st_mtime_ns"] == stat_result.st_mtime_ns:
            cache_valid = True
    except Exception:
        pass

    if cache_valid:
        macro_and_dialect_imports = data["macroimports"] + data["dialectimports"]
        has_relative_macroimports = data["has_relative_macroimports"]
    else:
        # This can be slow, the point of `.pyc` is to avoid the parse-and-compile cost.
        # We do save the macro-expansion cost, though, and that's likely much more expensive.
        #
        # TODO: Dialects may inject imports in the template that the dialect transformer itself
        # TODO: doesn't need. How to detect those? Regex-search the source text?
        with tokenize.open(path) as sourcefile:
            tree = ast.parse(sourcefile.read())
        macroimports = [stmt for stmt in tree.body if ismacroimport(stmt)]
        dialectimports = [stmt for stmt in tree.body if ismacroimport(stmt, magicname="dialects")]

        macro_and_dialect_imports = macroimports + dialectimports
        has_relative_macroimports = any(macroimport.level for macroimport in macro_and_dialect_imports)

        # macro-import statement cache goes with the .pyc
        if not sys.dont_write_bytecode:
            data = {"st_mtime_ns": stat_result.st_mtime_ns,
                    "macroimports": macroimports,
                    "dialectimports": dialectimports,
                    "has_relative_macroimports": has_relative_macroimports}
            try:
                with open(importcachepath, "wb") as importcachefile:
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
            approx_sourcecode = unparse_with_fallbacks(macroimport)
            loc = format_location(path, macroimport, approx_sourcecode)
            raise SyntaxError(f"{loc}\nmissing module name in macro-import")
        module_absname = importlib.util.resolve_name('.' * macroimport.level + macroimport.module, package_absname)

        spec = importlib.util.find_spec(module_absname)
        origin = spec.origin
        stats = path_xstats(self, origin)
        mtimes.append(stats['mtime'])

    mtime = stat_result.st_mtime_ns * 1e-9
    # size = stat_result.st_size
    mtimes.append(mtime)

    result = {'mtime': max(mtimes)}  # and sum(sizes)? OTOH, as of Python 3.8, only 'mtime' is mandatory.
    if sys.version_info >= (3, 7, 0):
        # Docs say `size` is optional, and this is correct in 3.6 (and in PyPy3 7.3.0):
        # https://docs.python.org/3/library/importlib.html#importlib.abc.SourceLoader.path_stats
        #
        # but in 3.7 and later, the implementation is expecting at least a `None` there,
        # if the `size` is not used. See `get_code` in:
        # https://github.com/python/cpython/blob/master/Lib/importlib/_bootstrap_external.py
        result['size'] = None
    _xstats_cache[path] = result
    return result


_invalidate_caches = FileFinder.invalidate_caches
def invalidate_xcaches(self):
    '''[mcpyrate] Clear the macro dependency tree cache.

    Then delegate to the standard implementation of `FileFinder.invalidate_caches`.
    '''
    _xstats_cache.clear()
    return _invalidate_caches(self)
