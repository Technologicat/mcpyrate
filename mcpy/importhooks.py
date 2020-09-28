# -*- coding: utf-8; -*-

__all__ = ['nop', 'source_to_xcode']

import ast
from .core import MacroExpansionError
from .expander import find_macros, expand_macros
from .markers import get_markers

def nop(*args, **kw): pass

def source_to_xcode(self, data, path, *, _optimize=-1):
    '''Intercepts the source to code transformation and expand the macros
    before compiling to actual code.'''
    tree = ast.parse(data)
    module_macro_bindings = find_macros(tree)
    expansion = expand_macros(tree, bindings=module_macro_bindings, filename=path)
    remaining_markers = get_markers(expansion)
    if remaining_markers:
        raise MacroExpansionError("{path}: AST markers remaining after expansion: {remaining_markers}")
    return compile(expansion, path, 'exec', dont_inherit=True,
                   optimize=_optimize)
