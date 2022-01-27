# -*- coding: utf-8 -*-
"""The dialect should inject its template into this module, hence the weirdest test ever."""

from .dialects import dialects, OurPowersCombined  # noqa: F401

def runtests():
    assert x1 == "Hello from transform_source of OurPowersCombined dialect"  # noqa: F821, `x1` is injected by the dialect.
    assert x2 == "Hello from transform_ast of OurPowersCombined dialect"  # noqa: F821, `x2` is injected by the dialect.

if __name__ == '__main__':
    runtests()
