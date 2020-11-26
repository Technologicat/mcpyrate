# -*- coding: utf-8; -*-
"""Utilities for splicing the actual code into a code template."""

__all__ = ["splice_expression", "splice_statements", "splice_dialect"]

import ast
from copy import deepcopy

from .astfixers import fix_locations
from .coreutils import ismacroimport
from .markers import ASTMarker
from .walkers import ASTTransformer


def splice_expression(expr, template, tag="__paste_here__"):
    """Splice `expr` into `template`.

    This is somewhat like `mcpyrate.quotes.a`, but must be called from outside the
    quoted snippet.

    Parameters:

        `expr`: an expression AST node, or an AST marker containing such.
            The expression you would like to splice in.

        `template`: an AST node, or a `list` of AST nodes.
            Template into which to splice `expr`.

            Must contain a paste-here indicator AST node that specifies where
            `expr` is to be spliced in. The node is expected to have the format::

                ast.Name(id=tag)

            Or in plain English, it's a bare identifier.

            The first-found instance (in AST scan order) of the paste-here indicator
            is replaced by `expr`.

            If the paste-here indicator appears multiple times, second and further
            instances are replaced with a `copy.deepcopy` of `expr` so that they will
            stay independent during any further AST edits.

        `tag`: `str`
            The name of the paste-here indicator in `template`.

    Returns `template` with `expr` spliced in. Note `template` is **not** copied,
    and will be mutated in-place.

    """
    if not template:
        return expr

    if not (isinstance(expr, ast.expr) or
            (isinstance(expr, ASTMarker) and isinstance(expr.body, ast.expr))):
        raise TypeError(f"`expr` must be an expression AST node or AST marker containing such; got {type(expr)} with value {repr(expr)}")
    if not isinstance(template, (ast.AST, list)):
        raise TypeError(f"`template` must be an AST or `list`; got {type(template)} with value {repr(template)}")

    def ispastehere(tree):
        return type(tree) is ast.Expr and type(tree.value) is ast.Name and tree.value.id == tag

    class ExpressionSplicer(ASTTransformer):
        def __init__(self):
            self.first = True
            super().__init__()

        def transform(self, tree):
            if ispastehere(tree):
                if not self.first:
                    return deepcopy(expr)
                self.first = False
                return expr
            return self.generic_visit(tree)

    return ExpressionSplicer().visit(template)


# TODO: this is actually a generic list-of-ast splicer, not specific to statements.
def splice_statements(body, template, tag="__paste_here__"):
    """Splice `body` into `template`.

    This is somewhat like `mcpyrate.quotes.a`, but must be called from outside the
    quoted snippet.

    Parameters:

        `body`: `list` of statements
            The statements you would like to splice in.

        `template`: `list` of statements
            Template into which to splice `body`.

            Must contain a paste-here indicator AST node, in a statement position,
            that specifies where `body` is to be spliced in. The node is expected
            to have the format::

                ast.Expr(value=ast.Name(id=tag))

            Or in plain English, it's a bare identifier in a statement position.

            The first-found instance (in AST scan order) of the paste-here indicator
            is replaced by `body`.

            If the paste-here indicator appears multiple times, second and further
            instances are replaced with a `copy.deepcopy` of `body` so that they will
            stay independent during any further AST edits.

        `tag`: `str`
            The name of the paste-here indicator in `template`.

    Returns `template` with `body` spliced in. Note `template` is **not** copied,
    and will be mutated in-place.

    Example::

        from mcpyrate.quotes import macros, q
        from mcpyrate.splicing import splice_statements

        body = [...]  # a list of statements

        with q as template:
            ...
            __paste_here__
            ...

        splice_statements(body, template)

    (Flake8 will complain about the undefined name `__paste_here__`. You can silence
     it with the appropriate `# noqa`, or to make it happy, import the `n` macro from
     `mcpyrate.quotes` and use `n["__paste_here__"]` instead of a plain `__paste_here__`.)
    """
    if isinstance(body, ast.AST):
        body = [body]
    if isinstance(template, ast.AST):
        body = [template]
    if not body:
        raise ValueError("expected at least one statement in `body`")
    if not template:
        return body

    def ispastehere(tree):
        return type(tree) is ast.Expr and type(tree.value) is ast.Name and tree.value.id == tag

    class StatementSplicer(ASTTransformer):
        def __init__(self):
            self.first = True
            super().__init__()

        def transform(self, tree):
            if ispastehere(tree):
                if not self.first:
                    return deepcopy(body)
                self.first = False
                return body
            return self.generic_visit(tree)

    return StatementSplicer().visit(template)


