# -*- coding: utf-8; -*-

from ast import (Call, arg, Name, Attribute, Str, FunctionDef, Assign, Load, Store,
                 NodeTransformer, copy_location)
from mcpyrate import unparse

def customliterals(statements, expander, **kw):
    '''
    Provide custom meaning to literals. Example:

        class MyStr(str): pass

        with customliterals:
            str = MyStr
            assert('hi!'.__class__ is MyStr)

        assert('hi!'.__class__ is not MyStr)

    You can use `str`, `tuple`, `list`, `dict`, `set` and `num` to customize
    literals.
    '''
    visitor = _WrapLiterals()
    return map(visitor.visit, map(expander.visit, statements))

def log(expr, **kw):
    '''
    Print the passed value, labeling the output with the expression. Example:

        d = { 'a': 1 }
        log[d['a']]

        # prints
        # d['a']: 1
    '''
    label = unparse(expr) + ': '
    return Call(func=Name(id='print', ctx=Load()),
                args=[Str(s=label), expr], keywords=[])

def value(classdef, **kw):
    '''
    Quick definition of singleton values a-la Scala. Example:

        @value
        class superman:
            name = 'Klark'
            surname = 'Kent'
            def completename(): return name + ' ' + surname

        assert(not isinstance(superman, type))
        assert(isinstance(superman, object))
        assert(superman.completename() == 'Klark Kent')
    '''
    symbols = _gather_symbols(classdef)
    baked_class = _IntoValueTransformer(symbols).visit(classdef)
    replacement = Assign(targets=[Name(id=baked_class.name, ctx=Store())],
                         value=Call(func=Name(id=baked_class.name, ctx=Load()),
                                    args=[], keywords=[]))
    return [baked_class, replacement]

class _WrapLiterals(NodeTransformer):
    '''
    Wrap each appearance of a literal with a constructor call to that literal type.
    '''

    def _wrap(self, fname, node):
        '''
        Convert `node` into `fname(node)`
        '''
        return copy_location(
            Call(func=Name(id=fname, ctx=Load()),
                 args=[node], keywords=[]),
            node
        )

    def visit_Constant(self, node):  # Python 3.8+
        v = node.value
        tv = type(v)
        if tv is tuple:
            return self._wrap('tuple', node)
        elif tv is str:
            return self._wrap('str', node)
        elif tv is list:
            return self._wrap('list', node)
        elif tv is set:
            return self._wrap('set', node)
        elif tv is dict:
            return self._wrap('dict', node)
        elif tv in (int, float, complex):
            return self._wrap('num', node)

    def visit_Tuple(self, node):
        return self._wrap('tuple', node)

    def visit_Str(self, node):
        return self._wrap('str', node)

    def visit_List(self, node):
        return self._wrap('list', node)

    def visit_Set(self, node):
        return self._wrap('set', node)

    def visit_Dict(self, node):
        return self._wrap('dict', node)

    def visit_Num(self, node):
        return self._wrap('num', node)

class _IntoValueTransformer(NodeTransformer):
    '''
    Convert simplified method syntax into traditional Python syntax.
    '''

    def __init__(self, symbols):
        self._symbols = symbols

    def visit_FunctionDef(self, functiondef):
        '''
        Add self as first argument of the simplified method, and bind to
        self all the internal names belonging to symbols.
        '''
        args = functiondef.args.args
        if not args or args[0].arg != 'self':
            args.insert(0, arg(arg='self', annotation=None))
        return _NameBinder(self._symbols).generic_visit(functiondef)

class _NameBinder(NodeTransformer):
    '''
    Transform each `Name` into an access to `self` if the `Name`
    belongs to a given set of symbols.
    '''

    def __init__(self, symbols):
        self._symbols = symbols

    def visit_Name(self, name):
        '''
        Transform name into self.name
        '''
        self_name = name
        if name.id in self._symbols:
            self_name = Attribute(value=Name(id='self', ctx=Load()),
                                  attr=name.id, ctx=Load())
            copy_location(self_name, name)

        return self_name


def _gather_symbols(expr):
    symbols = set()
    for stmt in expr.body:
        if isinstance(stmt, Assign):
            for target in stmt.targets:
                if isinstance(target, Name):
                    symbols.add(target.id)

        elif isinstance(stmt, FunctionDef):
            symbols.add(stmt.name)

    return symbols
