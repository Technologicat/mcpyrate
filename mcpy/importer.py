# -*- coding: utf-8; -*-
'''Importer (finder/loader) customizations, to inject the macro expander.'''

__all__ = ['resolve_package',
           'source_to_xcode', 'path_xstats', 'invalidate_xcaches']

import ast
import tokenize
import pathlib
import sys
import os
import importlib.util
from importlib.machinery import FileFinder, SourceFileLoader
from .core import MacroExpansionError
from . import expander
from .markers import get_markers

def resolve_package(filename):  # TODO: for now, `guess_package`, really. Check the docs again.
    """Resolve absolute Python package name for .py source file `filename`.

    If `filename` is at the top level of the matching entry in `sys.path`, raises `ImportError`.
    If `filename` is not under any directory in `sys.path`, raises `ValueError`.
    """
    pyfiledir = pathlib.Path(filename).expanduser().resolve().parent
    for rootdir in sys.path:
        rootdir = pathlib.Path(rootdir).expanduser().resolve()
        if str(pyfiledir).startswith(str(rootdir)):
            package_relative_path = str(pyfiledir)[len(str(rootdir)):]
            if not package_relative_path:  # at the rootdir - not inside a package
                raise ImportError(f"{filename} is not in a package, but at the root level of syspath {str(rootdir)}")
            package_relative_path = package_relative_path[len(os.path.sep):]  # drop the initial path sep
            package_dotted_name = package_relative_path.replace(os.path.sep, '.')
            return package_dotted_name
    raise ValueError(f"{filename} not under any directory in `sys.path`")

def source_to_xcode(self, data, path, *, _optimize=-1):
    '''[mcpy] Expand macros, then compile.

    Intercepts the source to bytecode transformation.'''
    tree = ast.parse(data)
    module_macro_bindings = expander.find_macros(tree, filename=path)
    expansion = expander.expand_macros(tree, bindings=module_macro_bindings, filename=path)
    remaining_markers = get_markers(expansion)
    if remaining_markers:
        raise MacroExpansionError("{path}: AST markers remaining after expansion: {remaining_markers}")
    return compile(expansion, path, 'exec', dont_inherit=True, optimize=_optimize)

# TODO: Support PEP552 (Deterministic pycs). Need to intercept source file hashing, too.
# TODO: https://www.python.org/dev/peps/pep-0552/
_path_stats = SourceFileLoader.path_stats
_xstats_cache = {}
def path_xstats(self, path):
    '''[mcpy] Compute a `.py` source file's mtime, accounting for macro-imports.

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

    try:
        # TODO: This can be slow, the point of `.pyc` is to avoid the parse-and-compile cost.
        # TODO: We do save the macro-expansion cost, though, and that's likely much more expensive.
        #
        # Maybe make our own pyc-like cache file storing the macro-imports found,
        # store it in the pyc directory, and invalidate it based on the mtime
        # of `path` (only)?
        with tokenize.open(path) as sourcefile:
            tree = ast.parse(sourcefile.read())
        macroimports = [stmt for stmt in tree.body if expander.is_macro_import(stmt)]
        has_relative_imports = any(macroimport.level for macroimport in macroimports)

        package_absname = None
        if has_relative_imports:
            try:
                package_absname = resolve_package(path)
            except (ValueError, ImportError) as err:
                raise ImportError(f"while resolving absolute package name of {path}, which uses relative macro-imports") from err

        mtimes = []
        for macroimport in macroimports:
            if macroimport.module is None:
                lineno = macroimport.lineno  # comes from file, always has one
                raise SyntaxError(f"{path}:{lineno}: missing module name in macro-import")
            absname = importlib.util.resolve_name('.' * macroimport.level + macroimport.module, package_absname)
            spec = importlib.util.find_spec(absname)
            origin = spec.origin
            stats = path_xstats(self, origin)
            mtimes.append(stats['mtime'])

        stat_result = os.stat(path)
        mtime = stat_result.st_mtime_ns * 1e-9
        # size = stat_result.st_size
        mtimes.append(mtime)

        result = {'mtime': max(mtimes)}  # and sum(sizes)? OTOH, as of Python 3.8, only 'mtime' is mandatory.
        _xstats_cache[path] = result
        return result
    except Exception as err:
        raise ImportError(f"while computing modification time of {path}") from err

_invalidate_caches = FileFinder.invalidate_caches
def invalidate_xcaches(self):
    '''[mcpy] Clear the macro dependency tree cache.

    Then delegate to the standard implementation of `FileFinder.invalidate_caches`.
    '''
    _xstats_cache.clear()
    return _invalidate_caches(self)
