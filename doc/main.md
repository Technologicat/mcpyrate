<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Using macros](#using-macros)
    - [3-file setup](#3-file-setup)
    - [2-file setup](#2-file-setup)
    - [1-file setup](#1-file-setup)
    - [Interactive use (a.k.a. REPL)](#interactive-use-aka-repl)
    - [Macro invocation syntax](#macro-invocation-syntax)
    - [Importing macros](#importing-macros)
- [Writing macros](#writing-macros)
    - [Macro invocation types](#macro-invocation-types)
    - [Quasiquotes](#quasiquotes)
        - [Differences to `macropy`](#differences-to-macropy)
    - [Get the source of an AST](#get-the-source-of-an-ast)
        - [Syntax highlighting](#syntax-highlighting)
    - [Walk an AST](#walk-an-ast)
    - [The named parameters](#the-named-parameters)
        - [Differences to `mcpy`](#differences-to-mcpy)
    - [Macro arguments](#macro-arguments)
        - [Using parametric macros](#using-parametric-macros)
        - [Writing parametric macros](#writing-parametric-macros)
        - [Arguments or no arguments?](#arguments-or-no-arguments)
        - [Differences to `macropy`](#differences-to-macropy-1)
    - [Identifier macros](#identifier-macros)
        - [Syntax limitations](#syntax-limitations)
        - [Creating a magic variable](#creating-a-magic-variable)
    - [Expand macros inside-out](#expand-macros-inside-out)
    - [Expand macros inside-out, but only those in a given set](#expand-macros-inside-out-but-only-those-in-a-given-set)
- [Multi-phase compilation](#multi-phase-compilation)
    - [Displaying the source code for each phase](#displaying-the-source-code-for-each-phase)
    - [The phase level countdown](#the-phase-level-countdown)
    - [Notes](#notes)
- [Dialects](#dialects)
- [The import algorithm](#the-import-algorithm)
- [Questions & Answers](#questions--answers)
    - [How to debug macro-enabled code?](#how-to-debug-macro-enabled-code)
    - [I just ran my program again and no macro expansion is happening?](#i-just-ran-my-program-again-and-no-macro-expansion-is-happening)
    - [My own macros are working, but I'm not seeing any output from `step_expansion` (or `show_bindings`)?](#my-own-macros-are-working-but-im-not-seeing-any-output-from-stepexpansion-or-showbindings)
    - [Macro expansion time where exactly?](#macro-expansion-time-where-exactly)
    - [`step_expansion` is treating the `expands` family of macros as a single step?](#stepexpansion-is-treating-the-expands-family-of-macros-as-a-single-step)
    - [Can I use the `step_expansion` macro to report steps with `expander.visit(tree)`?](#can-i-use-the-stepexpansion-macro-to-report-steps-with-expandervisittree)
    - [`step_expansion` and `stepr` report different results?](#stepexpansion-and-stepr-report-different-results)
    - [Error in `compile`, an AST node is missing the required field `lineno`?](#error-in-compile-an-ast-node-is-missing-the-required-field-lineno)
        - [Unexpected bare value](#unexpected-bare-value)
        - [Wrong type of list](#wrong-type-of-list)
        - [Wrong type of AST node](#wrong-type-of-ast-node)
        - [The notorious invisible `ast.Expr` statement](#the-notorious-invisible-astexpr-statement)
        - [Wrong unquote operator](#wrong-unquote-operator)
        - [Failing all else](#failing-all-else)
    - [Expander says it doesn't know how to `astify` X?](#expander-says-it-doesnt-know-how-to-astify-x)
        - [Expander says it doesn't know how to `unastify` X?](#expander-says-it-doesnt-know-how-to-unastify-x)
    - [Why do my block and decorator macros generate extra do-nothing nodes?](#why-do-my-block-and-decorator-macros-generate-extra-do-nothing-nodes)
    - [`Coverage.py` says some of the lines inside my block macro invocation aren't covered?](#coveragepy-says-some-of-the-lines-inside-my-block-macro-invocation-arent-covered)
    - [`Coverage.py` says my quasiquoted code block is covered? It's quoted, not running, so why?](#coveragepy-says-my-quasiquoted-code-block-is-covered-its-quoted-not-running-so-why)
    - [My line numbers aren't monotonically increasing, why is that?](#my-line-numbers-arent-monotonically-increasing-why-is-that)
    - [My macro needs to fill in `lineno` recursively, any recommendations?](#my-macro-needs-to-fill-in-lineno-recursively-any-recommendations)
    - [I tried making a PyPI package with `setuptools` out of an app that uses `mcpyrate`, and it's not working?](#i-tried-making-a-pypi-package-with-setuptools-out-of-an-app-that-uses-mcpyrate-and-its-not-working)
    - [I tried making a Debian package out of an app that uses `mcpyrate`, and it's not working?](#i-tried-making-a-debian-package-out-of-an-app-that-uses-mcpyrate-and-its-not-working)
- [Macro expansion error reporting](#macro-expansion-error-reporting)
    - [Recommended exception types](#recommended-exception-types)
    - [Differences to `macropy`](#differences-to-macropy-2)

<!-- markdown-toc end -->


# Using macros

As usual for a macro expander for Python, `mcpyrate` must be explicitly enabled before importing any module that uses macros. There are two ways to enable it: `import mcpyrate.activate`, or by running your script or module via the `macropython` command-line wrapper.

If you want to enable the macro expander only temporarily, the module `mcpyrate.activate`, beside initially enabling the macro expander, also exports two functions: `activate` and `deactivate`. Calling the `deactivate` function disables the macro expander; then calling `activate` enables it again.

Macros are often defined in a separate module; but in `mcpyrate`, it is also possible to define macros in the same module that uses them.

## 3-file setup

The following classical **3-file setup**, familiar from `macropy` and `mcpy`, works fine:

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

## 2-file setup

In `mcpyrate`, the wrapper `run.py` is optional. The following **2-file setup** works fine:

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

## 1-file setup

By telling `mcpyrate` to use [multi-phase compilation](#multi-phase-compilation), the following **1-file setup** works fine:

```python
# application.py
from mcpyrate.multiphase import macros, phase  # enable multi-phase compiler

with phase[1]:
    def echo(expr, **kw):
        print('Echo')
        return expr

from __self__ import macros, echo  # magic self-macro-import from a higher phase
echo[6 * 7]
```

To run, `macropython -m application`.

Useful when the program is so small that a second module is just bureaucracy; or when a quick, small macro can shave lots of boilerplate.


## Interactive use (a.k.a. REPL)

[[full documentation](repl.md)]

For interactive macro-enabled sessions, we provide a macro-enabled equivalent for `code.InteractiveConsole` (also available from the shell, as `macropython -i`), as well as an IPython extension (`mcpyrate.repl.iconsole`).

Interactive sessions support not only importing and using macros, but also defining them, for quick interactive experiments.


## Macro invocation syntax

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


## Importing macros

In the tradition of `mcpy`, in `mcpyrate` macros are just functions. To use functions from `module` as macros, use a *macro-import statement*:

```python
from module import macros, ...
```

replacing `...` with the macros you want to use. Importing all via `*` won't work. You must declare the macros you want explicitly. This syntax tells the macro expander to register macro bindings. The macro bindings are in scope for the module in which the macro-import statement appears.

All macro-import statements must appear at the top level of a module. (The sole exception is with [multi-phase compilation](#multi-phase-compilation), where macro-imports may appear at the top level of a `with phase`, which itself must appear at the top level of the module.)

`mcpyrate` prevents you from accidentally using macros as regular functions in your code by transforming the macro-import into:

```python
import module
```

Even if the original macro-import was relative, the transformed import is always resolved to an absolute one, based on `sys.path`, like Python itself does. If the import cannot be resolved, it is a macro-expansion-time error. (Not just because of this; the import must resolve successfully, so that the expander can find the macro functions.)

This macro-import transformation is part of the public API. If the expanded form of your macro needs to refer to `thing` that exists in (whether is defined in, or has been imported to) the global, top-level scope of the module where the macro definition lives, you can just refer to `module.thing` in your expanded code. This is the `mcpyrate` equivalent of `macropy`'s `expose_unhygienic` mechanism.

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

Note this implies that, when writing your own macros, if one of them needs to analyze whether the tree it's expanding is going to invoke specific other macros, then in `expander.bindings`, you **must look at the values** (whether they are the function objects you expect), not at the names - since names can be aliased to anything at the use site.


# Writing macros

No special imports are needed to write your own macros. Just consider a macro as a function accepting an AST `tree` and returning another AST (i.e., the macro function is a [syntax transformer](http://www.greghendershott.com/fear-of-macros/)).

```python
def macro(tree, **kw):
    """[syntax, expr] Example macro."""
    return tree
```

Refer to [Green Tree Snakes](https://greentreesnakes.readthedocs.io/en/latest/nodes.html) (a.k.a. the missing Python AST docs) for details on the AST node types. The documentation for the [AST module](https://docs.python.org/3/library/ast.html) may also be occasionally useful.

The `tree` parameter is the only positional parameter the macro function is called with. All other parameters are passed by name, so you can easily pick what you need (and let `**kw` gather the ones you don't).

A macro can return a single AST node, a list of AST nodes, or `None`. See [Macro invocation types](#macro-invocation-types) below for details.

The result of the macro expansion is recursively expanded until no new macro invocations are found.

The only explicit hint at the definition site that a function is actually a macro is the `**kw`. To be more explicit, mention it at the start of the docstring, such as above. (We recommend the terminology used in [The Racket Reference](https://docs.racket-lang.org/reference/): a macro is *a syntax*, as opposed to *a procedure* a.k.a. garden variety function.)

Although you don't strictly have to import anything to write macros, there are some useful functions in the top-level namespace of `mcpyrate`. See `gensym`, `unparse`, `dump`, `@namemacro`, and `@parametricmacro`.

Other modules contain utilities for writing macros:

 - [`mcpyrate.quotes`](../mcpyrate/quotes.py) provides [quasiquote](https://en.wikipedia.org/wiki/Lisp_(programming_language)#Self-evaluating_forms_and_quoting) syntax as macros, to easily build ASTs in your macros, using syntax that mostly looks like regular code. [Documentation](quasiquotes.md).
 - [`mcpyrate.metatools`](../mcpyrate/metatools.py) provides utilities; particularly, to expand macros in run-time AST values, while using the macro bindings from your macro's *definition* site (vs. its *use* site like `expander.visit` does). Useful for quoted trees. [Documentation](quasiquotes.md#the-expand-family-of-macros).
 - [`mcpyrate.utils`](../mcpyrate/utils.py) provides some macro-writing utilities that are too specific to warrant a spot in the top-level namespace; of these, at least `rename` and `flatten` (for statement suites) solve problems that come up relatively often.
 - [`mcpyrate.walkers`](../mcpyrate/walkers.py) provides AST walkers (both visitor and transformer variants) that can context-manage their state for different subtrees, while optionally collecting items across the whole walk. They are based on `ast.NodeVisitor` and `ast.NodeTransformer`, respectively, but with functionality equivalent to `macropy.core.walkers.Walker`. [Documentation](walkers.md).
 - [`mcpyrate.splicing`](../mcpyrate/splicing.py) helps splice statements (or even a complete module body) into a code template. Note in quasiquoted code you can locally splice statements with the block mode of the `a` (ast-unquote) operator.
 - [`mcpyrate.debug`](../mcpyrate/debug.py) may be useful if something in your macro is not working. **See especially the macro `step_expansion`.**

Any missing `ctx` fields are fixed automatically in a postprocessing step, so you don't need to care about those when writing your AST.

For **source location information**, the recommendation is:

 - If you generate new AST nodes that do not correspond to any line in the original unexpanded source code, **do not fill in their source location information**.
   - For any node whose source location information is missing, the expander will auto-fill it. This auto-fill copies the source location from the macro invocation node. This makes it easy to pinpoint in `unparse` output in debug mode (e.g. for a block macro) which lines originate in the unexpanded source code and which lines were added by the macro invocation.

 - If you generate a new AST node based on an existing one from the input AST, and then discard the original node, **be sure to `ast.copy_location` the original node's source location information to your new node**.
   - For such edits, **it is the macro's responsibility** to ensure correct source location information in the output AST, so that coverage reporting works. There is no general rule that could generate source location information for arbitrary AST edits correctly.

 - If you just edit an existing AST node, just leave its source location information as-is.

(What we can do automatically, and what `mcpyrate` indeed does, is to make sure that *the line with the macro invocation* shows as covered, on the condition that the macro was actually invoked.)

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


## Macro invocation types

A macro can be called in four different ways. The macro function acts as a dispatcher for all of them.

The way the macro was called, i.e. the *invocation type*, is recorded in the `syntax` named parameter, which has one of the values `'expr'`, `'block'`, `'decorator'`, or `'name'`. With this, you can distinguish the syntax used in the invocation, and provide a different implementation for each one (or `raise SyntaxError` on those your macro is not interested in).

When valid macro invocation syntax for one of the other three types is detected, the name part of the invocation is skipped, and it **does not** get called as an identifier macro. The identifier macro mechanism is invoked only for appearances of the name *in contexts that are not other types of macro invocations*.

Furthermore, identifier macros are an opt-in feature. The value of the `syntax` parameter can be `name` only if the macro function is declared as a `@namemacro`. The decorator must be placed outermost (along with `@parametricmacro`, if that is also used).

Let us call all descendants of `ast.expr` (note lowercase `e`) *expression AST nodes*, and all descendants of `ast.stmt` *statement AST nodes*. The different invocation types behave as follows:

 - If `syntax == 'expr'`, then `tree` is a single **expression** AST node.

 - If `syntax == 'block'`, then `tree` is always a `list` of **statement** AST nodes. If several block macros appear in the same `with`, they are popped one by one, left-to-right; the `with` goes away when (if) all its context managers have been popped. As long as the `with` is there, it appears as the only top-level statement in the list `tree`.

 - If `syntax == 'decorator'`, then `tree` is the decorated node itself, which is a **statement** AST node (a class definition, function definition, or async function definition). If several decorator macros decorate the same node, they are popped one by one, innermost-to-outermost. This is the same processing order as Python uses for regular decorators.

 - If `syntax == 'name'`, then `tree` is the `Name` node itself. It is an **expression** AST node.

Valid return values from a macro are as follows:

 - `expr` and `name` macros must return a single **expression** AST node, or `None`.
   - The node replaces the macro invocation.
   - Because expression AST node slots in the AST cannot be empty, returning `None` is shorthand for returning a dummy expression node that does nothing, and at run time, evaluates to `None`.

 - `block` and `decorator` macros must return one or more **statement** AST nodes, or `None`.
   - The node or nodes replace the macro invocation.
   - To return several statement nodes, place them in a `list`. Note this must be a regular run-time `list`, **not** an `ast.List` node. The nodes in the `list` will be spliced in to replace the macro invocation node.
   - Returning `None` removes the macro invocation subtree from the output.

`mcpyrate` takes care to arrange the AST to report correct coverage *for the line containing the macro invocation* even if a macro returns `None`. If the macro invocation ran, coverage tools will see the source line as covered.

(If a `block` macro deletes the whole block, any lines in the source code *inside that block* will *not* be reported as covered, since they will then not run.)


## Quasiquotes

[[full documentation](quasiquotes.md)]

We provide a [quasiquote system](https://en.wikipedia.org/wiki/Lisp_(programming_language)#Self-evaluating_forms_and_quoting) (both classical and hygienic) to make macro code both much more readable and simpler to write.

Rewriting the above example, note the `ast` import is gone:

```python
from mcpyrate import unparse
from mcpyrate.quotes import macros, q, u, a

def log(expr, **kw):
    '''[syntax, expr] Replace log[expr] with print('expr: ', expr)'''
    label = unparse(expr) + ': '
    return q[print(u[label], a[expr])]
```

Here `q[]` quasiquotes an expression, `u[]` unquotes a simple value, and `a[]` unquotes an expression AST. If you're worried that `print` may refer to something else at the use site of `log[]`, you can hygienically capture the function with `h[]`: `q[h[print](u[label], a[expr])]`.

### Differences to `macropy`

By default, in `mcpyrate`, macros in quasiquoted code are not expanded when the quasiquote itself expands.

In `mcpyrate`, all quote and unquote operators have single-character names by default: `q`, `u`, `n`, `a`, `s`, `h`. Of these, `q` and `u` are as in `macropy`, the operator `n` most closely corresponds to `name`, `a` to `ast_literal`, and `s` to `ast_list`.

In `mcpyrate`, there is **just one *quote* operator**, `q[]`, although just like in `macropy`, there are several different *unquote* operators, depending on what you want to do. In `mcpyrate`, there is no `unhygienic` operator, because there is no separate `hq` quote.

For [macro hygiene](https://en.wikipedia.org/wiki/Hygienic_macro), we provide a **hygienic unquote** operator, `h[]`. So instead of implicitly hygienifying all `Name` nodes inside a `hq[]` like `macropy` does, `mcpyrate` instead expects the user to use the regular `q[]`, and explicitly say which subexpressions to hygienify, by unquoting each of those separately with `h[]`. The hygienic unquote operator captures expressions by snapshotting a value; it does not care about names, except for human-readable output.

In `mcpyrate`, also macro names can be captured hygienically.

In `mcpyrate`, there is no `expose_unhygienic`, and no names are reserved for the macro system. (You can call a variable `ast` if you want, and it won't shadow anything important.)

The `expose_unhygienic` mechanism is not needed, because in `mcpyrate`, each macro-import is transformed into a regular import of the module the macros are imported from. So the macros can refer to anything in the top-level namespace of their module as attributes of that module object. (As usual in Python, this includes any imports. For example, `mcpyrate.quotes` refers to the stdlib `ast` module in the macro expansions as `mcpyrate.quotes.ast` for this reason.)

In `mcpyrate`, the `n[]` operator is a wrapper for `ast.parse`, so it will lift any source code that represents an expression, not only lexical variable references.


## Get the source of an AST

`mcpyrate.unparse` is a function that converts an AST back into Python source code.

Because the code is backconverted from the AST representation, the result may differ in minute details of surface syntax, such as parenthesization, whitespace, and the exact source code representation of string literals.

By default, `unparse` attempts to render code that can be `eval`'d (expression) or `exec`'d (statements). But if the AST contains any AST markers, then the unparsed result cannot be `eval`'d or `exec`'d. If you need to delete AST markers recursively, see `mcpyrate.markers.delete_markers`.

When debugging macros, it is often useful to see the invisible AST nodes `Expr` and `Module`, which have no surface syntax representation. To show them, as well as display line numbers, pass the named argument `debug=True`. Then the result cannot be `eval`'d or `exec`'d, but it shows much more clearly what is going on.

The line numbers shown in debug mode are taken from *statement* AST nodes, because in Python, a statement typically begins a new line. If you need to see line numbers stored in *expression* AST nodes, then instead of `unparse`, you can use the function `mcpyrate.dump` to view the raw AST, with (mostly) PEP8-compliant indentation, optionally with syntax highlighting (node types, field names, bare values). The output will be very verbose, so it is recommended to do this only for a minimally small AST snippet.

### Syntax highlighting

In `unparse`, syntax highlighting is available for terminal output. To enable, pass the named argument `color=True`. Beside usual Python syntax highlighting, if you provide a `MacroExpander` instance, also macro names bound in that expander instance will be highlighted. The macros `mcpyrate.debug.step_expansion` and `mcpyrate.metatools.stepr` automatically pass the appropriate expander to `unparse` when they print unparsed source code.

The `dump` function also has minimal highlighting support; to enable, pass `color=True`. AST node types, field names, and bare values (the content of many leaf fields) will be highlighted.

The color scheme for syntax highlighting is read from the bunch of constants `mcpyrate.colorizer.ColorScheme`. By writing to that bunch (or completely replacing its contents with the `replace` method), you can choose which of the 16 colors of the terminal's color palette to use for which purpose. Changes will take effect immediately for any new output. But which actual colors those palette entries map to, is controlled by the color theme of your terminal app. So the constant `RED` actually represents palette entry number 2 (1-based), not the actual color red.

`mcpyrate` automatically uses the [`colorama`](https://github.com/tartley/colorama) library if it is installed, so the coloring works on any OS. If `colorama` is not installed, and the OS we are running on is a *nix, `mcpyrate` will directly use ANSI escape codes instead. (This is to make the syntax highlighting work also e.g. in Docker images that do not have `colorama` installed.)

Depending on the terminal app, some color themes might not have 16 *useful* colors. For example, if you like the [*Zenburn*](https://kippura.org/zenburnpage/) color theme (which is nowadays widely supported by code editors), the *Solarized* theme of `gnome-terminal` looks somewhat similar, but in that *Solarized* theme, most of the "light" color variants are useless, as they all map to a shade of gray. Also, with that theme, the `gnome-terminal` option *Show bold text in bright colors* (which is enabled by default) is useless, because any bolding then makes the text gray. So to get optimal results, depending on your terminal app, you may need to configure how it displays colors.

Note `mcpyrate` can syntax-highlight ***unparsed* source code only**, because in order to know where to highlight and with which color, the code must be analyzed. Parsing source code into an AST is a form of syntactic analysis; it is the AST that is providing the information about which text snippet (in the output of `unparse`) represents what.

Thus, syntax-highlighting is not available in all contexts. For example, if you use the `mcpyrate.debug.StepExpansion` debugging dialect to view dialect transforms, during source transforms the code is not syntax-highlighted at all (because at that point, the surface syntax could mean anything). Similarly, REPL input is not syntax-highlighted (unless you use the IPython version, in which case syntax highlighting will be provided by IPython).

And when using the `mcpyrate.debug.StepExpansion` debugging dialect, then during dialect AST transforms, the AST is available, so syntax highlighting is enabled, but macro names are not highlighted (because while processing the whole-module AST transforms of a dialect, the *macro* expander is not yet running).


## Walk an AST

[[full documentation](walkers.md)]

To bridge the feature gap between [`ast.NodeVisitor`](https://docs.python.org/3/library/ast.html#ast.NodeVisitor)/  [`ast.NodeTransformer`](https://docs.python.org/3/library/ast.html#ast.NodeTransformer) and `macropy`'s `Walker`, we provide `ASTVisitor` and `ASTTransformer` that can context-manage their state for different subtrees, while optionally collecting items across the whole walk. These can be found in the module [`mcpyrate.walkers`](../mcpyrate/walkers.py).

The walkers are based on `ast.NodeVisitor` and `ast.NodeTransformer`, respectively. So `ASTVisitor` only looks at the tree, gathering information from it, while `ASTTransformer` may perform edits.


## The named parameters

Full list as of v3.0.0, in alphabetical order:

 - `args`: macro argument ASTs, if the invocation provided any. If not, `args = []`.
   - A macro function only accepts macro arguments if declared `@parametricmacro`. For non-parametric macros (default), `args=[]`.
 - `expander`: the macro expander instance.
   - To expand macro invocations inside the current one, use `expander.visit(tree)`, or in special use cases (when you know why), `expander.visit_recursively(tree)` or `expander.visit_once(tree)`.
     - These methods will use the macro bindings *from the use site of your macro*. If you instead need to use the macro bindings *from the definition site of your macro*, see the `expand` family of macros in [`mcpyrate.metatools`](../mcpyrate/metatools.py). [Full documentation](quasiquotes.md#the-expand-family-of-macros).
   - Also potentially useful are `expander.bindings` and `expander.filename`.
   - See [`mcpyrate.core.BaseMacroExpander`](../mcpyrate/core.py) and [`mcpyrate.expander.MacroExpander`](../mcpyrate/expander.py) for the expander API; it's just a few methods and attributes.
- `invocation`: the whole macro invocation AST node as-is, not only `tree`. For introspection.
   - Very rarely needed; if you need it, you'll know.
   - **CAUTION**: not a copy, or at most a shallow copy.
 - `optional_vars`: only exists when `syntax='block'`. The *as-part* of the `with` statement. (So use it as `kw['optional_vars']`.)
 - `syntax`: invocation type. One of `expr`, `block`, `decorator`, `name`.
   - Can be `name` only if the macro function is declared `@namemacro`.

### Differences to `mcpy`

No named parameter `to_source`. Use the function `mcpyrate.unparse`.

No named parameter `expand_macros`. Use the named parameter `expander`, which grants access to the macro expander instance. Call `expander.visit(tree)`.

You might also want to see the `expand` family of macros in [`mcpyrate.metatools`](../mcpyrate/metatools.py). [Documentation](quasiquotes.md#the-expand-family-of-macros).

The named parameters `args` and `invocation` are new.

The fourth `syntax` invocation type `name` is new.


## Macro arguments

To accept arguments, the macro function must be declared parametric.

### Using parametric macros

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


### Writing parametric macros

To declare a macro parametric, use the `@parametricmacro` decorator on your macro function. Place it outermost (along with `@namemacro`, if used too).

The parametric macro function receives macro arguments as the `args` named parameter. It is a raw `list` of the ASTs `arg0` and so on. If the macro was invoked without macro arguments, `args` is an empty list.

Macro invocations inside the macro arguments **are not automatically expanded**. If those ASTs end up in the macro output, they are expanded after the primary macro invocation itself (as part of the default outside-in processing); but if not, they are not expanded at all. To expand them, use `expander.visit(args)` in your macro implementation. (Or, in the rare case where you need to use the macro bindings *from your macro's definition site* when expanding the args, use the `expand` family of macros from `mcpyrate.metatools`.)


### Arguments or no arguments?

Macro arguments are a rarely needed feature. Often, instead of taking macro arguments, you can just require `tree` to have a specific layout instead.

For example, a *let* macro invoked as `let[x << 1, y << 2][...]` could alternatively be designed to be invoked as `let[[x << 1, y << 2] in ...]`. But if this `let` example should work also as a decorator, then macro arguments are the obvious, uniform syntax, because then you can allow also `with let[x << 1, y << 2]:` and `@let[x << 1, y << 2]`.


### Differences to `macropy`

In `mcpyrate`, macro arguments are passed using brackets, e.g. `macroname[arg0, ...][expr]`. This syntax looks macropythonic, as well as makes it explicit that macro arguments are positional-only.

In `mcpyrate`, macros must explicitly opt in to accept arguments. This makes it easier to implement macros that don't need arguments (which is a majority of all macros), since then you don't need to worry about `args` (it's guaranteed to be empty).


## Identifier macros

Identifier macros are a rarely used feature, but one that is indispensable for
that rare use case. The reason this feature exists is to allow creating magic
variables that may appear only in certain contexts.

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

### Syntax limitations

The run-time result of an identifier macro cannot be subscripted in place, because the syntax to do that looks like an `expr` macro invocation. If you need to do that, first assign the result to a temporary variable, and then subscript that.

### Creating a magic variable

Here's the pattern for creating a magic variable that may appear only in certain
contexts:

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

If you want to expand only `it` inside an invocation of `mymacro[...]` (thus checking that the mentions are valid), leaving other nested macro invocations untouched, that's also possible. See below how to expand only macros in a given set (from which you can omit everything but `it`).

## Expand macros inside-out

Use the named parameter `expander` to access the macro expander. This is useful for making inner macro invocations expand first.

To expand macros in `tree`, use `expander.visit(tree)`. Any code in your macro that runs before the `visit` behaves outside-in, any code after it behaves inside-out. If there's no explicit `visit` in your macro definition, the default behavior is outside-in.

The `visit` method uses the expander's current setting for recursive mode, which is almost always The Right Thing to do. The default mode is recursive, i.e. expand again in the result until no macros remain.

(Strictly speaking, the default outside-in behavior arises because the actual default, after a macro invocation has been expanded once (i.e. just after the macro function has returned), is to loop the expander on the output until no macro invocations remain. Even more strictly, we use a functional loop, which is represented as a recursion instead of a `while`. Hence the name *recursive mode*.)

If you want to expand until no macros remain (even when inside the dynamic extent of an expand-once - this is only recommended if you know why you want to do it), use `expander.visit_recursively(tree)` instead.

If you want to expand only one layer of macro invocations (even when inside the dynamic extent of an expand-until-no-macros-remain), use `expander.visit_once(tree)`. This can be useful during debugging of a macro implementation. You can then convert the result into a printable form using `mcpyrate.unparse` or `mcpyrate.dump`.

If you need to temporarily expand one layer, but let the expander continue expanding your AST later (when your macro returns), observe that `visit_once` will return a `Done` AST marker, which is the thing whose sole purpose is to tell the expander not to expand further in that subtree. It is a wrapper with the actual AST stored in its `body` attribute. So if you need to ignore the `Done`, you can grab the actual AST from there, and discard the wrapper.

All of the above will use the macro bindings *from your macro's use site*. This is almost always The Right Thing. But if you need to use the macro bindings *from your macro's definition site* instead, see the `expand` family of macros in [`mcpyrate.metatools`](../mcpyrate/metatools.py). [Full documentation](quasiquotes.md#the-expand-family-of-macros).


## Expand macros inside-out, but only those in a given set

This can be done by temporarily running a second expander instance with different macro bindings. This is cheaper than it sounds; really the only state the expander keeps are the macro bindings, the filename of the source file being expanded, and a flag for the current recursive mode setting. Everything else is data-driven, based on the input AST.

The recipe is as follows:

 1. Add the import `from mcpyrate.expander import MacroExpander`.
 2. In your macro, on your primary `expander`, consult `expander.bindings` to grab the macro functions you need.
    - Note you **must look at the values** (whether they are the function objects you expect), not at the names. Names can be aliased to anything at the use site - and that very use site also gives you the `tree` that uses those possibly aliased names.
    - If you need to do the same on the expander from the macro expansion time of your macro definition (not the expander of your macro's *use site*, which is what the `expander` named argument refers to), see [`mcpyrate.metatools`](../mcpyrate/metatools.py), particularly the name macro `macro_bindings`. That will evaluate, at your macro's run time, to a snapshot of the bindings from the time its implementation was macro-expanded.
 3. In your macro, call `MacroExpander(modified_bindings, expander.filename).visit(tree)` to invoke a new expander instance with the modified bindings.

The implementation of the quasiquote system has an example of this.

Obviously, if you want to expand just one layer with the second expander, use its `visit_once` method instead of `visit`. (And if you do that, you'll need to decide if you should keep the `Done` marker - to prevent further expansion in that subtree - or discard it and grab the real AST from its `body` attribute.)


# Multi-phase compilation

*Multi-phase compilation*, a.k.a. `with phase`, allows to use macros in the
same module where they are defined. To tell `mcpyrate` to enable the multi-phase
compiler for your module, add the following macro-import somewhere in the top
level of the module body:

```python
from mcpyrate.multiphase import macros, phase
```

Actually `with phase` is a feature of `mcpyrate`'s importer, not really a
regular macro, but its docstring must live somewhere, and it's nice if `flake8`
is happy. This macro-import mainly acts as a flag for the importer, but it does
also import a dummy macro that will trigger a syntax error if the `with phase`
construct is used improperly (i.e. in a position where it is not compiled away
by the importer, and slips through to the macro expander).

When multi-phase compilation is enabled, use the `with phase[n]` syntactic
construct to define which parts of your module should be compiled before which
other ones. The phase number `n` must be a positive integer literal. **Phases count
down**, run time is phase `0`. For any `k >= 0`, the run time of phase `k + 1` is
the macro-expansion time of phase `k`. Phase `0` is defined implicitly. All code
that is **not** inside any `with phase` block belongs to phase `0`.

```python
# application.py
from mcpyrate.multiphase import macros, phase

with phase[1]:
    # macro definitions here

# everything not inside a `with phase` is implicitly phase 0

# use the magic module name __self__ to import macros from a higher phase of the same module
from __self__ import macros, ...

# then just code as usual
```

To run, `macropython application.py` or `macropython -m application`. For a full example, see [`demo/multiphase_demo.py`](../demo/multiphase_demo.py).

The `with phase` construct may only appear at the top level of the module body.
Appearing anywhere else, it is a syntax error. It is a block macro only; using
any other invocation type for it is a syntax error. It is basically just data
for the importer that is compiled away before the macro expander runs. Thus,
macros cannot inject `with phase` invocations.

Multiple `with phase` blocks with the same phase number **are** allowed; the code
from each of them is considered part of that phase.

The syntax `from __self__ import macros, ...` is a *self-macro-import*, which
imports macros from any higher-numbered phase of the same module it appears in.
Self-macro-imports vanish during macro expansion (leaving just a [coverage dummy
node](#why-do-my-block-and-decorator-macros-generate-extra-do-nothing-nodes)),
because a module does not need to really import itself. This is just the closest
possible adaptation of the traditional macropythonic syntax to register macro
bindings, when the macros come from the same module. The `__self__` as a module
name in a from-import just tells `mcpyrate`'s importer that we want to refer to
*this module*, whatever its absolute dotted name happens to be; there is no
run-time object named `__self__`.

If you need to write helper macros to define your phase 1 macros, you can define
them in phase 2 (and so on):

```python
from mcpyrate.multiphase import macros, phase

with phase[2]:
    # define macros used by phase 1 here

with phase[1]:
    # macro-imports (also self-macro-imports) may appear
    # at the top level of a `with phase`.
    from __self__ import macros, ...

    # define macros used by phase 0 here

# everything not inside a `with phase` is implicitly phase 0

# you can import macros from any higher phase, not just phase 1
from __self__ import macros, ...

# then just code as usual
```

Macro-imports usually appear at the top level of the module body. That causes
the macros to be imported at phase `0`. If you need to import some macros
earlier, it is allowed to place macro-imports at the top level of the body of a
`with phase[n]`. This will make those macros available at phase `n` and at any
later (lower-numbered) phases, including at the implicit phase `0`.


## Displaying the source code for each phase

To display the unparsed source code for the AST of each phase before macro
expansion, you can enable the multi-phase compiler's debug mode, with this
additional macro-import (somewhere in the top level of the module body):

```python
from mcpyrate.debug import macros, step_phases
```

This allows to easily see whether the definition of each phase looks the way
you intended.

Similarly to `with phase`, `step_phases` is not really a macro at all; the
presence of that macro-import acts as a flag for the multi-phase compiler.
Trying to actually use the imported `step_phases` macro is considered
a syntax error. (It's a `@namemacro`, so even accessing the bare name
will trigger the syntax error.)

The macro expansion itself will **not** be stepped; this debug tool is
orthogonal to that. For that, use the `step_expansion` macro, as usual.

There is a limitation, to keep the implementation reasonably simple: because
`with_phase` must appear at the top level of the module body, it is not
conveniently possible to `with step_expansion` across multiple phase
definitions.

You must macro-import `step_expansion` inside the earliest (highest-number)
phase where you need it, and then `with step_expansion` separately inside each
`with phase` whose expansion you want to step. Be careful to leave the phase's
macro-imports, if any, *outside* the `with step_expansion`. The debug mode of
the multi-phase compiler does **not** need to be enabled to use `step_expansion`
like this.


## The phase level countdown

Phases higher than `0` only exist during module initialization, locally for each
module. Once a module finishes importing, it has reached phase `0`, and that's
all that the rest of the program sees. This means that another module that wants
to import macros from `mymodule` doesn't need to care which phase the macros
were defined in `mymodule.py`. The macros will be present in the final phase-`0`
module. Phase is important only for invoking those macros inside `mymodule` itself.

During module initialization, for `k >= 1`, each phase `k` is reified into a
temporary module, placed in `sys.modules`, with **the same absolute dotted name**
as the final one. This allows the next phase to import macros from it, using the
self-macro-import syntax.

When the macro expander and bytecode compiler are done with phase `k`, that
phase is reified, completely overwriting the module from phase `k + 1`.

All code from phase `k + 1` is automatically lifted into the code for phase `k`.
Phase `k` then lifts it to phase `k - 1`, and the chain continues all the way
down to the implicit phase `0`. So `with phase[n]` actually means that code is
present *starting from phase `n`*.

Once phase `0` has been macro-expanded, the temporary module is removed from
`sys.modules`. The resulting final phase-`0` module is handed over to Python's
import machinery. Thus Python will perform any remaining steps of module
initialization, such as placing the final module into `sys.modules`. (We don't
do it manually, because the machinery may need to do something else, too, and
the absence from `sys.modules` may act as a trigger.)

The **ordering** of the `with phase` code blocks **is preserved**. The code will
always execute at the point where it appears in the source file. Like a receding
tide, each phase will reveal increasing subsets of the original source file,
until (at the implicit phase `0`) all of the file is processed.

**Mutable state**, if any, **is not preserved** between phases, because each phase
starts as a new module instance. There is no way to transmit information to a
future phase, except by encoding it in macro output (so it becomes part of the
next phase's AST, before that phase reaches run time).

Phases are mainly a convenience feature to allow using macros defined in the
same module, but if your use case requires to transmit information to a future
phase, you could define a `@namemacro` that expands into an AST for the data you
want to transmit. (Then maybe use `q[u[...]]` in its implementation, to generate
the expansion easily.)


## Notes

Multi-phase compilation is applied interleaved with dialect AST transformers,
so that modules that need multi-phase compilation can be written using a dialect.
For details, see [`mcpyrate`'s import algorithm](#the-import-algorithm).

In the REPL, explicit multi-phase compilation is neither needed nor supported.
Conceptually, just consider the most recent state of the REPL (i.e. its state
after the last completed REPL input) as the content of *the previous phase*.
You can `from __self__ import macros, ...` in the REPL, and it'll just work.
There's also a REPL-only shorthand to declare a function as a macro, namely
the `@macro` decorator.

Multi-phase compilation was inspired by Racket's [phase level
tower](https://docs.racket-lang.org/guide/phases.html), but is much simpler.
Racketeers should observe that in `mcpyrate`, phase separation is not strict.
Code from **all** phases will be available in the final phase-`0` module. Also,
due to the automatic code lifting, it is not possible to have different definitions
for the same name in different phases; the original definition will "cascade down"
via the lifting process, at the point in the source file where it appears.

This makes `mcpyrate`'s phase level into a module initialization detail,
local to each module. Other modules don't need to care at which phase a thing was
defined when they import that thing - for them, all definitions exist at phase `0`.

This is a design decision; it's more pythonic that macros don't "disappear" from
the final module just because they were defined in a higher phase. The resulting
system is simple, and `with phase` affects Python's usual scoping rules as
little as possible. This is a minimal extension of the Python language, to make
it possible to use macros in the same source file where they are defined.


# Dialects

[[full documentation](dialects.md)]

Dialects are essentially *whole-module source and AST transformers*. Think [Racket's](https://racket-lang.org/) `#lang`, but for Python. Source transformers are akin to *reader macros* in the Lisp family.

Dialects allow you to define languages that use Python's surface syntax, but change the semantics; or let you plug in a per-module transpiler that (at import time) compiles source code from some other programming language into macro-enabled Python. Also an AST [optimizer](http://compileroptimizations.com/) could be defined as a dialect.


# The import algorithm

When a module is imported with `mcpyrate` enabled, here's what the importer does to the source code:

 1. Decode the content of the `.py` source file into a unicode string (i.e. `str`).
    - Character encoding is detected the same way Python itself does. That is, the importer reads the magic comment at the top of the source file (such as `# -*- coding: utf-8; -*-`), and assumes `utf-8` if this magic comment is not present.
 2. Apply [dialect](dialects.md) **source** transformers to the source text.
 3. Parse the source text into a (macro-enabled) Python AST, using `ast.parse`.
 4. Detect the number of [phases](#multi-phase-compilation) by scanning the top level of the module body AST.
    - If the AST does **not** request multi-phase compilation, there is just one phase, namely phase `0`.
 5. Extract the AST for the highest-numbered remaining phase. Then, for the extracted AST:
    1. Apply dialect **AST** transformers.
    2. Apply the macro expander.
    3. Apply dialect **AST postprocessors**.
 6. If the phase that was just compiled was not phase `0`, reify the current temporary module into `sys.modules`, and jump back to step 5.
 7. Delete the temporary module, if any, from `sys.modules`.
 8. Apply the builtin `compile` function to the resulting AST. Hand the result over to Python's standard import system.

**CAUTION**: As of `mcpyrate` 3.0.0, *code injected by dialect AST transformers cannot itself use multi-phase compilation*. The client code can; just the dialect code template AST cannot.

In practice this is not a major limitation. If the code injected by your dialect definition needs macros, just define them somewhere outside that injected code, and make the injected code import them in the usual way. The macros can even live in the module that provides the dialect definition, and that module can also use multi-phase compilation if you want; the only place the macros can't be defined in is the code template itself.


# Questions & Answers

## How to debug macro-enabled code?

At run time, just debug as usual. At compile time:

In whichever way the program is editing the source code, looking at the steps of that transformation often helps. We provide several utilities for this purpose:

 - To troubleshoot regular macro expansion, see the module [`mcpyrate.debug`](../mcpyrate/debug.py), particularly the macro `step_expansion`. It is both an `expr` and `block` macro. This is the one you'll likely need most often.

 - To troubleshoot macro expansion of a run-time AST value (such as quasiquoted code), see [`mcpyrate.metatools`](../mcpyrate/metatools.py), particularly the macro `stepr`. It is an `expr` macro that takes in a run-time AST value. (In Python, values are always referred to by expressions. Hence no block mode.) This one you'll likely need second-most often.

   Also, use `print(unparse(tree, debug=True, color=True))` if there's a particular `tree` whose source code representation you'd like to look at, or even `print(dump(tree, color=True))`. Look at the docstrings of those functions for other possibly useful parameters.

 - To troubleshoot multi-phase compilation, see `step_phases` in `mcpyrate.debug`. Just macro-import it (`from mcpyrate.debug import macros, step_phases`). It will show you the unparsed source code of each phase just after AST extraction.

 - To troubleshoot dialect transformations, see the dialect `StepExpansion` in `mcpyrate.debug`; just dialect-import it (`from mcpyrate.debug import dialects, StepExpansion`). It will step source and AST transformers as well as AST postprocessors in the dialect compiler, one step per transformer.

When interpreting the output, keep in mind [the import algorithm](#the-import-algorithm) as outlined above.


## I just ran my program again and no macro expansion is happening?

This is normal. The behavior is due to bytecode caching (`.pyc` files). When `mcpyrate` processes a source file, it will run the expander only if that file, or the source file of at least one of its macro-dependencies, has changed on disk. This is detected from the *mtime* (modification time) of the source files. The macro-dependencies are automatically considered recursively in a `make`-like fashion.

Even if you use [`sys.dont_write_bytecode = True`](https://docs.python.org/3/library/sys.html#sys.dont_write_bytecode) or the environment variable [`PYTHONDONTWRITEBYTECODE=1`](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONDONTWRITEBYTECODE), Python will still **use** existing `.pyc` files if they are up to date.

If you want to force all of your code to be macro-expanded again, delete your bytecode cache (`.pyc`) files; they'll be re-generated automatically. Typically, they can be found in a folder named `__pycache__`, at each level of your source tree.

Normally there is no need to delete bytecode caches manually.

However, there is an edge case. If you hygienically capture a value that was imported (to the macro definition site) from another module, and that other module is not a macro-dependency, then - if the class definition of the hygienically captured value changes on disk, that is not detected.

This can be a problem, because hygienic value storage uses `pickle`, which in order to unpickle the value, expects to be able to load the original (or at least a data-compatible) class definition from the same place where it was defined when the value was pickled. If this happens, then delete the bytecode cache (`.pyc`) files, and the program should work again once the macros re-expand.


## My own macros are working, but I'm not seeing any output from `step_expansion` (or `show_bindings`)?

The most likely cause is that the bytecode cache (`.pyc`) for your `.py` source file is up to date. Hence, the macro expander was skipped.

Unlike most macros, the whole point of `step_expansion` and `show_bindings` are their side effects - which occur at macro expansion time. So you'll get output from them only if the expander runs.

Your own macros do indeed work; but Python is loading the bytecode, which was macro-expanded during an earlier run. Your macros didn't run this time, but the expanded code from the previous run is still there in the bytecode cache (and, since it is up to date, it matches the output the macros would have, were they to run again).

Force an *mtime* update on your source file (`touch` it, or just save it again in a text editor), so the expander will then run again (seeing that the source file has been modified).


## Macro expansion time where exactly?

This is mainly something to keep in mind when developing macros where the macro implementation itself is macro-enabled code (vs. just emitting macro invocations in the output AST). Since the [quasiquote system](quasiquotes.md) is built on macros, this includes any macros that use `q`.

As an example, consider a macro `mymacro`, which uses `q` to define an AST using the quasiquote notation. When `mymacro` reaches run time, any macro invocations used as part of its own implementation (such as the `q`) are already long gone. On the other hand, the use site of `mymacro` has not yet reached run time - for that use site, it is still macro expansion time.

Any macros that `mymacro` invokes in its output AST are just data, to be spliced in to the use site. By default, they'll expand (run!) after `mymacro` has returned.

As the old saying goes, *it's always five'o'clock **somewhere***. *There is no global macro expansion time* - the "time" must be considered separately for each source file.

And if you use [multi-phase compilation](#multi-phase-compilation) (a.k.a. `with phase`), then in a particular source file, each phase will have its own macro-expansion time as well as its own run time. For any `k >= 0`, the run time of phase `k + 1` is the macro expansion time of phase `k`.


## `step_expansion` is treating the `expands` family of macros as a single step?

This is a natural consequence of the `expands` macros (see [`mcpyrate.metatools`](../mcpyrate/metatools.py)) being macros, and - the `s` meaning *static*, them doing their work at macro expansion time.

For example, in the case of `expands`, when `step_expansion` (see [`mcpyrate.debug`](../mcpyrate/debug.py)) takes one step, by telling the expander to visit the tree once, the expander will (eventually) find the `expands` invocation. So it will invoke that macro.

The `expands` macro, by definition, expands whatever is inside the invocation until no macros remain there. So by the time `step_expansion` gets control back, all macro invocations within the `expands` are gone.

Now consider the case with two or more nested `expand1s` invocations. When `step_expansion` takes one step, by telling the expander to visit the tree once, the expander will (eventually) find the outermost `expand1s` invocation. So it will invoke that macro.

The `expand1s` macro, by definition, expands once whatever is inside the invocation. So it will call the expander to expand once... and now the expander will find the next inner `expand1s`. This will get invoked, too. The chain continues until all `expand1s` in the expression or block are gone.

In the case of `expandr`/`expand1r`, using `step_expansion` on them will show what those macros do - but it won't show what they do to your `tree`, since in the `r` variants expansion is delayed until run time. (Note that in case of the `r` variants, the name `tree` points to a run-time AST value - expanding macros in the lexical identifier `tree` itself would make no sense.)

If want to step the expansion of an `expandr`, use the expr macro `mcpyrate.metatools.stepr` instead of using `expandr` itself. (If using quasiquotes, create your `quoted` tree first, and then do `stepr[quoted]` as a separate step, like you would do `expandr[quoted]`.)

If you want to do something similar manually, you can use the `macro_bindings` macro (from `mcpyrate.metatools`) to lift the macro bindings into a run-time dictionary, then instantiate a `mcpyrate.expander.MacroExpander` with those bindings (and `filename=__file__`), and then call `mcpyrate.debug.step_expansion` as a regular function, passing it the expander you instantiated. It will happily use that alternative expander instance. (This is essentially how `mcpyrate.metatools.stepr` does it; though it is a macro, so strictly speaking, it arranges for something like that to happen at run time.)

If you want to just experiment in the REPL, note that `step_expansion` is available there, as well. Just macro-import it, as usual.


## Can I use the `step_expansion` macro to report steps with `expander.visit(tree)`?

Right now, no. We might add a convenience function in the future, but for now:

If you need it for `expander.visit_recursively(tree)`, just import and call `mcpyrate.debug.step_expansion` as a function. Beside printing the debug output, it'll do the expanding for you, and return the expanded `tree`. Since you're calling it from inside your own macro, you'll have `expander` and `syntax` you can pass on. The `args` you can set to the empty list (or to `[ast.Constant(value="dump")]` if that's what you want).

If you need it for `expander.visit_once(tree)`, just perform the `visit_once` first, and then `mcpyrate.unparse(tree, debug=True, color=True)` and print the result to `sys.stderr`. This is essentially what `step_expansion` does at each step.

If you need it for `expander.visit(tree)`, detect the current mode from `expander.recursive`, and use one of the above.

(We recommend `sys.stderr`, because that's what `step_expansion` uses, and that's also the stream used for detecting the availability of color support, if `colorama` is not available. If `colorama` is available, it'll detect separately for `sys.stdout` and `sys.stderr`.)


## `step_expansion` and `stepr` report different results?

In general, **they should**, because:

 - `mcpyrate.debug.step_expansion` hooks into the expander at macro expansion time,
 - `mcpyrate.metatools.stepr` captures the expander's macro bindings at macro expansion time, but delays expansion (of the run-time AST value provided as its argument) until run time.

To look at this more closely, let's fire up a REPL with `macropython -i`. With the macro-imports:

```python
from mcpyrate.quotes import macros, q
from mcpyrate.debug import macros, step_expansion
from mcpyrate.metatools import macros, stepr
```

on Python 3.6, the invocation `step_expansion[q[42]]` produces:

```
**Tree 0x7f515e2454e0 (<ipython-session>) before macro expansion:
  q[42]
**Tree 0x7f515e2454e0 (<ipython-session>) after step 1:
  mcpyrate.quotes.ast.Num(n=42)
**Tree 0x7f515e2454e0 (<ipython-session>) macro expansion complete after 1 step.
```

Keep in mind each piece of source code shown is actually the unparse of an AST. So the source code `q[42]` actually stands for an `ast.Subscript`, while the expanded result is an `ast.Call` that, **once it is compiled and run**, will call `ast.Num`. (If you're not convinced, try `step_expansion["dump"][q[42]]`, which pretty-prints the raw AST instead of unparsed source code.)

The invocation `stepr[q[42]]`, on the other hand, produces:

```
**Tree 0x7f515e00aac8 (<ipython-session>) before macro expansion:
  42
**Tree 0x7f515e00aac8 (<ipython-session>) macro expansion complete after 0 steps.
```

or in other words, an `ast.Num` object. (Again, if not convinced, try `stepr["dump"][q[42]]`.)

So the **run-time result** of both invocations is an `ast.Num` object (or `ast.Constant`, if running on Python 3.8+). But they see the expansion differently, because `step_expansion` operates at macro expansion time, while `stepr` operates at run time.

Whereas unquotes are processed at run time of the use site of `q` (see [the quasiquote system docs](quasiquotes.md)), the `q` itself is processed at macro expansion time. Hence, `step_expansion` will see the `q`, but when `stepr` expands the tree at run time, it will already be gone. (And the expression mode of `q` itself does not have a run-time part, so it just vanishes.)


## Error in `compile`, an AST node is missing the required field `lineno`?

Welcome to the club. It is likely not much of an exaggeration that all Python macro authors (regardless of which expander you pick) have seen this error at some point.

It is overwhelmingly likely the actual error is something else, because all macro expanders for Python automatically fill in source location information for any AST nodes that don't have it. (There are differences in what exact line numbers are filled in by `mcpyrate`/`mcpy`/`macropy`, but they all do this in some form.)

The misleading error message is due to an unfortunate lack of input validation in Python's compiler. Python wasn't designed for an environment where AST editing is part of the daily programming experience.

So let's look at the likely causes.

### Unexpected bare value

Is your macro placing AST nodes where the compiler expects those, and not accidentally using bare run-time values? (This gets tricky if you're delaying something until run time. You might need a `mcpyrate.quotes.astify` there.)

### Wrong type of list

If you edit ASTs manually, check that you're really using a `list` where the [AST docs at Green Tree Snakes](https://greentreesnakes.readthedocs.io/en/latest/nodes.html) say *"a list of ..."*, and not a `tuple` or something else. (Yes, Python's compiler is that picky.)

Note that statement suites are represented as a bare `list`, and **not** as an `ast.List`. Any optional statement suite, when not present, is represented by an empty list, `[]`.

### Wrong type of AST node

Is your macro placing *expression* AST nodes where Python's grammar expects those, and *statement* AST nodes where it expects those?

There is no easy way to check this automatically, because Python's AST format does not say which places in the AST require what.

### The notorious invisible `ast.Expr` statement

The "expression statement" node `ast.Expr` is a very common cause of mysterious compile errors. It is an implicit AST node with no surface syntax representation.

Python's grammar requires that whenever, in the source code, an expression appears in a position where a statement is expected, then in the AST, the expression node must be wrapped in an `ast.Expr` statement node. The purpose of that statement is to run the expression, and discard the resulting value. (This is useful mainly for a bare function call, if the function is called for its side effects; consider e.g. `list.append` or `set.add`.)

(Note `ast.Expr` should not be confused with `ast.expr`, which is the base class for expression AST nodes.)

When manually building an AST, the common problem is an accidentally omitted `ast.Expr`.

When using quasiquotes to build an AST, the common problem is the opposite, i.e. the accidental presence of an `ast.Expr`. For example, one may attempt to use an `ast.Name(id="__paste_here__")` as a paste target marker in a quoted code block, and manually replace that marker with some statement node. Unless one is very careful, the statement node will then easily end up in the `value` field of the `ast.Expr` node, producing an invalid AST.

The `ast.Expr` node is taken into account in `mcpyrate.splicing.splice_statements`, as well as in `with a` in `mcpyrate.quotes`. Both of them specifically remove the `ast.Expr` when splicing statements into quoted code.

To see whether this could be the problem, use `unparse(tree, debug=True, color=True)` to print out also invisible AST nodes. (The `color=True` is optional, but recommended for terminal output; it enables syntax highlighting.) The macro `mcpyrate.debug.step_expansion` will also print out invisible nodes (actually by using `unparse` with those settings).

### Wrong unquote operator

If you use quasiquotes, check that you're using the unquote operators you intended. It's easy to accidentally put an `u[]` or `h[]` in place of an `a[]`, or vice versa.

### Failing all else

Use `git diff` liberally. Most likely whatever the issue is, it's something in the latest changes.


## Expander says it doesn't know how to `astify` X?

This may happen in two cases: trying to `u[]` something that operator doesn't support, or trying to quasiquote a tree after advanced hackery on it. (Astification is the internal mechanism that produces a quasiquoted AST; if curious, see [`mcpyrate.quotes.astify`](../mcpyrate/quotes.py).)

If it's the former, check that what you have is listed among the supported value types for `u[]` in [the quasiquote docs](quasiquotes.md). If the value type is not supported for `u[]`, use `h[]` instead.

If it's the latter, and the expander is complaining specifically about an AST marker, those indeed can't currently be astified (except `mcpyrate.core.Done`, which is supported specifically to allow astification of coverage dummy nodes and expanded name macros). To remove AST markers from your tree recursively, you can use [`mcpyrate.markers.delete_markers`](../mcpyrate/markers.py).

If these don't help, I'd have to see the details. Please file an issue so we can either document the reason, or if reasonably possible, fix it.

### Expander says it doesn't know how to `unastify` X?

Most likely, the input to `expands` or `expand1s` wasn't a quasiquoted tree. See `expandsq`, `expand1sq`, `expandrq`, `expand1rq`, or just `expander.visit(tree)`, depending on what you want.


## Why do my block and decorator macros generate extra do-nothing nodes?

This is normal. It allows coverage analysis tools such as `Coverage.py` to report correct coverage for macro-enabled code.

We assign the line number from the macro invocation itself to any new AST nodes (that do not have a source location explicitly set manually) generated by a macro. This covers most use cases. But it's also legal for a block or decorator macro to just edit existing AST nodes, without adding any new ones.

The macro invocation itself is compiled away by the macro expander, so to guarantee that the invocation shows as covered, it must (upon successful macro expansion) be replaced by some other AST node that actually runs at run-time, with source location information taken from the invocation node, for the coverage analyzer to pick up.

For this, we use an assignment to a variable `_mcpyrate_coverage`, with a human-readable string as the value. We can't use an `ast.Pass` or a do-nothing `ast.Expr`, since CPython optimizes those away when it compiles the AST into bytecode.


## `Coverage.py` says some of the lines inside my block macro invocation aren't covered?

In `mcpyrate`, the rules for handling source location information are simple. When a macro returns control back to the expander:

 - Any node that already has source location information keeps it.
   - Especially, this includes nodes that existed in the unexpanded source code.
 - Any node that is missing source location information gets its source location information auto-filled, by copying it from the macro invocation node.
   - That's the most appropriate source location: the node is there, because the macro generated it, so in terms of the unexpanded source, it came from the line where the macro invocation is.

The auto-fill of missing location information is done recursively, so e.g. in `Expr(Constant(value="kitten"))`, the `Expr` and `Constant` nodes are considered independently.

The rules imply that by default, if a macro does not keep any original nodes from a particular source line in its output, **that line will show as not covered** in the coverage report. (This is as it should be - it's valid for a block macro to delete some statements from its input, in which case those statements won't run.)

So, if your macro generates new nodes based on the original nodes from the unexpanded source, and then discards the original nodes, **make sure to copy source location information manually** as appropriate. Use `ast.copy_location` for this, as usual.


## `Coverage.py` says my quasiquoted code block is covered? It's quoted, not running, so why?

When a `with q as quoted` block is expanded, it becomes an assignment to the variable `quoted` (or whatever name you gave it), setting the value of that variable to a `list` of the quoted representation of the code inside the block. Each statement that is lexically inside the block becomes an item in the list.

Consider the *definition site* of your macro function that uses `q`. In a quasiquoted block, having coverage means that the output of `q` contains code from each line reported as covered. **It says nothing about the run-time behavior of that code.**

Now consider the *use site* of your macro. It's not possible to see the run-time coverage of the code that originates from the quoted block (inside your macro), for two reasons:

 1. There are usually multiple use sites, because each invocation of your macro is a use site - that's the whole point of defining a macro.
 2. The quoted code does not belong to the final use site's source file, so looking at its unexpanded source (which is what coverage tools report against), those lines simply aren't there.

Note these are fundamental facts of macro-enabled code; it doesn't matter whether quasiquotes were used to construct the AST. Seeing the run-time coverage would require saving the expanded source code (not only expanded bytecode) to disk, and a coverage analyzer that knows about the macro expansion process.

Also, there's the technical obstacle that in Python, an AST node can only have one source location, and has no *filename* attribute that could be used to indicate which source file it came from. In the presence of macros, the assumptions underlying that design no longer hold.

With coverage analysis of regular functions, there is no such problem, because any activation of a function can be thought of as happening at its definition site (equipped with a stack frame for bookkeeping). With macros, the same does not hold; the code is pasted independently to each use site, and that's where it runs.


## My line numbers aren't monotonically increasing, why is that?

This is normal. In macro-enabled code, when looking at the expanded output (such as shown by `mcpyrate.debug.step_expansion`), the line numbers stored in the AST - which refer to the original, unexpanded source code - aren't necessarily monotonic.

Any AST node that existed in the unexpanded source code will, in the expanded code, refer to its original line number in the unexpanded code, whereas (as mentioned above) any macro-generated node will refer to the line of the macro invocation that produced it.

Hence, non-monotonicity occurs if a block (or decorator) macro adds new AST nodes *after* existing AST nodes that originate from lines below the macro invocation node itself in the unexpanded source file.

Note that the non-monotonicity, when present at all, is mild; it's local to each block.


## My macro needs to fill in `lineno` recursively, any recommendations?

See [`mcpyrate.astfixers.fix_locations`](../mcpyrate/astfixers.py), which is essentially an improved `ast.fix_missing_locations`. You'll likely want either `mode="overwrite"` or `mode="reference"`, depending on what your macro does.

There's also the stdlib barebones solution:

```python
from ast import walk, copy_location

for node in walk(tree):
    copy_location(node, reference_node)
```


## I tried making a PyPI package with `setuptools` out of an app that uses `mcpyrate`, and it's not working?

The `py3compile` (and `pypy3compile`) command-line tools are not macro-aware. So the bytecode produced by them tries to treat macro-imports as regular imports. If this happens, you'll get an error about being unable to import the name `macros`.

For now, as a workaround, do one of the following:

 - Activate `mcpyrate`, and call `py3compile` from Python.
   - The tool is just a wrapper around the standard library module [`py_compile`](https://docs.python.org/3/library/py_compile.html), which uses the standard loader (see `compile` in [the source code](https://github.com/python/cpython/blob/3.9/Lib/py_compile.py)). That standard loader is exactly what `mcpyrate.activate` monkey-patches to add macro support.
   - Explicitly: first `import mcpyrate.activate`, then `import py_compile`, and then use the functions from that module (either `compile` or `main`, depending on what you want).

 - Disable bytecode precompilation when making the package.

Another `setuptools` thing to be aware of is that **source files using macros are not `zip_safe`**, because the macros need to access source code of the use site, and the zip file importer does not provide that.


## I tried making a Debian package out of an app that uses `mcpyrate`, and it's not working?

The standard `postinst` script for Debian packages creates bytecode cache files using `py3compile` (and/or `pypy3compile`).

These bytecode cache files are invalid, because they are compiled without using `mcpyrate`. This prevents the installed package from running. It will report that it can't find `macros`. To make things worse, a regular user won't be able to remove the bytecode cache files, which are owned by `root`.

In order to fix this problem, you must provide a custom `postinst` script that generates the cache files using `mcpyrate`. One possible solution is to invoke the script in a way that all, or at least most, of the modules are imported. This will force the generation of the bytecode cache files.


# Macro expansion error reporting

In `mcpyrate`, any exception raised during macro expansion is reported immediately at macro expansion time, and the program exits.

The error report includes two source locations: the macro use site (which was being expanded, not running yet), and the macro code that raised the exception (that was running and was terminated due to the exception).

The use site source location is reported in a chained exception (`raise from`), so if the second stack trace is long, scroll back in your terminal to see the original exception that was raised by the macro (including a traceback of where it occurred in the macro code).


## Recommended exception types

We recommend raising:

 - `SyntaxError` with a descriptive message, if there's something wrong with how the macro was invoked, or with the AST layout of the `tree` (or `args`) it got vs. what it was expecting.
 - `TypeError` or a `ValueError`, as appropriate if there is a problem in the macro arguments meant for the macro itself. (As opposed to macro arguments such as in the `let` example, where `args` is just another place to send in an AST to be transformed.)

In general, you can use any exception type as appropriate, except `mcpyrate.core.MacroExpansionError`. This one type gets automatically telescoped (i.e. intermediate stack traces of causes are omitted); it is used internally for generating the use site report when an exception is raised during macro expansion.


## Differences to `macropy`

In `mcpyrate`, `AssertionError` is **not** treated specially; any exception (except `mcpyrate.core.MacroExpansionError`) raised while expanding a macro gets the same treatment.

In `mcpyrate`, all macro-expansion errors are reported immediately at macro expansion time.

The [quasiquote system](quasiquotes.md) **does** report some errors at run time, but it does so only when that's the earliest time possible, e.g. due to needing an unquoted value to become available before its validity can be checked. Note the error is still usually reported at the macro expansion time *of your macro*, which contains the use site of `q`. But it does mean *your macro* must be invoked before such an error can be triggered.
