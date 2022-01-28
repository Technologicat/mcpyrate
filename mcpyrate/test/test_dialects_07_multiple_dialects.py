# -*- coding: utf-8 -*-
"""Test using multiple dialects in the same source file."""

from .dialects import dialects, OurPowersCombined  # noqa: F401, F811
from .dialects import dialects, Tumbler  # noqa: F401, F811

def runtests():
    assert x1 == "Hello from transform_source of OurPowersCombined dialect"  # noqa: F821, `x1` is injected by the dialect.
    assert x2 == "Hello from transform_ast of OurPowersCombined dialect"  # noqa: F821, `x2` is injected by the dialect.

    assert 21 == int(2.0 * 21.0)  # AST postprocessor test

if __name__ == '__main__':
    runtests()
