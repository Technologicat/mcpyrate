# -*- coding: utf-8; -*-
"""mcpyrate test suite.

Test modules are numbered so that lower-layer infrastructure is tested first.
The test runner discovers and runs them in alphabetical (= numerical) order.
Numbers are zero-padded to three digits, spaced by 10 to allow insertion
without renumbering.

Layer map:

  Import hook:
    005  activate

  Rendering infrastructure:
    010  astdumper
    020  unparser

  Pure utilities (no macro infrastructure):
    030  bunch
    040  astfixers
    050  pycachecleaner
    060  utils
    070  walkers

  Higher abstractions:
    080  markers
    090  coreutils

  Expansion machinery:
    100  core (a), expander (b)
    110  debug
    115  metatools

  Macro-dependent tests (use quasiquotes):
    120  quotes (a), compiler (b)
    130  splicing

  Dialect tests use their own numbering scheme (test_dialects_NN_*).
"""
