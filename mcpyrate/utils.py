# -*- coding: utf-8; -*-
"""General utilities. Can be useful for writing both macros as well as macro expanders."""

__all__ = ["gensym", "scrub_uuid", "flatten", "rename", "extract_bindings",
           "format_location", "format_macrofunction", "format_context",
           "NestingLevelTracker"]

import ast
from contextlib import contextmanager
import uuid

from .colorizer import colorize, ColorScheme
from . import markers
from . import unparser
from . import walkers


_previous_gensyms = set()
def gensym(basename=None):
    """Create a name for a new, unused lexical identifier, and return the name as an `str`.

    We include an uuid in the name to avoid the need for any lexical scanning.

    Can also be used for globally unique string keys, in which case `basename`
    does not need to be a valid identifier.
    """
    basename = basename or "gensym"
    def generate():
        unique = str(uuid.uuid4()).replace("-", "")
        return f"{basename}_{unique}"
    sym = generate()
    # The uuid spec does not guarantee no collisions, only a vanishingly small chance.
    while sym in _previous_gensyms:
        sym = generate()  # pragma: no cover
    _previous_gensyms.add(sym)
    return sym


def scrub_uuid(string):
    """Scrub any existing `"_uuid"` suffix from `string`."""
    idx = string.rfind("_")
    if idx != -1:
        maybe_uuid = string[(idx + 1):]
        if len(maybe_uuid) == 32:
            try:
                _ = int(maybe_uuid, base=16)
            except ValueError:
                pass
            else:  # yes, it was an uuid
                return string[:idx]
    return string


def flatten(lst, *, recursive=True):
    """Flatten a nested list.

    Useful for splicing in transformations of statement suites.
    """
    out = []
    for elt in lst:
        if isinstance(elt, list):
            sublst = flatten(elt) if recursive else elt
            out.extend(sublst)
        elif elt is not None:
            out.append(elt)
    return out


def rename(oldname, newname, tree):
    """Rename all occurrences of a name in `tree`.

    We look in all places in the AST that hold name-like things.

    Currently: identifiers (names), attribute names, function and class names,
    function parameter names, arguments passed by name, name and asname in imports,
    and the as-part of an exception handler (binding a name to the exception object).

    Some constructs such as `For` and `With` use `Name` nodes for named things,
    so those are transformed too.

    With this you can do things like::

        from mcpyrate.quotes import macros, q
        from mcpyrate import gensym
        from mcpyrate.utils import rename

        tree = q[lambda _: ...]
        tree = rename("_", gensym(), tree)
    """
    class Renamer(walkers.ASTTransformer):
        def transform(self, tree):
            T = type(tree)
            if T is ast.Name:
                if tree.id == oldname:
                    tree.id = newname
            # Look for "raw string" in GTS for a full list of the following.
            # https://greentreesnakes.readthedocs.io/en/latest/nodes.html
            elif T is ast.Attribute:
                if tree.attr == oldname:
                    tree.attr = newname
            elif T in (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef):
                if tree.name == oldname:
                    tree.name = newname
            elif T is ast.arg:  # function parameter
                if tree.arg == oldname:
                    tree.arg = newname
            elif T is ast.keyword:  # in function call, argument passed by name
                if tree.arg == oldname:
                    tree.arg = newname
            elif T is ast.alias:  # in ast.Import, ast.ImportFrom
                if tree.name == oldname:
                    tree.name = newname
                if tree.asname == oldname:
                    tree.asname = newname
            elif T is ast.ExceptHandler:
                if tree.name == oldname:
                    tree.name = newname
            return self.generic_visit(tree)
    return Renamer().visit(tree)


def extract_bindings(bindings, *functions, global_only=False):
    """Scan `bindings` for given macro functions.

    Return all matching bindings as a dictionary of macro name/function pairs,
    which can be used to instantiate a new expander (that recognizes only those
    bindings).

    Note functions, not names. This is convenient as a helper when expanding
    macros inside-out, but only those in a given set, accounting for any renames
    due to as-imports.

    Useful input values for `bindings` include `expander.bindings` (in a macro;
    will see both local and global bindings), `mcpyrate.core.global_bindings`
    (for global bindings only), and the run-time output of the name macro
    `mcpyrate.metatools.macro_bindings`.

    Typical usage::

        bindings = extract_bindings(expander.bindings, mymacro1, mymacro2, mymacro3)
        tree = MacroExpander(bindings, expander.filename).visit(tree)
    """
    functions = set(functions)
    return {name: function for name, function in bindings.items() if function in functions}

# --------------------------------------------------------------------------------

def format_location(filename, tree, sourcecode):
    """Format a source code location in a standard way, for error messages.

    `filename`: full path to `.py` file.
    `tree`: AST node to get source line number from. (Looks inside AST markers.)
    `sourcecode`: source code (typically, to get this, `unparse(tree)`
                  before expanding it), or `None` to omit it.
    """
    lineno = None
    if hasattr(tree, "lineno"):
        lineno = tree.lineno
    elif isinstance(tree, markers.ASTMarker) and hasattr(tree, "body"):
        if hasattr(tree.body, "lineno"):
            lineno = tree.body.lineno
        elif isinstance(tree.body, list) and tree.body and hasattr(tree.body[0], "lineno"):  # e.g. `SpliceNodes`
            lineno = tree.body[0].lineno

    if sourcecode:
        sep = " " if "\n" not in sourcecode else "\n"
        source_with_sep = f"{sep}{sourcecode}"
    else:
        source_with_sep = ""

    return f'{colorize(filename, ColorScheme.SOURCEFILENAME)}:{lineno}:{source_with_sep}'


def format_macrofunction(function):
    """Format the fully qualified name of a macro function, for error messages."""
    if not function.__module__:  # Macros defined in the REPL have `__module__=None`.
        return function.__qualname__
    return f"{function.__module__}.{function.__qualname__}"


def format_context(tree, *, n=5):
    """Format up to the first `n` lines of source code of `tree`."""
    code_lines = unparser.unparse_with_fallbacks(tree, debug=True, color=True).split("\n")
    code = "\n".join(code_lines[:n])
    if len(code_lines) > n:
        code += "\n" + colorize("...", ColorScheme.GREYEDOUT)
    return code

# --------------------------------------------------------------------------------

class NestingLevelTracker:
    """Track the nesting level in a set of co-operating, related macros.

    Useful for implementing macros that are syntactically only valid inside the
    invocation of another macro (i.e. when the level is `> 0`).

    Note that in order for level tracking to work, the context (outer) macros
    must expand inside-out (i.e. call `expander.visit` explicitly). If they
    expand outside-in (default), the outer macro invocation will already have
    exited when the inner macro invocation gets expanded.
    """
    def __init__(self, start=0):
        """start: int, initial level"""
        self.stack = [start]

    def _get_value(self):
        return self.stack[-1]
    value = property(fget=_get_value, doc="The current level. Read-only. Use `set_to` or `change_by` to change.")

    def set_to(self, value):
        """Context manager. Run a section of code with the level set to `value`."""
        if not isinstance(value, int):
            raise TypeError(f"Expected integer `value`, got {type(value)} with value {repr(value)}")
        if value < 0:
            raise ValueError(f"`value` must be >= 0, got {repr(value)}")
        @contextmanager
        def _set_to():
            self.stack.append(value)
            try:
                yield
            finally:
                self.stack.pop()
                assert self.stack  # postcondition
        return _set_to()

    def changed_by(self, delta):
        """Context manager. Run a section of code with the level incremented by `delta`."""
        return self.set_to(self.value + delta)
