# -*- coding: utf-8; -*-

__all__ = ["Walker"]

from abc import ABCMeta, abstractmethod
from ast import NodeTransformer

from .bunch import Bunch
from .utils import flatten_suite


class Walker(NodeTransformer, metaclass=ABCMeta):
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
        """
        self._subtree_overrides[id(tree)] = self.state.copy().update(**bindings)

    def collect(self, value):
        """Collect a value. The values are placed in the list `self.collected`."""
        self.collected.append(value)
        return value

    def visit(self, tree):
        """Start walking `tree`. **Do not override this method; see `transform` instead.**"""
        newstate = self._subtree_overrides.pop(id(tree), False)
        if newstate:
            self._stack.append(newstate)
        try:
            if isinstance(tree, list):
                return flatten_suite(self.visit(elt) for elt in tree)
            return self.transform(tree)
        finally:
            if newstate:
                self._stack.pop()

    # TODO: Should we directly hand statement suites to `transform`, more general that way?
    @abstractmethod
    def transform(self, tree):
        """Examine and/or transform one node. **Abstract method, override this.**

        There is only one `transform` method. To detect node type, use `type(tree)`.

        This method must recurse explicitly where needed. Use:

          - `tree = self.generic_visit(tree)` to visit all children of `tree`
          - `tree.something = self.visit(tree.something)` to selectively visit
            only some children. Visiting a statement suite with `self.visit`
            is also ok.

        Return value as in `ast.NodeTransformer`. If you don't want to make changes,
        you must `return tree`. (If you return `None`, the subtree is removed.)
        """
