# -*- coding: utf-8; -*-
"""mcpyrate test suite.

Test modules are numbered so that lower-layer infrastructure is tested first.
The test runner discovers and runs them in alphabetical (= numerical) order.

Layer map:

  Rendering infrastructure:
    01  astdumper
    02  unparser

  Pure utilities (no macro infrastructure):
    03  bunch
    04  astfixers (a), pycachecleaner (b)
    05  utils
    06  walkers

  Higher abstractions:
    07  markers
    08  coreutils

  Expansion machinery:
    09  core (a), expander (b)
    10  debug

  Macro-dependent tests (use quasiquotes):
    11  quotes (a), compiler (b)
    12  splicing

  Dialect tests use their own numbering scheme (test_dialects_NN_*).
"""
