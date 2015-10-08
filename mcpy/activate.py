'''Install mcpy hooks to preprocess source files.

Actually, the library monkey-patches SourceFileLoader to compile the code
in a different way, providing the macro-expansion for the AST before compiling
into real code.
'''

from .importhooks import source_to_xcode, nop
from importlib.machinery import SourceFileLoader
SourceFileLoader.source_to_code = source_to_xcode
SourceFileLoader.set_data = nop
