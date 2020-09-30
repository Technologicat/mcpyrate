#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bootstrapper for Python programs powered by mcpy."""

from importlib import import_module
from importlib.util import resolve_name
import os
import sys
import argparse

from importlib.util import module_from_spec

import mcpy.activate

# TODO: Enable once we port `pydialect` to use `mcpy`.
#    https://github.com/Technologicat/pydialect
# try:  # this is all we need to enable dialect support.
#     import dialects.activate
# except ImportError:
#     dialects = None

__version__ = mcpy.__version__

def import_module_as_main(name, script_mode):
    """Import a module, pretending it's __main__.

    Upon success, replaces ``sys.modules["__main__"]`` with the module that
    was imported. Upon failure, propagates any exception raised.

    This is a customized approximation of the standard import semantics, based on:

        https://docs.python.org/3/library/importlib.html#approximating-importlib-import-module
        https://docs.python.org/3/reference/import.html#loading
        https://docs.python.org/3/reference/import.html#import-related-module-attributes
        https://docs.python.org/3/reference/import.html#module-path
        https://docs.python.org/3/reference/import.html#special-considerations-for-main
    """
    # We perform only the user-specified import ourselves; that we must, in order to
    # load it as "__main__". We delegate all the rest to the stdlib import machinery.

    absolute_name = resolve_name(name, package=None)
    # Normally we should return the module from sys.modules if already loaded,
    # but the __main__ in sys.modules is this bootstrapper program, not the user
    # __main__ we're loading. So pretend whatever we're loading isn't loaded yet.
    #
    # Note Python treats __main__ and somemod as distinct modules, even when it's
    # the same file, because __main__ triggers "if __name__ == '__main__':" checks
    # whereas somemod doesn't.
#    try:
#        return sys.modules[absolute_name]
#    except KeyError:
#        pass

    if "" not in sys.path:  # Python 3.6 removed the special entry "" (the cwd) from sys.path
        sys.path.insert(0, "")

    # path should be folder containing something.py if we are being run as "macropython something.py"
    # (script_mode=True), and cwd if run as "macropython -m something"
    path = None
    if '.' in absolute_name:
        parent_name, _, child_name = absolute_name.rpartition('.')
        if not script_mode:
            parent_module = import_module(parent_name)
            path = parent_module.__spec__.submodule_search_locations
        else:  # HACK: try to approximate what "python3 some/path/to/script.py" does
            cwd = os.getcwd()
            path_components = parent_name.split('.')
            path = [os.path.join(*([cwd] + path_components))]
            absolute_name = child_name

    for finder in sys.meta_path:
        if not hasattr(finder, "find_spec"):  # Python 3.6: pkg_resources.extern.VendorImporter has no find_spec
            continue
        spec = finder.find_spec(absolute_name, path)
        if spec is not None:
            break
    else:
        msg = 'No module named {}'.format(absolute_name)
        raise ModuleNotFoundError(msg, name=absolute_name)

    spec.name = "__main__"
    if spec.loader:
        spec.loader.name = "__main__"  # fool importlib._bootstrap.check_name_wrapper

    # TODO: support old-style loaders that have load_module (no create_module, exec_module)?
    module = module_from_spec(spec)
    try_mainpy = False
    if script_mode:  # e.g. "macropython somemod/__init__.py"
        module.__package__ = ""
    elif path:
        module.__package__ = parent_name
    elif spec.origin.endswith("__init__.py"):  # e.g. "macropython -m unpythonic"
        module.__package__ = absolute_name
        try_mainpy = True

    # TODO: is this sufficient? Any other cases where we directly handle a package?
    if spec.origin == "namespace":
        module.__path__ = spec.submodule_search_locations

    if try_mainpy:
        # e.g. "import unpythonic" in the above case; it's not the one running as main, so import it normally
        if not script_mode:
            parent_module = import_module(absolute_name)
    elif spec.loader is not None:  # namespace packages have loader=None
        # There's already a __main__ in sys.modules, so the most logical thing
        # to do is to switch it **after** a successful import, not before import
        # as for usual imports (where the ordering prevents infinite recursion
        # and multiple loading).
        spec.loader.exec_module(module)
        sys.modules["__main__"] = module
