# Quasiquotes

Build ASTs in your macros, using syntax that mostly looks like regular code.

```python
    from mcpyrate.quotes import macros, q, a
    
    def delay(tree, **kw):
        '''delay[expr] -> promise'''
        return q[lambda: a[tree]] 

    def force(promise):
        '''force(promise) -> value'''
        return promise()
```

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Quasiquotes](#quasiquotes)
    - [Quick reference](#quick-reference)
    - [Full reference](#full-reference)
    - [Introduction to quasiquoting](#introduction-to-quasiquoting)
        - [Avoiding name conflicts at the macro use site](#avoiding-name-conflicts-at-the-macro-use-site)
            - [`gensym`](#gensym)
            - [Macro hygiene](#macro-hygiene)
            - [Advanced uses of non-hygienic quasiquoting](#advanced-uses-of-non-hygienic-quasiquoting)
        - [Difference between `h[]` and `u[]`](#difference-between-h-and-u)
    - [For Common Lispers](#for-common-lispers)
    - [Python vs. Lisp](#python-vs-lisp)
    - [Differences to MacroPy](#differences-to-macropy)

<!-- markdown-toc end -->


## Quick reference

  - `q` quasiquote,
  - `u` value-unquote,
  - `n` name-unquote,
  - `a` AST-unquote,
  - `s` AST-list-unquote,
  - `h` hygienic-unquote.


## Full reference

Here *macro definition site* and *macro use site* refer to those sites for the
macro in whose implementation `q` is used to construct (part of) the output AST.

The operators:

 - `q[expr]` is the expression `expr`, lifted into an AST.

   By default, any names in the quasiquoted code remain exactly as they appear.

 - `h[expr]`, appearing inside a `q[]`, is the value of the expression `expr` at
   the macro *definition* site. The result of evaluating `expr` is allowed to
   be any run-time value, as long as it is picklable.

   (We use `pickle` to support bytecode caching for hygienically unquoted values.)

 - `u[expr]`, appearing inside a `q[]`, is the value of the expression `expr` at
   the macro definition site.

   The result of evaluating `expr` must be a constant (number, string, bytes,
   boolean or None), a built-in container (`list`, `dict` or `set`) containing
   only constants, or a tree built out of multiple levels of such containers,
   where all leaves are constants.

   In cases where that's all you need, prefer `u[]`; it's cheaper than `h[]`.

 - `n[expr]`, appearing inside a `q[]`, is a lexical identifier, with its name
   determined by evaluating the expression `expr` at the macro definition site.

   `expr` must evaluate to a string.

   With this, you can compute a name (e.g. by `mcpyrate.gensym`) and then use it as
   an identifier in quasiquoted code.

 - `a[tree]`, appearing inside a `q[]`, is the AST stored in the variable `tree`
   at the macro definition site. It's the same as just `tree` outside any `q[]`.

   The point is `a[]` can appear as a part of the expression inside the `q[]`,
   so you can construct subtrees separately (using any strategy of your
   choosing), and then interpolate them into a quasiquoted code snippet.

 - `s[lst]`, appearing inside a `q[]`, is the `ast.List` with its elements
   taken from `lst`.

   This allows interpolating a list of ASTs as an `ast.List` node.

Unquote operators may only appear inside quasiquoted code.

Otherwise, any of the operators may appear anywhere a subscript expression is
syntactically allowed, including on the LHS of an assignment, or as the operand
of a `del`. The macro expander fills in the correct `ctx` automatically.

Finally, observe that:

 - `n["x"]`, appearing inside a `q[]`, is the identifier with the literal name
   `x` at the macro use site. It's the same as just `x` inside the same `q[]`.

   This is a useless use of `n[]`. The reason `n[]` exists at all is that the
   argument may be a variable.

   Using `n[]` to name-unquote a string literal does shut up flake8 concerning
   the "undefined" name `x`, but for that use case, we recommend `# noqa: F821`.


## Introduction to quasiquoting

Quasiquoting is a way to build ASTs in notation that mostly looks like regular
code. Classically, in Lisps, the quasiquote operator doesn't need to do much,
because Lisps are homoiconic; i.e. there's not much of a difference between
source code and its AST representation.

In Python, as was pioneered by MacroPy, quasiquoting is a way to write ASTs
using the standard surface syntax of Python. This works surprisingly well,
although sometimes you, the macro writer, will have to do small old-fashioned
AST edits to the resulting AST, because some things that would be sensible as
a quasiquoted AST (but not as regular code) are not syntactically allowed by
Python.

For example, it is not possible to directly interpolate a name for a function
parameter in quasiquote notation, because parameter definitions must use literal
strings, not expressions. In this case, the technique is to first use a
placeholder name, such as `_`, and then manually assign a new name for the
parameter in the AST that was returned by the quasiquote operation. (Although
see [`mcpyrate.utils.rename`](mcpyrate/utils.py), which can do the editing for
you.)

You'll still need to keep [Green Tree
Snakes](https://greentreesnakes.readthedocs.io/en/latest/nodes.html) and maybe
also the [ast](https://docs.python.org/3/library/ast.html) documentation handy,
but usually not much manually written AST-generating code is needed when
quasiquotes automate most of it. This makes macro code much more readable.

By default, quasiquoting in `mcpyrate` is classical, i.e. non-hygienic. If you're
familiar with Common Lisp's `defmacro` (or if you've been reading
[Seibel](http://www.gigamonkeys.com/book/) or
[Graham](http://paulgraham.com/onlisp.html)), you'll feel almost right at home.


### Avoiding name conflicts at the macro use site

Classical quasiquoting passes through identifiers as-is. This leads to name
conflict issues, because the macro definition site has no control over what
names already appear at the macro use site.

There are two related aspects to this, which are in a sense dual to each other.
First, if a macro needs to establish new bindings in the expanded code, it must
be able to generate variable names that are not already taken at the macro use
site, no matter what names already appear there. This is the job of `gensym`.

Secondly, if the expanded code needs to refer to an object that was in scope at
the macro definition site (say, a function that you imported into the global
scope of your macro definition module, so it could be called by your macro
expansion), that's where *macro hygiene* comes in.


#### `gensym`

Short for *generate symbol*, `gensym` provides fresh, unused identifiers.

When your macro needs to generate code that establishes new bindings, see
`mcpyrate.gensym()`, and use `n[]` (and old-fashioned AST edits or
`mcpyrate.utils.rename` where needed) judiciously.


#### Macro hygiene

*Macro hygiene* refers to preserving the meaning of an identifier, from the
macro definition site, to the macro use site. This is a highly desirable
feature, and `mcpyrate` supports it via an explicit opt-in construct, which
we call *hygienic unquoting*.

*Hygienic unquoting* captures *a value* at macro definition time, and
automatically arranges things such that when the expanded code runs,
the hygienically unquoted expression refers to that value at run time.

The main use case is to allow the expanded code, at the macro *use* site, to
safely refer to a function (or indeed, any other variable) that was in scope at
the macro *definition* site. That way, at your macro's use site, it's guaranteed
to really call the function you meant, and not some other function that just
happened to have the same name at the use site.

To mark a value you want to be unquoted hygienically, use the `h[]`
(hygienic-unquote) operator inside a `q[]`.

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

    x = "tabby"
    mycat = q[h[x]]

    x = "scottishfold"
    yourcat = q[h[x]]

    # mycat -> AST that, when compiled and run,
    #          resolves to the value "tabby".
    # yourcat -> AST that, when compiled and run,
    #            resolves to the value "scottishfold".

If you want to `h[]` an object or an array, keep in mind that **the current
value will be pickled** and that pickled copy becomes the thing the `h[]`
refers to.


#### Advanced uses of non-hygienic quasiquoting

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

    That value is then intended to be referred to, by that name, at the macro
    definition site. In the macro code, it's a free variable (because the macro
    doesn't define it), hence the name of the technique.

    This term was seen in [Doug Hoyte: Let Over Lambda: 50 Years of Lisp](https://letoverlambda.com/).

Obviously, both of these techniques are somewhat magic, so unless absolutely
needed, they are discouraged. When used, good documentation is absolutely
critical.


### Difference between `h[]` and `u[]`

The `h[]` operator accepts any picklable run-time value, including those that
have no meaningful `repr`. Via pickling the captured value, to be stored with
the bytecode, it carries those values from macro expansion time to run time
(even if macro expansion time was last week).

The expansion result of `h[]` is actually a capture command that executes when
the use site of the surrounding `q[]` does, rewriting itself into a lookup
command at that time. The use site of `q[]` then sees just that lookup command.

The `u[]` operator operates statically, purely at macro expansion time. It takes
the value apart, and writes an AST that will re-construct it. It only works for
expressions that evaluate to constants, to built-in containers containing
constants, or to trees of such containers, where all leaves are constants.


## For Common Lispers

In `mcpyrate`, the Common Lisp macro-implementation pattern, where one gensyms
a new name, `let`-binds that to the current value of the old name, and then
unquotes the new name in the quasiquoted code, looks like this:

    hygx = q[h[x]]
    tree = q[...a[hygx]...]

Note in `mcpyrate` the `h[]` operator pickles its input, to support storing
macro-expanded code using hygienically unquoted values into a bytecode cache
(`.pyc`).


## Python vs. Lisp

It's a peculiarity of Python that the quasiquote system is implemented as
macros; in Lisps, these are typically special operators built in to the language
core.

Python's macro systems themselves are obviously third-party addons. The core
language wasn't designed to support this level of semantic extensibility, but
it's powerful enough to allow developing systems to do that.

Unlike Lisps, we must provide several types of unquotes (`u`, `n`, `a`), because
Python has a surface syntax, instead of representing source code directly as a
lightly dressed up AST, like Lisps do.


## Differences to MacroPy

Our implementation of the quasiquote system closely follows the impressive,
pioneering work that originally appeared in MacroPy. That source code, itself
quite short, is full of creative ingenuity, although at places could be written
more clearly, due to the first-generation nature of the system.

Since `mcpyrate` is a third-generation system, we have actively attempted to
make the best of lessons learned, to make the implementation as short and simple
as reasonably possible. We have liberally changed function and class names where
this makes the code easier to understand.

Our `h` operator is both simpler and more general than MacroPy's `hq[]`.
By using uuids in the lookup keys, we avoid the whole-file lexical scan.

We don't need to inject any additional imports. This makes the quasiquote system
fully orthogonal to the rest of `mcpyrate`. (Well, almost; it uses
`mcpyrate.core.global_bindings`. Still, although that was created for the use case
of supporting `h[]` on macro names, in principle it's a generic core feature.)

Because `mcpyrate` transforms `from module import macros, ...` (after collecting
macro definitions) into `import module`, we can just refer to our internal stuff
(including the stdlib `ast` module) as attributes of the module
`mcpyrate.quotes`. We feel this is the "better way" that source code comments in
MacroPy's `quotes.py` suggested must surely exist.

We allow capturing the value of any expr, not just identifiers. However, we also
take a somewhat different approach, in that we don't even pretend to capture
names; our `h[]` is an *unquote* operator that captures *values*, not a *quote*
operator that walks the tree and changes names.
