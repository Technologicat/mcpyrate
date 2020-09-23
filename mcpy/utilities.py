# -*- coding: utf-8; -*-

import ast
import uuid

__all__ = ['ast_aware_repr', 'gensym']

# TODO: monkey-patch ast.AST.__repr__ instead?
def ast_aware_repr(thing):
    """Like repr(), but supports ASTs.

    Similar to MacroPy's `real_repr`.
    """
    if isinstance(thing, ast.AST):
        fields = [ast_aware_repr(b) for a, b in ast.iter_fields(thing)]
        return '{}({})'.format(thing.__class__.__name__, ', '.join(fields))
    elif isinstance(thing, list):  # e.g. multi-statement body
        return '[{}]'.format(', '.join(ast_aware_repr(elt) for elt in thing))
    return repr(thing)

def gensym(basename=None):
    """Create a name for a new, unused lexical identifier, and return the name as an `str`.

    We include an uuid in the name to avoid the need for any lexical scanning.

    Can also be used for globally unique string keys, in which case `basename`
    does not need to be a valid identifier.
    """
    unique = "{}_gensym".format(str(uuid.uuid4()).replace('-', ''))
    if basename:
        sym = "{}_{}".format(basename, unique)
    else:
        sym = unique
    return sym

# TODO: for macro debugging, we need something like MacroPy's show_expanded.
# def expand(tree, *, syntax, expand_macros, **kw):
#     """Macroexpand an AST and return the result."""
#     tree = expand_macros(tree)
#     # We must use q as a regular function, since we can't import it as a macro in this module itself.
#     return q(tree, syntax=syntax, expand_macros=expand_macros)
