# -*- coding: utf-8 -*-
"""Example dialects for testing the dialects subsystem."""

from mcpyrate.quotes import macros, q  # noqa: F401

import ast
import textwrap

from mcpyrate.dialects import Dialect
from mcpyrate.quotes import is_captured_value
from mcpyrate.splicing import splice_dialect
from mcpyrate.walkers import ASTTransformer

# source transform only
class Sourcery(Dialect):
    def transform_source(self, text):
        return "x = 'Hello from Sourcery dialect'\n" + text

# AST transform only
class Texan(Dialect):
    def transform_ast(self, tree):  # tree is an ast.Module
        with q as template:
            x = "Howdy from Texan dialect"  # noqa: F841, it's for use by the user code.
            __paste_here__  # noqa: F821, just a splicing marker.

        tree.body = splice_dialect(tree.body, template, "__paste_here__",
                                   lineno=self.lineno, col_offset=self.col_offset)

        return tree

# `postprocess_ast` is a hook for AST optimizers and similar.
# Here we just do a silly transform. Postprocessing, get it?
class Tumbler(Dialect):
    def postprocess_ast(self, tree):  # tree is an ast.Module
        class TumbleTransformer(ASTTransformer):
            def transform(self, tree):
                if is_captured_value(tree):  # hygienic capture, do not recurse into it
                    return tree
                if type(tree) is ast.Constant and type(tree.value) is int:
                    # No one in their right mind would do this outside a unit test.
                    tree.value = 2 * tree.value
                return self.generic_visit(tree)
        return TumbleTransformer().visit(tree)

# both source and AST transforms
class OurPowersCombined(Dialect):
    def transform_source(self, text):
        return "x1 = 'Hello from transform_source of OurPowersCombined dialect'\n" + text

    def transform_ast(self, tree):  # tree is an ast.Module
        with q as template:
            x2 = "Hello from transform_ast of OurPowersCombined dialect"  # noqa: F841, it's for use by the user code.
            __paste_here__  # noqa: F821, just a splicing marker.

        tree.body = splice_dialect(tree.body, template, "__paste_here__",
                                   lineno=self.lineno, col_offset=self.col_offset)

        return tree

# AST transform, with a `__future__` import in the dialect template
class FutureTexan(Dialect):
    def transform_ast(self, tree):  # tree is an ast.Module
        # TODO: Just import *anything* from `__future__`, to trigger the handler in `splice_dialect`.
        #
        # TODO: We may need to update this as language versions march on
        # TODO: and the set of available `__future__` features changes.
        #
        # HACK: Having a future-import anywhere but a module top level confuses analysis tools
        # and technically isn't even valid Python. Particularly, `flake8` crashes on it.
        # So instead of using a quoted AST (which would get parsed as part of its containing file,
        # leading to invalid Python), we hide it inside a string.
        source = textwrap.dedent("""
        from __future__ import generator_stop

        x = "Howdy from FutureTexan dialect"  # noqa: F841, it's for use by the user code.

        __paste_here__  # noqa: F821, just a splicing marker.
        """)

        # Parse like `mcpyrate` itself would before expanding (exec mode, using `ast.parse`).
        #
        # Also `self.expander.filename` available (target file that is being transformed),
        # but maybe `__file__` (this file!) is better here.
        module_node = ast.parse(source, filename=__file__, mode="exec")

        # We need a list of statements, so grab it from the `AST.Module`.
        assert type(module_node) is ast.Module
        template = module_node.body

        tree.body = splice_dialect(tree.body, template, "__paste_here__",
                                   lineno=self.lineno, col_offset=self.col_offset)

        return tree
