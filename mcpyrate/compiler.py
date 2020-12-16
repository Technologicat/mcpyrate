# -*- coding: utf-8; -*-
"""Compile macro-enabled Python.

This is used by the import hooks in `mcpyrate.importer`.

Functions specific to multi-phase compilation live in `mcpyrate.multiphase`.
This module orchestrates all other transformations `mcpyrate` performs when
a module is imported.
"""

__all__ = ["compile", "expand_ast", "path_stats"]

import ast
import builtins
import importlib.util
import os
import pickle
import sys
import tokenize

from .coreutils import resolve_package, ismacroimport
from .dialects import DialectExpander
from .expander import find_macros, expand_macros
from .markers import check_no_markers_remaining
from .multiphase import ismultiphase, multiphase_expand, iswithphase
from .unparser import unparse_with_fallbacks
from .utils import format_location


# TODO: Think about how to support `mode="single"`, needed to use the same machinery for the REPL.
# TODO: Pass through also `flags` and `dont_inherit`?
def compile(source, filename, optimize=-1, self_module=None):
    """[mcpyrate] Compile macro-enabled Python.

    Like the built-in `compile` function, but with support for macros and dialects.
    The mode is always `"exec"`, there are no flags, and `dont_inherit` is always `True`.

    `source`:       `str` or `bytes` containing Python source code, or a `list` of statement AST nodes.

                    We always support macros, dialect AST transforms, dialect AST postprocessors,
                    and multi-phase compilation.

                    When source is a `list` of statement AST nodes, we do **not** support
                    dialect source transforms, because the input is then already an AST.

    `filename`:     Full path to the `.py` file being compiled.

    `optimize`:     Passed to Python's built-in `compile` function, as well as to
                    the multi-phase compiler. The multi-phase compiler uses the
                    `optimize` setting for the temporary higher-phase modules.

    `self_module`:  Absolute dotted module name of the module being compiled.
                    Needed for modules that request multi-phase compilation.
                    Ignored in single-phase compilation.

                    In multi-phase compilation, used for temporarily injecting
                    the temporary, higher-phase modules into `sys.modules`,
                    as well as resolving `__self__` in self-macro-imports
                    (`from __self__ import macros, ...`).

    Return value is a code object, ready for `exec`.
    """
    if not isinstance(source, (str, bytes, list)):
        raise TypeError(f"`source` must be Python source code (as `str` or `bytes`) or a `list` of statement AST nodes; got {type(source)} with value {repr(source)}")

    dexpander = DialectExpander(filename=filename)

    if isinstance(source, (str, bytes)):
        if isinstance(source, bytes):
            text = importlib.util.decode_source(source)
        else:
            text = source

        # dialect source transforms (transpilers, surface syntax extensions, etc.)
        text = dexpander.transform_source(text)

        # produce initial AST
        try:
            tree = ast.parse(text, filename=filename, mode="exec")
        except Exception as err:
            raise ImportError(f"Failed to parse {filename} as Python after applying all dialect source transformers.") from err

    else:  # `list` of statement AST nodes
        tree = ast.Module(body=source)

    # AST transforms: dialects, macros
    # TODO: Handle the case where a dialect AST transform causes `tree` to become multi-phase.
    #       The algorithm must be changed slightly.
    if not ismultiphase(tree):
        expansion = expand_ast(tree, filename=filename, self_module=self_module, dexpander=dexpander)
    else:
        if not self_module:
            raise ValueError("`self_module` must be specified when multi-phase compiling.")
        expansion = multiphase_expand(tree, filename=filename, self_module=self_module, dexpander=dexpander,
                                      _optimize=optimize)

    return builtins.compile(expansion, filename, mode="exec", dont_inherit=True, optimize=optimize)


def expand_ast(tree, *, filename, self_module, dexpander):
    """Expand dialects and macros in `tree`. Single phase.

    If you have a multi-phase `tree`, use `mcpyrate.multiphase.multiphase_expand` instead.

    Primarily meant to be called with `tree` the AST of a module that
    uses macros, but works with any `tree` that has a `body` attribute,
    where that `body` is a `list` of statement AST nodes.

    `filename`:     Full path to the `.py` file being compiled.

    `self_module`:  Passed in by the multi-phase compiler when it compiles an individual phase
                    using this function. Used for resolving `__self__` in self-macro-imports
                    (`from __self__ import macros, ...`).

                    Ignored in single-phase compilation.

    `dexpander`:    The `DialectExpander` instance to use for dialect AST transforms.
                    If not provided, dialect processing is skipped.

    Return value is the expanded `tree`.
    """
    if dexpander:
        tree, dialect_instances = dexpander.transform_ast(tree)
    module_macro_bindings = find_macros(tree, filename=filename, self_module=self_module)
    expansion = expand_macros(tree, bindings=module_macro_bindings, filename=filename)
    if dexpander:
        expansion = dexpander.postprocess_ast(expansion, dialect_instances)
    check_no_markers_remaining(expansion, filename=filename)
    return expansion


def path_stats(path, _stats_cache=None):
    """[mcpyrate] Compute a `.py` source file's mtime, accounting for macro-imports.

    Beside the source file `path` itself, we look at any macro definition files
    the source file imports macros from, recursively, in a `make`-like fashion.
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
            tree = ast.parse(sourcefile.read())

        macroimports = []
        dialectimports = []
        def scan(tree):
            for stmt in tree.body:
                if ismacroimport(stmt):
                    macroimports.append(stmt)
                elif ismacroimport(stmt, magicname="dialects"):
                    dialectimports.append(stmt)
                elif iswithphase(stmt):  # for multi-phase compilation: scan also inside top-level `with phase`
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
