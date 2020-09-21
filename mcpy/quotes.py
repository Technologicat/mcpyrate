# -*- coding: utf-8; -*-
"""Quasiquotes. Build ASTs in your macros, conveniently.

**Quick reference**

  - `q` quasiquote, like in MacroPy.
  - `u` value-unquote, like in MacroPy.
  - `n` name-unquote, like MacroPy's `name`.
  - `a` AST-unquote, like MacroPy's `ast_literal`.
  - `h` hygienify.


**Introduction**

By default, quasiquoting in `mcpy` is non-hygienic. If you're familiar with
Common Lisp's `defmacro`, you'll feel almost right at home.

But we provide one important convenience, `h[]`, which allows to selectively
quote identifiers hygienically.

Almost always:

  - If the quoted code is calling a function, you'll want the function name to
    be quoted hygienically. That way, at your macro's use site, it's guaranteed
    to really call the function you expect, and not some other function that
    just happens to have the same name at the use site.

  - If your macro establishes any new bindings, you'll want their names to be
    gensyms, so they won't conflict with any names already in scope at the
    macro use site, no matter what names already exist there. See `gensym`.


**Hygienic quasiquoting**

In `mcpy`, there is no separate hygienic-quasiquote macro. Instead, use `h[]`
inside a `q[]` to mark a use of an identifier that you want to be quoted
hygienically.

It doesn't matter whether the identifier is a local, nonlocal or global,
as long as it's in scope within the `q[]`. The identifier must be a bare name.

So if you have an object or an array, `h[]` just the thing itself. If you
need to perform any attribute or subscript accesses, do that on the result::

    q[h[x]]
    q[h[obj].someattr]
    q[h[array][42]]

To avoid capturing the same thing multiple times, assign the hygienically
quoted identifier (which is represented as an AST) to a variable, and then
AST-unquote that variable as many times as you need::

    hygx = q[h[x]]
    tree = q[...a[hygx]...]

This is the `mcpy` equivalent of the Common Lisp pattern, where one gensyms
a new name, `let`-binds that to the value of the old name, and then uses the
new name in the quoted code. The implementation details differ a bit, but
such a uniqifying bind is essentially what `h[]` does.

Because it's a bind operation, the hygienically quoted identifier points to the
value the identifier had at capture time, not to the name. It won't track any
rebinds of the original identifier within your macro code::

    x = "tabby"
    firstcat = q[h[x]]
    ...

    x = "scottishfold"

    # firstcat still points to "tabby". If you want to refer to the new value
    # at the macro use site, capture again:
    secondcat = q[h[x]]

    # firstcat points to "tabby", secondcat points to "scottishfold".


**Advanced uses of non-hygienic quasiquoting**

Macro hygiene has its place, but non-hygienic quoting leads to two advanced
techniques that sometimes turn out useful:

  - *Anaphora*. The macro defines an identifier that has a specific name.
    Typically, the macro computes some value and binds it to that identifier,
    meant to be read by the macro's use site. For example, the `it` in the
    classic *anaphoric if*.

    This is sometimes so useful that also Lisps that have a macro system that
    is hygienic by default (such as Scheme and Racket), provide a way to
    selectively break hygiene. For example, in Racket it's possible to produce
    a `return` "keyword" using this approach (by binding the function's escape
    continuation to a variable named `return`, and then leaking that identifier
    on purpose).

  - *Free variable injection*, the lesser-known dual to anaphora. The
    *use site* is expected to define an identifier having a specific name.
    The macro just assumes that name is in scope (without defining it itself)
    and proceeds to use it. (The term comes from Doug Hoyte, in Let Over
    Lambda: 50 Years of Lisp.)

Obviously, when using either of these techniques, it is absolutely critical to
document the expectations in the macro's documentation. And, they're slightly
magic, so it's best to avoid them except where absolutely needed.


**Summary**

Keep in mind that in `mcpy`, quasiquotes are a tool to make building macros easier.

Here *macro definition site* and *macro use site* refer to those sites for the
macro in whose implementation `q` is used to construct (part of) the output
AST.

Some simple cases, explained:

    `q[x]`      --> The thing the name `x` refers to at the macro *use site*.
                    In other words, just the bare name `x` at the macro use site.

    `q[h[x]]`   --> The thing the name `x` refers to at the macro *definition site*.

                    `x` must be a bare name. It doesn't matter what, if anything,
                    the name `x` refers to at the macro use site; the purpose of
                    `h[]` is to avoid such name conflicts.

    `q[u[x]]`   --> Value of the variable `x` at the macro definition site.

                    The value that results from evaluating `x` must be something
                    that can be easily lifted into an AST that, when compiled and run,
                    re-constructs that value.

                    Explicitly: constants (number, string, bytes, boolean or None),
                    containers (`list`, `dict` or `set`) containing such constants,
                    and trees built out of multiple levels of such containers,
                    where all the leaves are constants.

    `q[n[x]]`   --> Identifier with its name taken from the value of the str
                    variable `x` at the macro definition site.

                    With this, you can compute a name (as a string) and then
                    use it as an identifier.

    `q[a[x]]`   --> The AST stored in the variable `x` at the macro definition
                    site. Same thing as just `x` (note no `q[]`).

                    The point of `a[]` is that it can appear as a part of the
                    expression inside the `q[]`, so you can construct subtrees
                    separately (using any strategy of your choosing) and then
                    splice them into a quoted code snippet.

Note that:

    `q[n["x"]]` --> Identifier with the literal name `x` at the macro use site.
                    Same as `q[x]`.

                    This is a useless use of `n[]`. The reason `n[]` exists is
                    that the argument may be a variable.

                    Using `n[]` to name-unquote a string literal does shut up
                    flake8 concerning the "undefined" name `x`, but you can
                    also `# noqa: F821` to achieve the same effect.

**Note**

It's a peculiarity of Python that the quasiquote system is implemented as macros;
in Lisps, these are typically special operators built in to the language core.

Also, we must provide several types of unquotes (`u`, `n`, `a`), because Python
has a surface syntax, instead of representing source code directly as a lightly
dressed up AST, like Lisps do.

Our implementation closely follows MacroPy's, except `h`, which is simpler.
We don't pickle/unpickle, and the implementation is short enough that the
whole quasiquote system fits into one module.
"""

