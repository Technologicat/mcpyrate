# -*- coding: utf-8; -*-

from ast import (NodeTransformer,
                 Load, Store, Del,
                 Assign, AnnAssign, AugAssign,
                 Attribute, Subscript,
                 comprehension,
                 For, AsyncFor,
                 withitem,
                 Delete)

try:
    from ast import NamedExpr  # Python 3.8+
except ImportError:
    class _NoSuchNodeType:
        pass
    NamedExpr = _NoSuchNodeType

__all__ = ['fix_missing_ctx']

class _CtxFixer(NodeTransformer):
    '''Fix any missing `ctx` attributes in an AST.

    Allows you to build your ASTs without caring about that stuff and just
    fill it in later.
    '''
    def __init__(self):
        self.stack = [Load]
        self.subtrees = {}

    def visit(self, tree):
        newctx = self.subtrees.pop(id(tree), False)
        if newctx:
            self.stack.append(newctx)

        self._fix_one(tree)
        self._analyze_subtrees(tree)
        self.generic_visit(tree)

        if newctx:
            self.stack.pop()
        return tree

    def _fix_one(self, tree):
        '''Fix one missing `ctx` attribute, using the currently active ctx.'''
        if ("ctx" in type(tree)._fields and (not hasattr(tree, "ctx") or tree.ctx is None)):
            tree.ctx = self.stack[-1]()

    def _set_ctx_for(self, tree, newctx):
        '''Use ctx class `newctx` for `tree` and its subtrees, recursively.'''
        self.subtrees[id(tree)] = newctx

    def _analyze_subtrees(self, tree):
        '''Automatically set up which `ctx` to use for subtrees of `tree`, depending on `type(tree)`.'''
        # The default ctx class is `Load`. We have to set up any `Store` and
        # `Del`, as well as any `Load` for trees that may appear inside others
        # that have `Store` or `Del` (that mainly concerns expressions).
        tt = type(tree)
        if tt is Assign:
            for x in tree.targets:
                self._set_ctx_for(x, Store)
            self._set_ctx_for(tree.value, Load)
        elif tt is AnnAssign:
            self._set_ctx_for(tree.target, Store)
            self._set_ctx_for(tree.annotation, Load)
            if tree.value:
                self._set_ctx_for(tree.value, Load)
        elif tt is NamedExpr:  # TODO
            self._set_ctx_for(tree.target, Store)
            self._set_ctx_for(tree.value, Load)
        elif tt is AugAssign:
            # `AugStore` and `AugLoad` are for internal use only, not even
            # meant to be exposed to the user; the compiler expects `Store`
            # and `Load` here. https://bugs.python.org/issue39988
            self._set_ctx_for(tree.target, Store)
            self._set_ctx_for(tree.value, Load)

        elif tt is Attribute:
            # The tree's own `ctx` can be whatever, but `value` always has `Load`.
            self._set_ctx_for(tree.value, Load)
        elif tt is Subscript:
            # The tree's own `ctx` can be whatever, but `value` and `slice` always have `Load`.
            self._set_ctx_for(tree.value, Load)
            self._set_ctx_for(tree.slice, Load)

        elif tt is comprehension:
            self._set_ctx_for(tree.target, Store)
            self._set_ctx_for(tree.iter, Load)
            for x in tree.ifs:
                self._set_ctx_for(x, Load)

        elif tt in (For, AsyncFor):
            self._set_ctx_for(tree.target, Store)
            self._set_ctx_for(tree.iter, Load)
        elif tt is withitem:
            self._set_ctx_for(tree.context_expr, Load)
            self._set_ctx_for(tree.optional_vars, Store)

        elif tt is Delete:
            for x in tree.targets:
                self._set_ctx_for(x, Del)

def fix_missing_ctx(tree):
    '''Fix any missing `ctx` attributes in an AST.

    Allows you to build your ASTs without caring about that stuff and just
    fill it in later.
    '''
    ctxfixer = _CtxFixer()
    return ctxfixer.visit(tree)
