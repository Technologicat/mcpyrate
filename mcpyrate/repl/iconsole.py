# -*- coding: utf-8 -*-
"""IPython extension for a mcpyrate-enabled REPL.

To enable::

    %load_ext mcpyrate.repl.iconsole

To autoload it at IPython startup, put this into your ``ipython_config.py``::

    c.InteractiveShellApp.extensions = ["mcpyrate.repl.iconsole"]

To find your config file, ``ipython profile locate``.

The line magic `%macros` shows macros currently imported to the session.

The cell magic `%%dump_ast` pretty-prints the AST of a cell. But note that
you can also use the macro `mcpyrate.debug.step_expansion` in the REPL.

The function `macro(f)` binds a `f` as a macro. Works also as a decorator.
Note this comes from `mcpyrate`; it's different from IPython's `%macro`
line magic.
"""

import ast
from functools import partial
import sys
from types import ModuleType

from IPython.core import magic_arguments
from IPython.core.error import InputRejected
from IPython.core.magic import Magics, magics_class, cell_magic, line_magic

from .. import __version__ as mcpyrate_version
from ..astdumper import dump
from ..debug import format_bindings
from ..expander import find_macros, MacroExpander, global_postprocess
from .utils import get_makemacro_sourcecode

# Boot up `mcpyrate` so that the REPL can import modules that use macros.
# Despite the meta-levels, there's just one global importer for the Python process.
from .. import activate  # noqa: F401

_magic_module_name = "__repl_self__"
_placeholder = "<ipython-session>"
_instance = None

def load_ipython_extension(ipython):
    # TODO: The banner is injected too late.
    #
    # It seems IPython startup is
    # already complete when ``load_ipython_extension()`` is called.
    #
    # We shouldn't print anything directly here; doing that breaks tools
    # such as the Emacs Python autoimporter (see importmagic.el in Spacemacs;
    # it will think epc failed to start if anything but the bare process id
    # is printed). Tools expect to suppress **all** of the IPython banner
    # by telling IPython itself not to print it.
    #
    # For now, let's just put the info into banner2, and refrain from printing it.
    # https://stackoverflow.com/questions/31613804/how-can-i-call-ipython-start-ipython-with-my-own-banner
    ipython.config.TerminalInteractiveShell.banner2 = "mcpyrate {} -- Advanced macro expander for Python.".format(mcpyrate_version)
    global _instance
    if not _instance:
        _instance = IMcpyrateExtension(shell=ipython)
        ipython.register_magics(AstMagics)

# TODO: unregister magics at unload time?
def unload_ipython_extension(ipython):
    global _instance
    _instance = None


@magics_class
class AstMagics(Magics):
    """IPython magics related to `mcpyrate` macro support."""

    # avoid complaining about typoed macro names when the macro functions are loaded
    @cell_magic
    def ignore_importerror(self, line, cell):
        """Run `cell`, ignoring any `ImportError` silently."""
        try:
            # Set globals to the shell user namespace to respect assignments
            # made by code in the cell. (`import` is a binding construct!)
            exec(cell, self.shell.user_ns)
        except ImportError:
            pass

    @line_magic
    def macros(self, line):
        """Print a human-readable list of macros currently imported into the session."""
        # Line magics print an extra `\n` at the end automatically, so remove our final `\n`.
        print(format_bindings(_instance.macro_transformer.expander, color=True), end="")

    # I don't know if this is useful - one can use the `mcpyrate.debug.step_expansion`
    # macro also in the REPL - but let's put it in for now.
    # http://alexleone.blogspot.co.uk/2010/01/python-ast-pretty-printer.html
    @magic_arguments.magic_arguments()
    @magic_arguments.argument(
        "-m", "--mode", default="exec",
        help="The mode in which to parse the code. Can be exec (default), "
             "eval or single."
    )
    # TODO: add support for expand-once
    @magic_arguments.argument(
        "-e", "--expand", default="no",
        help="Whether to expand macros before dumping the AST. Can be yes "
             "or no (default)."
    )
    @cell_magic
    def dump_ast(self, line, cell):
        """Parse the code in the cell, and pretty-print the AST."""
        args = magic_arguments.parse_argstring(self.dump_ast, line)
        tree = ast.parse(cell, mode=args.mode)
        if args.expand != "no":
            tree = _instance.macro_transformer.visit(tree)
        print(dump(tree))


