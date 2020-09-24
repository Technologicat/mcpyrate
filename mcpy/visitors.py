# -*- coding: utf-8; -*-

from ast import NodeTransformer, AST, copy_location, fix_missing_locations
from .ctxfixer import fix_missing_ctx
from .unparse import unparse

__all__ = ['BaseMacroExpander', 'MacroExpansionError']

class MacroExpansionError(Exception):
    '''Represents an error during macro expansion.'''

class BaseMacroExpander(NodeTransformer):
    '''
    A base class for macro expander visitors. After identifying valid macro
    syntax, the actual expander should return the result of calling `_expand()`
    method with the proper arguments.
    '''

    def __init__(self, bindings, filepath):
        self.bindings = bindings
        self.filepath = filepath
        self.recursive = True

    def visit(self, tree):
        '''Expand macros.

        Short-circuit visit() to avoid expansions if no macros.
        '''
        return tree if not self.bindings else super().visit(tree)

    def visit_once(self, tree):
        '''Expand only one layer of macros.

        Useful for debugging implementations of macros that invoke other macros
        in their output.
        '''
        oldrec = self.recursive
        try:
            self.recursive = False
            return self.visit(tree)
        finally:
            self.recursive = oldrec

    def _expand(self, syntax, target, macroname, tree, kw=None):
        '''
        Transform `target` node, replacing it with the expansion result of
        applying the named macro on the proper node and recursively treat the
        expansion as well.
        '''
        macro = self.bindings[macroname]
        kw = kw or {}
        kw.update({
            'syntax': syntax,
            'to_source': unparse,
            'expand_macros': self.visit,
            'expand_once': self.visit_once})

        original_code = unparse(target)
        try:
            expansion = _apply_macro(macro, tree, kw)
        except Exception as err:
            lineno = target.lineno if hasattr(target, 'lineno') else None
            msg = f'use site was at {self.filepath}:{lineno}: {original_code}'
            raise MacroExpansionError(msg) from err

        return self._visit_expansion(expansion, target)

    def _visit_expansion(self, expansion, target):
        '''
        Perform postprocessing fix-ups such as adding in missing source
        location info.

        Then recurse (using `visit`) into the once-expanded macro output.
        '''
        if expansion is not None:
            is_node = isinstance(expansion, AST)
            expansion = [expansion] if is_node else expansion
            expansion = map(lambda n: copy_location(n, target), expansion)
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
