# -*- coding: utf-8; -*-

import ast
import uuid

__all__ = ['ast_aware_repr', 'gensym', 'Bunch']

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


_previous_gensyms = set()
def gensym(basename=None):
    """Create a name for a new, unused lexical identifier, and return the name as an `str`.

    We include an uuid in the name to avoid the need for any lexical scanning.

    Can also be used for globally unique string keys, in which case `basename`
    does not need to be a valid identifier.
    """
    def generate():
        unique = "gensym_{}".format(str(uuid.uuid4()).replace('-', ''))
        if basename:
            sym = "{}_{}".format(basename, unique)
        else:
            sym = unique
        return sym
    sym = generate()
    # This will never trigger, but let's be obsessively correct. The uuid
    # spec does not guarantee no collisions; they're only astronomically
    # unlikely.
    while sym in _previous_gensyms:
        generate()
    _previous_gensyms.add(sym)
    return sym

# TODO: for macro debugging, we need something like MacroPy's show_expanded.
# def expand(tree, *, syntax, expand_macros, **kw):
#     """Macroexpand an AST and return the result."""
#     tree = expand_macros(tree)
#     # We must use q as a regular function, since we can't import it as a macro in this module itself.
#     return q(tree, syntax=syntax, expand_macros=expand_macros)

class Bunch:  # see unpythonic.env for a complete solution
    """Utility: bunch of named values.

    Supports `Mapping` and `MutableMapping` interfaces from `collections.abc`.

    Example::

        b = Bunch(cat="meow", dog="woof")
        assert b.cat == "meow"
        assert b.dog == "woof"
    """
    def __init__(self, **bindings):
        self._data = bindings

    def copy(self):
        return Bunch(**{k: v for k, v in self._data.items()})

    def __getattr__(self, name):
        return self._data[name]
    def __setattr__(self, name, value):
        if name == "_data":
            return super().__setattr__(name, value)
        self._data[name] = value
    def __delattr__(self, name):
        del self._data[name]

    def __contains__(self, name):
        return self._data.__contains__(name)
    def __iter__(self):
        return self._data.__iter__()
    def __len__(self):
        return len(self._data)

    # Mapping
    def __eq__(self, other):
        return other == self._data
    def get(self, name, default=None):
        return self[name] if name in self else default
    def items(self):
        return self._data.items()
    def keys(self):
        return self._data.keys()
    def values(self):
        return self._data.values()

    # MutableMapping
    def clear(self):
        return self._data.clear()
    def pop(self, name, *default):
        return self._data.pop(name, *default)
    def popitem(self):
        return self._data.popitem()
    def setdefault(self, name, *default):
        return self._data.setdefault(name, *default)
    def update(self, **bindings):
        self._data.update(**bindings)

    def __repr__(self):  # pragma: no cover
        bindings = ["{:s}={}".format(name, repr(value)) for name, value in self._data.items()]
        return "Bunch({})".format(", ".join(bindings))