class InteractiveMacroTransformer(ast.NodeTransformer):
    """AST transformer for IPython that expands `mcpyrate` macros."""

    def __init__(self, extension_instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ipyextension = extension_instance
        self.expander = MacroExpander(bindings={}, filename="<ipython-session>")

    def visit(self, tree):
        try:
            sys.modules[_magic_module_name].__dict__.clear()
            sys.modules[_magic_module_name].__dict__.update(self._ipyextension.shell.user_ns)  # for self-macro-imports
            # macro-imports (this will import the modules)
            bindings = find_macros(tree, filename=self.expander.filename,
                                   reload=True, self_module=_magic_module_name)
            if bindings:
                self._ipyextension._macro_bindings_changed = True
                self.expander.bindings.update(bindings)
            new_tree = self.expander.visit(tree)
            new_tree = global_postprocess(new_tree)
            self._ipyextension.src = _placeholder
            return new_tree
        except Exception as err:
            # see IPython.core.interactiveshell.InteractiveShell.transform_ast()
            raise InputRejected(*err.args)


class IMcpyrateExtension:
    """IPython extension. Import, define and use `mcpyrate` macros in the IPython REPL."""

    def __init__(self, shell):
        self._macro_bindings_changed = False
        self.src = _placeholder
        self.shell = shell

        self.shell.input_transformers_post.append(self._get_source_code)

        self.macro_transformer = InteractiveMacroTransformer(extension_instance=self)
        self.shell.ast_transformers.append(self.macro_transformer)  # TODO: last or first?
        # Lucky that both meta-levels speak the same language, eh?
        shell.user_ns["__macro_expander__"] = self.macro_transformer.expander

        # support `from __self__ import macros, ...`
        magic_module = ModuleType(_magic_module_name)
        sys.modules[_magic_module_name] = magic_module

        self.shell.run_cell(get_makemacro_sourcecode(),
                            store_history=False,
                            silent=True)

        # TODO: If we want to support dialects in the REPL, we need to install
        # a string transformer here to call the dialect system's source transformer,
        # and then modify `InteractiveMacroTransformer` to run the dialect system's
        # AST transformer before it runs the macro expander.

        ipy = self.shell.get_ipython()
        ipy.events.register("post_run_cell", self._refresh_macro_functions)

    def __del__(self):
        ipy = self.shell.get_ipython()
        ipy.events.unregister("post_run_cell", self._refresh_macro_functions)
        del self.shell.user_ns["__macro_expander__"]
        self.shell.ast_transformers.remove(self.macro_transformer)
        self.shell.input_transformers_post.remove(self._get_source_code)

    def _get_source_code(self, lines):  # IPython 7.0+ with Python 3.5+
        """Get the source code of the current cell.

        This is a do-nothing string transformer that just captures the text.
        It is intended to run last, just before any AST transformers run.
        """
        self.src = lines
        return lines

    def _refresh_macro_functions(self, info):
        """Refresh macro function imports.

        Called after running a cell, so that IPython help "some_macro?" works
        for the currently available macros, allowing the user to easily view
        macro docstrings.
        """
        if not self._macro_bindings_changed:
            return
        self._macro_bindings_changed = False
        internal_execute = partial(self.shell.run_cell,
                                   store_history=False,
                                   silent=True)

        for asname, function in self.macro_transformer.expander.bindings.items():
            if not function.__module__:
                continue
            commands = ["%%ignore_importerror",
                        f"from {function.__module__} import {function.__qualname__} as {asname}"]
            internal_execute("\n".join(commands))
