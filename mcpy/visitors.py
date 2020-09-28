# -*- coding: utf-8; -*-
'''Expander core; essentially, how to apply a macro invocation.'''

__all__ = ['BaseMacroExpander',
           'MacroExpansionError',
           'MacroExpanderMarker',
           'toplevel_postprocess']

from ast import NodeTransformer, AST, fix_missing_locations
from .ctxfixer import fix_missing_ctx
from .markers import ASTMarker
from .unparse import unparse
from .utilities import flatten_suite

class MacroExpansionError(Exception):
    '''Error during macro expansion.'''

class MacroExpanderMarker(ASTMarker):
    '''Base class for AST markers used by the macro expander itself.'''

class Done(MacroExpanderMarker):
    '''Mark a subtree as done, so further visits by the expander won't affect it.

    Emitted by `visit_once`.'''

class BaseMacroExpander(NodeTransformer):
    '''
    A base class for macro expander visitors. After identifying valid macro
    syntax, the actual expander should return the result of calling `_expand()`
    method with the proper arguments.
    '''

    def __init__(self, bindings, filename):
        '''
        bindings: dict of macro name/function pairs
        filename: full path to `.py` file being expanded, for error reporting
        '''
        self.bindings = bindings
        self.filename = filename
        self.recursive = True

    def _needs_expansion(self, tree):
        '''No-op if no macro bindings or if `tree` is marked as `Done`.'''
        return self.bindings and not type(tree) is Done

    def visit(self, tree):
        '''Expand macros in `tree`. Treat `visit(stmt_suite)` as a loop for individual elements.'''
        if not self._needs_expansion(tree):
            return tree
        supervisit = super().visit
        if isinstance(tree, list):
            return flatten_suite(supervisit(elt) for elt in tree)
        return supervisit(tree)

    def visit_once(self, tree):
        '''Expand one layer of macros in `tree`. Helps debug macros that invoke other macros. '''
        oldrec = self._recursive
        try:
            self.recursive = False
            return Done(self.visit(tree))
        finally:
            self.recursive = oldrec

    def _expand(self, syntax, target, macroname, tree, kw=None):
        '''
        Transform `target` node, replacing it with the expansion result of
        applying `macroname` on `tree`, and recursively treat the expansion
        as well.
        '''
        macro = self.bindings[macroname]
        kw = kw or {}
        kw.update({
            'syntax': syntax,
            'expander': self})

        approximate_sourcecode = unparse(target)
        try:
            expansion = _apply_macro(macro, tree, kw)
        except Exception as err:
            # If expansion fails, report macro use site (possibly nested) as well as the definition site.
            lineno = target.lineno if hasattr(target, 'lineno') else None
            sep = " " if "\n" not in approximate_sourcecode else "\n"
            msg = f'use site was at {self.filename}:{lineno}:{sep}{approximate_sourcecode}'
            raise MacroExpansionError(msg) from err

        return self._visit_expansion(expansion, target)

    def _visit_expansion(self, expansion, target):
        '''
        Perform postprocessing fix-ups such as adding in missing source
        location info and `ctx`.

        Then recurse into (`visit`) the once-expanded macro output.
        '''
        if expansion is not None:
            is_node = isinstance(expansion, AST)
            expansion = [expansion] if is_node else expansion
            expansion = map(fix_missing_locations, expansion)
            expansion = map(fix_missing_ctx, expansion)
            if self.recursive:
                expansion = map(self.visit, expansion)
            expansion = list(expansion).pop() if is_node else list(expansion)

        return expansion

    def _ismacro(self, name):
        return name in self.bindings

def _apply_macro(macro, tree, kw):
    '''Execute the macro on tree passing extra kwargs.'''
    return macro(tree, **kw)

# Final postprocessing for the top-level walk can't be done at the end of the
# entrypoints `visit_once` and `visit_recursively`, because it is valid for a
# macro to call those for a subtree.
def toplevel_postprocess(tree):
    '''Perform final postprocessing fix-ups for the top-level expansion.

    Call this after macro expansion is otherwise done, before sending `tree`
    to Python's `compile`.

    Currently, this deletes any AST markers emitted by the macro expander to
    talk with itself during expansion.
    '''
    class InternalMarkerDeleter(NodeTransformer):
        def visit(self, tree):
            if isinstance(tree, list):
                return flatten_suite(self.visit(elt) for elt in tree)
            self.generic_visit(tree)
            if isinstance(tree, MacroExpanderMarker):
                return tree.body
            return tree
    return InternalMarkerDeleter().visit(tree)
