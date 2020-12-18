# -*- coding: utf-8; -*-
"""Install mcpyrate hooks to preprocess source files.

Actually, we monkey-patch `SourceFileLoader`, to compile the code in a
different way, macroexpanding the AST before compiling into bytecode.

We also change `.pyc` cache invalidation, so that updating a macro definition
causes any source files that import that macro definition file to be re-expanded
and recompiled. This is considered recursively in a `make`-like fashion.

We **DO NOT** support PEP 552 (Deterministic pycs); only mtime-based pycs will
use our invalidation logic.

By default, `mcpyrate` caches bytecode (creates `.pyc` files) if Python itself does.
As of Python 3.8, the default is *enabled*, using mtime-based mode.

If you want to disable `.pyc` bytecode caching, use the standard Python
mechanisms. See the `-B` command-line flag of the Python interpreter,
the `PYTHONDONTWRITEBYTECODE` environment variable, and the attribute
`sys.dont_write_bytecode`.

    https://docs.python.org/3/using/cmdline.html#id1
    https://docs.python.org/3/using/cmdline.html#envvar-PYTHONDONTWRITEBYTECODE
    https://docs.python.org/3/library/sys.html#sys.dont_write_bytecode
    https://www.python.org/dev/peps/pep-0552/
"""

__all__ = ["activate", "deactivate"]

from importlib.machinery import SourceFileLoader
from .importer import source_to_xcode, path_xstats


def activate():
    """Activate `mcpyrate`.

    Called automatically once, when the module's top-level code executes.
    This typically happens when `mcpyrate.activate` is imported for the
    first time in the current process.

    The function is available so that if you call `deactivate`, it is possible
    to call `activate` to re-activate the macro expander.
    """
    SourceFileLoader.source_to_code = source_to_xcode
    # Bytecode caching (`.pyc`) support. If you need to force-disable `.pyc`
    # caching, replace `SourceFileLoader.set_data` with a no-op, like `mcpy` does.
    SourceFileLoader.path_stats = path_xstats


def deactivate():
    """Deactivate `mcpyrate`.

    This can be useful if you want the macro expander to be enabled only for
    some part of your codebase.
    """
    SourceFileLoader.source_to_code = stdlib_source_to_code
    SourceFileLoader.path_stats = stdlib_path_stats


stdlib_source_to_code = SourceFileLoader.source_to_code
stdlib_path_stats = SourceFileLoader.path_stats
activate()
