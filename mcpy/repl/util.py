# -*- coding: utf-8; -*-
'''Utilities for building REPLs.'''

__all__ = ["doc", "sourcecode"]

import ast
import importlib
import inspect

def doc(obj):
    """Print an object's docstring, non-interactively.

    Additionally, if the information is available, print the filename
    and the starting line number of the definition of `obj` in that file.
    This is printed before the actual docstring.

    This works around the problem that in a REPL session using
    `imacropy.console` or `imacropy.iconsole`, the builtin `help()`
    fails to see the docstring of the stub, and sees only the generic
    docstring of `WrappedMacro`.

    And that looking directly at `some_macro.__doc__` prints the string
    value as-is, without formatting it.
    """
    if not hasattr(obj, "__doc__") or not obj.__doc__:
        print("<no docstring>")
        return
    try:
        filename = inspect.getsourcefile(obj)
        source, firstlineno = inspect.getsourcelines(obj)
        print(f"{filename}:{firstlineno}")
    except (TypeError, OSError):
        pass
    print(inspect.cleandoc(obj.__doc__))

def sourcecode(obj):
    """Print an object's source code, non-interactively.

    Additionally, if the information is available, print the filename
    and the starting line number of the definition of `obj` in that file.
    This is printed before the actual source code.
    """
    try:
        filename = inspect.getsourcefile(obj)
        source, firstlineno = inspect.getsourcelines(obj)
        print(f"{filename}:{firstlineno}")
        for line in source:
            print(line.rstrip("\n"))
    except (TypeError, OSError):
        print("<no source code available>")

# TODO: see if we can reuse `mcpy.expander.find_macros` here
# TODO: (or modify it slightly to accommodate both use cases).
def _reload_macro_modules(tree, package=None):
    """Walk an AST, importing and reloading macro definition modules.

    A macro definition module is a module from which `tree` imports macro definitions,
    i.e. the `module` in `from module import macros, ...`.

    Reloading the relevant macro definition modules ensures that the REPL
    always has access to the latest macro definitions, even if they are
    modified on disk during the REPL session.

    `package` is passed to `importlib.util.resolve_name` to resolve relative imports.
    """
    macro_modules = []
    for stmt in tree.body:
        if (isinstance(stmt, ast.ImportFrom) and stmt.module is not None and
                stmt.names[0].name == 'macros' and stmt.names[0].asname is None):
            fullname = importlib.util.resolve_name('.' * stmt.level + stmt.module, package)
            macro_modules.append(fullname)
    for fullname in macro_modules:
        try:
            mod = importlib.import_module(fullname)
            mod = importlib.reload(mod)
        except ModuleNotFoundError:
            pass