#        # __main__ has no parent module.
#        if path is not None:
#            setattr(parent_module, child_name, module)
    else:  # namespace package
        try_mainpy = True

    if try_mainpy:  # __init__.py (if any) has run; now run __main__.py, like "python3 -m mypackage" does
        has_mainpy = True
        try:
            # __main__.py doesn't need the name "__main__" so we can just import it normally
            import_module("{}.__main__".format(absolute_name))
        except ImportError as e:
            if "No module named" in e.msg:
                has_mainpy = False
            else:
                raise
        if not has_mainpy:
            raise ImportError("No module named {}.__main__; '{}' is a package and cannot be directly executed".format(absolute_name, absolute_name))

    return module

def main():
    """Handle command-line arguments and run the specified main program."""
    parser = argparse.ArgumentParser(description="""Run a Python program or an interactive interpreter with mcpy enabled.""",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-v', '--version', action='version', version=('%(prog)s-bootstrapper ' + __version__))
    parser.add_argument(dest='filename', nargs='?', default=None, type=str, metavar='file',
                        help='script to run')
    parser.add_argument('-m', '--module', dest='module', default=None, type=str, metavar='mod',
                        help='run library module as a script (like python3 -m mod)')
    parser.add_argument('-i', '--interactive', dest='interactive', action="store_true", default=False,
                        help='interactive mode (macro-enabled Python interpreter). '
                             'If -i is given, <filename> and -m <mod> are ignored.')
    parser.add_argument('-p', '--pylab', dest='pylab', action="store_true", default=False,
                        help='For use together with "-i". Automatically "import numpy as np", '
                             '"import matplotlib.pyplot as plt", and enable mpl\'s interactive '
                             'mode (somewhat like IPython\'s pylab mode).')
    opts = parser.parse_args()

    if opts.interactive:
        import readline  # noqa: F401, imported for side effects: enable GNU readline in input()
        import rlcompleter  # noqa: F401, imported for side effects
        repl_locals = {}
        if opts.pylab:  # like IPython's pylab mode, but we keep things in separate namespaces.
            import numpy
            import matplotlib.pyplot
            repl_locals["np"] = numpy
            repl_locals["plt"] = matplotlib.pyplot
            matplotlib.pyplot.ion()
        readline.set_completer(rlcompleter.Completer(namespace=repl_locals).complete)
        readline.parse_and_bind("tab: complete")  # PyPy ignores this, but not needed there.
        from mcpy.repl.console import MacroConsole
        import sys
        sys.path.insert(0, '')  # Add CWD to import path like the builtin interactive console does.
        m = MacroConsole(locals=repl_locals)
        return m.interact()

    if not opts.filename and not opts.module:
        parser.print_help()
        import sys
        sys.exit(0)
    if opts.filename and opts.module:
        raise ValueError("Please specify just one program to run (either filename or -m module, not both).")

    # Import the module, pretending its name is "__main__".
    #
    # We must import so that macros get expanded, so we can't use
    # runpy.run_module here (which just execs without importing).
    if opts.filename:
        # like "python3 foo/bar.py", we don't initialize any parent packages.
        if not os.path.isfile(opts.filename):
            raise FileNotFoundError("Can't open file '{}'".format(opts.filename))
        # This finds the wrong (standard) loader for macro-enabled scripts...
#        spec = spec_from_file_location("__main__", opts.filename)
#        if not spec:
#            raise ImportError("Not a Python module: '{}'".format(opts.filename))
#        module = module_from_spec(spec)
#        spec.loader.exec_module(module)
        # FIXME: wild guess (see Pyan3 for a better guess?)
        module_name = opts.filename.replace(os.path.sep, '.')
        if module_name.endswith(".__init__.py"):
            module_name = module_name[:-12]
        elif module_name.endswith(".py"):
            module_name = module_name[:-3]
        import_module_as_main(module_name, script_mode=True)
    else:  # opts.module
        # like "python3 -m foo.bar", we initialize parent packages.
        import_module_as_main(opts.module, script_mode=False)

if __name__ == '__main__':
    main()
