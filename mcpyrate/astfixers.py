# -*- coding: utf-8; -*-
'''Fix missing `ctx` attributes and source location info in an AST.'''

__all__ = ['fix_missing_ctx', 'fix_missing_locations']

from ast import (Load, Store, Del,
                 Assign, AnnAssign, AugAssign,
                 Attribute, Subscript,
                 comprehension,
                 For, AsyncFor,
                 withitem,
                 Delete,
                 iter_child_nodes)

from .walker import Walker

try:  # Python 3.8+
    from ast import NamedExpr
except ImportError:
    class _NoSuchNodeType:
        pass
    NamedExpr = _NoSuchNodeType


class _CtxFixer(Walker):
    def __init__(self):
        super().__init__(ctxclass=Load)

    def transform(self, tree):
        self._fix_one(tree)
        self._setup_subtree_contexts(tree)
        return self.generic_visit(tree)

    def _fix_one(self, tree):
        '''Fix one missing `ctx` attribute, using the currently active ctx class.'''
        if ("ctx" in type(tree)._fields and (not hasattr(tree, "ctx") or tree.ctx is None)):
            tree.ctx = self.state.ctxclass()

    def _setup_subtree_contexts(self, tree):
        '''Autoselect correct `ctx` class for subtrees of `tree`.'''
        # The default ctx class is `Load`. We set up any `Store` and `Del`, as
        # well as any `Load` for trees that may appear inside others that are
        # set up as `Store` or `Del` (that mainly concerns expressions).
        tt = type(tree)
        if tt is Assign:
            self.withstate(tree.targets, ctxclass=Store)
            self.withstate(tree.value, ctxclass=Load)
        elif tt is AnnAssign:
            self.withstate(tree.target, ctxclass=Store)
            self.withstate(tree.annotation, ctxclass=Load)
            if tree.value:
                self.withstate(tree.value, ctxclass=Load)
        elif tt is NamedExpr:
            self.withstate(tree.target, ctxclass=Store)
            self.withstate(tree.value, ctxclass=Load)
        elif tt is AugAssign:
            # `AugStore` and `AugLoad` are for internal use only, not even
            # meant to be exposed to the user; the compiler expects `Store`
            # and `Load` here. https://bugs.python.org/issue39988
            self.withstate(tree.target, ctxclass=Store)
            self.withstate(tree.value, ctxclass=Load)

        elif tt is Attribute:
            # The tree's own `ctx` can be whatever, but `value` always has `Load`.
            self.withstate(tree.value, ctxclass=Load)
        elif tt is Subscript:
            # The tree's own `ctx` can be whatever, but `value` and `slice` always have `Load`.
            self.withstate(tree.value, ctxclass=Load)
            self.withstate(tree.slice, ctxclass=Load)

        elif tt is comprehension:
            self.withstate(tree.target, ctxclass=Store)
            self.withstate(tree.iter, ctxclass=Load)
            self.withstate(tree.ifs, ctxclass=Load)

        elif tt in (For, AsyncFor):
            self.withstate(tree.target, ctxclass=Store)
            self.withstate(tree.iter, ctxclass=Load)
        elif tt is withitem:
            self.withstate(tree.context_expr, ctxclass=Load)
            self.withstate(tree.optional_vars, ctxclass=Store)

        elif tt is Delete:
            self.withstate(tree.targets, ctxclass=Del)


def fix_missing_ctx(tree):
    '''Fix any missing `ctx` attributes in `tree`.

    Modifies `tree` in-place. For convenience, returns the modified `tree`.
    '''
    return _CtxFixer().visit(tree)


def fix_missing_locations(tree, reference_node):
    '''Like `ast.fix_missing_locations`, but customized for a macro expander.

    Differences:

      - At the top level of `tree`, initialize `lineno` and `col_offset`
        to those of `reference_node`.
        - If `reference_node` has no location info, no-op.
      - If `tree is None`, no-op.
      - If `tree` is a `list` of AST nodes, loop over it.

    Modifies `tree` in-place. For convenience, returns the modified `tree`.
    '''
    if not (hasattr(reference_node, "lineno") and hasattr(reference_node, "col_offset")):
        return tree
    def _fix(tree, lineno, col_offset):
        if tree is None:
            return
        if isinstance(tree, list):
            for elt in tree:
                _fix(elt, lineno, col_offset)
            return
        if 'lineno' in tree._attributes:
            if not hasattr(tree, 'lineno'):
                tree.lineno = lineno
            else:
                lineno = tree.lineno
        if 'col_offset' in tree._attributes:
            if not hasattr(tree, 'col_offset'):
                tree.col_offset = col_offset
            else:
                col_offset = tree.col_offset
        for child in iter_child_nodes(tree):
            _fix(child, lineno, col_offset)
    _fix(tree, reference_node.lineno, reference_node.col_offset)
    return tree
