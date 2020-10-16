# mcpyrate

Advanced, third-generation macro expander for Python, after the pioneering [macropy](https://github.com/lihaoyi/macropy), and the compact, pythonic [mcpy](https://github.com/delapuente/mcpy). The emphasis is on correctness, feature-completeness for serious macro-enabled work, and simplicity, in that order.

Builds on `mcpy`, with a similar explicit and compact approach, but with a lot of new features - including some excellent ideas from MacroPy. Finally, we provide integrated equivalents of [`imacropy`](https://github.com/Technologicat/imacropy) and [`pydialect`](https://github.com/Technologicat/pydialect).

Supports Python 3.6, 3.7, 3.8, and PyPy3.

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [mcpyrate](#mcpyrate)
    - [Highlights](#highlights)
    - [Install & uninstall](#install--uninstall)
    - [Using macros](#using-macros)
        - [Interactive use](#interactive-use)
        - [Macro invocation syntax](#macro-invocation-syntax)
        - [Importing macros](#importing-macros)
    - [Writing macros](#writing-macros)
        - [Macro invocation types](#macro-invocation-types)
        - [Quasiquotes](#quasiquotes)
            - [Differences to `macropy`](#differences-to-macropy)
        - [Get the source of an AST](#get-the-source-of-an-ast)
        - [Walk an AST](#walk-an-ast)
        - [The named parameters](#the-named-parameters)
            - [Differences to `mcpy`](#differences-to-mcpy)
        - [Macro arguments](#macro-arguments)
            - [Using parametric macros](#using-parametric-macros)
            - [Writing parametric macros](#writing-parametric-macros)
            - [Arguments or no arguments?](#arguments-or-no-arguments)
            - [Differences to `macropy`](#differences-to-macropy-1)
        - [Identifier macros](#identifier-macros)
        - [Expand macros inside-out](#expand-macros-inside-out)
    - [Debugging](#debugging)
        - [I just ran my program again and no macro expansion is happening?](#i-just-ran-my-program-again-and-no-macro-expansion-is-happening)
        - [Error in `compile`, an AST node is missing the required field `lineno`?](#error-in-compile-an-ast-node-is-missing-the-required-field-lineno)
        - [Why do my block and decorator macros generate extra do-nothing nodes?](#why-do-my-block-and-decorator-macros-generate-extra-do-nothing-nodes)
        - [`Coverage.py` says my quasiquoted code block is covered? It's quoted, not running, so why?](#coveragepy-says-my-quasiquoted-code-block-is-covered-its-quoted-not-running-so-why)
        - [My line numbers aren't monotonically increasing, why is that?](#my-line-numbers-arent-monotonically-increasing-why-is-that)
    - [Macro expansion error reporting](#macro-expansion-error-reporting)
        - [Recommended exception types](#recommended-exception-types)
        - [Differences to `macropy`](#differences-to-macropy-2)
    - [Examples](#examples)
    - [Understanding the code](#understanding-the-code)

<!-- markdown-toc end -->

## Highlights

- **Agile development**.
  - Universal bootstrapper: `macropython`. Import and use macros in your main program.
  - Interactive console: `macropython -i`. Import, define and use macros in a console session.
    - Embeddable à la `code.InteractiveConsole`. See `mcpyrate.repl.console.MacroConsole`.
  - IPython extension `mcpyrate.repl.iconsole`. Import, define and use macros in an IPython session.
- **Testing and debugging**.
  - Correct statement coverage from tools such as [`Coverage.py`](https://github.com/nedbat/coveragepy/).
  - Macro expansion errors are reported at macro expansion time, with use site traceback.
  - Debug output with a step-by-step expansion breakdown. See macro `mcpyrate.debug.step_expansion`.
  - Manual expand-once. See `expander.visit_once`; get the `expander` as a named argument of your macro.
- **Dialects, i.e. whole-module source and AST transforms**.
  - Think [Racket's](https://racket-lang.org/) `#lang`, but for Python.
  - Define languages that use Python's surface syntax, but change the semantics; or plug in a per-module transpiler that (at import time) compiles source code from some other programming language into macro-enabled Python. Also an AST [optimizer](http://compileroptimizations.com/) could be defined as a dialect. (Dialects can be chained.)
  - Sky's the limit, really. Until we get [`unpythonic`](https://github.com/Technologicat/unpythonic) ported to use `mcpyrate`, see [`pydialect`](https://github.com/Technologicat/pydialect) for old example dialects.
  - For documentation, see the docstrings in [`mcpyrate.dialects`](mcpyrate/dialects.py).
  - For debugging, `from mcpyrate.debug import dialects, StepExpansion`.
  - If writing a full-module AST transformer that splices the whole module into a template, see `mcpyrate.splicing.splice_dialect`.
- **Advanced quasiquoting**.
  - Hygienically interpolate both regular values **and macro names**.
  - Delayed macro expansion inside quasiquoted code.
    - User-controllable, see macros `expand1` and `expand` in `mcpyrate.quotes`.
    - Or just leave it to expand automatically once your macro (that uses quasiquoting) returns.
  - Inverse quasiquote operator. See function `mcpyrate.quotes.unastify`.
    - Convert a quasiquoted AST back into a direct AST, typically for further processing before re-quoting it.
      - Not an unquote; we have those too, but the purpose of unquotes is to interpolate values into quoted code. The inverse quasiquote, instead, undoes the quasiquote operation itself, after any unquotes have already been applied.
    - Useful for second-order macros that need to process quasiquoted code at macro expansion time, before the quasiquoted tree has a chance to run.
- **Macro arguments**.
  - Opt-in. Declare by using the `@parametricmacro` decorator on your macro function.
  - Use brackets to invoke, e.g. `macroname[arg0, ...][expr]`. If no args, just leave that part out, e.g. `macroname[expr]`.
  - The `macroname[arg0, ...]` syntax works in `expr`, `block` and `decorator` macro invocations in place of a bare `macroname`.
  - The named parameter `args` is a raw `list` of the macro argument ASTs. Empty if no args were sent, or if the macro function is not parametric.
- **Identifier (a.k.a. name) macros**.
  - Can be used for creating magic variables that may only appear inside specific macro invocations.
  - Opt-in. Declare by using the `@namemacro` decorator on your macro function.
- **Bytecode caching**.
  - `.pyc` bytecode caches are created and kept up-to-date. This saves the macro
    expansion cost at startup for modules that have not changed.

    Beside a `.py` source file itself, we look at any macro definition files
    the source file imports macros from, recursively, in a `make`-like fashion.

    The mtime is the latest of those of the source file and its macro-dependencies,
    considered recursively, so that if any macro definition anywhere in the
    macro-dependency tree of a source file is changed, Python will treat that
    source file as "changed", thus re-expanding and recompiling it (hence,
    updating the corresponding `.pyc`).
  - **CAUTION**: [PEP 552 - Deterministic pycs](https://www.python.org/dev/peps/pep-0552/) is not supported; we support only the default *mtime* invalidation mode, at least for now.
- **Conveniences**.
  - Relative macro-imports (for code in packages), e.g. `from .other import macros, kittify`.
  - The expander automatically fixes missing `ctx` attributes (and source locations) in the AST, so you don't need to care about those in your macros.
  - Several block macros can be invoked in the same `with` (equivalent to nesting them, with leftmost outermost).
  - Walker à la `macropy`, to easily context-manage state for subtrees, and collect items across the whole walk.
  - AST markers (pseudo-nodes) for communication in a set of co-operating macros (and with the expander).
  - `gensym` to create a fresh, unused lexical identifier.
  - `unparse` to convert an AST to the corresponding source code.
  - `dump` to look at an AST representation directly, with (mostly) PEP8-compliant indentation.


## Install & uninstall

PyPI package will follow later. For now, install from source:

```bash
python -m setup install
```

possibly with `--user`, if your OS is a *nix, and you feel lucky enough to use the system Python. If not, activate your venv first; the `--user` flag is then not needed.

To uninstall:

```bash
pip uninstall mcpyrate
```

but first, make sure you're not in a folder that has an `mcpyrate` subfolder - `pip` will think it got a folder name instead of a package name, and become confused.


## Using macros

Just like earlier macro expanders for Python, `mcpyrate` must be explicitly enabled before importing any module that uses macros. Macros must be defined in a separate module.

The following classical 3-file setup works fine:

```python
# run.py
import mcpyrate.activate
import application

# mymacros.py with your macro definitions
def echo(expr, **kw):
    print('Echo')
    return expr

# application.py 
from mymacros import macros, echo
echo[6 * 7]
```

To run, `python -m run`.

In `mcpyrate`, the wrapper `run.py` is optional. The following 2-file setup works fine, too:

```python
# mymacros.py with your macro definitions
def echo(expr, **kw):
    print('Echo')
    return expr

# application.py
from mymacros import macros, echo
echo[6 * 7]
```

To run, `macropython -m application`.

This will import `application`, making that module believe it's `__main__`. In a sense, it really is: if you look at `sys.modules["__main__"]`, you'll find the `application` module. The conditional main idiom works, too.

`macropython` is installed as a [console script](https://python-packaging.readthedocs.io/en/latest/command-line-scripts.html#the-console-scripts-entry-point). Thus it will use the `python` interpreter that is currently active according to `/usr/bin/env`. So if you e.g. set up a venv with PyPy3 and activate the venv, `macropython` will use that.


### Interactive use

[[full documentation](repl.md)]

For interactive macro-enabled sessions, we provide an macro-enabled equivalent for `code.InteractiveConsole` (also available from the shell, as `macropython -i`), as well as an IPython extension.


### Macro invocation syntax

`mcpyrate` macros can be used in **four** forms:

```python
# block form
with macro:
    ...

# expression form
macro[...]

# decorator form
@macro
...

# identifier form
macro
```

In the first three forms, the macro will receive the `...` part as input. An identifier macro will receive the `Name` AST node itself.

The expander will replace the macro invocation with the expanded content. By default, expansion occurs first for outermost nodes, i.e, from outside to inside. However, each macro can control whether it expands before or after any nested macro invocations.


### Importing macros

Just like in `mcpy`, in `mcpyrate` macros are just functions. To use functions from `module` as macros, use a *macro-import statement*:

```python
from module import macros, ...
```

replacing `...` with the macros you want to use. Importing all via `*` won't work. You must declare the macros you want explicitly. This syntax tells the macro expander to register macro bindings. The macro bindings are in scope for the module in which the macro-import statement appears.

All macro-import statements must appear at the top level of a module.

`mcpyrate` prevents you from accidentally using macros as regular functions in your code by transforming the macro-import into:

```python
import module
```

Even if the original macro-import was relative, the transformed import is always resolved to an absolute one, based on `sys.path`, like Python itself does. If the import cannot be resolved, it is a macro-expansion-time error. (Not just because of this; the import must resolve successfully, so that the expander can find the macro functions.)

This macro-import transformation is part of the public API. If the expanded form of your macro needs to refer to `thing` that exists in (whether is defined in, or has been imported to) the global, top-level scope of the module where the macro definition lives, you can just refer to `module.thing` in your expanded code. This is the `mcpyrate` equivalent of `macropy`'s `unhygienic_expose` mechanism.

If your expansion needs to refer to some other value from the macro definition site (including local and nonlocal variables, and imported macros), see [the quasiquote system](quasiquotes.md), specifically the `h[]` (hygienic-unquote) operator.

If you want to use some of your macros as regular functions, simply use:

```python
from module import ...
```

Or, noting the above guarantee, use fully qualified names for them:

```python
module.macroname
```

If the name of a macro conflicts with a name you can provide an alias for the macro:

```python
from module import macros, macroname as alias
```

This will register the macro binding under the name `alias`.

Note this implies that, when writing your own macros, if one of them needs to analyze whether the tree it's expanding is going to invoke specific other macros, then in `expander.bindings`, you **must look at the values** (whether they are the function objects you expect), not at the names (since names can be aliased to anything at the use site).


## Writing macros

No special imports are needed to write your own macros. Just consider a macro as a function accepting an AST `tree` and returning another AST (i.e., the macro function is a [syntax transformer](http://www.greghendershott.com/fear-of-macros/)).

```python
def macro(tree, **kw):
    """[syntax, expr] Example macro."""
    return tree
```

Refer to [Green Tree Snakes](https://greentreesnakes.readthedocs.io/en/latest/nodes.html) (a.k.a. the missing Python AST docs) for details on the AST node types. The documentation for the [AST module](https://docs.python.org/3/library/ast.html) may also be occasionally useful.

The `tree` parameter is the only positional parameter the macro function is called with. All other parameters are passed by name, so you can easily pick what you need (and let `**kw` gather the ones you don't).

Beside returning an AST, you can return `None` to remove the `tree` you got in (provided that deleting it is syntactically valid), or return a list of `AST` nodes (if in a position where that is syntactically admissible; so `block` and `decorator` macros only). The result of the macro expansion is recursively expanded until no new macro invocations are found.

The only explicit hint at the definition site that a function is actually a macro is the `**kw`. To be more explicit, mention it at the start of the docstring, such as above. (We recommend the terminology used in [The Racket Reference](https://docs.racket-lang.org/reference/): a macro is *a syntax*, as opposed to *a procedure* a.k.a. garden variety function.)

Although you don't strictly have to import anything to write macros, there are some useful functions in the top-level namespace of `mcpyrate`. See `gensym`, `unparse`, `dump`, `@namemacro`, and `@parametricmacro`.

Other modules contain utilities for writing macros:

 - [`mcpyrate.quotes`](mcpyrate/quotes.py) provides [quasiquote syntax](quasiquotes.md) as macros, to easily build ASTs in your macros.
 - [`mcpyrate.utils`](mcpyrate/utils.py) provides some macro-writing utilities that are too specific to warrant a spot in the top-level namespace; of these, at least `rename` and `flatten_suite` solve problems that come up relatively often.
 - [`mcpyrate.walker`](mcpyrate/walker.py) provides an AST walker that can context-manage its state for different subtrees, while optionally collecting items across the whole walk. It's an `ast.NodeTransformer`, but with functionality equivalent to `macropy.core.walkers.Walker`.
 - [`mcpyrate.splicing`](mcpyrate/splicing.py) helps splice a list of statements into a code template. This is especially convenient when the template is written in the quasiquoted notation; there's no need to think about how the template looks like as an AST in order to paste statements into it.
 - [`mcpyrate.debug`](mcpyrate/debug.py) may be useful if something in your macro is not working.

Any missing source locations and `ctx` fields are fixed automatically in a postprocessing step, so you don't need to care about those when writing your AST.

The recommendation is, **do not fill in source location information manually**, because if it is missing, this allows the expander to auto-fill it for any macro-generated nodes. If auto-filled, those nodes will have the source location of the macro invocation node. This makes it easy to pinpoint in debug output (e.g. for a block macro) which lines originate in the unexpanded source code and which were added by the macro invocation.

Simple example:

```python
from ast import *
from mcpyrate import unparse
def log(expr, **kw):
    '''[syntax, expr] Replace log[expr] with print('expr: ', expr)'''
    label = unparse(expr) + ': '
    return Call(func=Name(id='print', ctx=Load()),
                args=[Str(s=label), expr], keywords=[])
```


### Macro invocation types

A macro can be called in four different ways. The macro function acts as a dispatcher for all of them.

The way the macro was called, i.e. the *invocation type*, is recorded in the `syntax` named parameter, which can have the values `'expr'`, `'block'`, `'decorator'`, or `'name'`. With this, you can distinguish the syntax used in the invocation, and provide a different implementation for each one (or `raise SyntaxError` on those your macro is not interested in).

When valid macro invocation syntax for one of the other three types is detected, the name part is skipped, and it **does not** get called as an identifier macro. The identifier macro mechanism is invoked only for appearances of the name *in contexts that are not other types of macro invocations*.

Furthermore, identifier macros are an opt-in feature. The value of the `syntax` parameter can be `name` only if the macro function is declared as a `@namemacro`. The decorator must be placed outermost (along with `@parametricmacro`, if that is also used).

Notes on each invocation type:

- If `syntax == 'expr'`, then `tree` is a single AST node.

- If `syntax == 'block'`, then `tree` is always a `list` of AST nodes. If several block macros appear in the same `with`, they are popped one by one, left-to-right; the `with` goes away when (if) all its context managers have been popped. As long as the `with` is there, it appears as the only top-level statement in the list `tree`. The macro may return a `list` of AST nodes.

- If `syntax == 'decorator'`, then `tree` is the decorated node itself. If several decorator macros decorate the same node, they are popped one by one, innermost-to-outermost (same processing order as in regular decorators). The macro may return a `list` of AST nodes.

- If `syntax == 'name'`, then `tree` is the `Name` node itself.


### Quasiquotes

[[full documentation](quasiquotes.md)]

We provide a [quasiquote system](https://en.wikipedia.org/wiki/Lisp_(programming_language)#Self-evaluating_forms_and_quoting) (both classical and hygienic) to make macro code both much more readable and simpler to write. Rewriting the above example, note the `ast` import is gone:

```python
from mcpyrate import unparse
from mcpyrate.quotes import macros, q, u, a

def log(expr, **kw):
    '''[syntax, expr] Replace log[expr] with print('expr: ', expr)'''
    label = unparse(expr) + ': '
    return q[print(u[label], a[expr])]
```

Here `q[]` quasiquotes an expression, `u[]` unquotes a simple value, and `a[]` unquotes an expression AST. If you're worried that `print` may refer to something else at the use site of `log[]`, you can hygienically unquote the function name with `h[]`: `q[h[print](u[label], a[expr])]`.

#### Differences to `macropy`

By default, in `mcpyrate`, macros in quasiquoted code are not expanded when the quasiquote itself expands. We provide macros to perform expansion in quoted code, to give you control. See `mcpyrate.quotes.expand` and `mcpyrate.quotes.expand1`.

In `mcpyrate`, there is **just one *quote* operator**, `q[]`, although just like in `macropy`, there are several different *unquote* operators, depending on what you want to do.

For [macro hygiene](https://en.wikipedia.org/wiki/Hygienic_macro), we provide a **hygienic unquote** operator, `h[]`. So instead of implicitly hygienifying all `Name` nodes inside a `hq[]` like `macropy` does, `mcpyrate` instead expects the user to use the regular `q[]`, and explicitly say which subexpressions to hygienify, by unquoting each of those separately with `h[]`.

In `mcpyrate`, also macro names can be unquoted hygienically. Doing this registers a macro binding, with a uniqified name, into a global table for the current process. This allows the expanded code of your macro to hygienically invoke a macro imported to your macro definition site (and leave that invocation unexpanded, for the expander to handle later), without requiring the use site of your macro to import that macro.


### Get the source of an AST

`mcpyrate.unparse` is a function that converts an AST back into Python source code.

Because the code is backconverted from the AST representation, the result may differ in minute details of surface syntax, such as parenthesization, whitespace, and the exact source code representation of string literals.


### Walk an AST

To bridge the feature gap between [`ast.NodeTransformer`](https://docs.python.org/3/library/ast.html#ast.NodeTransformer) and `macropy`'s `Walker`, we provide [`mcpyrate.walker.Walker`](walker.md), a zen-minimalistic AST walker base class based on `ast.NodeTransformer`, that can context-manage its state for different subtrees, while optionally collecting items across the whole walk.


### The named parameters

Full list as of v3.0.0, in alphabetical order:

 - `args`: macro argument ASTs, if the invocation provided any. If not, `args = []`.
   - A macro function only accepts macro arguments if declared `@parametricmacro`. For non-parametric macros (default), `args=[]`.
 - `expander`: the macro expander instance.
   - To expand macro invocations inside the current one, use `expander.visit(tree)`, or in special use cases (when you know why), `expander.visit_recursively(tree)` or `expander.visit_once(tree)`.
   - Also potentially useful are `expander.bindings` and `expander.filename`.
   - See [`mcpyrate.core.BaseMacroExpander`](mcpyrate/core.py) and [`mcpyrate.expander.MacroExpander`](mcpyrate/expander.py) for the expander API; it's just a few methods and attributes.
- `invocation`: the whole macro invocation AST node as-is, not only `tree`. For introspection.
   - Very rarely needed; if you need it, you'll know.
   - **CAUTION**: not a copy, or at most a shallow copy.
 - `optional_vars`: only exists when `syntax='block'`. The *as-part* of the `with` statement. (So use it as `kw['optional_vars']`.)
 - `syntax`: invocation type. One of `expr`, `block`, `decorator`, `name`.
   - Can be `name` only if the macro function is declared `@namemacro`.

#### Differences to `mcpy`

No named parameter `to_source`. Use the function `mcpyrate.unparse`.

No named parameter `expand_macros`. Use the named parameter `expander`, which grants access to the macro expander instance. Call `expander.visit(tree)`.

The named parameters `args` and `invocation` are new.

The fourth `syntax` invocation type `name` is new.


### Macro arguments

To accept arguments, the macro function must be declared parametric.

#### Using parametric macros

Macro arguments are sent by calling `macroname` with bracket syntax:

```python
macroname[arg0, ...][...]

with macroname[arg0, ...]:
    ...

@macroname[arg0, ...]
...
```

For simplicity, macro arguments are always positional. `name` macro invocations do not take macro arguments.

To invoke a parametric macro with no arguments, just use it like a regular, non-parametric macro:

```python
macroname[...]

with macroname:
    ...

@macroname
...
```

Observe that the syntax `macroname[a][b]` may mean one of **two different things**:

  - If `macroname` is parametric, a macro invocation with `args=[a]`, `tree=b`.

  - If `macroname` is **not** parametric, first a macro invocation with `tree=a`,
    followed by a subscript operation on the result.

    Whether that subscript operation is applied at macro expansion time
    or at run time, depends on whether `macroname[a]` returns an AST for
    a `result`, for which `result[b]` can be interpreted as an invocation
    of a macro that is bound in the use site's macro expander. (This is
    exploited by the hygienic unquote operator `h`, when it is applied
    to a macro name. The trick is `h` takes no macro arguments.)


#### Writing parametric macros

To declare a macro parametric, use the `@parametricmacro` decorator on your macro function. Place it outermost (along with `@namemacro`, if used too).

The parametric macro function receives macro arguments as the `args` named parameter. It is a raw `list` of the ASTs `arg0` and so on. If the macro was invoked without macro arguments, `args` is an empty list.

Macro invocations inside the macro arguments **are not automatically expanded**. If those ASTs end up in the macro output, they are expanded after the primary macro invocation itself (as part of the default outside-in processing); but if not, they are not expanded at all. To expand them, use `expander.visit(args)` in your macro implementation.


#### Arguments or no arguments?

Macro arguments are a rarely needed feature. Often, instead of taking macro arguments, you can just require `tree` to have a specific layout instead.

For example, a *let* macro invoked as `let[x << 1, y << 2][...]` could alternatively be designed to be invoked as `let[[x << 1, y << 2] in ...]`. But if this `let` example should work also as a decorator, then macro arguments are the obvious, uniform syntax, because then you can allow also `with let[x << 1, y << 2]:` and `@let[x << 1, y << 2]`.


#### Differences to `macropy`

In `mcpyrate`, macro arguments are passed using brackets, e.g. `macroname[arg0, ...][expr]`. This syntax looks macro-like, as well as makes it explicit that macro arguments are positional-only.

In `mcpyrate`, macros must explicitly opt in to accept arguments. This makes it easier to implement macros that don't need arguments (which is a majority of all macros), since then you don't need to worry about `args` (it's guaranteed to be empty).


### Identifier macros

To be eligible to be called as an identifier macro, a macro must be declared as
an identifier macro. Declare by using the `@namemacro` decorator on your macro
function. Place it outermost (along with `@parametricmacro`, if used too).

Identifier macro invocations do not take macro arguments. So when a macro
function is invoked as an identifier macro, `args=[]`. The `tree` will be the
`Name` node itself.

Note it is valid for the same macro function to be invoked with one of the other
macro invocation types; in such contexts, it can take macro arguments if
declared (also) as `@parametricmacro`.

To tell the expander to go ahead and use the original name as a regular run-time
name, you can `return tree` without modifying it. This is useful when the
identifier macro is needed only for its side effects, such as validating its use
site.

Of course, if you want something else, you can return any tree you want to
replace the original with - after all, an identifier macro is just a macro,
and an identifier is just a special kind of expression.

Identifier macros are a rarely used feature, but one that is indispensable for
that rare use case. The reason this feature exists is to allow creating magic
variables that may appear only in certain contexts. Here's the pattern:

```python
from mcpyrate import namemacro
from mcpyrate.utils import NestingLevelTracker

_mymacro_level = NestingLevelTracker()

def mymacro(tree, *, syntax, expander, **kw):
    """[syntax, expr] The construct where the magic variable `it` may appear."""
    if syntax != "expr":
        raise SyntaxError("`mymacro` is an expr macro only")
    with _mymacro_level.changed_by(+1):
        tree = expander.visit(tree)  # this expands any `it` inside
        # Macro code goes here. You'll want it to define an actual
        # run-time `it` for the invocation site to refer to.
        # (But first check from `expander.bindings` what name
        #  the `it` macro function is actually bound to!)
    return tree

@namemacro
def it(tree, *, syntax, **kw):
    """[syntax, name] The `it` that may appear inside a `mymacro[]`."""
    if syntax != "name":
        raise SyntaxError("`it` is a name macro only")
    if _mymacro_level.value < 1:
        raise SyntaxError("`it` may only appear within a `mymacro[...]`")
    return tree
```

This way any invalid, stray mentions of the magic variable `it` trigger an error at macro expansion time. (It's not quite [`syntax-parameterize`](https://docs.racket-lang.org/reference/stxparam.html), but it'll do for Python.)

If you want to expand only `it` inside an invocation of `mymacro[...]` (thus checking that the mentions are valid), leaving other nested macro invocations untouched, that's also possible. See below how to temporarily run a second expander with different bindings (from which you can omit everything but `it`).


### Expand macros inside-out

Use the named parameter `expander` to access the macro expander. This is useful for making inner macro invocations expand first.

To expand macros in `tree`, use `expander.visit(tree)`. Any code in your macro that runs before the `visit` behaves outside-in, any code after it behaves inside-out. If there's no explicit `visit` in your macro definition, the default behavior is outside-in.

The `visit` method uses the expander's current setting for recursive mode, which is almost always The Right Thing to do. The default mode is recursive, i.e. expand again in the result until no macros remain.

(Strictly speaking, the default outside-in behavior arises because the actual default, after a macro invocation has been expanded once (i.e. just after the macro function has returned), is to loop the expander on the output until no macro invocations remain. Even more strictly, we use a functional loop, which is represented as a recursion instead of a `while`. Hence the name *recursive mode*.)

If you want to expand until no macros remain (even when inside the dynamic extent of an expand-once - this is only recommended if you know why you want to do it), use `expander.visit_recursively(tree)` instead.

If you want to expand only one layer of macro invocations (even when inside the dynamic extent of an expand-until-no-macros-remain), use `expander.visit_once(tree)`. This can be useful during debugging of a macro implementation. You can then convert the result into a printable form using `mcpyrate.unparse` or `mcpyrate.dump`.

If you need to temporarily expand one layer, but let the expander continue expanding your AST later (when your macro returns), observe that `visit_once` will return a `Done` AST marker, which is the thing whose sole purpose is to tell the expander not to expand further in that subtree. It is a wrapper with the actual AST stored in its `body` attribute. So if you need to ignore the `Done`, you can grab the actual AST from there, and discard the wrapper.

If you need to temporarily run a second expander with different macro bindings, consult `expander.bindings` to grab the macro functions you need.  Note you **must look at the values** (whether they are the function objects you expect), not at the names (since names can be aliased to anything at the use site - and that very use site also gives you the `tree`). Then, add the import `from mcpyrate.expander import expand_macros`, and in your macro, use `expand_macros(tree, modified_bindings, expander.filename)` to invoke a new expander with the modified bindings. The implementation of the quasiquote system has an example.

Currently, there is no single call to expand only one layer of macros using a second expander. But if you need to do that, look at how `expand_macros` is implemented (it's just two lines), and adapt that.


## Debugging

To troubleshoot your macros, see [`mcpyrate.debug`](mcpyrate/debug.py), particularly the macro `step_expansion`. It is both an `expr` and `block` macro.


### I just ran my program again and no macro expansion is happening?

This is normal. The behavior is due to bytecode caching (`.pyc` files). When `mcpyrate` processes a source file, it will run the expander only if that file, or the source file of at least one of its macro-dependencies, has changed on disk. This is detected from the *mtime* (modification time) of the source files. The macro-dependencies are automatically considered recursively in a `make`-like fashion.

Even if you use [`sys.dont_write_bytecode = True`](https://docs.python.org/3/library/sys.html#sys.dont_write_bytecode) or the environment variable [`PYTHONDONTWRITEBYTECODE=1`](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONDONTWRITEBYTECODE), Python will still **use** existing `.pyc` files if they are up to date.

If you want to force all of your code to be macro-expanded again, delete your bytecode cache (`.pyc`) files; they'll be re-generated automatically. Typically, they can be found in a folder named `__pycache__`, at each level of your source tree.

Normally there is no need to delete bytecode caches manually.

However, there is an edge case. If you hygienically unquote a value that was imported (to the macro definition site) from another module, and that other module is not a macro-dependency, then - if the class definition of the hygienically stored value changes on disk, that is not detected.

This can be a problem, because hygienic value storage uses `pickle`, which in order to unpickle the value, expects to be able to load the original (or at least a data-compatible) class definition from the same place where it was defined when the value was pickled. If this happens, then delete the bytecode cache (`.pyc`) files, and the program should work again once the macros re-expand.


### Error in `compile`, an AST node is missing the required field `lineno`?

Welcome to the club. It is likely the actual error is something else, because the expander automatically fills in missing source location information.

The misleading error message is due to an unfortunate lack of input validation in Python's compiler, because Python wasn't designed for an environment where AST editing is part of the daily programming experience.

The first thing to check is that your macro is really placing AST nodes where the compiler expects those, instead of accidentally using bare values.

If you edit ASTs manually, check that you're really using a `list` where the [AST docs at Green Tree Snakes](https://greentreesnakes.readthedocs.io/en/latest/nodes.html) say *"a list of ..."*, and not a `tuple`. Also note statement suites are represented as a bare `list`, and **not** as an `ast.List`.

If you use quasiquotes, check that you're using the unquote operators you intended. It's easy to accidentally put an `u[]` or `h[]` in place of an `a[]`, or vice versa.

Finally, it goes without saying, but use `git diff` liberally. Most likely whatever the issue is, it's something in the latest changes.


### Why do my block and decorator macros generate extra do-nothing nodes?

This is normal. It allows coverage analysis tools such as `Coverage.py` to report correct coverage for macro-enabled code.

We assign the line number from the macro invocation itself to any new AST nodes (that do not have a source location explicitly set manually) generated by a macro. This covers most use cases. But it's also legal for a block or decorator macro to just edit existing AST nodes, without adding any new ones.

The macro invocation itself is compiled away by the macro expander, so to guarantee that the invocation shows as covered, it must (upon successful macro expansion) be replaced by some other AST node that actually runs at run-time, with source location information taken from the invocation node, for the coverage analyzer to pick up.

For this, we use an assignment to a variable `_mcpyrate_coverage`, with a human-readable string as the value. We can't use an `ast.Pass` or a do-nothing `ast.Expr`, since CPython optimizes those away when it compiles the AST into bytecode.


### `Coverage.py` says my quasiquoted code block is covered? It's quoted, not running, so why?

When a `with q as quoted` block is expanded, it becomes an assignment to the variable `quoted` (or whatever name you gave it), setting the value of that variable to a `list` of the quoted representation of the code inside the block. Each statement that is lexically inside the block becomes an item in the list.

Consider the *definition site* of your macro function that uses `q`. In a quasiquoted block, having coverage means that the output of `q` contains code from each line reported as covered. **It says nothing about the run-time behavior of that code.**

Now consider the *use site* of your macro. It's not possible to see the run-time coverage of the code that originates from the quoted block (inside your macro), for two reasons:

 1. There are usually multiple use sites, because each invocation of your macro is a use site - that's the whole point of defining a macro.
 2. The quoted code does not belong to the final use site's source file, so looking at its unexpanded source (which is what coverage tools report against), those lines simply aren't there.

Note these are fundamental facts of macro-enabled code; it doesn't matter whether quasiquotes were used to construct the AST. Seeing the run-time coverage would require saving the expanded source code (not only expanded bytecode) to disk, and a coverage analyzer that knows about the macro expansion process.

Also, there's the technical obstacle that in Python, an AST node can only have one source location, and has no *filename* attribute that could be used to indicate which source file it came from. In the presence of macros, the assumptions underlying that design no longer hold.

With coverage analysis of regular functions, there is no such problem, because any activation of a function can be thought of as happening at its definition site (equipped with a stack frame for bookkeeping). With macros, the same does not hold; the code is pasted independently to each use site, and that's where it runs.


### My line numbers aren't monotonically increasing, why is that?

This is normal. In macro-enabled code, when looking at the expanded output (such as shown by `step_expansion`), the line numbers stored in the AST - which refer to the original, unexpanded source code - aren't necessarily monotonic.

Any AST node that existed in the unexpanded source code will, in the expanded code, refer to its original line number in the unexpanded code, whereas (as mentioned above) any macro-generated node will refer to the line of the macro invocation that produced it.

Hence, non-monotonicity occurs if a block (or decorator) macro adds new AST nodes *after* existing AST nodes that originate from lines below the macro invocation node itself in the unexpanded source file.

(Note that the non-monotonicity, when present at all, is mild; it's local to each block.)


## Macro expansion error reporting

In `mcpyrate`, any exception raised during macro expansion is reported immediately at macro expansion time, and the program exits.

The error report includes two source locations: the macro use site (which was being expanded, not running yet), and the macro code that raised the exception (that was running and was terminated due to the exception).

The use site source location is reported in a chained exception (`raise from`), so if the second stack trace is long, scroll back in your terminal to see the original exception that was raised by the macro (including a traceback of where it occurred in the macro code).


### Recommended exception types

We recommend raising:

 - `SyntaxError` with a descriptive message, if there's something wrong with how the macro was invoked, or with the AST layout of the `tree` (or `args`) it got vs. what it was expecting.
 - `TypeError` or a `ValueError`, as appropriate if there is a problem in the macro arguments meant for the macro itself. (As opposed to macro arguments such as in the `let` example, where it's just another place to send in an AST to be transformed.)


### Differences to `macropy`

In `mcpyrate`, `AssertionError` is not treated specially; all exceptions get the same treatment.

In `mcpyrate`, all macro-expansion errors are reported immediately.


## Examples

`mcpyrate` is a macro expander, not a library containing macros. However, we provide a `demo` folder, to see `mcpyrate` in action. Navigate to it and run a Python console, then import `run`:

```python
import run
```


## Understanding the code

We follow the `mcpy` philosophy that macro expanders aren't rocket science. We keep things as explicit and compact as reasonably possible. However, the extra features do cost some codebase size. We also tolerate a small amount of extra complexity, if it improves the programmer [UX](https://en.wikipedia.org/wiki/User_experience).

For a clean overview of the core design, look at [mcpy](https://github.com/delapuente/mcpy), version 2.0.0. Of the parts that come from it, its `visitors` is our [`core`](mcpyrate/core.py) (the `BaseMacroExpander`), its `core` is our [`expander`](mcpyrate/expander.py) (the actual `MacroExpander`), and its `import_hooks` is our [`importer`](mcpyrate/importer.py). Its `BaseMacroExpander.ismacro` method is our `BaseMacroExpander.isbound`, because that method checks for a raw string name, not an AST structure. The rest should be clear.

Then see our [`importer`](mcpyrate/importer.py). After [`mcpyrate.activate`](mcpyrate/activate.py) has been imported, the importer becomes the top-level entry point whenever a module is imported.