def splice_dialect(body, template, tag="__paste_here__"):
    """In a dialect AST transformer, splice module `body` into `template`.

    On top of what `splice_statements` does, this function handles macro-imports
    and dialect-imports specially, gathering them all at the top level of the
    final module body, so that mcpyrate sees them when the module is sent to
    the macro expander.

    Any dialect-imports in the template are placed first (in the order they
    appear in the template), followed by any dialect-imports in the user code
    (in the order they appear in the user code), followed by macro-imports in
    the template, then macro-imports in the user code.

    This also handles the module docstring and the magic `__all__` (if any)
    from `body`. The docstring comes first, before dialect-imports. The magic
    `__all__` is placed after dialect-imports, before macro-imports.

    Parameters:

        `body`: `list` of statements
            Original module body from the user code (input).

        `template`: `list` of statements
            Template for the final module body (output).

            Must contain a paste-here indicator as in `splice_statements`.

        `tag`: `str`
            The name of the paste-here indicator in `template`.

    Returns `template` with `body` spliced in. Note `template` is **not** copied,
    and will be mutated in-place.

    Also `body` is mutated, to remove macro-imports, `__all__` and the module
    docstring; these are pasted into the final result.
    """
    if isinstance(body, ast.AST):
        body = [body]
    if isinstance(template, ast.AST):
        body = [template]
    if not body:
        raise ValueError("expected at least one statement in `body`")
    if not template:
        return body

    # Generally speaking, dialect templates are fully macro-generated
    # quasiquoted snippets with no source location info to start with.
    # Even if they have location info, it's for a different file compared
    # to the use site where `body` comes from.
    #
    # Pretend the template code appears at the beginning of the user module.
    for stmt in template:
        fix_locations(stmt, body[0], mode="overwrite")

    # TODO: remove ast.Str once we bump minimum language version to Python 3.8
    if type(body[0]) is ast.Expr and type(body[0].value) in (ast.Constant, ast.Str):
        docstring, *body = body
        docstring = [docstring]
    else:
        docstring = []

    def extract_magic_all(tree):
        def ismagicall(tree):
            if not (type(tree) is ast.Assign and len(tree.targets) == 1):
                return False
            target = tree.targets[0]
            return type(target) is ast.Name and target.id == "__all__"
        class MagicAllExtractor(ASTTransformer):
            def transform(self, tree):
                if ismagicall(tree):
                    self.collect(tree)
                    return None
                # We get just the top level of body by not recursing.
                return tree
        w = MagicAllExtractor()
        w.visit(tree)
        return tree, w.collected
    body, user_magic_all = extract_magic_all(body)

    def extract_macroimports(tree, *, magicname="macros"):
        class MacroImportExtractor(ASTTransformer):
            def transform(self, tree):
                if ismacroimport(tree, magicname):
                    self.collect(tree)
                    return None
                return self.generic_visit(tree)
        w = MacroImportExtractor()
        w.visit(tree)
        return tree, w.collected
    template, template_dialect_imports = extract_macroimports(template, magicname="dialects")
    template, template_macro_imports = extract_macroimports(template)
    body, user_dialect_imports = extract_macroimports(body, magicname="dialects")
    body, user_macro_imports = extract_macroimports(body)

    finalbody = splice_statements(body, template, tag)
    return (docstring +
            user_magic_all +
            template_dialect_imports + user_dialect_imports +
            template_macro_imports + user_macro_imports +
            finalbody)
