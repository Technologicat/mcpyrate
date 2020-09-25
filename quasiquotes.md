# Quasiquotes

Build ASTs in your macros, using syntax that mostly looks like regular code.

```python
    from mcpy.quotes import macros, q, a
    
    def delay(tree, **kw):
        '''delay[expr] -> promise'''
        return q[lambda: a[tree]] 

    def force(promise):
        '''force(promise) -> value'''
        return promise()
```


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
   be any run-time value.

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

   With this, you can compute a name (e.g. by `mcpy.gensym`) and then use it as
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
parameter in the AST that was returned by the quasiquote operation.

You'll still need to keep [Green Tree
Snakes](https://greentreesnakes.readthedocs.io/en/latest/nodes.html) and maybe
also the [ast](https://docs.python.org/3/library/ast.html) documentation handy,
but usually not much manually written AST-generating code is needed when
quasiquotes automate most of it. This makes macro code much more readable.

By default, quasiquoting in `mcpy` is classical, i.e. non-hygienic. If you're
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


#### gensym

Short for *generate symbol*, `gensym` provides fresh, unused identifiers.

When your macro needs to generate code that establishes new bindings, see
`mcpy.gensym()`, and use `n[]` (and old-fashioned AST edits where needed)
judiciously.


#### Macro hygiene

*Macro hygiene* refers to preserving the meaning of an identifier, from the
macro definition site, to the macro use site. This is a highly desirable
feature, and `mcpy` supports it via an explicit opt-in construct, which
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
(hygienic-unquote) operator inside a `q[]`. Each unique hygienic-unquoted value,
in the sense of `id`, is stored exactly once, regardless of how many times it is
`h[]`'d across the codebase.

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

So if you have an object or an array, you might want to `h[]` just the thing
itself, and perform any attribute or subscript accesses on the result:

    q[h[cat].wantsfood]
    q[h[shoppinglist][0]]

This way, any later modifications to the state of `cat`, or to the contents of
`shoppinglist`, will be seen by the code that uses the hygienically unquoted
value.


#### Advanced uses of non-hygienic quasiquoting

Macro hygiene has its place, but non-hygienic quoting leads to two advanced
techniques that are sometimes useful:

  - *Anaphora*. The macro defines an identifier that has a specific name.

    Typically, the macro computes some value and binds it to that identifier.
    That value is then intended to be referred to, by that name, at the macro
    use site. For example, the `it` in the classic *anaphoric if*.

    This is sometimes so useful that also Lisps that have a macro system that
    is hygienic by default (such as Scheme and Racket), provide a way to
    selectively *break hygiene*.

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


## Technical notes

Various technical points about the quasiquote system.


### Difference between `h[]` and `u[]`

The `h[]` operator accepts any run-time value, including those that have no
meaningful `repr`, such as function objects. By internally using a dictionary to
store the captured values, it carries those values from macro expansion time to
run time.

The expansion result of `h[]` is actually a capture command that executes when
the use site of the surrounding `q[]` does, rewriting itself into a lookup
command at that time. The use site of `q[]` then sees just that lookup command.

The `u[]` operator operates statically, purely at macro expansion time. It takes
the value apart, and writes an AST that will re-construct it. It only works for
expressions that evaluate to constants, to built-in containers containing
constants, or to trees of such containers, where all leaves are constants.


## Memory usage of the hygienic capture system

The hygienic capture occurs anew each time `q[]` expands (inside your macro
definition). So for each `h[]` in a macro definition, a capture operation will
execute for each *invocation* of the macro. It must work like this in order to
always capture the right thing.

However, only unique values, determined by their `id()`, are stored in the
hygienic capture registry. Capturing the same value again just transforms
into a lookup using the key for the already existing value.

Currently, these captures are never deleted, so this potentially produces a
memory leak; but a mild one that depends only on lexical properties of the
codebase that uses macros.

The memory required for the hygienic captures is proportional to the number of
times `h[]` occurs in each macro definition, times the number of invocations of
that macro in the target codebase, summed over all macros invoked by the target
codebase. Furthermore, each item is only a string key, paired with an object
reference, so that in itself doesn't take much memory.

Another question is how much memory the object itself takes, since it'll never
become unreachable. But the most common use case of hygienic unquoting is to
safely refer to a top-level function imported at the macro definition site, so
it's usually just a top-level function object. These aren't typically that
large.

Critically, the memory usage does not depend on how many times the final
expanded code is called. The expanded code contains only lookups, no captures.

So in a majority of realistic use cases, not deleting the captures is just fine.

One exception is a long-lived REPL session involving many reloads of macro
definitions (to test interactively in an agile way, while developing macros). In
such a use case, if those macros use `q[h[]]`, the memory usage of the capture
registry will grow at each reload (as the uses of `h[]` get expanded).


## For Common Lispers

The `mcpy` equivalent of the Common Lisp macro-implementation pattern, where one
gensyms a new name, `let`-binds that to the current value of the old name, and
then unquotes the new name in the quasiquoted code, looks like this:

    hygx = q[h[x]]
    tree = q[...a[hygx]...]

The implementation details differ a bit, but such a uniqifying bind is
essentially what `h[]` does.

It's allowed, but not necessary to write it like this; you can also `h[x]` the
same thing multiple times, since only unique values result in a new entry in the
capture registry.


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


## mcpy vs. MacroPy

Our implementation of the quasiquote system closely follows the impressive,
pioneering work that originally appeared in MacroPy. That source code, itself
quite short, is full of creative ingenuity, at places muddled by the first-gen
nature of the system.

Since `mcpy` is a second-gen system, we have actively attempted to make the best
of lessons learned, to make the implementation as short and simple as reasonably
possible. We have liberally changed function and class names where this makes
the code easier to understand.

Our `h` operator is both simpler and more general than MacroPy's `hq[]`. We
avoid pickling/unpickling, and by using uuids in the lookup keys, we also avoid
the whole-file lexical scan.

We don't need to inject any additional imports. This makes the quasiquote system
fully orthogonal to the rest of `mcpy`. Because `mcpy` transforms `from module
import macros, ...` (after collecting macro definitions) into `import module`,
we can just refer to our internal stuff (including the stdlib `ast` module) as
attributes of the module `mcpy.quotes`. We feel this is the "better way" that
source code comments in MacroPy's `quotes.py` suggested must surely exist.

We allow capturing the value of any expr, not just identifiers. However, we also
take a somewhat different approach, in that we don't even pretend to capture
names; our `h[]` is an *unquote* operator that captures *values*, not a *quote*
operator that walks the tree and changes names.
