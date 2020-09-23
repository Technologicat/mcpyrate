# -*- coding: utf-8; -*-
'''Provide the functionality to find and expand macros.'''

import sys
from ast import Name, Import, ImportFrom, alias, copy_location
from .visitors import BaseMacroExpander

__all__ = ['expand_macros', 'find_macros']

class _MacroExpander(BaseMacroExpander):

    def visit_With(self, withstmt):
        '''
        Check for a with macro as::

            with macroname:
                # with's body is the target of the macro

        It replaces the `with` node with the result of the macro.
        '''
        with_item = withstmt.items[0]
        candidate = with_item.context_expr
        if isinstance(candidate, Name) and self._ismacro(candidate.id):
            macro = candidate.id
            tree = withstmt.body
            kw = {'optional_vars': with_item.optional_vars}
            new_tree = self._expand('block', withstmt, macro, tree, kw)
        else:
            new_tree = self.generic_visit(withstmt)

        return new_tree

    def visit_Subscript(self, subscript):
        '''
        Check for a expression macro as::

            macroname['index expression is the target of the macro']

        It replaces the expression node with the result of the macro.
        '''
        candidate = subscript.value
        if isinstance(candidate, Name) and self._ismacro(candidate.id):
            macro = candidate.id
            tree = subscript.slice.value
            new_tree = self._expand('expr', subscript, macro, tree)
        else:
            new_tree = self.generic_visit(subscript)

        return new_tree

    def visit_ClassDef(self, classdef):
        return self._visit_Decorated(classdef)

    def visit_FunctionDef(self, functiondef):
        return self._visit_Decorated(functiondef)

    def _visit_Decorated(self, decorated):
        '''
        Check for a decorator macro as::

            @macroname
            def f():
                # The whole function is the target of the macro

        Or::

            @macroname
            class C():
                # The whole class is the target of the macro

        It replaces the whole decorated node with the result of the macro.
        '''
        macros, decorators = self._filter_out_macros(decorated.decorator_list)
        decorated.decorator_list = decorators
        if macros:
            for macro in reversed(macros):
                new_tree = self._expand('decorator', decorated, macro, decorated)
        else:
            new_tree = self.generic_visit(decorated)

        return new_tree

    def _filter_out_macros(self, decorators):
        '''
        Identify macro names inside a decorator list, and return a pair with
        macro names and the decorators not identified as macros.
        '''
        macros, remaining = [], []
        for d in decorators:
            if isinstance(d, Name) and self._ismacro(d.id):
                macros.append(d.id)
            else:
                remaining.append(d)

        return macros, remaining

def expand_macros(tree, bindings, filepath):
    '''
    Return an expanded version of tree with macros applied.
    '''
    expansion = _MacroExpander(bindings, filepath).visit(tree)
    return expansion

def find_macros(tree):
    '''
    Look for `from ... import macros, ...` statements in the module body, and
    return a dict with names and implementations for found macros, or an empty
    dict if no macros are used.
    '''
    bindings = {}
    for index, statement in enumerate(tree.body):
        if _is_macro_import(statement):
            bindings.update(_get_macros(statement))
            # Remove all names to prevent macro names to be used
            module = statement.module
            tree.body[index] = copy_location(
                Import(names=[alias(name=module, asname=None)]),
                statement
            )

    return bindings

def _is_macro_import(statement):
    '''
    A "macro import" is a statement of the form::

        from ... import macros, ...

    '''
    is_macro_import = False
    if isinstance(statement, ImportFrom):
        firstimport = statement.names[0]
        if firstimport.name == 'macros' and firstimport.asname is None:
            is_macro_import = True

    return is_macro_import

def _get_macros(macroimport):
    '''
    Return a map with names and macros from the macro import statement.
    '''
    modulename = macroimport.module
    __import__(modulename)
    module = sys.modules[modulename]
    return {name.asname or name.name: getattr(module, name.name)
             for name in macroimport.names[1:]}
