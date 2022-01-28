"""mcpyrate: Advanced macro expander and language lab for Python."""

from .astdumper import dump  # noqa: F401
from .core import MacroExpansionError  # noqa: F401
from .dialects import Dialect  # noqa: F401
from .expander import namemacro, parametricmacro  # noqa: F401
from .unparser import unparse  # noqa: F401
from .utils import gensym  # noqa: F401

# For public API inspection, import modules that wouldn't otherwise get imported.
from . import ansi  # noqa: F401
from . import debug  # noqa: F401
from . import metatools  # noqa: F401
from . import pycachecleaner  # noqa: F401
from . import quotes  # noqa: F401
from . import splicing  # noqa: F401

__version__ = "3.6.0"
