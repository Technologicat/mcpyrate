# -*- coding: utf-8; -*-
'''Provide the functionality to find and expand macros.'''

import sys
from ast import Name, Import, ImportFrom, alias, AST, Expr, Constant, copy_location
from .visitors import BaseMacroExpander

__all__ = ['expand_macros', 'find_macros', 'MacroExpander']

class MacroExpander(BaseMacroExpander):
    '''This concrete macro expander layer defines macro invocation syntax.'''

    def visit_With(self, withstmt):
        '''
        Check for a with macro as::

            with macroname:
                "with's body is the target of the macro"

        Replace the `With` node with the result of the macro.
        '''
        with_item = withstmt.items[0]
        candidate = with_item.context_expr
        if isinstance(candidate, Name) and self._ismacro(candidate.id):
            macroname = candidate.id
            tree = withstmt.body
            kw = {'optional_vars': with_item.optional_vars}
            new_tree = self._expand('block', withstmt, macroname, tree, kw)
            new_tree = _fix_coverage_reporting(new_tree, withstmt)
        else:
            new_tree = self.generic_visit(withstmt)

        return new_tree

    def visit_Subscript(self, subscript):
        '''
        Check for an expression macro as::

            macroname['index expression is the target of the macro']

        Replace the `SubScript` node with the result of the macro.
        '''
        candidate = subscript.value
        if isinstance(candidate, Name) and self._ismacro(candidate.id):
            macroname = candidate.id
            tree = subscript.slice.value
            new_tree = self._expand('expr', subscript, macroname, tree)
            new_tree = copy_location(new_tree, subscript)
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
                "The whole function is the target of the macro"

        Or::

            @macroname
            class C():
                "The whole class is the target of the macro"

        Replace the whole decorated node with the result of the macro.
        '''
        macros, decorators = self._detect_decorator_macros(decorated.decorator_list)
        decorated.decorator_list = decorators
        if macros:
            for macro in reversed(macros):
                macroname = macro.id
                new_tree = self._expand('decorator', decorated, macroname, decorated)
            for macro in reversed(macros):
                new_tree = _fix_coverage_reporting(new_tree, macro)
        else:
            new_tree = self.generic_visit(decorated)

        return new_tree

    def _detect_decorator_macros(self, decorators):
        '''
        Identify macro names in a decorator list, and return a pair with
        macro decorators and the decorators not identified as macros,
        preserving ordering within each of the two subsets.
        '''
        macros, remaining = [], []
        for d in decorators:
            if isinstance(d, Name) and self._ismacro(d.id):
                macros.append(d)
            else:
                remaining.append(d)

        return macros, remaining

def expand_macros(tree, bindings, filename):
    '''
    Return an expanded version of `tree` with macros applied.

    `bindings` is a dictionary of the macro name/function pairs.

    `filename` is the full path to the `.py` being macroexpanded, for error reporting.
    '''
    expansion = MacroExpander(bindings, filename).visit(tree)
    return expansion

def find_macros(tree):
    '''
    Look for `from ... import macros, ...` statements in the module body, and
    return a dict with names and implementations for found macros, or an empty
    dict if no macros are used.

    As a side effect, transform each macro import statement into `import ...`,
    where `...` is the module the macros are being imported from.
    '''
    bindings = {}
    for index, statement in enumerate(tree.body):
        if _is_macro_import(statement):
            bindings.update(_get_macros(statement))
            # Remove all names to prevent the macros being accidentally used as regular run-time objects
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
    Return a dict with names and macros from the macro import statement.
    '''
    modulename = macroimport.module
    __import__(modulename)
    module = sys.modules[modulename]
    return {name.asname or name.name: getattr(module, name.name)
             for name in macroimport.names[1:]}

def _fix_coverage_reporting(tree, target):
    '''
    Fix Coverage.py test coverage reporting for block and decorator macros.

    The line invoking the macro is compiled away, so we insert a dummy node,
    copying source location information from the AST node `target`.

    `tree` must appear in a position where `ast.NodeTransformer.visit` is
    allowed to return a list of nodes.
    '''
    if tree is None:
        tree = []
    elif isinstance(tree, AST):
        tree = [tree]
    # The dummy node must be something that actually runs so it gets
    # a coverage hit, an `ast.Pass` won't do.
    non = copy_location(Constant(value=None), target)
    dummy = copy_location(Expr(value=non), target)
    tree.insert(0, dummy)
    return tree
