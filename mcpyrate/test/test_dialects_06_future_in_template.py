# -*- coding: utf-8 -*-
"""Test whether a template with future imports compiles when using a dialect."""

from .dialects import dialects, FutureTexan  # noqa: F401

def runtests():
    assert x == "Howdy from FutureTexan dialect"  # noqa: F821, `x` is injected by the dialect.

if __name__ == '__main__':
    runtests()
