# Quasiquotes

Build ASTs in your macros, conveniently.


## Quick reference

  - `q` quasiquote, like in MacroPy.
  - `u` value-unquote, like in MacroPy.
  - `n` name-unquote, like MacroPy's `name`.
  - `a` AST-unquote, like MacroPy's `ast_literal`.
  - `h` hygienic-unquote.


## Introduction

By default, quasiquoting in `mcpy` is non-hygienic. If you're familiar with
Common Lisp's `defmacro`, you'll feel almost right at home.

Almost always:

  - If the quasiquoted code is calling a function, you'll want the function
    to be unquoted hygienically. That way, at your macro's use site, it's
    guaranteed to really call the function you expect, and not some other
    function that just happens to have the same name at the use site.

  - If your macro needs to establish any new bindings, you'll want to `gensym`
    their names, so they won't conflict with any names already in scope at the
    macro use site, no matter what names already exist there.

    See `mcpy.utilities.gensym`.


## Hygienic quasiquoting

In `mcpy`, there is no separate hygienic-quasiquote macro. Instead, use `h[]`
inside a `q[]` to mark a value you want to be unquoted hygienically.

To avoid capturing the same thing multiple times, assign the hygienically
quasiquote-unquoted identifier (which is represented as an AST that, when
compiled and run, will perform the lookup) to a variable, and then
AST-unquote that variable as many times as you need::

    hygx = q[h[x]]
    tree = q[...a[hygx]...]

This is the `mcpy` equivalent of the Common Lisp pattern, where one gensyms a
new name, `let`-binds that to the value of the old name, and then unquotes the
new name in the quasiquoted code. The implementation details differ a bit, but
such a uniqifying bind is essentially what `h[]` does.

Because it's a bind operation, the result of `h[expr]` will forever point to
the *value* `expr` had at capture time::

    x = "tabby"
    firstcat = q[h[x]]
    ...

    x = "scottishfold"

    # firstcat still points to "tabby". If you want a hygienic reference
    # to the new value, capture again:
    secondcat = q[h[x]]

    # firstcat points to "tabby", secondcat points to "scottishfold".

So if you have an object or an array, you might want to `h[]` just the thing
itself, and perform any attribute or subscript accesses on the result::

    q[h[x]]
    q[h[cat].wantsfood]
    q[h[shoppinglist][0]]

This way, modifications to the state of `obj`, or to the contents of `array`,
will be seen by the code that uses the hygienic value.


## Difference between `h[]` and `u[]`

The `h[]` operator, because it accepts any run-time value (also those
that have no meaningful repr), must bridge between macro-expansion-time
and run-time. It takes a value that exists at macro-expansion-time, and
arranges things to make that value available at run-time.

The `u[]` operator takes the value apart, and creates an AST that will
re-construct it. It does not need to bridge between the different times,
but it only works for values that, essentially, can be easily transmitted
as building instructions.


## Advanced uses of non-hygienic quasiquoting

Macro hygiene has its place, but non-hygienic quoting leads to two advanced
techniques that are sometimes useful:

  - *Anaphora*. The macro defines an identifier that has a specific name.
    Typically, the macro computes some value and binds it to that identifier,
    meant to be used at the macro's use site. For example, the `it` in the
    classic *anaphoric if*.

    This is sometimes so useful that also Lisps that have a macro system that
    is hygienic by default (such as Scheme and Racket), provide a way to
    selectively *break hygiene*.

    For example, in Racket it's possible to produce a `return` "keyword" using
    this approach, by binding the function's escape continuation to a variable
    named `return`, and then leaking that identifier on purpose.

  - *Free variable injection*, the lesser-known dual to anaphora. The term
    comes from Doug Hoyte, in Let Over Lambda: 50 Years of Lisp.

    In this technique, the *use site* is expected to define an identifier
    having a specific name, and bind some particular value to it. The macro
    assumes that name is in scope (without defining it itself) and proceeds
    to use it.

Obviously, when using either of these techniques, it is absolutely critical to
document the expectations in the macro's documentation. And, they're slightly
magic, so they are discouraged unless absolutely needed.


## Examples

Keep in mind that in `mcpy`, quasiquotes are a tool to make building macros easier.

