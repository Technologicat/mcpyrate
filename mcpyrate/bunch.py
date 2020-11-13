# -*- coding: utf-8; -*-

__all__ = ["Bunch"]

from collections.abc import Mapping, MutableMapping, Container, Iterable, Sized

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
        """Return a copy of this `Bunch`."""
        return Bunch(**{k: v for k, v in self._data.items()})
    def replace(self, other):
        """Replace all data in this `Bunch` with data from the `other` one (shallow-copying it)."""
        if not isinstance(other, Bunch):
            raise TypeError(f"expected Bunch, got {type(other)} with value {repr(other)}")
        self._data = other.copy()._data

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
    def __contains__(self, name):
        return self._data.__contains__(name)
    def __iter__(self):
        return self._data.__iter__()
    def __len__(self):
        return len(self._data)

    # Mapping
    def __getitem__(self, name):
        return self._data.__getitem__(name)
    def __setitem__(self, name, value):
        return self._data.__setitem__(name, value)
    def __delitem__(self, name):
        return self._data.__delitem__(name)
    def keys(self):
        return self._data.keys()
    def items(self):
        return self._data.items()
    def values(self):
        return self._data.values()
    def get(self, name, default=None):
        return self[name] if name in self else default
    def __eq__(self, other):
        return other == self._data
    def __ne__(self, other):
        return other != self._data

    # MutableMapping
    def pop(self, name, *default):
        return self._data.pop(name, *default)
    def popitem(self):
        return self._data.popitem()
    def clear(self):
        return self._data.clear()
    def update(self, **bindings):
        self._data.update(**bindings)
    def setdefault(self, name, *default):
        return self._data.setdefault(name, *default)

    def __repr__(self):  # pragma: no cover
        bindings = [f"{name:s}={repr(value)}" for name, value in self._data.items()]
        args = ", ".join(bindings)
        return f"Bunch({args})"

for abscls in (Mapping, MutableMapping, Container, Iterable, Sized):  # virtual ABCs
    abscls.register(Bunch)
del abscls
