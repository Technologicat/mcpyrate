# -*- coding: utf-8 -*-
"""mcpy-enabled `code.InteractiveConsole`.

Special commands:

  - `obj?` shows obj's docstring, `obj??` shows its source code.
  - `macros?` shows macros currently imported to the session.
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
import textwrap
from collections import OrderedDict

from mcpy import __version__ as mcpy_version
from mcpy.expander import find_macros, expand_macros

import mcpy.activate  # noqa: F401, boot up mcpy.

class MacroConsole(code.InteractiveConsole):
    def __init__(self, locals=None, filename="<console>"):
        """Parameters like in `code.InteractiveConsole`."""
        super().__init__(locals, filename)

        # macro support
        self._bindings = OrderedDict()
        self._bindings_changed = False

        # ? and ?? help syntax
        self._internal_execute("import mcpy.repl.utils")

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
        code = compile(tree, "<console_internal>", "single", self.compile.compiler.flags, 1)
        self.runcode(code)

    def _list_macros(self):
        """Print a human-readable list of macros currently imported into the session."""
        if not self._bindings:
            self.write("<no macros imported>\n")
            return
        themacros = []
        for asname, function in self._bindings.items():
            themacros.append((asname, f"{function.__module__}.{function.__qualname__}"))
        for asname, fullname in themacros:
            print(f"{asname}: {fullname}")

    def interact(self, banner=None, exitmsg=None):
        """See `code.InteractiveConsole.interact`.

        The only thing we customize here is that if `banner is None`, in which case
        `code.InteractiveConsole` will print its default banner, we print help for
        our special commands and a line containing the `mcpy` version before that
        default banner.
        """
        if banner is None:
            self.write("Use obj? to view obj's docstring, and obj?? to view its source code.\n")
            self.write("Use macros? to see macros you have currently imported into the session.\n")
            self.write(f"mcpy {mcpy_version} -- Syntactic macros for Python.\n")
        return super().interact(banner, exitmsg)

    def runsource(self, source, filename="<interactive input>", symbol="single"):
        # ? and ?? help syntax
        if source == "macros?":
            self._list_macros()
            return False  # complete input
        elif source.endswith("??"):
            return self.runsource(f'mcpy.repl.utils.sourcecode({source[:-2]})')
        elif source.endswith("?"):
            return self.runsource(f"mcpy.repl.utils.doc({source[:-1]})")

        try:
            code = self.compile(source, filename, symbol)
        except (OverflowError, SyntaxError, ValueError):
            code = ""
        if code is None:  # incomplete input
            return True

        try:
            tree = ast.parse(source)

            bindings = find_macros(tree, filename="<interactive input>", reload=True)  # macro-imports (this will import the modules)
            if bindings:
                self._bindings_changed = True
                self._bindings.update(bindings)
            tree = expand_macros(tree, self._bindings, filename="<interactive input>")

            tree = ast.Interactive(tree.body)
            code = compile(tree, filename, symbol, self.compile.compiler.flags, 1)
        except (OverflowError, SyntaxError, ValueError):
            self.showsyntaxerror(filename)
            return False  # erroneous input
        except ModuleNotFoundError as err:  # during macro module lookup
            # In this case, the standard stack trace is long and points only to our code and the stdlib,
            # not the erroneous input that's the actual culprit. Better ignore it, and emulate showsyntaxerror.
            # TODO: support sys.excepthook.
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
        if not self._bindings_changed:
            return
        self._bindings_changed = False

        for asname, function in self._bindings.items():
            source = f"from {function.__module__} import {function.__qualname__} as {asname}"
            self._internal_execute(source)
