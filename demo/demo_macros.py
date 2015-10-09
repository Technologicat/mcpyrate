
from ast import *
from mcpy import unparse

def customliterals(sentences, **kw):
    '''
    Allow to provide custom meaning to literals. Example:

        class MyStr(str): pass
        
        with customliterals:
            str = MyStr
            assert('hi!'.__class__ is MyStr)
        
        assert('hi!'.__class__ is not MyStr)

    You can use `str`, `tuple`, `list`, `dict`, `set` and `num` to customize
    literals.
    '''
    visitor = _WrapLiterals() 
    return map(visitor.visit, sentences)

def log(expr, **kw):
    '''
    Prints the passed value labeling the output with the expression. Example:

        d = { 'a': 1 }
        log[d['a']]

        # prints
        # d['a']: 1
        
    '''
    label = unparse(expr) + ': '
    return Call(func=Name(id='print', ctx=Load()),
                args=[Str(s=label), expr], keywords=[], starargs=None,
                kwargs=None)

def value(classdef, **kw):
    '''
    Allows quick definition of singleton values a-la Scala. Example:

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
                         args=[], keywords=[], starargs=None, kwargs=None))
    return [baked_class, replacement]

class _WrapLiterals(NodeTransformer):
    '''
    A visitor to wrap each literal appariton with a proper name.
    '''

    def _wrap(self, fname, node):
        '''
        Converts a node in fname(node)
        '''
        return copy_location(
            Call(func=Name(id=fname, ctx=Load()),
                 args=[node], keywords=[], starargs=None, kwargs=None),
            node
        )

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
    A visitor to convert simplified method syntax into traditional Python
    syntax.
    '''

    def __init__(self, symbols):
        self._symbols = symbols

    def visit_FunctionDef(self, functiondef):
        '''
        Adds self as first argument of the simplified method and bind to
        self all the internal names belonging to symbols.
        '''
        args = functiondef.args.args
        if not args or args[0].arg != 'self':
            args.insert(0, arg(arg='self', annotation=None))
        return _NameBinder(self._symbols).generic_visit(functiondef)

class _NameBinder(NodeTransformer):
    '''
    A visitor to transform each Name into an access to `self` if the Name
    belongs to a set of symbols.
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
