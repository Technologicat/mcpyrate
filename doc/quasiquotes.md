<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Introduction](#introduction)
- [Avoiding name conflicts at the macro use site](#avoiding-name-conflicts-at-the-macro-use-site)
    - [`gensym`](#gensym)
    - [Macro hygiene](#macro-hygiene)
    - [Macro hygiene without quasiquotes](#macro-hygiene-without-quasiquotes)
    - [Advanced uses of non-hygienic quasiquoting](#advanced-uses-of-non-hygienic-quasiquoting)
- [Reference manual](#reference-manual)
    - [`q`: quasiquote](#q-quasiquote)
    - [`u`: unquote](#u-unquote)
    - [`n`: name-unquote](#n-name-unquote)
    - [`a`: ast-unquote](#a-ast-unquote)
        - [Expression mode](#expression-mode)
        - [Block mode](#block-mode)
        - [Notes](#notes)
    - [`s`: ast-list-unquote](#s-ast-list-unquote)
    - [`h`: hygienic-unquote](#h-hygienic-unquote)
        - [Hygienically captured run-time values](#hygienically-captured-run-time-values)
        - [Hygienically captured macros](#hygienically-captured-macros)
    - [Syntactically allowed positions for unquotes](#syntactically-allowed-positions-for-unquotes)
    - [Quotes, unquotes, and macro expansion](#quotes-unquotes-and-macro-expansion)
- [The `expand` family of macros](#the-expand-family-of-macros)
    - [When to use](#when-to-use)
    - [Stepping a run-time macro expansion with `stepr`](#stepping-a-run-time-macro-expansion-with-stepr)
    - [Using the `expand` macros](#using-the-expand-macros)
- [Understanding the quasiquote system](#understanding-the-quasiquote-system)
    - [How `q` arranges hygienic captures](#how-q-arranges-hygienic-captures)
- [Notes](#notes-1)
    - [Difference between `h[]` and `u[]`](#difference-between-h-and-u)
    - [Differences to Common Lisp](#differences-to-common-lisp)
    - [Differences to `macropy`](#differences-to-macropy)
        - [In usage](#in-usage)
        - [In implementation](#in-implementation)
    - [Etymology](#etymology)

<!-- markdown-toc end -->


# Introduction

Here's a complete implementation of `delay`/`force`, with memoization and plain-value passthrough. Spot the macro!

```python
__all__ = ["delay", "force"]

from mcpyrate.quotes import macros, q, a

_ununitialized = object()
class Promise:
    def __init__(self, thunk):
        self.thunk = thunk
        self.value = _uninitialized

    def force(self):
        if self.value is _uninitialized:
            self.value = self.thunk()
        return self.value

def delay(tree, **kw):
    """[syntax, expr] Delay an expression."""
    return q[Promise(lambda: a[tree])]

def force(promise):
    """Evaluate a delayed expression, at most once."""
    return promise.force() if isinstance(promise, Promise) else promise
```

Quasiquoting is a way to build ASTs in notation that mostly looks like regular
code. Classically, in Lisps, the quasiquote operator doesn't need to do much,
because Lisps are homoiconic; i.e. there's not much of a difference between
source code and its AST representation.

In Python, as was pioneered by `macropy`, quasiquoting is a way to write ASTs
using the standard surface syntax of Python. This works surprisingly well,
although sometimes you, the macro writer, will have to do small old-fashioned
AST edits to the resulting AST, because some things that would be sensible as
a quasiquoted AST (but not as regular code) are not syntactically allowed by
Python.

For example, it is not possible to directly interpolate a name for a function
parameter in quasiquote notation, because parameter definitions must use literal
strings, not expressions. In this case, the technique is to first use a
placeholder name, such as `_`, and then manually assign a new name for the
parameter in the AST that was returned by the quasiquote operation. See [`mcpyrate.utils.rename`](../mcpyrate/utils.py), which can do this editing for
you.

You'll still need to keep [Green Tree
Snakes](https://greentreesnakes.readthedocs.io/en/latest/nodes.html) and maybe
also the [ast](https://docs.python.org/3/library/ast.html) documentation handy,
but usually not much manually written AST-generating code is needed when
quasiquotes automate most of it. This makes macro code much more readable.

By default, quasiquoting in `mcpyrate` is classical, i.e. non-hygienic. If you're
familiar with Common Lisp's `defmacro` (or if you've been reading
[Seibel](http://www.gigamonkeys.com/book/) or
[Graham](http://paulgraham.com/onlisp.html)), you'll feel almost right at home.

The system is similar in flavor to [`macropy`'s quasiquote system](https://macropy3.readthedocs.io/en/latest/reference.html#quasiquotes), but with some important differences.


# Avoiding name conflicts at the macro use site

Classical (non-hygienic) quasiquoting passes through identifiers as-is. This
may lead to name conflicts, because the macro definition site has no control
over what names are already in scope at the macro use site.

The problem has two related aspects, which are in a sense dual to each other.
First, if a macro needs to establish new bindings in the expanded code, it must
be able to generate variable names that are not already taken at the macro use
site, no matter what names already appear there. This is the job of `gensym`.

Secondly, if the expanded code needs to refer to a value (in Python terms, an
object) that was in scope at the macro definition site, that's where *macro
hygiene* comes in. An example of such an object is a function that you imported
into the global scope of your macro definition module, to be able to call that
function in the code generated by your macro.


## `gensym`

Short for *generate symbol*, `gensym` provides fresh, unused identifiers.

When your macro needs to generate code that establishes new bindings, see
`mcpyrate.gensym()`, and use `n[]` (and old-fashioned AST edits or
`mcpyrate.utils.rename` where needed) judiciously.


## Macro hygiene

*Macro hygiene* refers to preserving the meaning of an identifier, from the
macro definition site, to the macro use site. This is a highly desirable
feature, and `mcpyrate` supports it via an explicit opt-in construct, which
we call *hygienic unquoting*.

*Hygienic unquoting* captures *a value* from the macro definition site, at the
time when the macro is running (i.e. when its use site is being macro-expanded),
and automatically arranges things such that when the expanded code runs, the
hygienically unquoted expression refers to that value.

The main use case is to allow the expanded code, at the macro *use* site, to
safely refer to a function (or indeed, any other variable) that was in scope at
the macro *definition* site. That way, at your macro's use site, it's guaranteed
to really call the function you meant, and not some other function that just
happened to have the same name at the use site.

To mark a value you want to be unquoted hygienically, use the `h[]`
(hygienic-unquote) operator inside a quasiquoted code snippet.

In order for `mcpyrate` to support bytecode caching (`.pyc`), the value is pickled,
separately for each invocation of `h[]`. When the value is looked up at run
time, it is automatically unpickled the first time it is accessed in a given
Python process. Further accesses, by the same invocation of `h[]`, then refer
to the same object.

Note that due to how `pickle` works, you can hygienically unquote local and
nonlocal variables just fine, as long as the *type* of the value (i.e. the
`class`) is defined at the top-level scope of some module.

Because `h[]` is essentially a bind operation, the result of `h[expr]` will
forever point to the value `expr` had at capture time:

```python
x = "tabby"
mycat = q[h[x]]

x = "scottishfold"
yourcat = q[h[x]]

# mycat -> AST that, when compiled and run,
#          resolves to the value "tabby".
# yourcat -> AST that, when compiled and run,
#            resolves to the value "scottishfold".
```

If you want to `h[]` an object or an array, keep in mind that **the current
value will be pickled** and that pickled copy becomes the thing the `h[]`
refers to.


## Macro hygiene without quasiquotes

If you want to capture values or macro names hygienically in an old-school macro
that does not use the quasiquote notation, this is also possible. The machinery
underlying the `h[]` operator is part of the public API, by design.

The functions `mcpyrate.quotes.capture_value` and `mcpyrate.quotes.capture_macro`
perform the actual capture. The return value is the AST snippet for the hygienic
reference. You can call these functions directly in your macro implementation.


## Advanced uses of non-hygienic quasiquoting

Macro hygiene has its place, but non-hygienic quoting leads to two advanced
techniques that are sometimes useful:

  - [*Anaphora*](https://en.wikipedia.org/wiki/Anaphoric_macro). The macro defines an identifier that has a specific name.

    Typically, the macro computes some value and binds it to that identifier.
    That value is then intended to be referred to, by that name, at the macro
    use site. For example, the `it` in the classic *anaphoric if*.

    This is occasionally so useful that also Lisps that have a macro system
    that is hygienic by default (such as Scheme and Racket), provide a way
    to selectively *break hygiene*.

    For example, in Racket it's possible to produce a `return` "keyword" using
    this approach, by binding the function's escape continuation to a variable
    named `return`, and then leaking that identifier non-hygienically. (This
    is possible, because Scheme and Racket have first-class continuations,
    so it's just a callable value.)

  - *Free variable injection*, the lesser-known dual to anaphora. The *use site*
    is expected to define an identifier having a specific name, and bind some
    particular value to it.

    That value is then intended to be referred to, by that name, in the code
    generated by the macro. In that code, it's a free variable (because the macro
    doesn't define it), hence the name of the technique.

    This term was seen in [Doug Hoyte: Let Over Lambda: 50 Years of Lisp](https://letoverlambda.com/).

Obviously, both of these techniques are somewhat magic, so unless absolutely
needed, they are discouraged. When used, good documentation is absolutely
critical.


# Reference manual

Here *macro definition site* and *macro use site* refer to those sites for the
macro in whose implementation `q` is used to construct (part of) the output AST.

The AST for the quoted code becomes fully available at the run time of the use
site of `q`, i.e. when your macro reaches run time.


## `q`: quasiquote

`q[expr]` lifts the expression `expr` into an AST. E.g. `q[42]` becomes
`ast.Constant(value=42)`.

To lift statements, use block mode. `with q as quoted` lifts the `with` block
body into a `list` of AST nodes. The list is assigned to the name given as the
asname (in the example, `quoted`).

In both expression and block modes, any names in the quoted code remain exactly
as they appear in the source. This may cause name conflicts with names already
present at the macro use site. See `gensym` and `h[]`, as discussed above.

For usage examples of `q`, see the examples of the unquote operators below.

Like `macropy`'s `q`, except macro invocations within the quoted code are not
expanded by default.

The macro [`mcpyrate.metatools.expandsq`](../mcpyrate/metatools.py) produces results closest to `macropy`'s `q`.


## `u`: unquote

`u[expr]` unquotes `expr`. It evaluates the value of the expression `expr`
at the macro definition site, and lifts the result into an AST that is
spliced into the quoted code.

`expr` must evaluate to a value of a built-in type (number, string, bytes,
boolean or None), a built-in container (`list`, `dict` or `set`) containing
only such values, or a tree built out of multiple levels of such containers,
where all leaves are such values.

If you need to unquote a more general value from the macro definition site
(e.g. an object instance, or a top-level function), see `h[]`.

In cases where the type restriction is acceptable, prefer `u[]`;
it's cheaper than `h[]`.

Typical use is like:

```python
sourcecode = unparse(tree)
logging_call = q[h[log_value_with_sourcecode](a[tree], u[sourcecode])]
```

If you don't need the extra line for clearer stack traces, the temporary variable is not needed:

```python
logging_call = q[h[log_value_with_sourcecode](a[tree], u[unparse(tree)])]
```


## `n`: name-unquote

`n[code]` parses the expression `code` as Python source code at the macro
definition site, and splices the resulting AST into the quoted code.

`code` must evaluate to a string.

This operator was mainly designed for generating an AST to access a lexical
variable, whose name is computed when your macro runs (identifiers, attributes,
subscripts, in any syntactically allowed nested combination). But who knows
what else can be done with it?

Examples:

```python
temp = q[n[gensym()]]
with q as quoted:
    a[temp] = "I'm in a lexical variable with a computed name"

x = "computed_name"
with q as quoted:
    n[f"self.{x}"] = "I'm in an attribute with a computed name"

q[n[f"kitties[{j}].paws[{k}].claws"]]
```

The second example can also be written as:

```python
x = "computed_name"
with q as quoted:
    setattr(self, u[x], "I'm in an attribute with a computed name")
```

The first version generates the AST that corresponds to the source code
`self.computed_name = ...`, whereas the second generates the AST that
corresponds to `setattr(self, "computed_name", ...)`.

The first example, on the other hand, cannot (in general) be written using
`setattr`, since it is assigning *to a lexical variable with a computed name*,
which is not supported by Python.

As an alternative to `n[]`, see also [`mcpyrate.utils.rename`](../mcpyrate/utils.py),
which can replace a literal dummy name (e.g. `_`) by a computed name in all places
in a given AST where name-like things appear (e.g. function parameters, call keywords,
except-as, imports, ...).

Essentially, `n[code]` is defined as `a[ast.parse(code, mode="eval").body]`,
but it will also automatically set the `filename` argument of `ast.parse`
to the `.py` filename the invocation of `n[]` appears in.

Finally, observe that `q[n["x"]]` is the name `x` at the macro use site. It's
the same as just `q[x]`. This is a useless use of `n[]`. The reason `n[]` exists
at all is that its argument can be the result of a computation.

Using `n[]` to name-unquote a string literal does shut up flake8 concerning
the "undefined" name `x`, but for that use case, we recommend `# noqa: F821`.

Generalized from `macropy`'s `name`, which converts a string into a lexical variable access.


## `a`: ast-unquote

Splice an existing AST into quoted code. This unquote supports both expr and block modes.

### Expression mode

```python
a[expr]
```

The expression `expr` must evaluate, at run time at the use site of the
surrounding `q`, to an *expression* AST node. Typically, it is the name of a
variable that holds such a node, but any kind of expression is fine.

The result is an *expression* AST, replacing the invocation of `a[]`. Note that
if `a[]` appears in a statement position (inside a block mode `q`), it actually
appears in the AST inside Python's invisible `ast.Expr` "expression statement"
node. If you want to inject a tree to the raw statement position without a
surrounding `ast.Expr`, use the block mode of `a`.

The `a[]` operator will type-check at run time, at the use site of the
surrounding `q`, that the value of `expr` is an *expression* AST node
(or an `ASTMarker`, with an expression AST node in its `body`).

### Block mode

```python
with a:
    stmts
    ...
```

Each `stmts` must evaluate, at run time at the use site of the surrounding `q`,
to either a single *statement* AST node, or a `list` of *statement* AST nodes.
Typically, `stmts` is the name of a variable that holds such data.

This expands as if all those statements appeared in the `with` body,
in the order listed. The `with a` block itself is compiled away;
the statements are spliced into the surrounding context.

The body of the `with a` must not contain anything else.

The `with a` operator will type-check at run time, at the use site of the
surrounding `q`, once each `stmts` has been resolved to a value, that each node
it got is a *statement* AST node (or an `ASTMarker`, with such valid data in its
`body`).

### Notes

**Very important**: *If `mymacro` uses `q`, run time for the use site of `q`
is typically macro expansion time for an invocation of `mymacro`.*

Furthermore, when the use site of `q` has reached run time, the `q` macro
invocation is already long gone - it was expanded away when the **definition**
of `mymacro` was macro-expanded. At run time of the use site of `q`, the AST
corresponding to the quoted code has already been mostly constructed, with just
some final details to be filled in by the run-time parts of the quote/unquote
operators. (Mainly, any value or tree splicing occurs at that time, because
that's the earliest time that has the values available.)

So any AST node type errors in invocations of the `a` ast-unquote are still
caught during macro expansion time, but it's the macro expansion time *of some
module in your app*. The macro that uses `q` must be invoked in order for the
type check to run. It must behave like this, simply because the trees being
spliced in are not available until the use site of `q` reaches run time.

The type checks are **not recursive**, because Python's AST format provides
no information on which positions in the AST expect statements and which ones
expect expressions. So this cannot be automatically checked, short of
duplicating the full grammar, which would increase the maintenance effort
for `mcpyrate` beyond a reasonable level, whenever a new minor version of the
Python language is released.

So we check only the node(s) explicitly given to `a`, because there the macro
invocation type (expr or block) explicitly tells which node type is expected.
If the tree being spliced was built manually (not using quasiquotes), it may
still contain type-invalid data at a deeper level.

Or in plain English: the type checks will **not** eliminate *all* sources of
mysterious compile errors caused by manually introduced type errors in a macro
output AST. They only eliminate the most common error source for such when
quasiquotes are used (which is to say, the accidental incorrect use of `a`).

The tree being spliced is **not copied**, so if you `a` the same AST instance
multiple times, it will do exactly that. If needed, explicitly `copy.copy`
or `copy.deepcopy`, depending on what you want.

However, as a convenience, in the final global postprocess pass, the expander's
automatic `ctx` fixer detects if a node instance requiring a `ctx` has already
been seen during that postprocess pass, and shallow-copies it automatically
to eliminate `ctx` conflicts, because the same node instance might appear
in two or more positions that require different `ctx`. But until that final
global postprocess pass, the `id` of any node you pass into `a` is not
affected by the `a`.

The expression mode is equivalent to `macropy`'s `ast_literal`.


## `s`: ast-list-unquote

`s[lst]` takes a `list`, and into the quoted code, splices an `ast.List` node,
with the original list as its `elts` attribute. Note the list is **not** copied.

This allows interpolating a list of expression AST nodes as an `ast.List` node.
This can be convenient because in Python, lists can appear in many places, such
as on the LHS of an assignment:

```python
lst = [q[a], q[b], q[c]]  # noqa: F821, only quoted.
with q as quoted:
    s[lst] = 1, 2, 3
```

In this example, the resulting AST corresponds to the source code `[a, b, c] = 1, 2, 3`.

**With `s[]`, the result is always an expression AST.** (And as in the example, on the LHS of an assignment, that's perfectly fine - the assignment itself is a statement, but both its LHS and RHS are expressions.)

If you need to splice statements, see the block mode of `a` (ast-unquote), or
the function `mcpyrate.splicing.splice_statements`.

Equivalent to `macropy`'s `ast_list`.


## `h`: hygienic-unquote

`h[expr]` captures the value of the expression `expr` at the macro *definition*
site, and makes the expansion use the captured value.

The main use case of `h[]` is to safely (*hygienically*) refer to a function
or a macro that is in scope at the macro *definition* site, so that you can be
sure that when the macro expansion is spliced in at the macro *use* site, the
expanded code will call the function you meant, and not some other function
that just happened to have the same name at the macro use site. Hygienic
unquoting also means that the macro use site *does not need to import* the
thing being referred to:

```python
# mymacros.py
from mcpyrate.quotes import macros, q, a, h

from math import log  # as in logarithm

def mymacro(tree, **kw):
    return q[h[log](a[tree])]


# application.py
from .mymacros import macros, mymacro

def log(x):  # as in logging
    print(x)

log(mymacro[10.0])  # no name conflict, because `mymacro` uses `h[log]`
```

Alternatively, instead of a run-time value, `expr` may be the name of a macro
bound in the expander instance that is expanding the use site of `q`. Then that
macro is captured. This allows macros in scope at the use site of `q` to be
hygienically propagated out to the use site of the macro that uses `q`. So you
can write macros that `q[h[macroname][...]]`, and `macroname` doesn't have to be
macro-imported wherever that code gets spliced in:

```python
# meowmacros.py
from mcpyrate.quotes import macros, q, a, h

# let's assume we have a macro kittify[meowtype][expr]
from .catmemes import macros, kittify

def meowify(tree, **kw):
    return q[h[kittify]["meow!"][a[tree]]]


# application.py
from .meowmacros import macros, meowify

print(meowify["Hello, world!"])
```

When `meowify` runs (i.e. when its use site is macro-expanded), the macro
`kittify` is captured hygienically, but **not** immediately expanded. It will be
expanded (by the expander's recursive mode) when `meowify` returns. In this
trivial example, we could just as well use `mcpyrate.metatools.expandr` (see
[The `expand` family of macros](#the-expand-family-of-macros)) to expand the
quoted tree immediately (before returning it), to avoid the need for hygienic
unquoting. But sometimes in real-world use - especially if some of your macros
expand in an inside-out order - it may be beneficial to temporarily leave the
tree unexpanded (particularly, for much easier analysis by code-walking macros),
and let the expander handle it later.

Whether `expr` is a run-time value or a macro name, `h[]` works also across
process boundaries; that is, the hygienically captured thing can be looked up
even in another Python process later. This allows bytecode caching of use sites
of macros that use `q[h[...]]`.

### Hygienically captured run-time values

The result of evaluating `expr` can be any run-time value, as long as it is
picklable.

We use `pickle` to support bytecode caching for hygienically captured values.
For maximum flexibility, the pickled data is embedded as a byte string in the
macro-expanded source code.

The value is frozen once (by pickling) at the macro definition site, and each
use site (of the macro that used `q[h[...]]`) gets a fresh copy of the value.

At each use site, the value is unpickled only once (per Python process).
Further activations of any particular use site refer to the same object
instance the unpickling during that site's first activation (in the current
process) produced.

### Hygienically captured macros

Hygienic macro capture must be asked for explicitly, and it is not
recursive. Only the macro explicitly tagged `h[macroname][...]` will be
captured hygienically; any macro invocations in its output will not be.

Thus, each macro in a chain must use `h[]` explicitly, if it wants macro
invocations in its output to be hygienified. This is a feature, to keep
things explicit.


## Syntactically allowed positions for unquotes

Unquote operators may only appear inside quasiquoted code. This is checked at
macro expansion time. Otherwise, they may appear anywhere a subscript expression
is syntactically allowed.

Especially, when `q` is used block mode, unquotes may appear on the LHS of an
assignment, and as the operand of a `del`, simply because these are syntactically
allowed positions for subscript expressions. The macro expander fills in the
correct `ctx` automatically. Examples:

```python
target = ...  # AST for something that can appear on the LHS of an assignment
with q as quoted:
    a[target] = ...

target1 = ...
target2 = ...
with q as quoted:
    a[target1], a[target2] = ...

targets = [target1, target2]
with q as quoted:
    s[targets] = ...

with q as quoted:
    del n[some_computed_name]
```


## Quotes, unquotes, and macro expansion

**In an unquote expression** inside quoted code, regardless of how many levels of
quoting are present, macros are always fully expanded, because the purpose of
an unquote is to interpolate a value.

Anywhere else **in quoted code**, macros are **not** expanded by default.
Depending on what you want, you can:

 - Just leave them for the expander to handle automatically, *in the use site's context*,
   after the macro using `q` has returned. Useful if you hygienically unquote any
   macro names in your macro output.

 - Expand them explicitly. See below. Useful if you want to return a plain AST that has
   no macro invocations remaining.


# The `expand` family of macros

In the simple case, when no quasiquotes are used and macros never return a tree containing further macro invocations, then `expander.visit` is always sufficient. But otherwise, more fine-grained control is needed, to tell the expander which macro bindings to use, so that the tree expands correctly.

Generally, considering the source code, it is always the site that built a particular AST snippet - whether implicitly by source code text, or explicitly by manual construction - that knows what the correct macro bindings for that snippet are. For example, if `mymacro` uses some macro invocations in its output, the definition site of `mymacro` is the place that has the right macro bindings for those. For any user-provided parts of `tree`, it's the *use site* of `mymacro` that has the right macro bindings for any macro invocations that appear in it.

When `mymacro` needs to invoke other macros in its output, one possibility is to use the `h[]` unquote to hygienically transmit the correct binding from `mymacro`'s definition site to its use site (where the expander's recursive mode will automatically kick in). Another possibility is to expand the macros explicitly, before returning the tree. This section is about how to do the latter.

## When to use

There are two main ways to explicitly expand macros in run-time AST values (such as `tree` in a macro, or a quoted code snippet stored in a variable): the `expander.visit` method with its sisters (`visit_once`, `visit_recursively`), and the `expand` family of macros defined in `mcpyrate.metatools`.

If you want to expand a tree using the macro bindings *from your macro's use site*, you should use `expander.visit` and its sisters.

If you want to expand a tree using the macro bindings *from your macro's definition site*, you should use the `expand` family of macros.

Of the `expand` macros, you'll most likely want `expandr` or `expand1r`, which delay expansion until your macro's run time.

## Stepping a run-time macro expansion with `stepr`

If you need to see the steps of macro expansion of a run-time AST value, see [`mcpyrate.metatools.stepr`](../mcpyrate/metatools.py).

Note `stepr` is an expr macro only, because it takes as its input a run-time AST value, and in Python, values are always referred to by expressions. So if you use quasiquotes, create your quoted tree first, as usual, and then `quoted = stepr[quoted]`, where `quoted` is the variable you stored it in. It doesn't matter whether the quoted snippet itself is an expression or a block of statements.

The usual tool [`mcpyrate.debug.step_expansion`](../mcpyrate/debug.py) does not work for debugging run-time macro expansion, because it operates at the macro expansion time of its use site. The `stepr` macro is otherwise the same, but it delays the stepping until the run time of its use site - and uses the same macro bindings `expandr` would.

## Using the `expand` macros

Let's look at the `expand` macros in more detail. The [`mcpyrate.metatools`](../mcpyrate/metatools.py) module provides a family of macros to expand macros, all named `expand` plus a suffix of up to three characters in the order `1Xq`, where `X` is one of `s` or `r`. All of the `expand` macros have both expr and block modes.

These macros are convenient when working with quasiquoted code, and with run-time AST values in general. Run-time AST values are exactly the kind of thing macros operate on: the macro expansion time of the use site is the run time of the macro implementation itself.

The suffixes mean:

 - `1`: once. Expand one layer of macros only.
 - `s`: statically, i.e. at macro expansion time.
 - `r`: dynamically, i.e. at run time.
 - `q`: quote first. Apply `q` first, then the expander.

The **`s` (static) variants** simply hook into the expander at macro expansion time of their use site (which is, typically, inside your macro definition). This is simple, but it means that if you have defined a quoted `tree`, you can't just literally write `expands[tree]` (or `expand1s[tree]`) and expect it to work - because at macro expansion time, that `tree` argument to the `expands` (or `expand1s`) macro is just the lexical name `tree`, it has no value yet. Also, in quasiquoted code, operating at macro expansion time means that unquotes aren't fully processed yet, because they depend on run-time values from the use site of `q`.

The **`r` (run-time) variants** cover this use case. They snapshot the expander bindings at macro expansion time (of their use site), and then delay until run time (of that use site) to perform the actual expansion. They behave like calling `expander.visit` (or its sisters), but using the macro bindings *from their use site* (your macro's definition site).

Thus, `expandr[tree]` (as well as `expand1r[tree]`) will do the expected thing - i.e. expand the thing the name `tree` refers to when, at run time, the source code line with the `expandr` (respectively `expand1r`) invocation is reached. So you can create a quoted tree, save it to a variable `tree`, and then separately expand it from that variable, in the context of the macro bindings from your macro definition site.

When working with quasiquoted code, run-time expansion also has the benefit that any unquoted values will have been spliced in. Unquotes operate partly at run time of the use site of `q`. They must; the only context that has the user-provided names (where the unquoted data comes from) in scope is each particular use site of `q`, at its run time. The quasiquoted tree is only fully ready at run time of the use site of `q`.


# Understanding the quasiquote system

This section is intended for both users and developers. The quasiquote system is probably the most complex part of `mcpyrate`. In the words of Matthew Might, [*to understand is to implement*](http://matt.might.net/articles/parsing-with-derivatives/). So let's talk about the implementation.

Whether working with quasiquoted code, or thinking about how the quasiquote system itself works, one must be **very careful** to avoid conflating different meta-levels.

Below, let `mymacro` be a macro that uses `q` to build (part of) its output AST.

 - "Time" (as in macro expansion time vs. run time) [must be considered separately for each source file](../README.md#macro-expansion-time-where-exactly).
 - As for how `q` works, the question is: how does one lift the input AST of a macro, from macro expansion time (of the macro's use site), into the corresponding AST, at run time (of the macro's use site)?
   - *We make a new AST for code that, when it runs, it builds the original input AST **as a run-time value**.* In `mcpyrate`, the function that does this is called `astify`.
   - For example, consider the expression `q[cat]`, appearing inside the definition of `mymacro`. The input AST to `q` is `ast.Name(id='cat')`. Roughly speaking, the `q` macro outputs the "astified" AST `ast.Call(ast.Name, [], [ast.keyword('id', ast.Constant(value='cat'))])`.
     - **Before reading on, let that sink in.** The output AST says, *call the function `ast.Name` with the named argument `id='cat'`*. The `ast.Call` and `ast.Constant` nodes are there only because we represent that code as an AST.
       - In surface syntax notation, the same conversion is represented as `cat` becoming `ast.Name(id='cat')`.
     - So when that code runs (**at run time**), the resulting run-time value, i.e. the result of the function call `ast.Name(id='cat')`, is a copy the original input AST that was supplied to the `q` macro.
       - Strictly speaking, it's a copy of the original AST **minus any source location info**, because we **didn't** say `ast.Call(ast.Name, [], [ast.keyword('id', ast.Constant(value='cat')), ast.keyword('lineno', ...), ast.keyword('col_offset', ...)])`. This is on purpose. The result of a quasiquote will be likely spliced into a different source file, so whatever line numbers we fill, they are wrong. Thus we let the macro expander fill in the appropriate line number (which is that of the macro invocation at the use site of `mymacro`) in the source file where the code is actually used.
     - Run time, at the use site of `q`, is exactly when we want the value. Keep in mind that in this example, the use site of `q` is inside `mymacro`. The run time of `mymacro` is the macro expansion time of **its** use site.
     - Also keep in mind that whatever the `q` macro returns - because `q` is a macro - is spliced into the AST of the use site (inside the definition of `mymacro`), to replace the macro invocation of `q`.
       - The code that is spliced in is the "astified" AST, which at run time builds the original input AST.
       - When the source file containing the definition of `mymacro` is macro-expanded, the `q` macro invocation expands away, into the "astified" AST. At run time of `mymacro` the `q` macro invocation **is already long gone**.
 - It cannot be overemphasized that **values are a run-time thing**. This includes any trees sent to the `a` (ast-unquote) operator.
   - For example, for the invocation `a[tree]`, at macro expansion time of `a` (as well as that of the surrounding `q`), all that the `a` operator (respectively, the `q` operator) sees is just `ast.Name(id='tree')`. That `tree` **refers to a run-time value** at the use site of `q` - a value that doesn't exist yet at macro expansion time.
   - Hence, the unquote operators must perform part of their work at run time (of their use site), when the values are available. This includes any type checking of those values.

The above explanation is somewhat simplified.

The code generated by `q` is mostly an "astified" AST consisting of calls to various AST node constructors, but it may also have some other function calls (to functions defined in `mcpyrate.quotes`) sprinkled in that do something and then return an AST snippet. These function calls perform the run-time work of the operators.

So when the run-time value is evaluated, at run time of the use site of `q`, both the "astified" `ast.Call` function calls as well as the run-time parts of the operators run to construct the final AST. This final result is a plain AST, with no more function calls into the quasiquote system, and no extra `ast.Call` layer. **This final AST only becomes available at run time of the use site of `q`.** 


## How `q` arranges hygienic captures

Regular macros that want to use hygienic capture, without using quasiquotes, can just call the API functions `capture_value` or `capture_macro`.

`q` itself can't simply call `capture_value`, because *it generates code for your macro*. So instead of calling `capture_value` directly in the implementation of `q`, it needs to arrange things so that `capture_value` gets called *at the use site of `q`*.

If you write your own macro-generating macro that needs to do something similar, you can make an `ast.Call` that will, at run time, call `capture_value` with the appropriate arguments, and splice that `ast.Call` into your output. As the arguments in the `ast.Call`, you'll want to set `value` to the tree for the expression whose value you want to capture, and `name` to an `ast.Constant` with a human-readable string value.

`q` **does** call `capture_macro` directly. This works because the use site imports all the macros that source file will use already at macro-expansion time. (Even if some of the macros are only imported for use in macro output, specifically so that `h[]` can detect references to them.) So the relevant macro binding is available in the expander that is running that invocation of `q`.

This is better than delaying the macro capture until run time of the use site, because at run time, macro imports are gone. So the relevant binding must be recorded at macro expansion time anyway, from the expander that's expanding the use site of `q`. That's exactly the `expander` argument of the `q` macro function.

Also, there might not be an `expander` at the use site, if the use site is not in a macro. But even if it's in a macro and there happens to be a name `expander` in scope *at run time*, that points to the wrong expander - namely, the one expanding *the use site of your macro* (which is in a different file, that has different macro bindings). At that point, your macro has reached run time, so the `expander` that processed it is already gone.


# Notes

## Difference between `h[]` and `u[]`

The `h[]` operator accepts any picklable run-time value, including those that
have no meaningful `repr`. Via pickling the captured value, to be stored with
the bytecode, it carries those values from macro expansion time to run time
(even if macro expansion time was last week).

The expansion result of `h[]` is actually a capture command that executes when
the use site of the surrounding `q[]` does, rewriting itself into a lookup
command at that time. The use site of `q[]` then sees just that lookup command.

The `u[]` operator operates statically, purely at macro expansion time. It takes
the value apart, and generates an AST that will re-construct it. It is cheaper,
but only works for expressions that evaluate to certain built-in types.


## Differences to Common Lisp

In `mcpyrate`, the Common Lisp macro-implementation pattern, where one gensyms
a new name, `let`-binds that to the current value of the old name, and then
unquotes the new name in the quasiquoted code, looks like this:

```python
thex = q[h[x]]
tree = q[...a[thex]...]
```

In the Lisp family, this is perhaps closer to how Scheme and Racket handle things,
except that the hygienification must be asked for explicitly.

The above is for use cases where you need to *access* something that exists at
the macro definition site.

If you instead need a new lexical variable name to *assign something to*, do this:

```python
name = q[n[gensym()]]
with q as quoted:
    a[name] = ...
```

It's a peculiarity of Python that the quasiquote system is implemented as
macros, unlike in Lisps, where these are typically special operators built in
to the language core.

Python's macro systems themselves are obviously third-party addons. The core
language wasn't designed to support this level of semantic extensibility, but
it's powerful enough to allow developing systems to do that.

Unlike Lisps, we must provide several types of unquotes (`u`, `n`, `a`), because
Python has a surface syntax, instead of representing source code directly as a
lightly dressed up AST, like Lisps do.


## Differences to `macropy`

### In usage

By default, in `mcpyrate`, macros in quasiquoted code are not expanded when the quasiquote itself expands. 

In `mcpyrate`, all quote and unquote operators have single-character names by default: `q`, `u`, `n`, `a`, `s`, `h`. Of these, `q` and `u` are as in `macropy`, the operator `n` most closely corresponds to `name`, `a` to `ast_literal`, and `s` to `ast_list`.

In `mcpyrate`, there is **just one *quote* operator**, `q[]`, although just like in `macropy`, there are several different *unquote* operators, depending on what you want to do. In `mcpyrate`, there is no `unhygienic` operator, because there is no separate `hq` quote.

For [macro hygiene](https://en.wikipedia.org/wiki/Hygienic_macro), we provide a **hygienic unquote** operator, `h[]`. So instead of implicitly hygienifying all `Name` nodes inside a `hq[]` like `macropy` does, `mcpyrate` instead expects the user to use the regular `q[]`, and explicitly say which subexpressions to hygienify, by unquoting each of those separately with `h[]`. The hygienic unquote operator captures expressions by snapshotting a value; it does not care about names, except for human-readable output.

In `mcpyrate`, also macro names can be captured hygienically.

In `mcpyrate`, there is no `expose_unhygienic`, and no names are reserved for the macro system. (You can call a variable `ast` if you want, and it won't shadow anything important.)

The `expose_unhygienic` mechanism is not needed, because in `mcpyrate`, each macro-import is transformed into a regular import of the module the macros are imported from. So the macros can refer to anything in the top-level namespace of their module as attributes of that module object. (As usual in Python, this includes any imports. For example, `mcpyrate.quotes` refers to the stdlib `ast` module in the macro expansions as `mcpyrate.quotes.ast` for this reason.)

In `mcpyrate`, the `n[]` operator is a wrapper for `ast.parse`, so it will lift any source code that represents an expression, not only lexical variable references.

### In implementation

We have closely followed the impressive, pioneering work that originally
appeared in `macropy`. That source code, itself quite short, is full of creative
ingenuity, although at places could be written more clearly, due to the
first-generation nature of the system.

Since `mcpyrate` is a third-generation macro expander (and second-generation
having quasiquote support), we have actively attempted to make the best of
lessons learned, to make the implementation as readable as reasonably possible.
We have liberally changed function and class names, and refactored things where
this makes the code easier to understand.

Our `h` operator is both simpler and more general than `macropy`'s `hq[]`.
By using uuids in the lookup keys, we avoid the whole-file lexical scan.

We don't need to inject any additional imports. This makes the quasiquote system
fully orthogonal to the rest of `mcpyrate`. (Well, almost; it uses
`mcpyrate.core.global_bindings`. Still, although that was created for the use case
of supporting `h[]` on macro names, in principle it's a generic core feature.)

Because `mcpyrate` transforms `from module import macros, ...` (after collecting
macro definitions) into `import module`, we can just refer to our internal stuff
(including the stdlib `ast` module) as attributes of the module
`mcpyrate.quotes`. We feel this is the "better way" that source code comments in
`macropy`'s `quotes.py` suggested must surely exist.

We allow capturing the value of any expr, not just identifiers. However, we also
take a somewhat different approach, in that we don't even pretend to capture
names; our `h[]` is an *unquote* operator that captures *values*, not a *quote*
operator that walks the tree and changes names.


## Etymology

Based on quasiquotation [as popularized by the Lisp family](https://en.wikipedia.org/wiki/Lisp_(programming_language)#Self-evaluating_forms_and_quoting) of languages, in turn based on [Quine's linguistic device](https://en.wikipedia.org/wiki/Quasi-quotation) of the same name.