import ast

from .unparse import unparse
from .utilities import gensym

# --------------------------------------------------------------------------------

class Hygienic(ast.expr):
    """Pseudo-node. Tell `astify` to hygienically capture the given identifier.

    This is essentially an AST marker used internally by `q[]`.
    It is expanded away by `astify`, to allow the rest of `mcpy`
    to deal with real AST nodes only.

    Like MacroPy's `Captured`. We inherit from `ast.expr` to let
    `mcpy`'s expander know this behaves somewhat like an expr node.
    """
    def __init__(self, id):
        self.id = id
        self._fields = ["id"]

    def __repr__(self):
        return "Hygienic({})".format(self.id)

# Memory usage:
#
# The hygienic capture occurs anew each time `q[]` expands (inside your macro
# definition). So for each `h[]` in a macro definition, a new capture will
# occur for each *invocation* of the macro. It must do that in order to always
# capture the right thing.
#
# Currently, these captures are never deleted, so this potentially produces a
# memory leak; but a mild one that depends only on lexical properties of the
# codebase using macros.
#
# The memory required for the hygienic captures is proportional to the number
# of times `h[]` occurs in each macro definition, times the number of
# invocations of that macro in the target codebase, summed over all macros
# invoked by the target codebase. Furthermore, each item is only a string key,
# paired with an object reference, so they don't take much memory.
#
# (Another question is how much memory that object takes, since it'll never
#  become unreachable; but the most common use case of hygienic quasiquoting
#  is to safely refer to top-level functions imported at the macro definition
#  site, so it's likely just a function object, and these aren't typically
#  that large.)
#
# Critically, the memory usage does not depend on how many times the final
# expanded code is called. The expanded code contains only lookups, no
# captures.
#
# In a majority of realistic use cases, not deleting the captures is just fine.
#
# One exception is a long-lived REPL session involving many reloads of macro
# definitions (to test them interactively in an agile way); in such a use case,
# if those macros use `q[h[]]`, the memory usage of the capture registry will
# grow at each reload (as the uses of `h[]` get expanded).
#
captured = {}  # hygienic capture registry
def capture(value, asname):
    """Store a value into the hygienic capture registry. Used by `q[h[]]`.

    `value`: Any run-time value.

    `asname`: Basename for gensymming a unique key for the value.

              For human-readability, to see in an AST dump (that contains just
              a lookup command with the unique key) what that captured thing is.

              The original identifier name, when available, is the recommended
              `asname`; but any human-readable label is fine.

    The return value is an AST that, when compiled and run, looks up the
    captured value.

    This runs when `q[]` expands. Available to be used from other
    macro-writing-utility macros.
    """
    unique_name = gensym(asname)
    captured[unique_name] = value
    # print("capture: registry now:")  # DEBUG
    # for k, v in captured.items():  # DEBUG
    #     print("    ", k, "-->", ast_aware_repr(v))
    return generate_lookup_ast(unique_name)

