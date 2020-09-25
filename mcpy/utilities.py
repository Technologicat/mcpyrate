# -*- coding: utf-8; -*-

import ast
from collections.abc import Mapping, MutableMapping, Container, Iterable, Sized
import uuid

__all__ = ['ast_aware_repr', 'gensym', 'Bunch']

def ast_aware_repr(thing):
    """Like repr(), but supports ASTs.

    Similar to MacroPy's `real_repr`. The method `ast.AST.__repr__` itself
    can't be monkey-patched, because `ast.AST` is a built-in/extension type.
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
    basename = basename or "gensym"
    def generate():
        unique = str(uuid.uuid4()).replace('-', '')
        return "{}_{}".format(basename, unique)
    sym = generate()
    # The uuid spec does not guarantee no collisions, only a vanishingly small chance.
    while sym in _previous_gensyms:
        sym = generate()  # pragma: no cover
    _previous_gensyms.add(sym)
    return sym

# TODO: for macro debugging, we need something like MacroPy's show_expanded.
# def expand(tree, *, syntax, expand_macros, **kw):
#     """Macroexpand an AST and return the result."""
#     tree = expand_macros(tree)
#     # We must use q as a regular function, since we can't import it as a macro in this module itself.
#     return q(tree, syntax=syntax, expand_macros=expand_macros)

class Bunch:
    """A bunch of named values.

    Can be used instead of a `dict` when `b.someattr` is more readable than
    `d['somekey']`. In terms of `collections.abc`, a `MutableMapping`,
    `Container`, `Iterable`, `Sized`.

    Example::

        b = Bunch(cat="meow", dog="woof")
        assert b.cat == "meow"
        assert b.dog == "woof"
    """
    def __init__(self, **bindings):
        self._data = bindings
        self._reserved_names = []
        self._reserved_names = dir(self)

    def copy(self):
        return Bunch(**{k: v for k, v in self._data.items()})

    def __getattr__(self, name):
        return self._data[name]
    def __setattr__(self, name, value):
        if name in ("_data", "_reserved_names"):
            return super().__setattr__(name, value)
        if name in self._reserved_names:  # prevent shadowing get, pop, et al.
            raise AttributeError(f"Cannot write to reserved attribute '{name}'")
        self._data[name] = value
    def __delattr__(self, name):
        del self._data[name]

    # Container, Iterable, Sized
    def __contains__(self, name): return self._data.__contains__(name)
    def __iter__(self): return self._data.__iter__()
    def __len__(self): return len(self._data)

    # Mapping
    def __getitem__(self, name): return self._data.__getitem__(name)
    def __setitem__(self, name, value): return self._data.__setitem__(name, value)
    def __delitem__(self, name): return self._data.__delitem__(name)
    def keys(self): return self._data.keys()
    def items(self): return self._data.items()
    def values(self): return self._data.values()
    def get(self, name, default=None): return self[name] if name in self else default
    def __eq__(self, other): return other == self._data
    def __ne__(self, other): return other != self._data

    # MutableMapping
    def pop(self, name, *default): return self._data.pop(name, *default)
    def popitem(self): return self._data.popitem()
    def clear(self): return self._data.clear()
    def update(self, **bindings): self._data.update(**bindings)
    def setdefault(self, name, *default): return self._data.setdefault(name, *default)

    def __repr__(self):  # pragma: no cover
        bindings = ["{:s}={}".format(name, repr(value)) for name, value in self._data.items()]
        return "Bunch({})".format(", ".join(bindings))

for abscls in (Mapping, MutableMapping, Container, Iterable, Sized):  # virtual ABCs
    abscls.register(Bunch)
del abscls
