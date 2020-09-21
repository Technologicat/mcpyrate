# -*- coding: utf-8; -*-

import ast
import uuid

def ast_aware_repr(thing):
    """Like repr(), but supports ASTs.

    Like MacroPy's `real_repr`.
    """
    if isinstance(thing, ast.AST):
        fields = [ast_aware_repr(b) for a, b in ast.iter_fields(thing)]
        return '{}({})'.format(thing.__class__.__name__, ', '.join(fields))
    elif isinstance(thing, list):  # e.g. multi-statement body
        return '[{}]'.format(', '.join(ast_aware_repr(elt) for elt in thing))
    return repr(thing)

def gensym(basename=None):
    """Create a name for a new, unused lexical identifier, and return the name as an `str`."""
    # We use an uuid to avoid the need for any lexical scanning.
    unique = "{}_gensym".format(str(uuid.uuid4()).replace('-', ''))
    if basename:
        sym = "{}_{}".format(basename, unique)
    else:
        sym = unique
    assert sym.isidentifier()
    return sym

# TODO: for macro debugging, we need something like MacroPy's show_expanded.
# def expand(tree, *, syntax, expand_macros, **kw):
#     """Macroexpand an AST and return the result."""
#     tree = expand_macros(tree)
#     # We must use q as a regular function, since we can't import it as a macro in this module itself.
#     return q(tree, syntax=syntax, expand_macros=expand_macros)
