# -*- coding: utf-8; -*-
"""Utilities for building REPLs."""

__all__ = ["doc", "sourcecode", "get_makemacro_sourcecode"]

import inspect
from sys import stderr
import textwrap

from ..colorizer import colorize, ColorScheme


def _get_source(obj):
    # `inspect.getsourcefile` accepts "a module, class, method, function,
    # traceback, frame, or code object" (the error message says this if
    # we try it on something invalid).
    #
    # So if `obj` is an instance, we need to try again with its `__class__`.
    for x in (obj, obj.__class__):  # TODO: other places to fall back to?
        try:
            filename = inspect.getsourcefile(x)
            source, firstlineno = inspect.getsourcelines(x)
            return filename, source, firstlineno
        except (TypeError, OSError):
            continue
    raise NotImplementedError


def doc(obj):
    """Print an object's docstring, non-interactively.

    If available, print also the filename and the starting line number
    of the definition of `obj`.
    """
    try:
        filename, source, firstlineno = _get_source(obj)
        print(colorize(f"{filename}:{firstlineno}", ColorScheme.SOURCEFILENAME),
              file=stderr)
    except NotImplementedError:
        pass
    if not hasattr(obj, "__doc__") or not obj.__doc__:
        print(colorize("<no docstring>", ColorScheme.GREYEDOUT),
              file=stderr)
        return
    print(inspect.cleandoc(obj.__doc__), file=stderr)


def sourcecode(obj):
    """Print an object's source code, non-interactively.

    If available, print also the filename and the starting line number
    of the definition of `obj`.
    """
    try:
        filename, source, firstlineno = _get_source(obj)
        print(colorize(f"{filename}:{firstlineno}", ColorScheme.SOURCEFILENAME),
              file=stderr)
        # TODO: No syntax highlighting for now, because we'd have to parse and unparse,
        # TODO: which loses the original formatting and comments.
        for line in source:
            print(line.rstrip("\n"))
    except NotImplementedError:
        print(colorize("<no source code available>", ColorScheme.GREYEDOUT))


def get_makemacro_sourcecode():
    """Return source code for the REPL's `macro` magic function.

    For injection by REPL into the session.

    We assume the expander instance has been bound to the global variable
    `__macro_expander__` inside the REPL session.
    """
    return textwrap.dedent('''
    def macro(function):
        """[mcpyrate] `macro(f)`: bind function `f` as a macro. Works also as a decorator. REPL only."""
        if not callable(function):
            raise TypeError(f"`function` must be callable, got {type(function)} with value {repr(function)}")
        if function.__name__ == "<lambda>":
            raise TypeError("`function` must be a named function, got a lambda.")
        __macro_expander__.bindings[function.__name__] = function
        return function
    ''')
