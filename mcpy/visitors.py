
from functools import wraps
from ast import NodeTransformer, AST, copy_location

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
    
    def _expand(self, kind, macronode, name, target, kw=None):
        '''
        Transform `macronode` node, replacing it with the expansion result of
        aplying the named macro on the proper node and recursively treat the
        expansion as well.
        '''
        macro = self.bindings[name]
        kw = kw or {}
        kw.update({ 'mode': kind })
        expansion = _apply_macro(macro, target, kw)

        return self._visit_expansion(macronode, expansion)

    def _visit_expansion(self, macronode, expansion):
        '''
        Ensures the macro expansions into None (deletions), other nodes or
        list of nodes are expanded too.
        '''
        if expansion is not None:
            is_node = isinstance(expansion, AST)
            expansion = [expansion] if is_node else expansion
            expansion = map(self.visit, expansion)
            expansion = map(lambda n: copy_location(n, macronode), expansion)
            expansion = list(expansion).pop() if is_node else list(expansion)

        return expansion
        
    def _ismacro(self, name):
        return name in self.bindings

def _apply_macro(macro, target, kw):
    '''
    Executes the macro on target passing extra kwargs.
    '''
    return macro(target, **kw)

def dfs(f):
    '''
    Decorate a NodeVisitor method to perform a depth-first search visitation.
    '''
    @wraps(f)
    def _dfs(self, node):
        new_node = self.generic_visit(node)
        return f(self, new_node)

    return _dfs

