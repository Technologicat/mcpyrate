# -*- coding: utf-8 -*-
"""Tests for the Bunch container."""

from collections.abc import Mapping, MutableMapping, Container, Iterable, Sized

from ..bunch import Bunch, bunchify


def runtests():
    # -- Construction and attribute access --

    def test_basic_construction():
        b = Bunch(cat="meow", dog="woof")
        assert b.cat == "meow"
        assert b.dog == "woof"
    test_basic_construction()

    def test_empty_construction():
        b = Bunch()
        assert len(b) == 0
    test_empty_construction()

    def test_setattr():
        b = Bunch()
        b.x = 42
        assert b.x == 42
    test_setattr()

    def test_delattr():
        b = Bunch(x=42)
        del b.x
        assert "x" not in b
    test_delattr()

    def test_setattr_reserved_raises():
        b = Bunch()
        try:
            b.copy = "nope"
        except AttributeError:
            pass
        else:
            assert False, "setting a reserved attribute should raise"
    test_setattr_reserved_raises()

    def test_getattr_missing_raises():
        b = Bunch()
        try:
            _ = b.nonexistent
        except KeyError:
            pass
        else:
            assert False, "accessing a missing attribute should raise"
    test_getattr_missing_raises()

    # -- copy and replace --

    def test_copy():
        b = Bunch(x=1, y=2)
        c = b.copy()
        assert c.x == 1 and c.y == 2
        c.x = 99
        assert b.x == 1  # original unchanged
    test_copy()

    def test_replace():
        a = Bunch(x=1)
        b = Bunch(y=2)
        a.replace(b)
        assert "y" in a and "x" not in a
    test_replace()

    def test_replace_type_error():
        b = Bunch()
        try:
            b.replace({"not": "a bunch"})
        except TypeError:
            pass
        else:
            assert False, "replace with non-Bunch should raise TypeError"
    test_replace_type_error()

    # -- Container, Iterable, Sized --

    def test_contains():
        b = Bunch(x=1)
        assert "x" in b
        assert "y" not in b
    test_contains()

    def test_iter():
        b = Bunch(a=1, b=2, c=3)
        assert set(b) == {"a", "b", "c"}
    test_iter()

    def test_len():
        assert len(Bunch()) == 0
        assert len(Bunch(a=1, b=2)) == 2
    test_len()

    # -- Mapping (dict-like) interface --

    def test_getitem_setitem():
        b = Bunch()
        b["x"] = 42
        assert b["x"] == 42
    test_getitem_setitem()

    def test_delitem():
        b = Bunch(x=42)
        del b["x"]
        assert "x" not in b
    test_delitem()

    def test_keys_values_items():
        b = Bunch(a=1, b=2)
        assert set(b.keys()) == {"a", "b"}
        assert set(b.values()) == {1, 2}
        assert set(b.items()) == {("a", 1), ("b", 2)}
    test_keys_values_items()

    def test_get():
        b = Bunch(x=1)
        assert b.get("x") == 1
        assert b.get("y") is None
        assert b.get("y", 42) == 42
    test_get()

    def test_eq_ne():
        b = Bunch(x=1, y=2)
        assert b == {"x": 1, "y": 2}
        assert b != {"x": 1}
        assert b != {"x": 1, "y": 99}
    test_eq_ne()

    # -- MutableMapping --

    def test_pop():
        b = Bunch(x=1, y=2)
        assert b.pop("x") == 1
        assert "x" not in b
        assert b.pop("z", "default") == "default"
    test_pop()

    def test_popitem():
        b = Bunch(x=1)
        k, v = b.popitem()
        assert k == "x" and v == 1
        assert len(b) == 0
    test_popitem()

    def test_clear():
        b = Bunch(x=1, y=2)
        b.clear()
        assert len(b) == 0
    test_clear()

    def test_update():
        b = Bunch(x=1)
        b.update(y=2, z=3)
        assert b.y == 2 and b.z == 3
    test_update()

    def test_setdefault():
        b = Bunch(x=1)
        assert b.setdefault("x", 99) == 1  # existing key unchanged
        assert b.setdefault("y", 42) == 42  # new key gets default
        assert b.y == 42
    test_setdefault()

    # -- ABC registration --

    def test_abc_isinstance():
        b = Bunch()
        for abc in (Mapping, MutableMapping, Container, Iterable, Sized):
            assert isinstance(b, abc), f"Bunch should be a virtual subclass of {abc}"
    test_abc_isinstance()

    # -- bunchify --

    def test_bunchify_from_dict():
        d = {"foo": "variable", "bar": "tavern"}
        b = bunchify(d)
        assert b.foo == "variable"
        assert b.bar == "tavern"
        # No copy — mutating d is visible through b.
        d["foo"] = "changed"
        assert b.foo == "changed"
    test_bunchify_from_dict()

    def test_bunchify_idempotent():
        b = Bunch(x=1)
        assert bunchify(b) is b
    test_bunchify_idempotent()

    def test_bunchify_bad_type():
        try:
            bunchify("not a mapping")
        except TypeError:
            pass
        else:
            assert False, "bunchify with non-mapping should raise TypeError"
    test_bunchify_bad_type()

    def test_bunchify_invalid_keys():
        try:
            bunchify({"valid": 1, "not valid": 2, "3bad": 3})
        except ValueError as e:
            msg = str(e)
            assert "not valid" in msg
            assert "3bad" in msg
        else:
            assert False, "bunchify with non-identifier keys should raise ValueError"
    test_bunchify_invalid_keys()

    print("    test_bunch: all passed")


if __name__ == '__main__':
    runtests()
