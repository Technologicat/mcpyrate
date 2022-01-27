# -*- coding: utf-8 -*-
"""Test whether a user module with future imports compiles when using a dialect."""

# TODO: We may need to update this as language versions march on
# TODO: and the set of available `__future__` features changes.
from __future__ import annotations

from .dialects import dialects, Texan  # noqa: F401

def runtests():
    assert x == "Howdy from Texan dialect"  # noqa: F821, `x` is injected by the dialect.

if __name__ == '__main__':
    runtests()