def lookup(captured_sym):
    """Look up a hygienically captured name. Used in the output of `q[h[]]`."""
    # print("lookup:", captured_sym, "-->", ast_aware_repr(captured[captured_sym]))
    return captured[captured_sym]

def generate_lookup_ast(captured_sym):
    """Create the AST that, when compiled and run, looks up the given hygienically captured name."""
    # print("creating lookup for:", captured_sym)
    return ast.Call(ast.Name(id="lookup", ctx=ast.Load()), [ast.Constant(value=captured_sym)], [])

# --------------------------------------------------------------------------------

class ASTLiteral(ast.expr):
    """Pseudo-node. Tell `astify` to keep the given expr as-is.

    This is essentially an AST marker used internally by `q[]`.
    It is expanded away by `astify`, to allow the rest of `mcpy`
    to deal with real AST nodes only.

    Like MacroPy's `Literal`. We inherit from `ast.expr` to let
    `mcpy`'s expander know this behaves somewhat like an expr node.
    """
    def __init__(self, body):
        """body: the original AST to preserve"""
        self.body = body
        self._fields = ["body"]  # support ast.iterfields

    def __repr__(self):
        return "ASTLiteral({})".format(unparse(self.body))

def astify(x):
    """Lift a value into its AST representation, if possible.

    When the AST is compiled and run, it will return the given value.

    Like MacroPy's `ast_repr`.
    """
    tx = type(x)

    if tx is ASTLiteral:
        # We just drop the ASTLiteral pseudo-node wrapper; its only purpose is
        # to tell us this subtree needs no further processing.
        return x.body

    elif tx is Hygienic:
        # This is the magic part of q[h[]]. We convert the `Hygienic`
        # pseudo-node into an AST which, when compiled and run, captures the
        # value the desired name (at that time) points to. The return value of
        # the capture call is the AST to perform a lookup for that captured value.
        #
        # So at the use site of q[], it captures the value, and at the use site of
        # the macro that used q[], it looks up the captured value.
        return ast.Call(ast.Name(id='capture', ctx=ast.Load()),
                        [ast.Name(id=x.id, ctx=ast.Load()),
                         ast.Constant(value=x.id)],
                        [])

    # Constants (Python 3.6+).
    elif tx in (int, float, str, bytes, bool, type(None)):
        return ast.Constant(value=x)

    # Containers.
    elif tx is list:
        return ast.List(elts=list(astify(elt) for elt in x),
                        ctx=ast.Load())
    elif tx is dict:
        return ast.Dict(keys=list(astify(k) for k in x.keys()),
                        values=list(astify(v) for v in x.values()),
                        ctx=ast.Load())
    elif tx is set:
        return ast.Set(elts=list(astify(elt) for elt in x),
                       ctx=ast.Load())

    # Anything that is already an AST node (e.g. `Name`).
    elif isinstance(x, ast.AST):
        # The magic is in the Call. We take apart the original input AST,
        # and construct a new AST, that (when compiled and run) will re-generate
        # the AST we got as input.
        fields = [ast.keyword(a, astify(b)) for a, b in ast.iter_fields(x)]
        # TODO: Instead of `ast.Name(id='ast')` here, have `ast` in the capture registry,
        # TODO: and look it up from there. Can use `generate_lookup_ast` to build the lookup AST.
        return ast.Call(ast.Attribute(value=ast.Name(id='ast', ctx=ast.Load()),
                                      attr=x.__class__.__name__, ctx=ast.Load()),
                        [],
                        fields)

    raise TypeError("Don't know how to astify {}".format(repr(x)))

