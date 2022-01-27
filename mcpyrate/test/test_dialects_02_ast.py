# -*- coding: utf-8 -*-
"""The dialect should inject its template into this module, hence the weirdest test ever."""

from .dialects import dialects, Texan  # noqa: F401

def runtests():
    assert x == "Howdy from Texan dialect"  # noqa: F821, `x` is injected by the dialect.

if __name__ == '__main__':
    runtests()
