# -*- coding: utf-8; -*-
"""Fix `ctx` attributes and source location info in an AST."""

__all__ = ["fix_ctx", "fix_locations"]

from ast import (AnnAssign, Assign, AsyncFor, Attribute, AugAssign, Del,
                 Delete, For, Load, Store, Subscript, comprehension,
                 iter_child_nodes, withitem)
from copy import copy
from typing import Type

from . import walkers

try:  # Python 3.8+
    from ast import NamedExpr
except ImportError:
    class _NoSuchNodeType:
        pass
    NamedExpr: Type = _NoSuchNodeType  # type: ignore[no-redef]


class _CtxFixer(walkers.ASTTransformer):
    def __init__(self, *, copy_seen_nodes):
        super().__init__(ctxclass=Load)
        self.copy_seen_nodes = copy_seen_nodes

    def reset(self, **bindings):
        super().reset(**bindings)
        self._seen = set()

    def transform(self, tree):
        tree = self._fix_one(tree)
        self._setup_subtree_contexts(tree)
        return self.generic_visit(tree)

    def _fix_one(self, tree):
        """Fix one `ctx` attribute, using the currently active ctx class."""
        if "ctx" in type(tree)._fields:
            if self.copy_seen_nodes:
                # Shallow-copy `tree` if already seen. This mode is used in the
                # global postprocess pass. Note only nodes whose `ctx` we have
                # already updated are considered seen.
                if id(tree) in self._seen:
                    tree = copy(tree)
            tree.ctx = self.state.ctxclass()
            self._seen.add(id(tree))
        return tree

    def _setup_subtree_contexts(self, tree):
        """Autoselect correct `ctx` class for subtrees of `tree`."""
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
            # Those internal classes are indeed deprecated in Python 3.9.
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


def fix_ctx(tree, *, copy_seen_nodes):
    """Fix `ctx` attributes in `tree`.

    If `copy_seen_nodes=True`, then, if the same AST node instance appears
    multiple times, and the node requires a `ctx`, shallow-copy it the second
    and further times it is encountered. This prevents problems if the same
    node instance has been spliced into two or more positions that require
    different `ctx`.

    Modifies `tree` in-place. For convenience, returns the modified `tree`.
    """
    return _CtxFixer(copy_seen_nodes=copy_seen_nodes).visit(tree)


def fix_locations(tree, reference_node, *, mode):
    """Like `ast.fix_missing_locations`, but customized for a macro expander.

    Differences:

      - If `reference_node` has source no location info, return immediately (no-op).
      - If `tree is None`, return immediately (no-op).
      - If `tree` is a `list` of AST nodes, loop over it.

    The `mode` parameter:

      - If `mode="reference"`, populate any missing location info by
        copying it from `reference_node`. Always use the same reference info.

        Good when expanding a macro invocation, to set the source location
        of any macro-generated nodes to that of the macro invocation node.

      - If `mode="update"`, behave exactly like `ast.fix_missing_locations`,
        except that at the top level of `tree`, initialize `lineno` and
        `col_offset` from `reference_node` (instead of using `1` and `0`
        like `ast.fix_missing_locations` does).

        So if a node is missing location info, copy the current reference info
        in, but if it has location info, then update the reference info.

        Good for general use.

      - If `mode="overwrite"`, copy location info from `reference_node`,
        regardless of if the target node already has it.

        Good when `tree` is a code template that comes from another file,
        so that any line numbers already in the AST would be misleading
        at the use site (because they point to lines in that other file).

    Modifies `tree` in-place. For convenience, returns the modified `tree`.
    """
    if not (hasattr(reference_node, "lineno") and hasattr(reference_node, "col_offset")):
        return tree
    def _fix(tree, lineno, col_offset):
        if tree is None:
            return
        if isinstance(tree, list):
            for elt in tree:
                _fix(elt, lineno, col_offset)
            return
        if "lineno" in tree._attributes:
            if mode == "overwrite":
                tree.lineno = lineno
            else:
                if not hasattr(tree, "lineno"):
                    tree.lineno = lineno
                elif mode == "update":
                    lineno = tree.lineno
        if "col_offset" in tree._attributes:
            if mode == "overwrite":
                tree.col_offset = col_offset
            else:
                if not hasattr(tree, "col_offset"):
                    tree.col_offset = col_offset
                elif mode == "update":
                    col_offset = tree.col_offset
        for child in iter_child_nodes(tree):
            _fix(child, lineno, col_offset)
    _fix(tree, reference_node.lineno, reference_node.col_offset)
    return tree
