# -*- coding: utf-8; -*-
'''Utilities related to writing macro expanders.'''

__all__ = ['ismacroimport', 'get_macros']

from ast import ImportFrom
import importlib
import importlib.util  # in PyPy3, this must be imported explicitly

from .importer import resolve_package
from .unparser import unparse_with_fallbacks
from .utilities import format_location


def ismacroimport(statement, magicname='macros'):
    '''Return whether `statement` is a macro-import.

    A macro-import is a statement of the form::

        from ... import macros, ...

    where "macros" is the literal string given as `magicname`.
    '''
    if isinstance(statement, ImportFrom):
        firstimport = statement.names[0]
        if firstimport.name == magicname and firstimport.asname is None:
            return True
    return False


def get_macros(macroimport, *, filename, reload=False):
    '''Get absolute module name, macro names and macro functions from a macro-import.

    As a side effect, import the macro definition module.

    Return value is `module_absname, {macroname0: macrofunction0, ...}`.

    Use the `reload` flag only when implementing a REPL, because it'll refresh modules,
    causing different uses of the same macros to point to different function objects.

    This function is meant for implementing actual macro expanders.
    '''
    package_absname = None
    if macroimport.level and filename.endswith(".py"):
        try:
            package_absname = resolve_package(filename)
        except (ValueError, ImportError) as err:
            raise ImportError(f"while resolving absolute package name of {filename}, which uses relative macro-imports") from err

    if macroimport.module is None:
        # fallbacks may trigger if the macro-import is programmatically generated.
        approx_sourcecode = unparse_with_fallbacks(macroimport)
        loc = format_location(filename, macroimport, approx_sourcecode)
        raise SyntaxError(f"{loc}\nmissing module name in macro-import")
    module_absname = importlib.util.resolve_name('.' * macroimport.level + macroimport.module, package_absname)

    module = importlib.import_module(module_absname)
    if reload:
        module = importlib.reload(module)

    return module_absname, {name.asname or name.name: getattr(module, name.name)
                            for name in macroimport.names[1:]}
