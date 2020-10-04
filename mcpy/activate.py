# -*- coding: utf-8; -*-
'''Install mcpy hooks to preprocess source files.

Actually, we monkey-patch SourceFileLoader to compile the code in a
different way, macroexpanding the AST before compiling into bytecode.
'''

from .importer import source_to_xcode, nop, path_xstats
from importlib.machinery import SourceFileLoader
SourceFileLoader.source_to_code = source_to_xcode
SourceFileLoader.set_data = nop
SourceFileLoader.path_stats = path_xstats
