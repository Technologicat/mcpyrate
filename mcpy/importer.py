# -*- coding: utf-8; -*-
'''Importer (finder/loader) customizations, to inject the macro expander.'''

__all__ = ['resolve_package', 'relativize', 'match_syspath',
           'source_to_xcode', 'path_xstats', 'invalidate_xcaches']

import ast
import tokenize
import pathlib
import sys
import os
import importlib.util
from importlib.machinery import FileFinder, SourceFileLoader

from .core import MacroExpansionError
from . import expander  # it's a higher-level thing and depends on us so import just the module.
from .markers import get_markers
from .unparser import unparse_with_fallbacks
from .utilities import format_location
from .walker import SourceLocationInfoValidator


def resolve_package(filename):  # TODO: for now, `guess_package`, really. Check the docs again.
    """Resolve absolute Python package name for .py source file `filename`.

    If `filename` is at the top level of the matching entry in `sys.path`, raises `ImportError`.
    If `filename` is not under any directory in `sys.path`, raises `ValueError`.
    """
    containing_directory = pathlib.Path(filename).expanduser().resolve().parent
    root_path, relative_path = relativize(containing_directory)
    if not relative_path:  # at the root_path - not inside a package
        absolute_filename = str(pathlib.Path(filename).expanduser().resolve())
        resolved = f" (resolved to {absolute_filename})" if absolute_filename != str(filename) else ""
        raise ImportError(f"{filename}{resolved} is not in a package, but at the root level of syspath {str(root_path)}")
    package_dotted_name = relative_path.replace(os.path.sep, '.')
    return package_dotted_name


def relativize(filename):
    """Convert `filename` into a relative one under the matching `sys.path`.

    Return value is `(root_path, relative_path)`, where `root_path` is the
    return value of `match_syspath` (a `pathlib.Path`), and `relative_path`
    is a string containing the relative path of `filename` under `root_path`.

    `filename` can be a .py source file or a package directory.
    """
    absolute_filename = str(pathlib.Path(filename).expanduser().resolve())
    root_path = match_syspath(absolute_filename)
    relative_path = absolute_filename[len(str(root_path)):]
    if relative_path.startswith(os.path.sep):
        relative_path = relative_path[len(os.path.sep):]
    return root_path, relative_path


def match_syspath(filename):
    """Return the entry in `sys.path` the `filename` is found under.

    Return value is a `pathlib.Path` for the matching `sys.path` directory,
    resolved to an absolute directory.

    If `filename` is not under any directory in `sys.path`, raises `ValueError`.
    """
    absolute_filename = str(pathlib.Path(filename).expanduser().resolve())
    for root_path in sys.path:
        root_path = pathlib.Path(root_path).expanduser().resolve()
        if absolute_filename.startswith(str(root_path)):
            return root_path
    resolved = f" (resolved to {absolute_filename})" if absolute_filename != str(filename) else ""
    raise ValueError(f"{filename}{resolved} not under any directory in `sys.path`")

# --------------------------------------------------------------------------------

def source_to_xcode(self, data, path, *, _optimize=-1):
    '''[mcpy] Expand macros, then compile.

    Intercepts the source to bytecode transformation.
    '''
    tree = ast.parse(data)
    module_macro_bindings = expander.find_macros(tree, filename=path)
    expansion = expander.expand_macros(tree, bindings=module_macro_bindings, filename=path)

    remaining_markers = get_markers(expansion)
    if remaining_markers:
        raise MacroExpansionError("{path}: AST markers remaining after expansion: {remaining_markers}")

    # The top-level module node doesn't need source location info,
    # but in any other AST node it's mandatory.
    validator = SourceLocationInfoValidator(ignore={expansion})
    validator.visit(expansion)
    if validator.collected:
        msg = f"{path}: required source location missing for the following nodes:\n"
        for tree, missing_fields in validator.collected:
            code_lines = unparse_with_fallbacks(tree).split("\n")
            code = "\n".join(code_lines[:5])
            if len(code_lines) > 5:
                code += "\n..."
            msg += f"{tree}: {missing_fields}, unparsed code:\n{code}\n"
        raise MacroExpansionError(msg)

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

    # TODO: This can be slow, the point of `.pyc` is to avoid the parse-and-compile cost.
    # TODO: We do save the macro-expansion cost, though, and that's likely much more expensive.
    #
    # If that becomes an issue, maybe make our own cache file storing the
    # macro-imports found in source file `path`, store it in the pyc
    # directory, and invalidate it based on the mtime of `path` (only)?
    with tokenize.open(path) as sourcefile:
        tree = ast.parse(sourcefile.read())
    macroimports = [stmt for stmt in tree.body if expander.ismacroimport(stmt)]
    has_relative_imports = any(macroimport.level for macroimport in macroimports)

    # TODO: some duplication with code in mcpy.expander._get_macros, including the error messages.
    package_absname = None
    if has_relative_imports:
        try:
            package_absname = resolve_package(path)
        except (ValueError, ImportError) as err:
            raise ImportError(f"while resolving absolute package name of {path}, which uses relative macro-imports") from err

    mtimes = []
    for macroimport in macroimports:
        if macroimport.module is None:
            approx_sourcecode = unparse_with_fallbacks(macroimport)
            loc = format_location(path, macroimport, approx_sourcecode)
            raise SyntaxError(f"{loc}\nmissing module name in macro-import")
        module_absname = importlib.util.resolve_name('.' * macroimport.level + macroimport.module, package_absname)

        spec = importlib.util.find_spec(module_absname)
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


_invalidate_caches = FileFinder.invalidate_caches
def invalidate_xcaches(self):
    '''[mcpy] Clear the macro dependency tree cache.

    Then delegate to the standard implementation of `FileFinder.invalidate_caches`.
    '''
    _xstats_cache.clear()
    return _invalidate_caches(self)
