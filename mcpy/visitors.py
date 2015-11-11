
from functools import wraps
from ast import NodeTransformer, AST, copy_location, fix_missing_locations
from .unparse import unparse

class BaseMacroExpander(NodeTransformer):
    '''
    A base class for macro expander visitors. After identifying valid macro
    syntax, the actual expander should return the result of calling `_expand()`
    method with the proper arguments.
    '''

    def __init__(self, bindings):
        self.bindings = bindings

    def visit(self, tree):
        '''Short-circuit visit() to avoid expansions if no macros.'''
        return super().visit(tree) if self.bindings else tree
    
    def _expand(self, syntax, target, macroname, tree, kw=None):
        '''
        Transform `target` node, replacing it with the expansion result of
        aplying the named macro on the proper node and recursively treat the
        expansion as well.
        '''
        macro = self.bindings[macroname]
        kw = kw or {}
        kw.update({
            'syntax': syntax,
            'to_source': unparse,
            'expand_macros': self.visit
        })
        expansion = _apply_macro(macro, tree, kw)

        return self._visit_expansion(expansion, target)

    def _visit_expansion(self, expansion, target):
        '''
        Ensures the macro expansions into None (deletions), other nodes or
        list of nodes are expanded too.
        '''
        if expansion is not None:
            is_node = isinstance(expansion, AST)
            expansion = [expansion] if is_node else expansion
            expansion = map(lambda n: copy_location(n, target), expansion)
            expansion = map(fix_missing_locations, expansion)
            expansion = map(self.visit, expansion)
            expansion = list(expansion).pop() if is_node else list(expansion)

        return expansion
        
    def _ismacro(self, name):
        return name in self.bindings

def _apply_macro(macro, tree, kw):
    '''
    Executes the macro on tree passing extra kwargs.
    '''
    return macro(tree, **kw)
