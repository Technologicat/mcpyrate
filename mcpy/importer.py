# -*- coding: utf-8; -*-

__all__ = ['nop', 'source_to_xcode', 'path_xstats', 'resolve_package']

import ast
import tokenize
import pathlib
import sys
import os
import importlib.util
from .core import MacroExpansionError
from . import expander
from .markers import get_markers

def nop(*args, **kw): pass

def source_to_xcode(self, data, path, *, _optimize=-1):
    '''Expand macros before compiling.

    Intercepts the source to bytecode transformation.'''
    tree = ast.parse(data)
    module_macro_bindings = expander.find_macros(tree, filename=path)
    expansion = expander.expand_macros(tree, bindings=module_macro_bindings, filename=path)
    remaining_markers = get_markers(expansion)
    if remaining_markers:
        raise MacroExpansionError("{path}: AST markers remaining after expansion: {remaining_markers}")
    return compile(expansion, path, 'exec', dont_inherit=True, optimize=_optimize)

# TODO: we should support invalidate_caches (see importlib); requires implementing a proper Finder/Loader pair.
xstats_cache = {}
def path_xstats(self, path):
    '''Account for macro definition modules, too, when computing a source file's mtime.'''
    if path in xstats_cache:
        return xstats_cache[path]

    with tokenize.open(path) as sourcefile:
        content = sourcefile.read()
    tree = ast.parse(content)

    macroimports = [stmt for stmt in tree.body if expander._is_macro_import(stmt)]
    has_relative_imports = any(macroimport.level for macroimport in macroimports)
    package_absname = None
    if has_relative_imports:
        package_absname = resolve_package(path)

    mtimes = []
    for macroimport in macroimports:
        absname = importlib.util.resolve_name('.' * macroimport.level + macroimport.module, package_absname)
        spec = importlib.util.find_spec(absname)
        origin = spec.origin
        stats = path_xstats(self, origin)
        mtimes.append(stats['mtime'])

    stat_result = os.stat(path)
    mtime = stat_result.st_mtime_ns * 1e-9
    # size = stat_result.st_size
    mtimes.append(mtime)

    result = {'mtime': max(mtimes)}  # sum(sizes)?
    xstats_cache[path] = result
    return result

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
