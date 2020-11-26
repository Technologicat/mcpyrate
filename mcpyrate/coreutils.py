# -*- coding: utf-8; -*-
"""Utilities related to writing macro expanders and similar meta-metaprogramming tasks."""

__all__ = ["resolve_package", "relativize", "match_syspath",
           "ismacroimport", "get_macros"]

from ast import ImportFrom
import importlib
import importlib.util
import os
import pathlib
import sys

from .unparser import unparse_with_fallbacks
from .utils import format_location

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
    package_dotted_name = relative_path.replace(os.path.sep, ".")
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

def ismacroimport(statement, magicname='macros'):
    """Return whether `statement` is a macro-import.

    A macro-import is a statement of the form::

        from ... import macros, ...

    where "macros" is the literal string given as `magicname`.
    """
    if isinstance(statement, ImportFrom):
        firstimport = statement.names[0]
        if firstimport.name == magicname and firstimport.asname is None:
            return True
    return False


def get_macros(macroimport, *, filename, reload=False, allow_asname=True, self_module=None):
    """Get absolute module name, macro names and macro functions from a macro-import.

    As a side effect, import the macro definition module.

    Return value is `module_absname, {macroname0: macrofunction0, ...}`.

    `filename` is the full path to the `.py` being macroexpanded, for resolving
    relative macro-imports and for error reporting. In interactive use, can be
    an arbitrary label.

    Use the `reload` flag only when implementing a REPL, because it'll refresh modules,
    causing different uses of the same macros to point to different function objects.

    Use `allow_asname` to say whether your expander supports renaming macros
    at the use site. Usually it's a good idea to support it; but e.g. renaming a
    dialect makes no sense.

    `self_module` is an optional string, the absolute dotted module name of the
    module being expanded. Used for supporting `from __self__ import macros, ...`
    for multi-phase compilation (a.k.a. `with phase`).

    This function is meant for implementing actual macro expanders.
    """
    package_absname = None
    if macroimport.level and filename.endswith(".py"):
        try:
            package_absname = resolve_package(filename)
        except (ValueError, ImportError) as err:
            raise ImportError(f"while resolving absolute package name of {filename}, which uses relative macro-imports") from err

    if macroimport.module is None:
        # fallbacks may trigger if the macro-import is programmatically generated.
        approx_sourcecode = unparse_with_fallbacks(macroimport, debug=True, color=True)
        loc = format_location(filename, macroimport, approx_sourcecode)
        raise SyntaxError(f"{loc}\nmissing module name in macro-import")

    # macro-import from an earlier phase of a module using `with phase`
    if macroimport.module == "__self__":
        if macroimport.level:
            approx_sourcecode = unparse_with_fallbacks(macroimport, debug=True, color=True)
            loc = format_location(filename, macroimport, approx_sourcecode)
            raise SyntaxError(f"{loc}\nself-macro-imports cannot be relative")
        # When we get here, the module, as compiled up to the previous phase,
        # is already in `sys.modules`, because the importer temporarily places
        # it there. That way we can load macro bindings from it, while the
        # current phase is being compiled.
        module_absname = self_module
        module = sys.modules[module_absname]

    else:  # regular macro-import
        module_absname = importlib.util.resolve_name("." * macroimport.level + macroimport.module, package_absname)

        try:
            module = importlib.import_module(module_absname)
        except ModuleNotFoundError as err:
            approx_sourcecode = unparse_with_fallbacks(macroimport, debug=True, color=True)
            loc = format_location(filename, macroimport, approx_sourcecode)
            raise ModuleNotFoundError(f"{loc}\nNo module named {module_absname}") from err

        if reload:
            module = importlib.reload(module)

    bindings = {}
    for name in macroimport.names[1:]:
        if not allow_asname and name.asname is not None:
            raise ImportError("This expander (see call stack) does not support as-naming macro-imports.")

        try:
            bindings[name.asname or name.name] = getattr(module, name.name)
        except AttributeError as err:
            approx_sourcecode = unparse_with_fallbacks(macroimport, debug=True, color=True)
            loc = format_location(filename, macroimport, approx_sourcecode)
            raise ImportError(f"{loc}\ncannot import name '{name.name}' from module {module_absname}") from err

    return module_absname, bindings
