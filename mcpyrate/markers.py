# -*- coding: utf-8; -*-
"""AST markers for internal communication.

*Internal* here means they are to be never passed to Python's `compile`;
macros may use them to work together.
"""

__all__ = ["ASTMarker", "get_markers", "delete_markers"]

import ast

from .walker import Walker


class ASTMarker(ast.AST):
    """Base class for AST markers.

    Markers are AST-node-like objects meant for communication between
    co-operating, related macros. They are also used by the macro expander
    to talk with itself during expansion.

    We inherit from `ast.AST`, so that during macro expansion, a marker
    behaves like a single AST node.

    It is a postcondition of a completed macro expansion that no markers
    remain in the AST.

    To help fail-fast, if you define your own marker types, use `get_markers`
    to check (at an appropriate point) that the expanded AST has no instances
    of your own markers remaining. (You'll want a base class for your own markers.)

    A typical usage example is in the quasiquote system, where the unquote
    operators (some of which expand to markers) may only appear inside a quoted
    section. So just before the quote operator exits, it checks that all
    quasiquote markers within that section have been compiled away.
    """
    def __init__(self, body):
        """body: the actual AST that is annotated by this marker"""
        self.body = body
        self._fields = ["body"]  # support ast.iter_fields


def get_markers(tree, cls=ASTMarker):
    """Return a `list` of any `cls` instances found in `tree`. For output validation."""
    class ASTMarkerCollector(Walker):
        def transform(self, tree):
            if isinstance(tree, cls):
                self.collect(tree)
            return self.generic_visit(tree)
    w = ASTMarkerCollector()
    w.visit(tree)
    return w.collected

def delete_markers(tree, cls=ASTMarker):
    """Delete any `cls` ASTMarker instances found in `tree`.

    The deletion takes place by replacing each marker node with
    the actual AST node stored in its `body` attribute.
    """
    class ASTMarkerDeleter(Walker):
        def transform(self, tree):
            if isinstance(tree, cls):
                tree = tree.body
            return self.generic_visit(tree)
    return ASTMarkerDeleter().visit(tree)
