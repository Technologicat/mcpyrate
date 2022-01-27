# -*- coding: utf-8 -*-
"""Test the `postprocess_ast` feature of dialects."""

from .dialects import dialects, Tumbler  # noqa: F401

def runtests():
    # On the RHS, use floats to avoid the test postprocessor that doubles bare `int`,
    # so that we can provide a value to assert against.
    assert 21 == int(2.0 * 21.0)

if __name__ == '__main__':
    runtests()
