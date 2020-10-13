# mcpyrate

Advanced, third-generation macro expander for Python, after the pioneering [macropy](https://github.com/lihaoyi/macropy), and the compact, pythonic [mcpy](https://github.com/delapuente/mcpy). Builds on `mcpy`, with a similar explicit and compact approach, but with a lot of new features.

Supports Python 3.6, 3.7, 3.8, and PyPy3.

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [mcpyrate](#mcpyrate)
    - [Highlights](#highlights)
    - [Install & uninstall](#install--uninstall)
    - [Using macros](#using-macros)
        - [REPL](#repl)
        - [Syntax](#syntax)
        - [Importing macros](#importing-macros)
    - [Writing macros](#writing-macros)
        - [Quasiquotes](#quasiquotes)
        - [Distinguish how the macro is called](#distinguish-how-the-macro-is-called)
        - [The named parameters](#the-named-parameters)
            - [Differences to `mcpy`](#differences-to-mcpy)
        - [Macro arguments](#macro-arguments)
            - [Arguments or no arguments?](#arguments-or-no-arguments)
        - [Identifier macros](#identifier-macros)
        - [Walk an AST](#walk-an-ast)
        - [Get the source of an AST](#get-the-source-of-an-ast)
        - [Expand macros](#expand-macros)
        - [Macro expansion error reporting](#macro-expansion-error-reporting)
        - [Examples](#examples)
    - [Test coverage reporting FAQ](#test-coverage-reporting-faq)
        - [Why do my block and decorator macros generate extra do-nothing `Expr` nodes?](#why-do-my-block-and-decorator-macros-generate-extra-do-nothing-expr-nodes)
        - [Why doesn't `mcpyrate` copy the source location of a `with` macro invocation to each top-level item in the body?](#why-doesnt-mcpyrate-copy-the-source-location-of-a-with-macro-invocation-to-each-top-level-item-in-the-body)
        - [`Coverage.py` says my quasiquoted code block is covered? It's quoted, not running, so why?](#coveragepy-says-my-quasiquoted-code-block-is-covered-its-quoted-not-running-so-why)
    - [Understanding the code](#understanding-the-code)

<!-- markdown-toc end -->

## Highlights

- **Agile development**:
  - Universal bootstrapper: `macropython`. **Import and use macros in your main program**.
  - Interactive console: `macropython -i`. **Import and use macros in a console session**.
    - Embeddable à la `code.InteractiveConsole`. See `mcpyrate.repl.console.MacroConsole`.
  - IPython extension `mcpyrate.repl.iconsole`. **Import and use macros in an IPython session**.
- **Testing and debugging**:
  - Statement coverage is correctly reported by tools such as [`Coverage.py`](https://github.com/nedbat/coveragepy/).
  - Macro expansion errors are reported **at macro expansion time**, with use site traceback.
  - Debug output with a step-by-step expansion breakdown. See macro `mcpyrate.debug.step_expansion`.
  - Manual expand-once. See `expander.visit_once`; get the `expander` as a named argument of your macro.
- **Dialects, i.e. whole-module source and AST transforms**.
  - Think [Racket's](https://racket-lang.org/) `#lang`, but for Python.
  - Define languages that use Python's surface syntax, but change the semantics; or plug in a per-module transpiler that (at import time) compiles source code from some other programming language into macro-enabled Python.
  - Sky's the limit, really. Until we get [`unpythonic`](https://github.com/Technologicat/unpythonic) ported to use `mcpyrate`, see [`pydialect`](https://github.com/Technologicat/pydialect) for old example dialects.
  - For documentation, see the docstrings of [`mcpyrate.dialects`](mcpyrate/dialects.py).
  - For debugging, `from mcpyrate.debug import dialects, StepExpansion`.
  - If you're writing a full-module AST transformer that splices the whole module into a template, you may be interested in `mcpyrate.splicing.splice_dialect`.
- **Advanced quasiquoting**:
  - Hygienically interpolate both regular values **and macro names**.
  - Delayed macro expansion inside quasiquoted code.
    - User-controllable, see macros `expand1` and `expand` in `mcpyrate.quotes`.
    - Expand when you want, or just leave it to `mcpyrate` to expand automatically once your macro (that uses quasiquoting) returns.
  - Inverse quasiquote operator. See function `mcpyrate.quotes.unastify`.
    - Convert a quasiquoted AST back into a direct AST, typically for further processing before re-quoting it.
      - Not an unquote; we have those too, but the purpose of unquotes is to interpolate values into quoted code. The inverse quasiquote, instead, undoes the quasiquote operation itself, after any unquotes have already been applied.
    - Useful for second-order macros that need to process a quasiquoted code section at macro expansion time, before the quasiquoted tree has a chance to run. (As usual, when it runs, it converts itself into a direct AST.)
- **Macro arguments**. Inspired by MacroPy.
  - Opt-in. Declare by using the `@parametricmacro` decorator on your macro function (along with `@namemacro`, if used too).
  - Use bracket syntax to invoke, e.g. `macroname[arg0, ...][expr]`. To send no args, invoke like a non-parametric macro, `macroname[expr]`.
  - For a parametric macro, `macroname[arg0, ...]` works in `expr`, `block` and `decorator` macro invocations in place of a bare `macroname`.
  - The named parameter `args` is a raw `list` of the macro argument ASTs. It is the empty list if no args were sent, or if the macro function is not declared as parametric.
- **Identifier (a.k.a. name) macros**
  - Can be used for creating magic variables that may only appear inside specific macro invocations, erroring out at macro expansion time if they appear anywhere else.
  - Opt-in. Declare by using the `@namemacro` decorator on your macro function. Place it outermost (along with `@parametricmacro`, if used too).
- **Bytecode caching**:
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
- **Conveniences**:
  - Relative macro-imports (for code in packages), e.g. `from .other import macros, kittify`.
  - The expander automatically fixes missing `ctx` attributes (and source locations) in the AST, so you don't need to care about those in your macros.
  - Several block macros can be invoked in the same `with` (equivalent to nesting them, with leftmost outermost).
  - Walker with a state stack, à la MacroPy, to easily temporarily override the state for a given subtree.
  - AST markers (pseudo-nodes) for communication in a set of co-operating macros (and with the expander).
  - `gensym` to create a fresh, unused lexical identifier.
  - `unparse` to convert an AST to the corresponding source code.
  - `dump` to look at an AST representation directly.


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

Just like earlier macro expanders for Python, `mcpyrate` must be explicitly enabled before importing any module that uses macros. Macros must be defined in a separate module. The following classical 3-file setup works fine:

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

The per-project wrapper `run.py` is optional. You can use the following 2-file setup:

```python
# mymacros.py with your macro definitions
def echo(expr, **kw):
  print('Echo')
  return expr

# application.py
from mymacros import macros, echo
echo[6 * 7]
```

To run, `macropython -m application`. It will import `application`, making that module believe it's `__main__`. (In a sense, it really is: if you look at `sys.modules["__main__"]`, you'll find the `application` module. The conditional main idiom works, too.)

`macropython` will use the `python` interpreter that is currently active according to `/usr/bin/env`. So if you e.g. set up a venv with PyPy3 and activate the venv, `macropython` will use that.


### REPL

For interactive macro-enabled sessions, we provide an macro-enabled equivalent for `code.InteractiveConsole`, as well as an IPython extension. See the [REPL system documentation](repl.md).


### Syntax

`mcpyrate` macros can be used in four forms:

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

In the first three cases, the macro will receive `...` as input. An identifier macro will receive the `Name` AST node itself.

In each case, the expander will replace the invocation with the expanded content. Expansion occurs first for outermost nodes, i.e, from outside to inside.


### Importing macros

Just like in `mcpy`, in `mcpyrate`, macros are just functions. To use functions from `module` as macros, use a *macro-import statement*:

```python
from module import macros, ...
```

replacing `...` with the macros you want to use. Importing all via `*` won't work. You must declare the macros you want explicitly. This syntax tells the macro expander to register macro bindings. The macro bindings are in scope for the module in which the macro-import statement appears.

All macro-import statements must appear at the top level of a module.

`mcpyrate` prevents you from accidentally using macros as regular functions in your code by transforming the macro-import into:

```python
import module
```

The transformed import is always absolute, even if the original macro-import was relative.

This is part of the public API. If the expanded form of your macro needs to refer to `thing` that exists in (whether is defined in, or has been imported to) the global, top-level scope of the module that defines the macro, you can just refer to `module.thing` in your expanded code. This is the `mcpyrate` equivalent of MacroPy's `unhygienic_expose` mechanism.

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

Note this implies that if one of your macros needs to analyze whether the tree it's expanding is going to invoke specific other macros, then in `expander.bindings`, you **must look at the values** (whether they are the function objects you expect), not at the names (since names can be aliased to anything at the use site).


## Writing macros

No special imports are needed to write your own macros. Just consider a macro as a function accepting an AST `tree` and returning another AST (i.e., the macro function is a [syntax transformer](http://www.greghendershott.com/fear-of-macros/)). Refer to [Green Tree Snakes](https://greentreesnakes.readthedocs.io/en/latest/nodes.html) (a.k.a. the missing Python AST docs) for details on the AST node types. The documentation for the [AST module](https://docs.python.org/3/library/ast.html) may also be occasionally useful.

```python
def macro(tree, **kw): return tree
```

Although you don't strictly have to import anything to write macros, there are some useful functions in the top-level namespace of `mcpyrate`. See `gensym`, `unparse`, `dump`, `@namemacro`, and `@parametricmacro`.

Other modules contain more utilities for writing macros:

 - [`mcpyrate.quotes`](mcpyrate/quotes.py) provides [quasiquote syntax](quasiquotes.md) as macros, to easily build ASTs in your macros.
 - [`mcpyrate.utils`](mcpyrate/utils.py) provides some macro-writing utilities that are too specific to warrant a spot in the top-level namespace; of these, at least `rename` and `flatten_suite` solve problems that come up relatively often.
 - [`mcpyrate.walker`](mcpyrate/walker.py) provides an AST walker that can context-manage its state for different subtrees, while optionally collecting items across the whole walk. It's an `ast.NodeTransformer`, but with functionality equivalent to `macropy.core.walkers.Walker`.
 - [`mcpyrate.splicing`](mcpyrate/splicing.py) helps splice a list of statements into a code template. This is especially convenient when the template is written in the quasiquoted notation; there's no need to think about how the template looks like as an AST in order to paste statements into it.
 - [`mcpyrate.debug`](mcpyrate/debug.py) may be useful if something in your macro is not working.

The `tree` parameter is the only positional parameter the macro function is called with. All other parameters are passed by name, so you can easily pick what you need (and let `**kw` gather the ones you don't).

Beside returning an AST, you can return `None` to remove the `tree` you got in, or return a list of `AST` nodes (if in a position where that is syntactically admissible; so `block` and `decorator` macros only). The result of the macro expansion is recursively expanded until no new macro invocations are found.

Any missing source locations and `ctx` fields are fixed automatically in a postprocessing step, so you don't need to care about those when writing your AST.

If you get an error saying an AST node is missing the required field `lineno`, the actual error is likely something else. This is due to an unfortunate lack of input validation in Python's compiler. The first thing to check is that your macro is really placing AST nodes where the compiler expects those, instead of accidentally using bare values.

Simple example:

```python
from ast import *
from mcpyrate import unparse
def log(expr, **kw):
    '''Replace log[expr] with print('expr: ', expr)'''
    label = unparse(expr) + ': '
    return Call(func=Name(id='print', ctx=Load()),
                args=[Str(s=label), expr], keywords=[])
```


### Quasiquotes

We provide [a quasiquote system](quasiquotes.md) (both classical and hygienic) to make macro code both much more readable and simpler to write. Rewriting the above example:

```python
from mcpyrate import unparse
from mcpyrate.quotes import macros, q, u, a

def log(expr, **kw):
    '''Replace log[expr] with print('expr: ', expr)'''
    label = unparse(expr) + ': '
    return q[print(u[label], a[expr])]
```

Here `u[]` unquotes a simple value, and `a[]` unquotes an expression AST. If you're worried that `print` may refer to something else at the use site of `log[]`, you can hygienically unquote the function name with `h[]`: `q[h[print](u[label], a[expr])]`.

The system was inspired by MacroPy's, but the details differ. For example, in `mcpyrate`, macro invocations can be unquoted hygienically, and by default, macros in quasiquoted code are not expanded when the quasiquote itself expands. We provide macros to perform expansion in quoted code, to give you control over when it expands.


### Distinguish how the macro is called

A macro can be called in four different ways. The way a macro is called is recorded in the `syntax` named parameter (one of `'block'`, `'expr'`, `'decorator'`, or `'name'`), so you can distinguish the syntax used in the source code and provide different implementations for each one. In other words, the macro function acts as a dispatcher for all types of uses of that macro.

When valid macro invocation syntax for one of the other three types is detected, the name part is skipped, and it **does not** get called as an identifier macro. The identifier macro mechanism is invoked only for appearances of the name *in contexts that are not other types of macro invocations*.

The other three work roughly the same as in MacroPy. An important difference is that in `mcpyrate`, macro arguments are passed using brackets, not parentheses, e.g. `macroname[arg0, ...][expr]`.

Also, in `mcpyrate` macros do not implicitly accept arguments. If you want your macro to accept them, declare it as a `@parametricmacro`. This explicitness makes it easier to implement macros that don't need arguments (the majority), since then you don't need to worry about `args`.


### The named parameters

Full list as of v3.0.0, in alphabetical order:

 - `args`: macro argument ASTs, if the invocation provided any. If not, `args = []`.
   - Macro arguments are a rarely needed feature. The macro function only accepts macro arguments if declared `@parametricmacro`. For non-parametric macros (default), `args = []` always.
 - `expander`: the macro expander instance.
   - To expand macro invocations inside the current one, use `expander.visit_recursively` or `expander.visit_once`, depending on whether you want expansion to continue until no macros remain. Use `expander.visit` to use current setting for recursive mode.
   - Also potentially useful are `expander.bindings` and `expander.filename`.
   - See [`mcpyrate.core.BaseMacroExpander`](mcpyrate/core.py) and [`mcpyrate.expander.MacroExpander`](mcpyrate/expander.py) for the expander API; it's just a few methods and attributes.
- `invocation`: the whole macro invocation AST node as-is, not only `tree`. For introspection.
   - Very rarely needed; if you need it, you'll know.
   - **CAUTION**: does not make a copy.
   - The node may have already been edited by the expander, for example to pop a block or decorator macro.
 - `optional_vars`: only exists when `syntax='block'`. The *as-part* of the `with` statement. (So actually use it as `kw['optional_vars']`.)
 - `syntax`: invocation type. One of `expr`, `block`, `decorator`, `name`.
   - Identifier macros are a rarely needed feature. The `syntax` parameter can be `name` only if the macro function is declared `@namemacro`.

#### Differences to `mcpy`

The named parameter `to_source` has been removed; use the top-level function `unparse` instead.

The named parameter `expand_macros` has been replaced with `expander`, which grants access to the macro expander instance.

The named parameters `args` and `invocation` have been added.

The fourth `syntax` kind `name` has been added.


### Macro arguments

Macro arguments are a rarely needed feature. Hence, the expander interprets macro argument syntax only for macros that are declared as parametric. Declare by using the `@parametricmacro` decorator on your macro function. Place it outermost (along with `@namemacro`, if used too).

Once a macro has been declared parametric, macro arguments are sent by calling `macroname` with bracket syntax:

     macroname[arg0, ...]

Such an expression can appear in place of a bare `macroname` in an `expr`, `block` and `decorator` macro invocation. `name` macro invocations do not take macro arguments.

To invoke a parametric macro with no arguments, just use bare `macroname`, as if it was not parametric.

For simplicity, macro arguments are always positional.

The parametric macro function receives macro arguments as the `args` named parameter. It is a raw `list` of the ASTs `arg0` and so on. If the macro was invoked without macro arguments, `args` is an empty list. Any macro invocations inside the macro arguments are expanded after the primary macro invocation itself. To expand them first, use `expander.visit` in your macro implementation, as usual.

Observe `macroname[a][b]` may mean two different things:

  - If `macroname` is parametric, a macro invocation with `args=[a]`, `tree=b`.

  - If `macroname` is **not** parametric, first a macro invocation with `tree=a`,
    followed by a subscript operation on the result.

    Whether that subscript operation is applied at macro expansion time
    or at run time, depends on whether `macroname[a]` returns an AST for
    a `result`, for which `result[b]` can be interpreted as an invocation
    of a macro that is bound in the use site's macro expander. (This is
    exploited by the hygienic unquote operator `h`, when it is applied
    to a macro name.)


#### Arguments or no arguments?

Often, instead of taking macro arguments, you can just require `tree` to have a specific layout instead.

For example, a *let* macro invoked as `let[x << 1, y << 2][...]` could alternatively be designed to be invoked as `let[[x << 1, y << 2] in ...]`. But if the example `let` should work also as a decorator, then macro arguments are the obvious, uniform syntax, because then you can also `with let[x << 1, y << 2]:` and `@let[x << 1, y << 2]`.


### Identifier macros

Identifier macros are a rarely used feature, but one that is indispensable for
that rare use case. To avoid clutter in the dispatch logic of most macros, if a
macro function wants to be called as an identifier macro, it must explicitly opt
in. Declare by using the `@namemacro` decorator on your macro function. Place it
outermost (along with `@parametricmacro`, if used too).

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

The main use case, why this feature exists, is to create magic variables that
are allowed to appear only in certain contexts. Here's the pattern:

```python
from mcpyrate import namemacro
from mcpyrate.utils import NestingLevelTracker

_mymacro_level = NestingLevelTracker()

# a valid context for `it`
def mymacro(tree, *, syntax, expander, **kw):
    if syntax != "expr":
        raise SyntaxError("`mymacro` is an expr macro only")
    with _mymacro_level.changed_by(+1):
        tree = expander.visit_recursively(tree)  # this expands any `it` inside
        # Macro code goes here. You'll want it to define an actual
        # run-time `it` for the invocation site to refer to.
        # (But first check from `expander.bindings` what name
        #  our `it` macro function is actually bound to!)
    return tree

@namemacro
def it(tree, *, syntax, **kw):
    if syntax != "name":
        raise SyntaxError("`it` is a name macro only")
    if _mymacro_level.value < 1:
        raise SyntaxError("`it` may only appear within a `mymacro[...]`")
    return tree
```

This way any invalid, stray mentions of the magic variable `it` trigger an error at macro expansion time.

If you want to expand only `it` inside an invocation of `mymacro[...]` (thus checking that the mentions are valid), leaving other nested macro invocations untouched, that's also possible. See below how to temporarily run a second expander with different bindings (from which you can omit everything but `it`).


### Walk an AST

To bridge the feature gap between [`ast.NodeTransformer`](https://docs.python.org/3/library/ast.html#ast.NodeTransformer) and MacroPy's `Walker`, we provide [`mcpyrate.walker.Walker`](walker.md), a zen-minimalistic AST walker base class based on `ast.NodeTransformer`, with a state stack and a node collector. If you need a walker that can temporarily change state while in a given subtree, maybe look here.


### Get the source of an AST

`mcpyrate.unparse` is a function that converts an AST back into Python source code.

Because the code is backconverted from the AST representation, the result may differ in minute details of surface syntax, such as parenthesization, whitespace, and the exact source code representation of string literals.


### Expand macros

Use the named parameter `expander` to access the macro expander. This is useful for making inner macro invocations expand first.

To expand macros in `tree`, use `expander.visit(tree)`. Any code in your macro that runs before the `visit` behaves outside-in, any code after it behaves inside-out. If there's no explicit `visit` in your macro definition, the default behavior is outside-in.

The `visit` method uses the expander's current setting for recursive mode, which is almost always The Right Thing to do. The default mode is recursive, i.e. expand again in the result until no macros remain.

(Strictly speaking, the default outside-in behavior arises because the actual default, after a macro invocation has been expanded once (i.e. just after the macro function has returned), is to loop the expander on the output until no macro invocations remain. Even more strictly, we use a functional loop, with recursion instead of a `while`. Hence the name *recursive mode*.)

If you want to expand until no macros remain (even when inside the dynamic extent of an expand-once - this is only recommended if you know why you want to do it), use `expander.visit_recursively(tree)` instead.

If you want to expand only one layer of macro invocations, use `expander.visit_once(tree)`. This can be useful during debugging of a macro implementation. You can then convert the result into a printable form using `mcpyrate.unparse` or `mcpyrate.dump`.

If you need to temporarily expand one layer, but let the expander continue expanding your AST later (when your macro returns), observe that `visit_once` will return a `Done` AST marker, which is the thing whose sole purpose is to prevent further macro expansion in that subtree. It is a wrapper with the actual AST stored in its `body` attribute. So if you need to ignore the `Done`, you can grab the actual AST from there, and discard the marker.

If you need to temporarily run a second expander with different macro bindings, consult `expander.bindings` to grab the macro functions you need. Note the names can be anything due to as-imports, so **you must check the values** whether they are the function objects of those macros you would like to expand. Then, add the import `from mcpyrate.expander import expand_macros`, and in your macro, use `expand_macros(tree, modified_bindings, expander.filename)` to invoke a new expander with the modified bindings. The implementation of the quasiquote system has an example.

Currently, there is no single call to expand only one layer of macros using a second expander. But if you need to do that, look at how `expand_macros` is implemented (it's just two lines), and adapt that.


### Macro expansion error reporting

Any exception raised during macro expansion is reported immediately at compile time, and the program exits.

The error report includes two source locations: the macro use site (which was being expanded, not running yet), and the macro code that raised the exception (that was running and was terminated due to the exception).

The use site source location is reported in a chained exception (`raise from`), so if the second stack trace is long, scroll back in your terminal to see the original exception that was raised by the macro.


### Examples

`mcpyrate` is a macro expander, not a library containing macros. However, we provide a `demo` folder, to see `mcpyrate` in action. Navigate to it and run a Python console, then import `run`:

```python
import run
```


## Test coverage reporting FAQ

These questions may arise when experimenting with the `step_expansion` macro from [`mcpyrate.debug`](mcpyrate/debug.py).

### Why do my block and decorator macros generate extra do-nothing `Expr` nodes?

This allows coverage analysis tools such as `Coverage.py` to report correct coverage for macro-enabled code.

We assign the line number from the macro invocation itself to any new AST nodes (that do not have a source location explicitly set manually) generated by a macro. This covers most use cases. But it's also legal for a block or decorator macro to just edit existing AST nodes, without adding any new ones.

The macro invocation itself is compiled away by the macro expander, so to guarantee that the invocation shows as covered, it must (upon successful macro expansion) be replaced by some other AST node that actually runs at run-time, with source location information taken from the invocation node, for the coverage analyzer to pick up.

For this, we use an `Expr` with a `Constant` string inside it, to aid human-readability of the expanded source code.


### Why doesn't `mcpyrate` copy the source location of a `with` macro invocation to each top-level item in the body?

This strategy was used by `mcpy`. The problem is, it overwrites the line numbers of any user code that exists at the top level of the `with` block, preventing the reporting of those lines as covered.

We only fill in the source location info for a node if it doesn't yet have any.


### `Coverage.py` says my quasiquoted code block is covered? It's quoted, not running, so why?

When a `with q as quoted` block is expanded, it becomes an assignment to the variable `quoted` (or whatever name you gave it), setting the value of that variable to a `list` of the quoted representation of the code inside the block. Each statement that is lexically inside the block becomes an item in the list.

Consider the *definition site* of your macro function that uses `q`. In a quasiquoted block, having coverage means that the output of `q` contains code from each line reported as covered. **It says nothing about the run-time behavior of that code.**

Now consider the *use site* of your macro. It's not possible to see the run-time coverage of the code that originates from the quoted block (inside your macro), for two reasons:

 1. There are usually multiple use sites, because each invocation of your macro is a use site - that's the whole point of defining a macro.
 2. The quoted code does not belong to the final use site's source file, so given a view to its unexpanded source (which is what coverage tools report against), those lines simply aren't there.

Note these are fundamental facts of macro-enabled code; it doesn't matter whether quasiquotes were used to construct the AST. Seeing the run-time coverage would require saving the expanded source code (at each level of expansion, possibly) to disk, and the coverage analyzer would have to know about the macro expansion process.


## Understanding the code

We follow the `mcpy` philosophy that macro expanders aren't rocket science. We keep things as explicit and compact as reasonably possible. However, the extra features do cost some codebase size, and we also tolerate a small amount of extra complexity, if it improves the programmer [UX](https://en.wikipedia.org/wiki/User_experience).

For a clean overview of the core design, look at [mcpy](https://github.com/delapuente/mcpy), version 2.0.0. Of the parts that come from it, its `visitors` is our [`core`](mcpyrate/core.py) (the `BaseMacroExpander`), its `core` is our [`expander`](mcpyrate/expander.py) (the actual `MacroExpander`), and its `import_hooks` is our [`importer`](mcpyrate/importer.py). Its `BaseMacroExpander.ismacro` method is our `BaseMacroExpander.isbound`, because that method checks for a raw string name, not an AST structure. The rest should be clear.

Then see our [`importer`](mcpyrate/importer.py). After [`mcpyrate.activate`](mcpyrate/activate.py) has been imported, the importer becomes the top-level entry point whenever a module is imported.
