# -*- coding: utf-8; -*-

__all__ = ['ast_aware_repr', 'gensym', 'flatten_suite', 'Bunch']

import ast
from collections.abc import Mapping, MutableMapping, Container, Iterable, Sized
import uuid

def ast_aware_repr(thing):
    """Like repr(), but supports ASTs.

    Similar to MacroPy's `real_repr`. The method `ast.AST.__repr__` itself
    can't be monkey-patched, because `ast.AST` is a built-in/extension type.
    """
    if isinstance(thing, ast.AST):
        fields = [ast_aware_repr(b) for a, b in ast.iter_fields(thing)]
        args = ', '.join(fields)
        return f"{thing.__class__.__name__}({args})"
    elif isinstance(thing, list):  # statement suite
        elts = ', '.join(ast_aware_repr(elt) for elt in thing)
        return f"[{elts}]"
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
        return f"{basename}_{unique}"
    sym = generate()
    # The uuid spec does not guarantee no collisions, only a vanishingly small chance.
    while sym in _previous_gensyms:
        sym = generate()  # pragma: no cover
    _previous_gensyms.add(sym)
    return sym


def flatten_suite(lst):
    """Flatten a statement suite (by one level).

    `lst` may contain both individual items and `list`s. Any item that
    `is None` is omitted. If the final result is empty, then instead of
    an empty list, return `None`.
    """
    out = []
    for elt in lst:
        if isinstance(elt, list):
            out.extend(elt)
        elif elt is not None:
            out.append(elt)
    return out if out else None


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
        bindings = [f"{name:s}={repr(value)}" for name, value in self._data.items()]
        args = ", ".join(bindings)
        return f"Bunch({args})"

for abscls in (Mapping, MutableMapping, Container, Iterable, Sized):  # virtual ABCs
    abscls.register(Bunch)
del abscls
