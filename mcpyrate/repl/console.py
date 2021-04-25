# -*- coding: utf-8 -*-
"""mcpyrate-enabled `code.InteractiveConsole`.

Special commands:

  - `obj?` shows obj's docstring, `obj??` shows its source code.
  - `macros?` shows macro bindings.
  - `macro(f)` binds a function as a macro. Works also as a decorator.
"""

# Based on `imacropy.console.MacroConsole` by Juha Jeronen,
# which was based on `macropy.core.MacroConsole` by Li Haoyi,
# Justin Holmgren, Alberto Berti and all the other contributors,
# 2013-2019. Used under the MIT license.
#    https://github.com/azazel75/macropy
#    https://github.com/Technologicat/imacropy

__all__ = ["MacroConsole"]

import ast
import code
import copy
import sys
import textwrap

from .. import __version__ as mcpyrate_version
from ..compiler import create_module
from ..core import MacroExpansionError
from ..debug import format_bindings
from ..expander import find_macros, MacroExpander, global_postprocess
from .utils import get_makemacro_sourcecode

# Boot up `mcpyrate` so that the REPL can import modules that use macros.
# Despite the meta-levels, there's just one global importer for the Python process.
from .. import activate  # noqa: F401

_magic_module_name = "__mcpyrate_repl_self__"

