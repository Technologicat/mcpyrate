**Navigation**

- [Main user manual](main.md)
- **Quasiquotes and `mcpyrate.metatools`**
- [REPL and `macropython`](repl.md)
- [The `mcpyrate` compiler](compiler.md)
- [AST walkers](walkers.md)
- [Dialects](dialects.md)
- [Troubleshooting](troubleshooting.md)

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
        - [Expression mode](#expression-mode)
        - [Block mode](#block-mode)
        - [Notes](#notes)
    - [`u`: unquote](#u-unquote)
    - [`n`: name-unquote](#n-name-unquote)
    - [`a`: ast-unquote](#a-ast-unquote)
        - [Expression mode](#expression-mode-1)
        - [Block mode](#block-mode-1)
        - [Notes](#notes-1)
    - [`s`: ast-list-unquote](#s-ast-list-unquote)
    - [`t`: ast-tuple-unquote](#t-ast-tuple-unquote)
    - [`h`: hygienic-unquote](#h-hygienic-unquote)
        - [Hygienically captured run-time values](#hygienically-captured-run-time-values)
        - [Hygienically captured macros](#hygienically-captured-macros)
        - [Hygienic macro recursion](#hygienic-macro-recursion)
        - [Treating hygienically captured values in AST walkers](#treating-hygienically-captured-values-in-ast-walkers)
    - [Syntactically allowed positions for unquotes](#syntactically-allowed-positions-for-unquotes)
    - [Quotes, unquotes, and macro expansion](#quotes-unquotes-and-macro-expansion)
- [The `expand` family of macros](#the-expand-family-of-macros)
    - [When to use](#when-to-use)
    - [Stepping a run-time macro expansion with `stepr`](#stepping-a-run-time-macro-expansion-with-stepr)
    - [Using the `expand` macros](#using-the-expand-macros)
- [Understanding the quasiquote system](#understanding-the-quasiquote-system)
    - [How `q` arranges hygienic captures](#how-q-arranges-hygienic-captures)
- [Notes](#notes-2)
    - [Difference between `h[]` and `u[]`](#difference-between-h-and-u)
    - [Differences to Common Lisp](#differences-to-common-lisp)
    - [Differences to `macropy`](#differences-to-macropy)
        - [In usage](#in-usage)
        - [In implementation](#in-implementation)
    - [Etymology](#etymology)

<!-- markdown-toc end -->


# Introduction

Here's a minimal, complete implementation of delayed evaluation, with memoization. Spot the macro!

```python
__all__ = ["delay", "force"]

from mcpyrate.quotes import macros, q, a

_uninitialized = object()
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

def force(x):
    """Evaluate a delayed expression, at most once."""
    return x.force() if isinstance(x, Promise) else x
```

For a production-quality version of this example, see [`demo/promise.py`](../demo/promise.py).

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

You'll still need to keep the [AST documentation](https://docs.python.org/3/library/ast.html) handy,
but usually not much manually written AST-generating code is needed when
quasiquotes automate most of it. This makes macro code much more readable.

By default, quasiquoting in `mcpyrate` is classical, i.e. non-hygienic. If you're
familiar with Common Lisp's `defmacro` (or if you've been reading
[Seibel](http://www.gigamonkeys.com/book/) or
[Graham](http://paulgraham.com/onlisp.html)), you'll feel almost right at home.

The system is similar in flavor to [`macropy`'s quasiquote system](https://macropy3.readthedocs.io/en/latest/reference.html#quasiquotes), but with [some important differences](#differences-to-macropy).


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

The functions `mcpyrate.quotes.capture_value` and `mcpyrate.quotes.capture_as_macro`
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

The quasiquote supports both expression and block modes.

### Expression mode

```python
q[expr]
```

Lift the expression `expr` into an AST. E.g. `q[42]` becomes `ast.Constant(value=42)`.

### Block mode

```python
with q as quoted:
    body0
    ...
```

To lift statements, use block mode. The `with q as quoted` construct lifts the
`with` block body into a `list` of AST nodes. The list is assigned to the name
given as the asname (in the example, `quoted`).

### Notes

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
spliced into the quoted code. Unquoting occurs at run time of the use site
of the surrounding `q` (which is typically inside the implementation of
one of your own macros).

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
based on the `.py` filename the invocation of `n[]` appears in.

Finally, observe that `q[n["x"]]` is the name `x` at the macro use site. It's
the same as just `q[x]`. This is a useless use of `n[]`. The reason `n[]` exists
at all is that its argument can be the result of a computation.

Using `n[]` to name-unquote a string literal does shut up flake8 concerning
the "undefined" name `x`, but for that use case, we recommend [`# noqa: F821`](https://flake8.pycqa.org/en/latest/user/error-codes.html).

Generalized from `macropy`'s `name`, which converts a string into a lexical variable access.


## `a`: ast-unquote

Splice an existing AST value into quoted code. This unquote supports both expr and block modes.

### Expression mode

```python
a[expr]
```

The expression `expr` must evaluate, at run time at the use site of the
surrounding `q`, to an *expression* AST node, an AST marker containing
an *expression* AST node in its `body` attribute, or in certain contexts
where that is valid in the AST, a `list` of such values.

Typically, `expr` is the name of a variable that holds such data, but it
doesn't have to be; any expression that evaluates to acceptable data is fine.

An example of a context that accepts a `list` of expression nodes is the
positional arguments of a function call. `q[myfunc(a[args])]` will splice
the `list` value `args` into the positional arguments of the `Call`. Each element
of the `list` becomes one positional argument. Of course, ast-unquoting single
positional arguments such as `q[myfunc(a[arg1], a[arg2])]` is also fine.

The result of `a[]` is an *expression* AST, replacing the invocation of `a[]`.
Note that if `a[]` appears in a statement position (inside a block mode `q`),
it actually appears in the AST inside Python's invisible `ast.Expr` "expression
statement" node. If you want to inject a tree to the raw statement position
without a surrounding `ast.Expr`, use the block mode of `a`.

The `a[]` operator will type-check at run time, at the use site of the
surrounding `q`, that the value of `expr` is of the correct type.

### Block mode

```python
with a:
    stmts
    ...
```

Each `stmts` must evaluate, at run time at the use site of the surrounding `q`,
to a *statement* AST node, an AST marker containing a *statement* AST node
(or a `list` of statement AST nodes) in its `body` attribute, or a `list`
of such values.

Typically, `stmts` is the name of a variable that holds such data, but it
doesn't have to be; any expression that evaluates to acceptable data is fine.

This expands as if all those statements appeared in the `with` body,
in the order listed. The `with a` block itself is compiled away;
the statements are spliced into the surrounding context.

The body of the `with a` must not contain anything else.

The `with a` operator will type-check at run time, at the use site of the
surrounding `q`, once each `stmts` has been resolved to a value, that the
value is of the correct type.

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

`s[lst]` takes an iterable of AST nodes, and into the quoted code, splices an
`ast.List` node, with all nodes from the iterable collected into its `elts`
attribute. The input iterable is converted to a `list` (so it can be assigned
as `elts`), but the nodes themselves are **not** copied.

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


## `t`: ast-tuple-unquote

Like `s`, but makes an `ast.Tuple`.

This is especially useful to splice in a list of ASTs into the [macro
arguments](main.md#macro-arguments) of some parametric macro. (In `mcpyrate`,
multiple macro arguments are always represented as an `ast.Tuple` node.)

```python
args = [q[[a, 1]], q[[b, 2]], q[[c, 3]]]
q[let[t[args]][a + b + c]]
```

It doesn't really matter here what `let` is, but you can consider it as the
[`let` macro from the demos](../demo/let.py). The result of the above is the
same as if we had written:

```python
q[let[[a, 1], [b, 2], [c, 3]][a + b + c]]
```

Note that in the `let` bindings, as in any macro invocation, the outer brackets
belong to the subscript expression; they do **not** denote a `list`. Because in
Python's surface syntax, a bare comma (without surrounding parentheses or brackets
that belong to that comma) creates a tuple, this is exactly the same as:

```python
q[let[([a, 1], [b, 2], [c, 3])][a + b + c]]
```

which is how the `let` bindings look like if you `unparse` the above. Hence the
natural container for multiple macro arguments in Python is a tuple; which is
why we provide the `t[]` unquote.


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


### Hygienic macro recursion

It is always possible, for a macro implementation, to call another macro
directly as a regular function (i.e. treating it as a syntax transformer);
this will expand it immediately. This is indeed how things were often done
using `macropy` when a macro needed to use another macro.

But what if we want, instead, to encode the use of that other macro as a
*hygienic* macro invocation in the output AST, and let the expander handle it?
This allows `step_expansion` to see the intermediate steps, while preserving
macro hygiene (so we can be sure the result expands using the macro we intended).

Using `q[h[...]]`, hygienically referring to a macro name works fine as long as
the target macro is bound in the expander that is expanding the use site of
`q[h[...]]` (keep in mind that use site is typically inside your own macro
definition).

Macro bindings are usually established using macro-imports. This implies that
the macro definition of the macro being hygienically referred to must have come
from another source file that has already finished compiling, or from an earlier
phase of the current source file (if multi-phase compiling); both cases rule out
loops. So it turns out that for hygienic macro recursion, we cannot use `q[h[...]]`.

Instead, we can use **the function `mcpyrate.quotes.capture_as_macro`**, which
manually captures a hygienic reference to a macro function into the expander's
global macro bindings table in the current process. This makes it possible to
inject any macro function to all expanders in the current process, without
caring about macro-imports. This is the same mechanism `q[h[...]]` itself uses;
we are now just using a different source for the bindings.

A [mutually recursive](https://en.wikipedia.org/wiki/Mutual_recursion) example (available as [`demo/hygienic_recursion.py`](../demo/hygienic_recursion.py)):

```python
from mcpyrate.quotes import macros, q, u, a

import ast

from mcpyrate.quotes import capture_as_macro

def even(tree, **kw):
    if type(tree) is ast.Constant:
        v = tree.value

    if v == 0:
        return q[True]
    return q[a[our_odd][u[v - 1]]]

def odd(tree, **kw):
    if type(tree) is ast.Constant:
        v = tree.value

    if v == 0:
        return q[False]
    return q[a[our_even][u[v - 1]]]

our_even = capture_as_macro(even)
our_odd = capture_as_macro(odd)
```

Note the use of `a[]` instead of `h[]` to splice in the hygienic reference.
This is because the function `capture_as_macro` already performs the capture,
and returns the AST snippet that represents the hygienic reference.

(It is the job of the `h[]` operator to *perform a capture*, using the current
expander's macro bindings as the source for macro captures. Now that we already
have a capture, we don't need `h[]`.)

Note the actual hygienic macro name **won't be** `our_even` or `our_odd`; the
`capture_as_macro` function takes the original name of the macro function and
tacks on an uuid. The variable names `our_even` and `our_odd` just refer to
the AST snippets.

Pasting that code into the IPython REPL (with the extension
`mcpyrate.repl.iconsole` loaded), we can now:

```python
from mcpyrate.debug import macros, step_expansion
from __self__ import macros, even, odd

step_expansion[odd[4]]
```

The output is:

```python
In [21]: step_expansion[odd[4]]
    ...:
**Tree 0x7f66113be710 (<ipython-session>) before macro expansion:
  odd[4]
**Tree 0x7f66113be710 (<ipython-session>) after step 1:
  even_5d1045354cfe42498f6854f3f59a519c[3]
**Tree 0x7f66113be710 (<ipython-session>) after step 2:
  odd_f498be9593b5448ba811661875364969[2]
**Tree 0x7f66113be710 (<ipython-session>) after step 3:
  even_5d1045354cfe42498f6854f3f59a519c[1]
**Tree 0x7f66113be710 (<ipython-session>) after step 4:
  odd_f498be9593b5448ba811661875364969[0]
**Tree 0x7f66113be710 (<ipython-session>) after step 5:
  False
**Tree 0x7f66113be710 (<ipython-session>) macro expansion complete after 5 steps.
Out[21]: False
```

This example used mutual recursion, but the same technique works for simple
self-recursion, too. Note the telltale uuid-suffixed names, indicating hygienic
captures.

Finally, for the sake of exposition, let us demonstrate another useful advanced
technique, using `mcpyrate.utils.extract_bindings`. If we know that the macro we
want to invoke is in the current expander's bindings, we can grab its name from
there, and then refer to it classically (non-hygienically):

```python
from mcpyrate.utils import extract_bindings

def mymacro(tree, *, expander, **kw):
    bindings = extract_bindings(expander.bindings, mymacro)
    myname = list(bindings.keys())[0]

    newtree = q[n[myname][...]]
    ...
```

However, this does not work for hygienic macro recursion, because some code may
call the macro function directly, instead of invoking it as a macro. So in this
example, even `mymacro` itself is **not** guaranteed to be bound in the current
expander. Also, mutual macro recursion cannot be achieved cleanly with this
technique, because any macro being queried must have been macro-imported
at the use site.

This technique does respect as-imports, though, and it's the right approach for
a different use case; see [`demo/anaphoric_if.py`](../demo/anaphoric_if.py) for
an example. This technique does the right thing when there is a set of macros
that must be imported together (such as `aif` and its magic variable `it`),
and *the use site* is expected to explicitly invoke all of them.

Note the subtle difference: in that other use case, the use site controls the
names of the macros (locally), via macro-imports. So the use site knows the
names, and may also rename them (via as-import). But in hygienic macro
recursion, the use site doesn't even care about macros other than the one it's
invoking directly. There the definition site has a macro function it wants to
refer to, and the name used in its macro binding can be anything, as long as
it's unambiguous.

In conclusion, for hygienic macro recursion, use the function `capture_as_macro`,
as demonstrated above. Using that, the macros invoked hygienically in the output AST
don't need to be in the expander's bindings at the use site.


### Treating hygienically captured values in AST walkers

In `mcpyrate`, hygienically captured run-time values are represented in the AST as a `Call` node that matches `mcpyrate.quotes.is_captured_value`. That function (added in `mcpyrate` 3.3.0) is the public API to detect and destructure them.

If you have code-walking macros - particularly, any `macropy` `@Walker`s you intend to port to use `mcpyrate`'s `ASTTransformer` - you may need to:
```python
if is_captured_value(tree):
    return tree  # don't recurse!
```
in order to avoid destroying the capture. In 99% of cases, this should be done before any other AST pattern matching, and the wisest course of action is to not edit the hygienic capture node, and not recurse there. (Our sister project [`unpythonic`](https://github.com/Technologicat/unpythonic/blob/master/doc/features.md#dyn-dynamic-assignment) contains some examples of the 1% where we need to do something else. See use sites of `is_captured_value`, particularly the syntax transformer for `unpythonic.syntax.lazify`.)

The important point is, the capture looks like a `Call`, but it's not really playing the role of a function call. That call is really just part of the plumbing that makes the captured value magically appear at run time. To keep things simple and explicit, it's not hidden from your macros; but this does mean you need to be aware of this detail.

From another viewpoint, the hygienic capture is a higher-level abstraction. It doesn't matter what AST node types it uses; the particular AST pattern is an implementation detail. Hence it should usually be matched first, before any AST node types in their usual roles.

If you need to analyze the captured name or expression, and/or the actual snapshotted value, the unparsed source code for the name or expression that was captured by `h[]` is in the return value of `mcpyrate.quotes.is_captured_value` (whenever there was a match; i.e. the return value is not `False`). The captured value can be looked up by passing the whole return value to `mcpyrate.quotes.lookup_value`. This can be useful if you e.g. need to see which function a hygienically unquoted function name points to. See the docstrings of `is_captured_value` and `lookup_value` for details.


## Syntactically allowed positions for unquotes

Unquote operators may only appear inside quasiquoted code. This is checked at
macro expansion time. If an unquote operator appears outside any quasiquote,
it is a macro-expansion-time error.

Quote level is tracked, and unquoting takes place when it hits zero.

```python
x = "hi"
assert unparse(q[u[x]]) == "'hi'"
assert unparse(q[q[u[x]]]) == "q[u[x]]"
assert unparse(q[q[u[u[x]]]]) == "q[u['hi']]"
```

In quasiquoted code, unquote operators may appear anywhere a subscript expression
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

**In quoted code**, macros are **not** expanded by default. Depending on what you want, you can:

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

 - "Time" (as in *macro expansion time* vs. *run time*) [must be considered separately for each source file](troubleshooting.md#macro-expansion-time-where-exactly).
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

Regular macros that want to use hygienic capture, without using quasiquotes, can just call the API functions `capture_value` or `capture_as_macro`.

`q` itself can't simply call `capture_value`, because *it generates code for your macro*. So instead of calling `capture_value` directly in the implementation of `q`, it needs to arrange things so that `capture_value` gets called *at the use site of `q`*.

If you write your own macro-generating macro that needs to do something similar, you can make an `ast.Call` that will, at run time, call `capture_value` with the appropriate arguments, and splice that `ast.Call` into your output. As the arguments in the `ast.Call`, you'll want to set `value` to the tree for the expression whose value you want to capture, and `name` to an `ast.Constant` with a human-readable string value.

`q` **does** call `capture_macro` (note no `as`) directly. This works because the use site imports all the macros that source file will use already at macro-expansion time. (Even if some of the macros are only imported for use in macro output, specifically so that `h[]` can detect references to them.) So the relevant macro binding is available in the expander that is running that invocation of `q`.

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

In `mcpyrate`, all quote and unquote operators have single-character names by default: `q`, `u`, `n`, `a`, `s`, `t`, `h`. Of these, `q` and `u` are as in `macropy`, the operator `n` most closely corresponds to `name`, `a` to `ast_literal`, and `s` to `ast_list`.

`mcpyrate` adds a sister for `s`, namely `t`, which works similarly, but makes an `ast.Tuple`. This is convenient especially in the macro argument position, because `mcpyrate` represents multiple macro arguments as a tuple.

In `mcpyrate`, there is **just one *quote* operator**, `q[]`, although just like in `macropy`, there are several different *unquote* operators, depending on what you want to do. In `mcpyrate`, there is no `unhygienic` operator, because there is no separate `hq` quote.

For [macro hygiene](https://en.wikipedia.org/wiki/Hygienic_macro), we provide a **hygienic unquote** operator, `h[]`. So instead of implicitly hygienifying all `Name` nodes inside a `hq[]` like `macropy` does, `mcpyrate` instead expects the user to use the regular `q[]`, and explicitly say which subexpressions to hygienify, by unquoting each of those separately with `h[]`. The hygienic unquote operator captures expressions by snapshotting a value; it does not care about names, except for human-readable output. Hygienically capturing an identifier snapshots its current value when the use site of the surrounding `q` reaches run time.

In `mcpyrate`, also macro names can be captured hygienically.

In `mcpyrate`, hygienically captured run-time values are represented in the AST as a `Call` node that matches `mcpyrate.quotes.is_captured_value`. In `macropy`, hygienically captured identifiers are represented as `Name` nodes, and its machinery jumps through more hoops to retain the illusion they are regular names. It will rename them to avoid name conflicts, though; `mcpyrate` doesn't need to rename anything due to the different capture mechanism.

In `mcpyrate`, there is no `expose_unhygienic`, and no names are reserved for the macro system. (You can call a variable `ast` if you want, and it won't shadow anything important.)

The `expose_unhygienic` mechanism is not needed, because in `mcpyrate`, each macro-import is transformed into a regular import of the module the macros are imported from. So the macros can refer to anything in the top-level namespace of their module as attributes of that module object. (As usual in Python, this includes any imports. For example, `mcpyrate.quotes` refers to the stdlib `ast` module in the macro expansions as `mcpyrate.quotes.ast` for this reason.)

If you need to expose some name to allow the user to override it locally (e.g. a callback function, to be overridden in a block macro invocation), consider *dynamic assignment* (a.k.a. dynamic variables), such as that provided by our sister project [`unpythonic`](https://github.com/Technologicat/unpythonic/blob/master/doc/features.md#dyn-dynamic-assignment), as [`unpythonic.dyn`](https://github.com/Technologicat/unpythonic/blob/master/doc/features.md#dyn-dynamic-assignment). You can then set a default (`make_dynvar(cat="tabby")`) and let the user override it at run time (`with dyn.let(cat="scottishfold")`).

In `mcpyrate`, the `a` operator has also a block mode (`with a`), which unquotes *statement* AST nodes.

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