Here *macro definition site* and *macro use site* refer to those sites for the
macro in whose implementation `q` is used to construct (part of) the output
AST.

Quasiquoted code and what it means:

    `q[x]`      --> The bare name `x`. Remains `x` at the macro use site, so it
                    really refers to whatever `x` refers to at the macro use site.

    `q[h[x]]`   --> The value of the expression `x` at the macro definition site.

                    The value that results from evaluating `x` can be any
                    run-time value.

    `q[u[x]]`   --> The value of the expression `x` at the macro definition site.

                    The value that results from evaluating `x` must be something
                    that can be easily lifted into an AST that, when compiled and run,
                    re-constructs that value.

                    Explicitly: the evaluation result must be a constant
                    (number, string, bytes, boolean or None), a container
                    (`list`, `dict` or `set`) containing such constants, or a
                    tree built out of multiple levels of such containers, where
                    all the leaves are constants.

                    In cases where that's all you need, prefer `u[]`; it's cheaper
                    on memory use than `h[]`, because it doesn't need to make an
                    entry in the hygienic capture registry.

    `q[n[x]]`   --> An identifier, with its name determined by evaluating the
                    expression `x` at the macro definition site.

                    `x` must evaluate to a string.

                    With this, you can compute a name (e.g. by `gensym`) and then
                    use it as an identifier in quasiquoted code.

    `q[a[x]]`   --> The AST stored in the variable `x` at the macro definition
                    site. Same thing as just `x` (note no `q[]`).

                    The point of `a[]` is that it can appear as a part of the
                    expression inside the `q[]`, so you can construct subtrees
                    separately (using any strategy of your choosing) and then
                    splice them into a quasiquoted code snippet.

Note that:

    `q[n["x"]]` --> Identifier with the literal name `x` at the macro use site.
                    Same as `q[x]`.

                    This is a useless use of `n[]`. The reason `n[]` exists is
                    that the argument may be a variable.

                    Using `n[]` to name-unquote a string literal does shut up
                    flake8 concerning the "undefined" name `x`, but you can
                    also `# noqa: F821` to achieve the same effect.


## Memory usage of the hygienic capture system

The hygienic capture occurs anew each time `q[]` expands (inside your macro
definition). So for each `h[]` in a macro definition, a new capture will occur
for each *invocation* of the macro. It must work like this in order to always
capture the right thing.

Only unique values, determined by their `id()`, are stored. Capturing the same
value again just transforms into a lookup using the key for the already existing
capture.

Currently, these captures are never deleted, so this potentially produces a
memory leak; but a mild one that depends only on lexical properties of the
codebase that uses macros.

The memory required for the hygienic captures is proportional to the number of
times `h[]` occurs in each macro definition, times the number of invocations of
that macro in the target codebase, summed over all macros invoked by the target
codebase. Furthermore, each item is only a string key, paired with an object
reference, so that in itself doesn't take much memory.

(Another question is how much memory that object takes, since it'll never become
unreachable; but the most common use case of hygienic quasiquoting is to safely
refer to top-level functions imported at the macro definition site, so it's
likely just a function object, and these aren't typically that large.)

Critically, the memory usage does not depend on how many times the final
expanded code is called. The expanded code contains only lookups, no captures.

In a majority of realistic use cases, not deleting the captures is just fine.

One exception is a long-lived REPL session involving many reloads of macro
definitions (to test interactively in an agile way, while developing macros); in
such a use case, if those macros use `q[h[]]`, the memory usage of the capture
registry will grow at each reload (as the uses of `h[]` get expanded).


## Note

It's a peculiarity of Python that the quasiquote system is implemented as macros;
in Lisps, these are typically special operators built in to the language core.

Also, we must provide several types of unquotes (`u`, `n`, `a`), because Python
has a surface syntax, instead of representing source code directly as a lightly
dressed up AST, like Lisps do.

Our implementation closely follows MacroPy's, except `h`, which is both
slightly simpler and more general. We don't pickle/unpickle, and by using uuids
in the keys, we avoid the need for a whole-file lexical scan. We allow capturing
any expr, not just identifiers. However, we also take a somewhat different approach,
in that we don't even pretend to capture names; our `h[]` captures *values*.
