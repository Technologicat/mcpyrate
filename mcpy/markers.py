# -*- coding: utf-8; -*-
"""AST markers for internal communication.

*Internal* here means they are to be never passed to Python's `compile`;
macros may use them to work together.
"""

__all__ = ["ASTMarker", "get_markers"]

import ast
from .walkers import Walker

class ASTMarker(ast.AST):
    """Base class for AST markers.

    Markers are AST-node-like entities used for communication between related
    macros, and within the `mcpy` macro expander and its subsystems (such as
    quasiquotes).

    We inherit from `ast.AST`, so that during macro expansion, a marker behaves
    like a single AST node.

    It is a postcondition of a completed macro expansion that no markers
    remain. To help fail-fast, if you define your own marker types, use
    `get_markers` to check (where appropriate) that the expanded AST has no
    instances of your own markers remaining.

    A typical example of usage of markers is in the quasiquote system, where
    the unquote operators (some of which expand to markers) may only appear
    inside a quoted section. So just before the quote operator exits, it checks
    that all quasiquote markers within that section have been compiled away.
    """
    def __init__(self, body):
        """body: the actual AST that is annotated by this marker"""
        self.body = body
        self._fields = ["body"]  # support ast.iterfields


def get_markers(tree, cls=ASTMarker):
    """Return a `list` of any `cls` instances found in `tree`. For output validation."""
    class ASTMarkerCollector(Walker):
        def transform(self, tree):
            if isinstance(tree, cls):
                self.collect(tree)
            self.generic_visit(tree)
            return tree
    p = ASTMarkerCollector()
    p.visit(tree)
    return p.collected
