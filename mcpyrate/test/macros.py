# -*- coding: utf-8 -*-

from ..quotes import macros, q, a, h  # noqa: F401

from ..expander import namemacro

def f():
    return "f from macro definition site"

# --------------------------------------------------------------------------------
# quasiquotes

@namemacro
def test_q(tree, **kw):
    return q[f()]

@namemacro
def test_hq(tree, **kw):
    return q[h[f]()]

# --------------------------------------------------------------------------------

@namemacro
def magicname(tree, **kw):
    return q[x]  # noqa: F821, only quoted

@namemacro
def magicname2(tree, **kw):
    return tree

# multi-layer macro expansion
def first(tree, *, syntax, **kw):
    return q[second[a[tree]]]

def second(tree, *, syntax, **kw):
    return q[third[a[tree]]]

def third(tree, *, syntax, **kw):
    return q[2 * a[tree]]
