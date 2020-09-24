# -*- coding: utf-8; -*-
"""Quasiquotes. Build ASTs in your macros, conveniently."""

__all__ = ['capture', 'lookup', 'astify',
           'q', 'u', 'n', 'a', 'h']

import ast
from .unparse import unparse
from .utilities import gensym, ast_aware_repr

# --------------------------------------------------------------------------------

class PseudoNode(ast.AST):
    """Almost like a real AST node.

    Pseudonodes are internal AST markers used by `q[]`. They are expanded away
    by `astify`, to allow the rest of `mcpy` to deal with real AST nodes only.

    We inherit from `ast.AST` to let `mcpy`'s expander know this behaves
    somewhat like an AST node, so it won't choke on this while expanding
    quasiquotes.
    """
    def __init__(self, body):
        """body: the real AST"""
        self.body = body
        self._fields = ["body"]  # support ast.iterfields

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, ast_aware_repr(self.body))

class ASTLiteral(PseudoNode):  # like MacroPy's `Literal`
    """Keep the given subtree as-is."""
    pass

class CaptureLater(PseudoNode):  # like MacroPy's `Captured`
    """Capture the value the given subtree evaluates to at the use site of `q[]`."""
    def __init__(self, body, name):
        super().__init__(body)
        self.name = name
        self._fields += "name"

    def __repr__(self):
        return "{}({}, {})".format(self.__class__.__name__, ast_aware_repr(self.body), repr(self.name))

# --------------------------------------------------------------------------------

_registry = {}

def _mcpy_quotes_attr(attr):
    """Create an AST that, when compiled and run, looks up `mcpy.quotes.attr` in `Load` context."""
    mcpy_quotes_module = ast.Attribute(value=ast.Name(id="mcpy", ctx=ast.Load()),
                                       attr="quotes",
                                       ctx=ast.Load())
    return ast.Attribute(value=mcpy_quotes_module,
                         attr=attr,
                         ctx=ast.Load())

def capture(value, basename):
    """Store a value into the hygienic capture registry. Used by `q[h[]]`.

    `value`:    Any run-time value.
    `basename`: Basename for gensymming a unique key for the value.
                Does not need to be an identifier.

    The return value is an AST that, when compiled and run, looks up the
    captured value. Each unique value (by `id`) is only stored once.
    """
    for k, v in _registry.items():
        if v is value:
            key = k
            break
    else:
        key = gensym(basename)
        _registry[key] = value
    # print("capture: registry now:")  # DEBUG
    # for k, v in _registry.items():  # DEBUG
    #     print("    ", k, "-->", ast_aware_repr(v))  # DEBUG
    return ast.Call(_mcpy_quotes_attr("lookup"),
                    [ast.Constant(value=key)],
                    [])

def lookup(key):
    """Look up a hygienically captured value. Used in the output of `q[h[]]`."""
    # print("lookup:", key, "-->", ast_aware_repr(_registry[key]))  # DEBUG
    return _registry[key]

# --------------------------------------------------------------------------------

def astify(x):  # like MacroPy's `ast_repr`
    """Lift a value into its AST representation, if possible.

    When the AST is compiled and run, it will evaluate to `x`.

    If `x` itself is an AST, then produce an AST that, when compiled and run,
    will generate the AST `x`.

    Raises `TypeError` when the lifting fails.
    """
    tx = type(x)

    # Drop the ASTLiteral pseudo-node wrapper; it only tells us to skip further processing.
    if tx is ASTLiteral:
        return x.body

    # This is the magic part of q[h[]].
    #
    # At the use site of q[], this captures the value, and rewrites itself
    # into a lookup. At the use site of the macro that used q[], that
    # rewritten code looks up the captured value.
    elif tx is CaptureLater:
        return ast.Call(_mcpy_quotes_attr('capture'),
                        [x.body,
                         ast.Constant(value=x.name)],
                        [])

    # Constants (Python 3.6+).
    elif tx in (int, float, str, bytes, bool, type(None)):
        return ast.Constant(value=x)

    # Containers.
    elif tx is list:
        return ast.List(elts=list(astify(elt) for elt in x))
    elif tx is dict:
        return ast.Dict(keys=list(astify(k) for k in x.keys()),
                        values=list(astify(v) for v in x.values()))
    elif tx is set:
        return ast.Set(elts=list(astify(elt) for elt in x))

    # Anything that is already an AST node (e.g. `Name`).
    elif isinstance(x, ast.AST):
        # The magic is in the Call. Take apart the input AST, and construct a
        # new AST, that (when compiled and run) will re-generate the input AST.
        #
        # We refer to the stdlib `ast` module as `mcpy.quotes.ast` to avoid
        # name conflicts at the use site of `q[]`.
        fields = [ast.keyword(a, astify(b)) for a, b in ast.iter_fields(x)]
        return ast.Call(ast.Attribute(value=_mcpy_quotes_attr('ast'),
                                      attr=x.__class__.__name__,
                                      ctx=ast.Load()),
                        [],
                        fields)

    raise TypeError("Don't know how to astify {}".format(repr(x)))

# --------------------------------------------------------------------------------
# Macros

# These operators are named after Qu'nah, the goddess of quasiquotes in high-tech-elven mythology.

# TODO: block variants. Use the macro interface as a dispatcher, in true mcpy style.

# TODO: `u`, `n`, `a` are not really independent macros, but only valid inside a `q`.
#
# TODO: Use/implement a walker and then, in `q`, act on `Subscript` nodes with the appropriate names.
# TODO: This would also make `q` behave like in Lisps - quasiquoted macro invocations
# TODO: will then not be expanded (the caller is expected to `expand_macros` on them if they want).
#
# TODO: q[] should assert the final output does not contain `PseudoNode` instances, those are internal.
# TODO: Doing that needs a walker.
def q(tree, *, syntax, expand_macros, **kw):
    """Quasiquote an expr, lifting it into its AST representation."""
    assert syntax == "expr"
    tree = expand_macros(tree)
    # The trick is to wrap the original AST such that when the macro system
    # compiles and runs our return value, that produces our input `tree`.
    return astify(tree)

# TODO: u[] should expand macros only when the quotelevel hits zero. Track it.
def u(tree, *, syntax, expand_macros, **kw):
    """Splice a simple value into quasiquoted code."""
    assert syntax == "expr"
    tree = expand_macros(tree)
    # We want to generate an AST that compiles to the *value* of `v`. But when
    # this runs, it is too early. We must astify *at the use site*. So use an
    # `ast.Call` to delay, and in there, splice in `tree` as-is.
    return ASTLiteral(ast.Call(_mcpy_quotes_attr("astify"), [tree], []))

def n(tree, *, syntax, expand_macros, **kw):
    """Splice an str, lifted into a lexical identifier, into quasiquoted code.

    The resulting node's `ctx` is filled in automatically by the macro expander later.
    """
    assert syntax == "expr"
    tree = expand_macros(tree)
    return ASTLiteral(astify(ast.Name(id=ASTLiteral(tree))))

def a(tree, *, syntax, **kw):
    """Splice an AST into quasiquoted code."""
    assert syntax == "expr"
    return ASTLiteral(tree)

def h(tree, *, syntax, **kw):
    """Splice any value into quasiquoted code (hygienic unquote)."""
    assert syntax == "expr"
    name = unparse(tree)
    return CaptureLater(tree, name)
