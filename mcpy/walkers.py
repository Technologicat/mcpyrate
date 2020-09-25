# -*- coding: utf-8; -*-

from abc import ABCMeta, abstractmethod
from ast import NodeTransformer
from .utilities import Bunch

__all__ = ["Walker"]

class Walker(NodeTransformer, metaclass=ABCMeta):
    """AST walker base class, providing a state stack and a node collector."""
    def __init__(self, **bindings):
        """Bindings are loaded into the initial `self.state` as attributes."""
        self.reset(**bindings)

    def reset(self, **bindings):
        self._stack = [Bunch(**bindings)]
        self._subtree_overrides = {}
        self.collected = []

    def _setstate(self, newstate):
        self._stack[-1] = newstate
        return newstate
    def _getstate(self):
        return self._stack[-1]
    state = property(fget=_getstate, fset=_setstate, doc="The current state. Can be rebound to replace it.")

    def withstate(self, tree, **bindings):
        """Arrange to visit a subtree with a temporarily replaced, updated state.

        `tree` can be an AST node or a statement suite (`list` of AST nodes).
        It is identified by `id(tree)` at enter time.
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
            if isinstance(tree, list):  # statement suite, unpack it
                result = []
                for elt in tree:
                    newelt = self.visit(elt)
                    if isinstance(newelt, list):  # flatten
                        result.extend(newelt)
                    elif newelt is not None:
                        result.append(newelt)
                return result if result else None
            return self.transform(tree)
        finally:
            if newstate:
                self._stack.pop()

    # TODO: should we directly hand statement suites to `transform`, more general that way?
    @abstractmethod
    def transform(self, tree):
        """Examine and/or transform one node. **Abstract method, override this.**

        There is only one `transform` method. To detect node type, use `type(tree)`.

        It is the responsibility of this method to recurse where needed. Use
        `self.generic_visit(tree)` to visit all children of `tree`, or
        `self.visit(tree.something)` to recurse selectively where you want.

        Return value as in `ast.NodeTransformer`. Particularly, to make no
        changes, `return tree`.
        """
