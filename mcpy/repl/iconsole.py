# -*- coding: utf-8 -*-
"""IPython extension for an mcpy-enabled REPL.

To enable::

    %load_ext mcpy.repl.iconsole

To autoload it at IPython startup, put this into your ``ipython_config.py``::

    c.InteractiveShellApp.extensions = ["mcpy.repl.iconsole"]

To find your config file, ``ipython profile locate``.

The line magic `%macros` shows macros currently imported to the session.
The cell magic `%%dump_ast` pretty-prints the AST of a cell.
"""

import ast
from collections import OrderedDict
from functools import partial

from IPython.core import magic_arguments
from IPython.core.error import InputRejected
from IPython.core.magic import (register_cell_magic, register_line_magic,
                                Magics, magics_class, cell_magic)

from mcpy import __version__ as mcpy_version
from mcpy.expander import find_macros, expand_macros
from mcpy.astpp import dump

_placeholder = "<interactive input>"
_instance = None

def load_ipython_extension(ipython):
    # FIXME: The banner is injected too late. It seems IPython startup has  already performed when ``load_ipython_extension()`` is called.
    #
    # FIXME: We shouldn't print anything directly here; doing that breaks tools such as the Emacs Python autoimporter (see importmagic.el
    # FIXME: in Spacemacs; it will think epc failed to start if anything but the bare process id is printed). Tools expect to suppress
    # FIXME: **all** of the IPython banner by telling IPython itself not to print it.
    #
    # FIXME: For now, let's just put the info into banner2, and refrain from printing it.
    # https://stackoverflow.com/questions/31613804/how-can-i-call-ipython-start-ipython-with-my-own-banner
    ipython.config.TerminalInteractiveShell.banner2 = "mcpy {} -- Syntactic macros for Python.".format(mcpy_version)
    global _instance
    if not _instance:
        _instance = IMcpyExtension(shell=ipython)
        ipython.register_magics(AstMagics)

# TODO: unregister magics at unload time?
def unload_ipython_extension(ipython):
    global _instance
    _instance = None

class InteractiveMacroTransformer(ast.NodeTransformer):
    def __init__(self, extension_instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ext = extension_instance
        self.bindings = OrderedDict()

    def visit(self, tree):
        try:
            bindings = find_macros(tree, filename="<interactive input>", reload=True)  # macro imports (this will import the modules)
            if bindings:
                self.ext.bindings_changed = True
                self.bindings.update(bindings)
            newtree = expand_macros(tree, self.bindings, filename="<interactive input>")
            self.ext.src = _placeholder
            return newtree
        except Exception as err:
            # see IPython.core.interactiveshell.InteractiveShell.transform_ast()
            raise InputRejected(*err.args)


# avoid complaining about typoed macro names when the macro functions are loaded
@register_cell_magic
def ignore_importerror(line, cell):
    try:
        exec(cell, _instance.shell.user_ns)  # set globals to the shell user namespace to respect assignments
    except ImportError:
        pass

@register_line_magic
def macros(line):
    """Print a human-readable list of macros currently imported into the session."""
    t = _instance.macro_transformer
    if not t.bindings:
        print("<no macros imported>")
        return
    themacros = []
    for asname, function in t.bindings.items():
        themacros.append((asname, f"{function.__module__}.{function.__qualname__}"))
    for asname, fullname in themacros:
        print(f"{asname}: {fullname}")

# AstMagics from astpp.py by Alex Leone
# http://alexleone.blogspot.co.uk/2010/01/python-ast-pretty-printer.html
@magics_class
class AstMagics(Magics):
    @magic_arguments.magic_arguments()
    @magic_arguments.argument(
        '-m', '--mode', default='exec',
        help="The mode in which to parse the code. Can be exec (default), "
             "eval or single."
    )
    @cell_magic
    def dump_ast(self, line, cell):
        """Parse the code in the cell, and pretty-print the AST."""
        args = magic_arguments.parse_argstring(self.dump_ast, line)
        tree = ast.parse(cell, mode=args.mode)
        print(dump(tree))


class IMcpyExtension:
    def __init__(self, shell):
        self.src = _placeholder
        self.shell = shell
        ipy = self.shell.get_ipython()

        self.shell.input_transformers_post.append(self._get_source_code)

        self.bindings_changed = False
        self.macro_transformer = InteractiveMacroTransformer(extension_instance=self)
        self.shell.ast_transformers.append(self.macro_transformer)  # TODO: last or first?

        ipy.events.register('post_run_cell', self._refresh_macro_functions)

        # initialize mcpy in the session
        self.shell.run_cell("import mcpy.activate", store_history=False, silent=True)

    def __del__(self):
        ipy = self.shell.get_ipython()
        ipy.events.unregister('post_run_cell', self._refresh_macro_functions)
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
        if not self.bindings_changed:
            return
        self.bindings_changed = False
        internal_execute = partial(self.shell.run_cell,
                                   store_history=False,
                                   silent=True)

        for asname, function in self.macro_transformer.bindings.items():
            commands = ["%%ignore_importerror",
                        f"from {function.__module__} import {function.__qualname__} as {asname}"]
            internal_execute("\n".join(commands))
