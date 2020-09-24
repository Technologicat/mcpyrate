# -*- coding: utf-8; -*-
"""Quasiquotes. Build ASTs in your macros, conveniently."""

__all__ = ['capture', 'lookup', 'astify',
           'q', 'u', 'n', 'a', 'h']

import ast
from .unparse import unparse
from .utilities import gensym, ast_aware_repr

# --------------------------------------------------------------------------------

class PseudoNode(ast.expr):
    """Almost like a real AST node.

    Pseudonodes are AST markers used internally by `q[]`. They are expanded
    away by `astify`, to allow the rest of `mcpy` to deal with real AST nodes
    only.

    We inherit from `ast.expr` to let `mcpy`'s expander know this behaves
    somewhat like an expr node, so it won't choke on this while expanding
    quasiquotes.
    """
    def __init__(self, body):
        """body: the real AST"""
        self.body = body
        self._fields = ["body"]  # support ast.iterfields

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, ast_aware_repr(self.body))

class ASTLiteral(PseudoNode):
    """Keep the given subtree as-is. Like MacroPy's `Literal`."""
    pass

class CaptureLater(PseudoNode):
    """Capture the value the given subtree evaluates to at the use site of `q[]`. Like MacroPy's `Captured`."""
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

    `value`: Any run-time value.

    `basename`: Basename for gensymming a unique key for the value.

                For human-readability, to see in an AST dump (that contains just
                a lookup command with the unique key) what that captured thing is.

                The original identifier name, when available, is the recommended
                `basename`; but any human-readable label is fine.

                It does not need to be a valid identifier.

    The return value is an AST that, when compiled and run, looks up the
    captured value.

    If the value `is` already in the registry, return an AST to look up
    with the existing key.
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

def astify(x):
    """Lift a value into its AST representation, if possible.

    When the AST is compiled and run, it will return `x`.

    If `x` itself is an AST, then produce an AST that, when compiled and run,
    will generate the AST `x`.

    Raises `TypeError` when the lifting fails.

    Like MacroPy's `ast_repr`.
    """
    tx = type(x)

    # We just drop the ASTLiteral pseudo-node wrapper; its only purpose is
    # to tell us this subtree needs no further processing.
    if tx is ASTLiteral:
        return x.body

    # This is the magic part of q[h[]]. We convert the `CaptureLater`
    # pseudo-node into an AST which, when compiled and run, captures the
    # value the desired name (at that time) points to. The capture call
    # returns an AST, which represents a lookup for that captured value.
    #
    # So at the use site of q[], this captures the value and rewrites itself
    # into a lookup, and at the use site of the macro that used q[], that
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
        # The magic is in the Call. We take apart the original input AST,
        # and construct a new AST, that (when compiled and run) will re-generate
        # the AST we got as input.
        #
        # We refer to the stdlib `ast` module as `mcpy.quotes.ast` to avoid
        # name conflicts with anything the user may want to refer to as `ast`.
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

# TODO: block variants. Use the macro interface as a dispatcher.

# TODO: `u`, `n`, `a` are not really independent macros, but only valid inside a `q`.
#
# TODO: Use/implement a walker and then, in `q`, act on `Subscript` nodes with the appropriate names.
# TODO: This would also make `q` behave like in Lisps - quasiquoted macro invocations
# TODO: will then not be expanded (the caller is expected to do that if they want).
#
# TODO: q[] should assert the final output does not contain pseudo-nodes such as `ASTLiteral` and `CaptureLater`.
# TODO: Doing that needs a walker.
def q(tree, *, syntax, expand_macros, **kw):
    """Quasiquote an expr, lifting it into its AST representation."""
    assert syntax == "expr"
    tree = expand_macros(tree)
    # The key idea here is that a macro system already lifts code into its AST
    # representation; to access that AST representation, we just need to define
    # a macro and look at the `tree` that arrives as input.
    #
    # A macro is expected to return a replacement for `tree`. If we return the
    # original `tree`, the macro system will compile and run the original code
    # - not what we want.
    #
    # The trick is to wrap the original AST such that when the macro system
    # compiles and runs our return value, that produces `tree`.
    return astify(tree)

# TODO: u[] should expand macros only when the quotelevel hits zero. Track it.
def u(tree, *, syntax, expand_macros, **kw):
    """Splice a simple value into quasiquoted code."""
    assert syntax == "expr"
    tree = expand_macros(tree)
    # Output:  astify(<value of tree>)
    #
    # Note: if e.g. `tree=ast.Name(id=v)`, we don't want to generate an AST
    # that compiles to a reference to a lexical variable named `v`; instead, we
    # want to generate an AST that compiles to the value of `v`. But when this
    # code runs, it is too early. Astification must wait until *our output AST*
    # is compiled and run.
    #
    # The magic is in the Call (this causes the delay), and in splicing in the
    # value of `tree`, without astifying it yet.
    return ASTLiteral(ast.Call(_mcpy_quotes_attr("astify"), [tree], []))

def n(tree, *, syntax, expand_macros, **kw):
    """Splice an str, lifted into a lexical identifier, into quasiquoted code.

    The resulting node's `ctx` is handled automatically by the macro expander later.
    """
    assert syntax == "expr"
    tree = expand_macros(tree)
    # These notes are from the first version that supported only `Load` context.
    #
    # Output:  ast.Name(id=..., ctx=ast.Load())
    #
    # This is clumsy to do manually. For documentation purposes:
    # return ASTLiteral(ast.Call(ast.Attribute(value=_generate_hygienic_lookup_ast('ast'),
    #                                          attr='Name', ctx=ast.Load()),
    #                            [],
    #                            [ast.keyword("id", tree),
    #                             # We must make *the output AST* invoke `ast.Load()` when it runs
    #                             # (so it can place that into `ctx`), hence the `ast.Call` business here.
    #                             ast.keyword("ctx", ast.Call(ast.Attribute(value=_generate_hygienic_lookup_ast('ast'),
    #                                                                       attr='Load',
    #                                                                       ctx=ast.Load()),
    #                                                         [],
    #                                                         []))]))
    #
    # But wait, that looks familiar... like the output of `astify`?
    # The inner `ASTLiteral` here tells `astify` not to astify that part, and then vanishes.
    #
    # We leave ctx undefined here, and fix missing ctx in a walker afterward,
    # so it gets either `Load`, `Store` or `Del`, depending on where the `n[]` appeared.
    return ASTLiteral(astify(ast.Name(id=ASTLiteral(tree))))

# TODO: Typecheck that the `tree` really is an AST. Difficult to do, since this is a
# TODO: macro - even the wrong kind of input is technically represented as an AST.
def a(tree, *, syntax, **kw):
    """Splice an AST into quasiquoted code."""
    assert syntax == "expr"
    return ASTLiteral(tree)

def h(tree, *, syntax, **kw):
    """Splice any value into quasiquoted code (hygienic unquote)."""
    assert syntax == "expr"
    name = unparse(tree)
    return CaptureLater(tree, name)