class MacroConsole(code.InteractiveConsole):
    def __init__(self, locals=None, filename="<interactive input>"):
        """Parameters like in `code.InteractiveConsole`."""
        self.expander = MacroExpander(bindings={}, filename=filename)
        self._macro_bindings_changed = False

        if locals is None:
            locals = {}
        # Lucky that both meta-levels speak the same language, eh?
        locals["__macro_expander__"] = self.expander

        # support `from __self__ import macros, ...`
        #
        # To do this, we need the top-level variables in the REPL to be stored
        # in the namespace of a module, so that `find_macros` can look them up.
        #
        # We create a module dynamically. The one obvious way would be to then
        # replace the `__dict__` of that module with the given `locals`, but
        # `types.ModuleType` is special in that the `__dict__` binding itself
        # is read-only:
        #   https://docs.python.org/3/library/stdtypes.html#modules
        #
        # This leaves two possible solutions:
        #
        #   a. Keep our magic module separate from `locals`, and shallow-copy
        #      the user namespace into its `__dict__` after each REPL input.
        #      The magic module's namespace is only used for macro lookups.
        #
        #      + Behaves exactly like `code.InteractiveConsole` in that the
        #        user-given `locals` *is* the dict where the top-level variables
        #        are stored. So the user can keep a reference to that dict, and
        #        they will see any changes made by assigning to top-level
        #        variables in the REPL.
        #
        #      - May slow down the REPL when a lot of top-level variables exist.
        #        Likely not a problem in practice.
        #
        #   b. Use the module's `__dict__` as the local namespace of the REPL
        #      session. At startup, update it from `locals`, to install any
        #      user-provided initial variable bindings for the session.
        #
        #      + Elegant. No extra copying.
        #
        #      - Behavior does not match `code.InteractiveConsole`. The
        #        `locals` argument only provides initial values; any updates
        #        made during the REPL session are stored in the module's
        #        `__dict__`, which is a different dict instance. Hence the user
        #        will not see any changes made by assigning to top-level
        #        variables in the REPL.
        #
        # We currently use strategy a., for least astonishment.
        #
        magic_module = create_module(dotted_name=_magic_module_name, filename=filename)
        self.magic_module_metadata = copy.copy(magic_module.__dict__)

        super().__init__(locals, filename)

        # Support for special REPL commands.
        self._internal_execute(get_makemacro_sourcecode())
        self._internal_execute("import mcpyrate.repl.utils")

    def _internal_execute(self, source):
        """Execute given source in the console session.

        This is support magic for internal operation of the console
        session itself, e.g. for auto-loading macro functions.

        The source must be pure Python, i.e. no macros.

        The source is NOT added to the session history.

        This bypasses `runsource`, so it too can use this function.
        """
        source = textwrap.dedent(source)
        tree = ast.parse(source)
        tree = ast.Interactive(tree.body)
        code = compile(tree, "<console internal>", "single", self.compile.compiler.flags, 1)
        self.runcode(code)

    def interact(self, banner=None, exitmsg=None):
        """See `code.InteractiveConsole.interact`.

        The only thing we customize here is that if `banner is None`, in which case
        `code.InteractiveConsole` will print its default banner, we print help for
        our special commands and a line containing the `mcpyrate` version before that
        default banner.
        """
        if banner is None:
            self.write(f"mcpyrate {mcpyrate_version} -- Advanced macro expander for Python.\n")
            self.write("- obj? to view obj's docstring, and obj?? to view its source code.\n")
            self.write("- macros? to view macro bindings.\n")
            self.write("- macro(f) to bind function f as a macro. Works also as a decorator.\n")
        return super().interact(banner, exitmsg)

    def runsource(self, source, filename="<interactive input>", symbol="single"):
        # Special REPL commands.
        if source == "macros?":
            self.write(format_bindings(self.expander, color=True))
            return False  # complete input
        elif source.endswith("??"):
            # Use `_internal_execute` instead of `runsource` to prevent expansion of name macros.
            return self._internal_execute(f"mcpyrate.repl.utils.sourcecode({source[:-2]})")
        elif source.endswith("?"):
            return self._internal_execute(f"mcpyrate.repl.utils.doc({source[:-1]})")

        try:
            code = self.compile(source, filename, symbol)
        except (OverflowError, SyntaxError, ValueError):
            code = ""
        if code is None:  # incomplete input
            return True

        try:
            # TODO: If we want to support dialects in the REPL, this is where to do it.
            #       Look at `mcpyrate.compiler.compile`.
            tree = ast.parse(source)

            # macro-imports (this will import the modules)
            sys.modules[_magic_module_name].__dict__.clear()
            sys.modules[_magic_module_name].__dict__.update(self.locals)  # for self-macro-imports
            # We treat the initial magic module metadata as write-protected: even if the user
            # defines a variable of the same name in the user namespace, the metadata fields
            # in the magic module won't be overwritten.
            sys.modules[_magic_module_name].__dict__.update(self.magic_module_metadata)
            bindings = find_macros(tree, filename=self.expander.filename,
                                   reload=True, self_module=_magic_module_name)
            if bindings:
                self._macro_bindings_changed = True
                self.expander.bindings.update(bindings)
            tree = self.expander.visit(tree)
            tree = global_postprocess(tree)

            tree = ast.Interactive(tree.body)
            code = compile(tree, filename, symbol, self.compile.compiler.flags, 1)
        except (OverflowError, SyntaxError, ValueError, MacroExpansionError):
            self.showsyntaxerror(filename)
            return False  # erroneous input
        except ModuleNotFoundError as err:  # during macro module lookup
            # In this case, the standard stack trace is long and points only to our code and the stdlib,
            # not the erroneous input that's the actual culprit. Better ignore it, and emulate showsyntaxerror.
            # TODO: support sys.excepthook.
            # TODO: Look at `code.InteractiveConsole.showsyntaxerror` for how to do that.
            self.write(f"{err.__class__.__name__}: {str(err)}\n")
            return False  # erroneous input
        except ImportError as err:  # during macro lookup in a successfully imported module
            self.write(f"{err.__class__.__name__}: {str(err)}\n")
            return False  # erroneous input

        self.runcode(code)
        self._refresh_macro_functions()
        return False  # Successfully compiled. `runcode` takes care of any runtime failures.

    def _refresh_macro_functions(self):
        """Refresh macro function imports.

        Called after successfully compiling and running an input, so that
        `some_macro.__doc__` points to the right docstring.
        """
        if not self._macro_bindings_changed:
            return
        self._macro_bindings_changed = False

        for asname, function in self.expander.bindings.items():
            # Catch broken bindings due to erroneous imports in user code
            # (e.g. accidentally to a module object instead of to a function object)
            if not (hasattr(function, "__module__") and hasattr(function, "__qualname__")):
                continue
            if not function.__module__:    # Macros defined in the REPL have `__module__=None`.
                continue
            try:
                source = f"from {function.__module__} import {function.__qualname__} as {asname}"
                self._internal_execute(source)
            except (ModuleNotFoundError, ImportError):
                pass