# --------------------------------------------------------------------------------
# Macros

# TODO: block variants. Use the macro interface as a dispatcher.

# TODO: `u`, `n`, `a` are not really independent macros, but only valid inside a `q`.
#
# TODO: Use/implement a walker and then, in `q`, act on `Subscript` nodes with the appropriate names.
# TODO: This would also make `q` behave like in Lisps - quoted macro invocations
# TODO: will then not be expanded (the caller is expected to do that if they want).
#
# TODO: Should assert that the final output does not contain pseudo-nodes such as `ASTLiteral` and `Hygienic`.
def q(tree, *, syntax, expand_macros, **kw):
    """Quasiquote an expr, lifting it into its AST representation."""
    assert syntax == "expr"
    tree = expand_macros(tree)
    return astify(tree)

# TODO: u[] should expand macros only when the quotelevel hits zero. Track it.
def u(tree, *, syntax, expand_macros, **kw):
    """Splice a value into quasiquoted code."""
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
    return ASTLiteral(ast.Call(ast.Name(id="astify", ctx=ast.Load()), [tree], []))

# TODO: to allow use on the LHS of an assignment, don't assume Load context;
# TODO: rather, leave ctx undefined here and fix missing ctx in a walker afterward.
def n(tree, *, syntax, expand_macros, **kw):
    """Splice an str, lifted into a lexical identifier in Load context, into quasiquoted code."""
    assert syntax == "expr"
    tree = expand_macros(tree)
    # Output:  ast.Name(id=..., ctx=ast.Load())
    #
    # Leaving this here for documentation purposes:
    # return ASTLiteral(ast.Call(ast.Attribute(value=ast.Name(id='ast', ctx=ast.Load()),
    #                                          attr='Name', ctx=ast.Load()),
    #                            [],
    #                            [ast.keyword("id", tree),
    #                             # We must make *the output AST* invoke `ast.Load()` when it runs
    #                             # (so it can place that into `ctx`), hence the `ast.Call` business here.
    #                             ast.keyword("ctx", ast.Call(ast.Attribute(value=ast.Name(id='ast',
    #                                                                                      ctx=ast.Load()),
    #                                                                       attr='Load',
    #                                                                       ctx=ast.Load()),
    #                                                         [],
    #                                                         []))]))
    #
    # Easier way to say the same thing:
    # The inner `ASTLiteral` tells `astify` not to astify that part, and then vanishes.
    return ASTLiteral(astify(ast.Name(id=ASTLiteral(tree),
                                      ctx=ast.Load())))

# TODO: Typecheck that the `tree` really is an AST. Difficult to do, since this is a
# TODO: macro - even the wrong kind of input is technically represented as an AST.
def a(tree, *, syntax, **kw):
    """Splice an AST into quasiquoted code."""
    assert syntax == "expr"
    return ASTLiteral(tree)

# TODO: Generalize to capture `Attribute` and `Subscript` nodes, to capture the thing itself.
# TODO: Unpythonic needs that to support h-capturing `let` variables, which expand to an `Attribute`.
def h(tree, *, syntax, **kw):
    """Splice a reference into quasiquoted code (hygienic quote).

    `tree` must be an `ast.Name`.

    When used inside a `q[]`, the end result is an AST, which, when compiled
    and run, refers to the unquoted name as it was at the use site of `h`,
    which is typically inside another macro.

    So using this, you can be sure the macro expansion calls the function you
    intended, and no other function that just happened to have the same name
    at the macro use site.
    """
    assert syntax == "expr"
    assert type(tree) is ast.Name
    return Hygienic(tree.id)
