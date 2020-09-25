# -*- coding: utf-8; -*-
'''Fix any missing `ctx` attributes in an AST.

Allows you to build your ASTs without caring about that stuff and just
fill it in later.
'''

from ast import (Load, Store, Del,
                 Assign, AnnAssign, AugAssign,
                 Attribute, Subscript,
                 comprehension,
                 For, AsyncFor,
                 withitem,
                 Delete)
from .walkers import Walker

try:
    from ast import NamedExpr  # Python 3.8+
except ImportError:
    class _NoSuchNodeType:
        pass
    NamedExpr = _NoSuchNodeType

__all__ = ['fix_missing_ctx']

class _CtxFixer(Walker):
    def __init__(self):
        super().__init__(ctx=Load)

    def process(self, tree):
        self._fix_one(tree)
        self._analyze_subtrees(tree)
        self.generic_visit(tree)
        return tree

    def _fix_one(self, tree):
        '''Fix one missing `ctx` attribute, using the currently active ctx class.'''
        if ("ctx" in type(tree)._fields and (not hasattr(tree, "ctx") or tree.ctx is None)):
            tree.ctx = self.state.ctx()

    def _analyze_subtrees(self, tree):
        '''Automatically set up which `ctx` to use for subtrees of `tree`, depending on `type(tree)`.'''
        # The default ctx class is `Load`. We have to set up any `Store` and
        # `Del`, as well as any `Load` for trees that may appear inside others
        # that have `Store` or `Del` (that mainly concerns expressions).
        tt = type(tree)
        if tt is Assign:
            self.withstate(tree.targets, ctx=Store)
            self.withstate(tree.value, ctx=Load)
        elif tt is AnnAssign:
            self.withstate(tree.target, ctx=Store)
            self.withstate(tree.annotation, ctx=Load)
            if tree.value:
                self.withstate(tree.value, ctx=Load)
        elif tt is NamedExpr:
            self.withstate(tree.target, ctx=Store)
            self.withstate(tree.value, ctx=Load)
        elif tt is AugAssign:
            # `AugStore` and `AugLoad` are for internal use only, not even
            # meant to be exposed to the user; the compiler expects `Store`
            # and `Load` here. https://bugs.python.org/issue39988
            self.withstate(tree.target, ctx=Store)
            self.withstate(tree.value, ctx=Load)

        elif tt is Attribute:
            # The tree's own `ctx` can be whatever, but `value` always has `Load`.
            self.withstate(tree.value, ctx=Load)
        elif tt is Subscript:
            # The tree's own `ctx` can be whatever, but `value` and `slice` always have `Load`.
            self.withstate(tree.value, ctx=Load)
            self.withstate(tree.slice, ctx=Load)

        elif tt is comprehension:
            self.withstate(tree.target, ctx=Store)
            self.withstate(tree.iter, ctx=Load)
            self.withstate(tree.ifs, ctx=Load)

        elif tt in (For, AsyncFor):
            self.withstate(tree.target, ctx=Store)
            self.withstate(tree.iter, ctx=Load)
        elif tt is withitem:
            self.withstate(tree.context_expr, ctx=Load)
            self.withstate(tree.optional_vars, ctx=Store)

        elif tt is Delete:
            self.withstate(tree.targets, ctx=Del)

def fix_missing_ctx(tree):
    '''Fix any missing `ctx` attributes in `tree`.

    Modifies `tree` in-place. For convenience, returns the modified `tree`.
    '''
    ctxfixer = _CtxFixer()
    return ctxfixer.visit(tree)
