# -*- coding: utf-8; -*-
"""Quasiquotes. Build ASTs in your macros, using syntax that mostly looks like regular code.."""

__all__ = ['capture', 'lookup', 'astify',
           'q', 'u', 'n', 'a', 's', 'h']

import ast
from contextlib import contextmanager
from .core import expand_macros
from .unparse import unparse
from .utilities import gensym, ast_aware_repr
from .walkers import Walker

# --------------------------------------------------------------------------------

class PseudoNode(ast.AST):
    """Almost like a real AST node.

    Pseudonodes are internal AST markers used by `q[]`. They are expanded away
    by `astify`, to allow the rest of `mcpy` to deal with real AST nodes only.

    We inherit from `ast.AST` to let `mcpy`'s expander know this behaves
    somewhat like a single AST node.
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

def get_pseudonodes(tree):
    """Return a `list` of any `PseudoNode` instances found in `tree`. For output validation."""
    class PseudoNodeCollector(Walker):
        def transform(self, tree):
            if isinstance(tree, PseudoNode):
                self.collect(tree)
            self.generic_visit(tree)
            return tree
    p = PseudoNodeCollector()
    p.visit(tree)
    return p.collected

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
    """Store a value into the hygienic capture registry.

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
    return ast.Call(_mcpy_quotes_attr("lookup"),
                    [ast.Constant(value=key)],
                    [])

def lookup(key):
    """Look up a hygienically captured value."""
    return _registry[key]

# --------------------------------------------------------------------------------

def astify(x):  # like MacroPy's `ast_repr`
    """Lift a value into its AST representation, if possible.

    When the AST is compiled and run, it will evaluate to `x`.

    If `x` itself is an AST, then produce an AST that, when compiled and run,
    will generate the AST `x`.

    If the input is a `list` of ASTs for a statement suite, the return value
    is a single `ast.List` node, with its `elts` taken from the input list.
    It's however not used this way, because `_BaseMacroExpander` already
    translates a `visit` to a statement suite into visits to individual nodes,
    because otherwise `ast.NodeTransformer` chokes on the input.

    Raises `TypeError` when the lifting fails.
    """
    tx = type(x)

    # Drop the ASTLiteral wrapper; it only tells us to pass through this subtree as-is.
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

    elif tx in (int, float, str, bytes, bool, type(None)):
        return ast.Constant(value=x)

    elif tx is list:
        return ast.List(elts=list(astify(elt) for elt in x))
    elif tx is dict:
        return ast.Dict(keys=list(astify(k) for k in x.keys()),
                        values=list(astify(v) for v in x.values()))
    elif tx is set:
        return ast.Set(elts=list(astify(elt) for elt in x))

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

_quotelevel = 0
@contextmanager
def _quotelevel_changed_by(delta):
    global _quotelevel
    _quotelevel += delta
    try:
        yield
    finally:
        _quotelevel -= delta
    assert _quotelevel >= 0

# These operators are named after Qu'nash, the goddess of quasiquotes in high-tech-elven mythology.

def q(tree, *, syntax, expander, **kw):
    """quasiquote. Lift code into its AST representation."""
    if syntax not in ("expr", "block"):
        raise SyntaxError("q is an expr and block macro only")
    with _quotelevel_changed_by(+1):
        tree = _expand_quasiquotes(tree, expander)
        tree = astify(tree)
        ps = get_pseudonodes(tree)  # postcondition: no remaining pseudonodes
        if ps:
            assert False, f"internal PseudoNode instances remaining in output: {ps}"
        if syntax == 'block':
            target = kw['optional_vars']  # List, Tuple, Name
            if type(target) is not ast.Name:
                raise SyntaxError(f"expected a single asname, got {unparse(target)}")
            tree = ast.Assign([target], tree)
        return tree

def u(tree, *, syntax, expander, **kw):
    """unquote. Splice a simple value into a quasiquote.

    The value is lifted into an AST that re-constructs that value
    """
    if syntax != "expr":
        raise SyntaxError("u is an expr macro only")
    if _quotelevel < 1:
        raise SyntaxError("u[] encountered while quotelevel < 1")
    with _quotelevel_changed_by(-1):
        if _quotelevel == 0:
            tree = expander.visit(tree)
        else:
            tree = _expand_quasiquotes(tree, expander)
        # We want to generate an AST that compiles to the *value* of `v`. But when
        # this runs, it is too early. We must astify *at the use site*. So use an
        # `ast.Call` to delay, and in there, splice in `tree` as-is.
        return ASTLiteral(ast.Call(_mcpy_quotes_attr("astify"), [tree], []))

def n(tree, *, syntax, **kw):
    """name-unquote. Splice a string, lifted into a lexical identifier, into a quasiquote.

    The resulting node's `ctx` is filled in automatically by the macro expander later.
    """
    if syntax != "expr":
        raise SyntaxError("n is an expr macro only")
    if _quotelevel < 1:
        raise SyntaxError("n[] encountered while quotelevel < 1")
    with _quotelevel_changed_by(-1):
        return ASTLiteral(astify(ast.Name(id=ASTLiteral(tree))))

def a(tree, *, syntax, **kw):
    """AST-unquote. Splice an AST into a quasiquote."""
    if syntax != "expr":
        raise SyntaxError("a is an expr macro only")
    if _quotelevel < 1:
        raise SyntaxError("a[] encountered while quotelevel < 1")
    with _quotelevel_changed_by(-1):
        return ASTLiteral(tree)

def s(tree, *, syntax, **kw):
    """list-unquote. Splice a `list` of ASTs, as an `ast.List`, into a quasiquote."""
    if syntax != "expr":
        raise SyntaxError("s is an expr macro only")
    if _quotelevel < 1:
        raise SyntaxError("s[] encountered while quotelevel < 1")
    return ASTLiteral(ast.Call(ast.Attribute(value=_mcpy_quotes_attr('ast'),
                                             attr='List'),
                               [],
                               [ast.keyword("elts", tree)]))

def h(tree, *, syntax, expander, **kw):
    """hygienic-unquote. Splice any value, from the macro definition site, into a quasiquote.

    Supports also values that have no meaningful `repr`.
    """
    if syntax != "expr":
        raise SyntaxError("h is an expr macro only")
    if _quotelevel < 1:
        raise SyntaxError("h[] encountered while quotelevel < 1")
    with _quotelevel_changed_by(-1):
        name = unparse(tree)
        if _quotelevel == 0:
            tree = expander.visit(tree)
        else:
            tree = _expand_quasiquotes(tree, expander)
        return CaptureLater(tree, name)

def _expand_quasiquotes(tree, expander):
    """Expand quasiquote macros only."""
    # Use a second expander instance, with different bindings. Copy only the
    # bindings of the quasiquote macros from the main `expander`, accounting
    # for possible as-imports.
    bindings = {k: v for k, v in expander.bindings.items() if v in (q, u, n, a, s, h)}
    return expand_macros(tree, bindings, expander.filename)
