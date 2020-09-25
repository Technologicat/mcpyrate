# -*- coding: utf-8; -*-

from abc import ABCMeta, abstractmethod
from ast import NodeTransformer
from .utilities import Bunch

__all__ = ["Walker"]

class Walker(NodeTransformer, metaclass=ABCMeta):
    """Simple functional-stateful AST walker.

    The state is a `Bunch` that lives in the property `state`. You can mutate
    it imperatively, replace it, anything you want.

    The point of `Walker` is it's possible to functionally update the state for
    a given subtree only::

        self.withstate(subtree, **bindings)

    While in that subtree, the updated state is available as `state`. When the
    walker exits that subtree, the previous value of `state` is automatically
    restored.

    We support collecting things during walking as well, à la MacroPy; see
    `collect()` and `collected`.

    To start walking, just `visit`. There's no separate `recurse`, `collect`,
    `recurse_collect`.

    Example::

        def kittify(mytree):
            class Kittifier(Walker):
                def process(self, tree):
                    if type(tree) is ast.Constant:
                        self.collect(tree.value)
                        tree.value = "meow!" if self.state.meows % 2 == 0 else "miaow!"
                        self.state.meows += 1  # *mutate* the state
                    self.generic_visit(tree)  # recurse
                    return tree
            k = Kittifier(meows=0)    # set the initial state here
            mytree = k.visit(mytree)  # it's basically an ast.NodeTransformer
            print(k.collected)        # collected values, in visited order
            return mytree
    """
    def __init__(self, **bindings):
        """**bindings are loaded into the state."""
        self.reset(**bindings)

    def reset(self, **bindings):
        """Clear the state, to walk another unrelated tree."""
        self.stack = [Bunch(**bindings)]
        self.collected = []
        self.subtrees = {}

    # --------------------------------------------------------------------------------

    def setstate(self, newstate):
        self.stack[-1] = newstate
        return newstate
    def getstate(self):
        return self.stack[-1]
    state = property(fget=getstate, fset=setstate)

    def withstate(self, tree, **bindings):
        """Functionally update the state for given `tree` only.

        The state is copied, and the new bindings are merged into the copy,
        overwriting existing keys.
        """
        self.subtrees[id(tree)] = self.state.copy().update(**bindings)

    # --------------------------------------------------------------------------------

    def collect(self, thing):
        """Collect `thing`.

        The collected things are accessible as the list `self.collected`. A
        collected thing will never become uncollected, this is by design an
        imperative operation.
        """
        self.collected.append(thing)

    # --------------------------------------------------------------------------------

    def visit(self, tree):
        """The standard visitor method. Call this on your `tree` to start walking it.

        **Do not override**, implement `process` instead.

        This handles the functional `state` updates when entering or exiting a
        `withstate`d subtree.
        """
        newstate = self.subtrees.pop(id(tree), False)
        if newstate:
            self.stack.append(newstate)
        try:
            if isinstance(tree, list):  # statement suite?
                result = []
                for elt in tree:
                    newelt = self.visit(elt)
                    if isinstance(newelt, list):
                        result.extend(newelt)
                    elif newelt is not None:
                        result.append(newelt)  # single node
                return result if result else None
            return self.process(tree)
        finally:
            if newstate:
                self.stack.pop()

    @abstractmethod
    def process(self, tree):
        """Process the node `tree`.

        Return value as in `ast.NodeTransformer.visit`. Usually the updated
        `tree`; can be a `list` of AST nodes to replace with multiple nodes
        (when syntactically admissible), or `None` to delete the subtree.

        To keep things explicit, it's the responsibility of this method to call
        `self.generic_visit(tree)` to recurse into the children of `tree` when
        that's desirable (i.e. almost always).

        To *not* recurse into children (cf. MacroPy's `stop()`), simply
        *don't* call `generic_visit` from this method in the desired branch.

        To recurse selectively, just `self.visit` the desired subtrees.

        See:
            https://docs.python.org/3/library/ast.html#ast.NodeTransformer
        """
