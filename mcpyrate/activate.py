# -*- coding: utf-8; -*-
'''Install mcpyrate hooks to preprocess source files.

Actually, we monkey-patch ``SourceFileLoader` and `FileFinder`, to compile the
code in a different way, macroexpanding the AST before compiling into bytecode.

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
'''

__all__ = ["activate", "deactivate"]

from importlib.machinery import SourceFileLoader, FileFinder
from .importer import source_to_xcode, path_xstats, invalidate_xcaches


def activate():
    SourceFileLoader.source_to_code = source_to_xcode
    # Bytecode caching (`.pyc`) support. If you need to force-disable `.pyc`
    # caching, replace `SourceFileLoader.set_data` with a no-op, like `mcpy` does.
    SourceFileLoader.path_stats = path_xstats
    FileFinder.invalidate_caches = invalidate_xcaches


def deactivate():
    SourceFileLoader.source_to_code = stdlib_source_to_code
    SourceFileLoader.path_stats = stdlib_path_stats
    FileFinder.invalidate_caches = stdlib_invalidate_caches


stdlib_source_to_code = SourceFileLoader.source_to_code
stdlib_path_stats = SourceFileLoader.path_stats
stdlib_invalidate_caches = FileFinder.invalidate_caches
activate()
