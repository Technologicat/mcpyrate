# -*- coding: utf-8; -*-
"""AST walkers.

These have a state stack and a node collector, and accept also a `list` of statements.
Otherwise they work like `ast.NodeVisitor` and `ast.NodeTransformer`.

Basic usage summary::

    def kittify(mytree):
        class Kittifier(ASTTransformer):
            def transform(self, tree):
                if type(tree) is ast.Constant:
                    self.collect(tree.value)
                    tree.value = "meow!" if self.state.meows % 2 == 0 else "miaow!"
                    self.state.meows += 1
                return self.generic_visit(tree)  # recurse
        w = Kittifier(meows=0)    # set the initial state here
        mytree = w.visit(mytree)  # it's basically an ast.NodeTransformer
        print(w.collected)        # collected values, in the order visited
        return mytree

    def getmeows(mytree):
        class MeowCollector(ASTVisitor):
            def examine(self, tree):
                if type(tree) is ast.Constant and tree.value in ("meow!", "miaow!"):
                    self.collect(tree)
                self.generic_visit(tree)
        w = MeowCollector()
        w.visit(mytree)
        print(w.collected)
        return w.collected

For an example of `withstate`, see `mcpyrate.astfixers`.
"""

__all__ = ["ASTVisitor", "ASTTransformer"]

from abc import ABCMeta, abstractmethod
from ast import NodeVisitor, NodeTransformer, iter_child_nodes

from .bunch import Bunch
from . import utils


class BaseASTWalker:
    """AST walker base class, providing a state stack and a node collector."""
    def __init__(self, **bindings):
        """Bindings are loaded into the initial `self.state` as attributes."""
        self.reset(**bindings)

    def reset(self, **bindings):
        """Clear everything. Load new bindings into a blank `self.state`."""
        self._stack = [Bunch(**bindings)]
        self._subtree_overrides = {}
        self.collected = []

    def _setstate(self, newstate):
        self._stack[-1] = newstate
        return newstate
    def _getstate(self):
        return self._stack[-1]
    state = property(fget=_getstate, fset=_setstate, doc="The current state. Mutable. Can be rebound to replace it.")

    def withstate(self, tree, **bindings):
        """Arrange to visit a subtree with a temporarily replaced, updated state.

        `tree` can be an AST node or a statement suite (`list` of AST nodes).
        It is identified by `id(tree)` at enter time. Bindings update a copy
        of `self.state`.

        If several `withstate` calls are made for the same `tree`, the last one
        overrides.

        Generally speaking:

        `withstate(subtree, ...)` should be used if you then intend to
        `visit(subtree)`, which recurses into that node (or suite) only.

        `generic_withstate(tree, ...)` should be used if you then intend to
        `generic_visit(tree)`, which recurses into the children of `tree`.

        (It is possible to mix and match, but think through what you're doing.)
        """
        newstate = self.state.copy()
        newstate.update(**bindings)
        # Due to how `ast.NodeTransformer.generic_visit` works, `visit` is
        # never called for a statement suite, but only separately for each
        # individual statement in it. So if we should set `newstate` for a
        # suite, do it for each statement in it.
        if isinstance(tree, list):
            for elt in tree:
                self._subtree_overrides[id(elt)] = newstate
        else:
            self._subtree_overrides[id(tree)] = newstate

    def generic_withstate(self, tree, **bindings):
        """Like `withstate`, but set up the new state for all children of `tree`.

        The same state instance is shared between the child nodes.

        If several `generic_withstate` calls are made for the same `tree`, the
        last one overrides (assuming the list of children has not changed in between).

        The silly name is because this relates to `withstate` as `generic_visit`
        relates to `visit`.

        Generally speaking:

        `generic_withstate(tree, ...)` should be used if you then intend to
        `generic_visit(tree)`, which recurses into the children of `tree`.

        `withstate(subtree, ...)` should be used if you then intend to
        `visit(subtree)`, which recurses into that node (or suite) only.

        (It is possible to mix and match, but think through what you're doing.)
        """
        newstate = self.state.copy()
        newstate.update(**bindings)

        for node in iter_child_nodes(tree):
            self._subtree_overrides[id(node)] = newstate

    def collect(self, value):
        """Collect a value. The values are placed in the list `self.collected`."""
        self.collected.append(value)
        return value


class ASTVisitor(BaseASTWalker, NodeVisitor, metaclass=ABCMeta):
    """AST visitor, like `ast.NodeVisitor`, but with the features of `BaseASTWalker`.

    (Because `return tree`, or `return self.generic_visit(tree)`, is too much
    to remember when not editing.)

    If you want to edit the tree, use `ASTTransformer` instead.
    """

    def visit(self, tree):
        """Start visiting `tree`. **Do not override this method; see `examine` instead.**"""
        newstate = self._subtree_overrides.pop(id(tree), False)
        if newstate:
            self._stack.append(newstate)
        try:
            if isinstance(tree, list):
                for elt in tree:
                    self.visit(elt)
                return
            return self.examine(tree)
        finally:
            if newstate:
                self._stack.pop()

    @abstractmethod
    def examine(self, tree):
        """Examine one node. **Abstract method, override this.**

        There is only one `examine` method. To detect node type, use `type(tree)`.

        This method must recurse explicitly where needed. Use:

          - `self.generic_visit(tree)` to visit all children of `tree`.
          - `self.visit(tree.something)` to selectively visit only some children.
            Visiting a statement suite with `self.visit` is also ok; it is treated
            like a `generic_visit`.

        As in `ast.NodeVisitor`:

          - Return value of `examine` is forwarded by `visit`.
          - `generic_visit` always returns `None`.
        """


class ASTTransformer(BaseASTWalker, NodeTransformer, metaclass=ABCMeta):
    """AST transformer, like `ast.NodeTransformer`, but with the features of `BaseASTWalker`.

    If you only want to examine the tree, not edit it, consider `ASTVisitor` instead.
    """

    def visit(self, tree):
        """Start transforming `tree`. **Do not override this method; see `transform` instead.**"""
        newstate = self._subtree_overrides.pop(id(tree), False)
        if newstate:
            self._stack.append(newstate)
        try:
            if isinstance(tree, list):
                new_tree = utils.flatten(self.visit(elt) for elt in tree)
                if not new_tree:
                    new_tree = []  # preserve the type of `tree`; an empty list shouldn't turn into `None`
                tree[:] = new_tree
                return tree
            return self.transform(tree)
        finally:
            if newstate:
                self._stack.pop()

    @abstractmethod
    def transform(self, tree):
        """Transform one node. **Abstract method, override this.**

        There is only one `transform` method. To detect node type, use `type(tree)`.

        This method must recurse explicitly where needed. Use:

          - `tree = self.generic_visit(tree)` to visit all children of `tree`.
          - `tree.something = self.visit(tree.something)` to selectively visit
            only some children. Visiting a statement suite with `self.visit`
            is also ok.

        Return value as in `ast.NodeTransformer`. If you don't want to make changes,
        you must `return tree`. If you return `None`, the subtree is removed.
        """
