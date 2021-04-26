**Navigation**

- **Main user manual**
- [Quasiquotes and `mcpyrate.metatools`](quasiquotes.md)
- [REPL and `macropython`](repl.md)
- [The `mcpyrate` compiler](compiler.md)
- [AST walkers](walkers.md)
- [Dialects](dialects.md)
- [Troubleshooting](troubleshooting.md)

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
    - [Macro-writing utilities in `mcpyrate`](#macro-writing-utilities-in-mcpyrate)
    - [Macro docstrings](#macro-docstrings)
    - [Source location information and `ctx` attributes](#source-location-information-and-ctx-attributes)
    - [Macro invocation types](#macro-invocation-types)
    - [Named parameters filled by expander](#named-parameters-filled-by-expander)
        - [Differences to `mcpy`](#differences-to-mcpy)
    - [Quasiquotes](#quasiquotes)
    - [Get the source of an AST](#get-the-source-of-an-ast)
        - [Syntax highlighting](#syntax-highlighting)
    - [Walk an AST](#walk-an-ast)
    - [Macro arguments](#macro-arguments)
        - [Using parametric macros](#using-parametric-macros)
            - [Multiple macro arguments are a tuple](#multiple-macro-arguments-are-a-tuple)
            - [The two possible meanings of the expression `macroname[a][b]`](#the-two-possible-meanings-of-the-expression-macronameab)
        - [Writing parametric macros](#writing-parametric-macros)
        - [Arguments or no arguments?](#arguments-or-no-arguments)
        - [Differences to `macropy`](#differences-to-macropy)
    - [Identifier macros](#identifier-macros)
        - [Syntax limitations](#syntax-limitations)
        - [Creating a magic variable](#creating-a-magic-variable)
    - [Expand macros inside-out](#expand-macros-inside-out)
    - [Expand macros inside-out, but only those in a given set](#expand-macros-inside-out-but-only-those-in-a-given-set)
- [Multi-phase compilation](#multi-phase-compilation)
- [Dialects](#dialects)
- [Macro expansion error reporting](#macro-expansion-error-reporting)
    - [Recommended exception types](#recommended-exception-types)
    - [Reserved exception type `mcpyrate.core.MacroApplicationError`](#reserved-exception-type-mcpyratecoremacroapplicationerror)
    - [Nested exceptions](#nested-exceptions)
    - [Differences to `macropy`](#differences-to-macropy-1)

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

The only explicit hint at the definition site that a function is actually a macro is the `**kw`.

Refer to [Green Tree Snakes](https://greentreesnakes.readthedocs.io/en/latest/nodes.html) (a.k.a. the missing Python AST docs) for details on the AST node types. The documentation for the [AST module](https://docs.python.org/3/library/ast.html) may also be occasionally useful.

The `tree` parameter is the only positional parameter the macro function is called with. All other parameters are passed by name, so you can easily pick what you need (and let `**kw` gather the ones you don't).

A macro can return a single AST node, a list of AST nodes, or `None`. See [Macro invocation types](#macro-invocation-types) below for details.

The result of the macro expansion is recursively expanded until no new macro invocations are found.

A simple working example:

```python
from ast import Call, Name, Constant
from mcpyrate import unparse

def log(expr, **kw):
    """[syntax, expr] Replace log[expr] with print("expr: ", expr)"""
    label = unparse(expr) + ": "
    return Call(func=Name(id="print"),
                args=[Constant(value=label), expr],
                keywords=[])
```


## Macro-writing utilities in `mcpyrate`

Although you don't strictly have to import anything to write macros, there are some useful functions in the top-level namespace of `mcpyrate`. See `gensym`, `unparse`, `dump`, `@namemacro`, and `@parametricmacro`.

Other modules contain utilities for writing macros:

 - [`mcpyrate.quotes`](../mcpyrate/quotes.py) provides [quasiquote](https://en.wikipedia.org/wiki/Lisp_(programming_language)#Self-evaluating_forms_and_quoting) syntax as macros, to easily build ASTs in your macros, using syntax that mostly looks like regular code. [Documentation](quasiquotes.md).
 - [`mcpyrate.metatools`](../mcpyrate/metatools.py) provides utilities; particularly, to expand macros in run-time AST values, while using the macro bindings from your macro's *definition* site (vs. its *use* site like `expander.visit` does). Useful for quoted trees. [Documentation](quasiquotes.md#the-expand-family-of-macros).
 - [`mcpyrate.utils`](../mcpyrate/utils.py) provides some macro-writing utilities that are too specific to warrant a spot in the top-level namespace; of these, at least `rename` and `flatten` (for statement suites) solve problems that come up relatively often.
 - [`mcpyrate.walkers`](../mcpyrate/walkers.py) provides AST walkers (both visitor and transformer variants) that can context-manage their state for different subtrees, while optionally collecting items across the whole walk. They are based on `ast.NodeVisitor` and `ast.NodeTransformer`, respectively, but with functionality equivalent to `macropy.core.walkers.Walker`. [Documentation](walkers.md).
 - [`mcpyrate.splicing`](../mcpyrate/splicing.py) helps splice statements (or even a complete module body) into a code template. Note in quasiquoted code you can locally splice statements with the block mode of the `a` (ast-unquote) operator.
 - [`mcpyrate.debug`](../mcpyrate/debug.py) may be useful if something in your macro is not working. **See especially the macro `step_expansion`.**


## Macro docstrings

*Docstrings for macros are important.* For convenience, [the REPL system](repl.md) imports each macro-imported macro also as a regular run-time function, precisely so that its docstring and source code can be viewed easily.

Because in `mcpyrate` macros are functions, the docstring should make it explicit that the function is actually a macro. `mcpyrate` itself follows the convention of prefixing the first line of each macro docstring with one of:

```
[syntax, expr]
[syntax, block]
[syntax, decorator]
[syntax, name]
```

or when applicable, a combination such as:

```
[syntax, expr/block]
```

If you're writing a [dialect](dialects.md), and doing something completely wild with something that looks like a macro, then we recommend:

```
[syntax, special]
```

For example, `mcpyrate` itself provides `mcpyrate.debug.step_phases`; its macro-import acts as a flag for the multi-phase compiler, and otherwise that "macro" is unused.

The term *syntax* to denote a macro was inspired by [The Racket Reference](https://docs.racket-lang.org/reference/). In Racket, a macro is *a syntax*, as opposed to *a procedure* a.k.a. garden variety function.


## Source location information and `ctx` attributes

Any missing `ctx` attributes are fixed automatically in a postprocessing step, so you don't need to care about those when writing your AST.

For **source location information**, the recommendation is:

 - If you generate new AST nodes that do not correspond to any line in the original unexpanded source code, **do not fill in their source location information**.
   - For any node whose source location information is missing, the expander will auto-fill it. This auto-fill copies the source location from the macro invocation node. This makes it easy to pinpoint in `unparse` output in debug mode (e.g. for a block macro) which lines originate in the unexpanded source code and which lines were added by the macro invocation.

 - If you generate a new AST node based on an existing one from the input AST, and then discard the original node, **be sure to `ast.copy_location` the original node's source location information to your new node**.
   - For such edits, **it is the macro's responsibility** to ensure correct source location information in the output AST, so that coverage reporting works. There is no general rule that could generate source location information for arbitrary AST edits correctly.

 - If you just edit an existing AST node, just leave its source location information as-is.

What we can do automatically, and what `mcpyrate` indeed does, is to make sure that *the line with the macro invocation* shows as covered, on the condition that the macro was actually invoked.


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


## Named parameters filled by expander

When calling a macro function to expand a macro, the expander passes certain named arguments to the macro function. Any unused ones are gathered by the macro function's `**kw` parameter.

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


## Quasiquotes

[[full documentation](quasiquotes.md)]

We provide a [quasiquote system](https://en.wikipedia.org/wiki/Lisp_(programming_language)#Self-evaluating_forms_and_quoting) (both classical and hygienic) to make macro code both much more readable and simpler to write.

Rewriting the above example, note the `ast` import is gone:

```python
from mcpyrate import unparse
from mcpyrate.quotes import macros, q, u, a

def log(expr, **kw):
    """[syntax, expr] Replace log[expr] with print("expr: ", expr)"""
    label = unparse(expr) + ": "
    return q[print(u[label], a[expr])]
```

Here `q[]` quasiquotes an expression, `u[]` unquotes a simple value, and `a[]` unquotes an expression AST. If you're worried that `print` may refer to something else at the use site of `log[]`, you can hygienically capture the function with `h[]`: `q[h[print](u[label], a[expr])]`.

If you are familiar with `macropy`'s quasiquotes, be aware that there are some important differences; see [differences to `macropy`](quasiquotes.md#differences-to-macropy).


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

#### Multiple macro arguments are a tuple

In `mcpyrate`, in the AST, multiple macro arguments are always represented as an
`ast.Tuple`. This is because in Python's surface syntax, a bare comma (without
surrounding parentheses or brackets that belong to that comma) creates a tuple,
and the brackets around the macro argument list actually belong to the subscript
expression.

So comma-separating macro arguments naturally encodes them as a tuple. These are
exactly the same:

```python
macroname[arg0, ...][...]
macroname[(arg0, ...)][...]
```

But if you use extra brackets to make a list, that whole list is treated a single macro argument.

If you need to pass a tuple as a single macro argument, wrap it in another tuple:

```python
macroname[((a, b, c),)][...]
macroname[(a, b, c),][...]
```

These are exactly the same, because a bare comma creates a tuple. The outer tuple
is interpreted by the macro expander to mean *multiple macro arguments*, and then
the inner tuple gets passed as a single macro argument.


#### The two possible meanings of the expression `macroname[a][b]`

Observe that the syntax `macroname[a][b]` may mean one of two different things:

  - If `macroname` is parametric, a macro invocation with `args=[a]`, `tree=b`.

  - If `macroname` is **not** parametric, first a macro invocation with `tree=a`,
    followed by a subscript operation on the result.

    Whether that subscript operation is applied at macro expansion time
    or at run time, depends on whether `macroname[a]` returns an AST for
    a `result`, for which `result[b]` can be interpreted as an invocation
    of a macro that is bound in the use site's macro expander.

    (This is exploited by the hygienic unquote operator `h`, when it is applied
    to a macro name. The trick is, `h` takes no macro arguments. So `h[mymacro][...]`
    means hygienify the `mymacro` reference, and then use that in `mymacro[...]`.)


### Writing parametric macros

To declare a macro parametric, use the `@parametricmacro` decorator on your macro function. It can be imported from the top-level namespace of `mcpyrate`. Place it outermost (along with `@namemacro`, if used too).

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
that rare use case. The main reason this feature exists is to allow creating
magic variables that may appear only in certain contexts.

To be eligible to be called as an identifier macro, a macro must be declared as
an identifier macro. Declare by using the `@namemacro` decorator on your macro
function. It can be imported from the top-level namespace of `mcpyrate`. Place
it outermost (along with `@parametricmacro`, if used too).

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

Of course, if you want to use this feature for something else, you can return
any expression AST you want to replace the `Name` node with - after all, an
identifier macro is just a macro, and an identifier is just a special kind of
expression. `mcpyrate` itself provides some identifier macros that have nothing
to do with magic variables; see [`mcpyrate.debug.show_bindings`](../mcpyrate/debug.py)
and [`mcpyrate.metatools.macro_bindings`](../mcpyrate/metatools.py).

### Syntax limitations

The run-time result of an identifier macro cannot be subscripted in place, because the syntax to do that looks like an `expr` macro invocation. If you need to do that, first assign the result to a temporary variable, and then subscript that.

### Creating a magic variable

It is useful to be able to create a magic expr macro or magic name (a.k.a. *magic variable*) that may appear only in certain surrounding contexts. These contexts are often other macro invocations. If the magic thing occurs anywhere else, we would like it to trigger a compile-time error, to facilitate [fail-fast](https://en.wikipedia.org/wiki/Fail-fast).

There are two main strategies to achieve this, depending on what you need:

 1. **The magic thing, when it appears in a valid context, is never intended to hit the macro expander.** It only acts as a pattern in the AST, to be matched and manually transformed away by the surrounding macro.

    In this case, you can just make a regular expr macro or name macro that unconditionally raises `SyntaxError`, with a descriptive message. The unconditional error ensures that if the magic thing occurs outside a valid context, the error is reported at compile time (strictly speaking, at macro expansion time, when the expander attempts to expand that macro).

    In `macropy`, this was done by introducing a `@macro_stub`. **In `mcpyrate`, just make a regular macro, which explicitly raises an error.**

    The limitation is the same in both expanders: the compile-time error can only be generated if the magic macro (whose sole purpose is to error out) is loaded into the expander's bindings, so that the expander will attempt to expand any misplaced mentions of it.

    So, it is important to mention in your docs that whenever your user intends to use whatever macro is the valid context for your magic thing, they should import both the context macro and the magic macro.

 2. **The magic thing is intended to be expanded normally, by the macro expander.** In this case, the macro must be able to expand normally when it appears in a valid context, but it must error out when it appears anywhere else.

    This requires the context and magic macros to work together to some extent. **It also relies on an outside-in expansion order.** The context macro (which expands first, because it is on the outside) should manipulate some appropriate global state, and then explicitly recurse to expand any mentions of the magic macro inside the lexical extent controlled by that context (i.e. inside the AST it got as its `tree` argument). You can store the state at the top level of the macro definition module, so both macros have access to it.

    This strategy has the advantage that the magic macro has access to all features of the macro expander. This is convenient especially if it needs to take macro arguments, because then you don't have to destructure the AST yourself, and your magic macro is guaranteed to always support the same argument passing syntax as any other macro. This also allows better modularity, since the magic macro can be separated from the implementation of the surrounding context.

    The quasiquote system in `mcpyrate` uses this strategy for the unquote operators; they are macros in their own right, but they are only allowed to occur when inside at least one level of quasiquoting.

    A special case worth mentioning is when a name, that is **not** intended to be transformed away, is only allowed to appear in certain contexts. Anaphoric if's `it` is an example. There is a special feature in `mcpyrate` that was made specifically for this use case: in a name macro, you can `return tree` to tell the expander to consider that particular occurrence done, while leaving the name node as-is. (Technically, it will be wrapped with a `Done` AST marker, so that the expander won't visit it further.) So when the magic macro expands, it can look at the global state (that is managed by its context macro), and then decide whether to `return tree` or error out.

Here's a sketch of the pattern for the last case. We have chosen this example, because it's probably the most difficult to get right:

```python
from mcpyrate import namemacro
from mcpyrate.utils import NestingLevelTracker

_mymacro_level = NestingLevelTracker()

def mymacro(tree, *, syntax, expander, **kw):
    """[syntax, expr] The construct where the magic variable `it` may appear."""
    if syntax != "expr":
        raise SyntaxError("`mymacro` is an expr macro only")
    # The global state should be managed using a context manager,
    # so that even if things go south, the state always resets properly.
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

This way any invalid, stray mentions of the magic variable `it` trigger an error at macro expansion time. This isn't quite Racket's [`syntax-parameterize`](https://docs.racket-lang.org/reference/stxparam.html), but this'll do for Python.

If you want to expand only `it` inside an invocation of `mymacro[...]` (thus checking that the mentions are valid), leaving other nested macro invocations untouched, that's also possible - and strongly recommended! See below how to expand only macros in a given set, from which you can omit everything but `it`.

The above example code is slightly simplified; look at [`demo/anaphoric_if.py`](../demo/anaphoric_if.py) for actual working code.


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
    - The `extract_bindings` function from [`mcpyrate.utils`](../mcpyrate/utils.py) can grab the relevant bindings for you. Usage is `modified_bindings = extract_bindings(expander.bindings, mymacro0, mymacro1, ...)`.
    - If you need to do the same on the expander from the macro expansion time of your macro definition (not the expander of your macro's *use site*, which is what the `expander` named argument refers to), see [`mcpyrate.metatools`](../mcpyrate/metatools.py), particularly the name macro `macro_bindings`. That will evaluate, at your macro's run time, to a snapshot of the bindings from the time the invocation of `macro_bindings` was macro-expanded. You can feed that snapshot to `extract_bindings`.
 3. In your macro, call `MacroExpander(modified_bindings, expander.filename).visit(tree)` to invoke a new expander instance with the modified bindings.

The implementation of the quasiquote system has an example of this. See also [demo/anaphoric_if.py](../demo/anaphoric_if.py), for how it expands the anaphoric `it`.

Obviously, if you want to expand just one layer with the second expander, use its `visit_once` method instead of `visit`. (And if you do that, you'll need to decide if you should keep the `Done` marker - to prevent further expansion in that subtree - or discard it and grab the real AST from its `body` attribute.)


# Multi-phase compilation

[[full documentation](compiler.md#multi-phase-compilation)]

*Multi-phase compilation*, a.k.a. *staging*, allows to use macros in the same module where they are defined. You can have multiple phases, each defining macros for the still remaining phases. Phases only exist internally in a module while that module is being compiled. When a module imports some other module, that other module is always imported in its final ("phase 0") state.

To aid debugging multi-phase modules, there is a facility to view the unparsed source code of each phase just before it is fed into the compiler.

For details, see the full documentation. For examples, look at the [anaphoric if](../demo/anaphoric_if.py) and [let](../demo/let.py) demos.


# Dialects

[[full documentation](dialects.md)]

Dialects are essentially *whole-module source and AST transformers*. Think [Racket's](https://racket-lang.org/) `#lang`, but for Python. Source transformers are akin to *reader macros* in the Lisp family.

Dialects allow you to define languages that use Python's surface syntax, but change the semantics; or let you plug in a per-module transpiler that (at import time) compiles source code from some other programming language into macro-enabled Python. Also an AST [optimizer](http://compileroptimizations.com/) could be defined as a dialect.


# Macro expansion error reporting

In `mcpyrate`, any exception raised during macro expansion is reported immediately at macro expansion time, and the program exits.

The error report includes two source locations: the macro code that raised the exception (that was running and was terminated due to the exception), and the macro use site (which was being expanded, not running yet).

The use site source location is reported in a chained exception (`raise from`). Note that the use site report may show the unparsed source code in a partially macro-expanded state, depending on when the exception occurred.

Each code snippet is shown as it was after the last successful macro expansion, i.e. just before the error occurred. This helps debug macros that output invocations of other macros, so you can see which step is failing. (If needed, use the macro `mcpyrate.debug.step_expansion` to show the successful steps, too.)

`mcpyrate` aims to produce compact error reports when an error occurs in a syntax transformer during macro expansion. Still, if a particular stack trace happens to be long, or if the report contains many chained exceptions, then as usual, scroll back in your terminal to see the details.


## Recommended exception types

For errors detected **at macro expansion time**, we recommend raising:

 - `SyntaxError` with a descriptive message, if there's something wrong with how the macro was invoked, or with the AST layout of the `tree` (or `args`) it got vs. what it was expecting.
 - `TypeError` or `ValueError` as appropriate, if there is a problem in the macro arguments meant for the macro itself. (As opposed to macro arguments such as in the `let` demo, where `args` is just another place to send in an AST to be transformed.)
 - `mcpyrate.core.MacroExpansionError`, or a custom descendant of it, if something else macro-related went wrong.

Some operations represented by a macro may inject a call to a run-time part of that operation itself (e.g. the [quasiquote system](quasiquotes.md) does this). For errors detected **at run time of the use site**:

 - Use whichever exception type you would in regular Python code that doesn't use macros. For example, a `TypeError`, `ValueError` or `RuntimeError` may be appropriate.


## Reserved exception type `mcpyrate.core.MacroApplicationError`

Generally speaking, for reporting errors in your macro-related code, you can use any exception type as appropriate, except `mcpyrate.core.MacroApplicationError`, which is **reserved for the expander core**.

This is not to be confused with `mcpyrate.core.MacroExpansionError`, which is just fine to use. The public API of `mcpyrate.core` reflects this; `MacroExpansionError` is considered public, whereas `MacroApplicationError` is not.

The type `mcpyrate.core.MacroApplicationError` is automatically used for reporting errors during macro expansion, when an exception propagates from a macro function into the expander that was calling that macro function. The name means **error detected while a macro was being applied** (it has nothing to do with the other sense of *application*, as in a program).

`MacroApplicationError` instances undergo some special processing. The expander automatically telescopes them: intermediate stack traces of causes are omitted, and the macro use site messages are combined.

Furthermore, if the program is being run through the `macropython` wrapper, `macropython` will strip most of the traceback for `MacroApplicationError` (for this one exception type only!), because that traceback is typically very long, and speaks (only) of things such as `macropython` itself, the importer, and the macro expander. The actually relevant tracebacks, for the client code, are contained within the linked (`__cause__`, *"The above exception was the direct cause..."*) exceptions.


## Nested exceptions

In macros, it is especially important to focus on the clarity of the error report when using nested exceptions, because a basic macro-expansion error report itself already consists of two parts: the macro code that raised the error, and the macro use site.

Any nested exceptions add more parts to the start of the chain. This, in turn, buries the report for the final problem location in the macro code into the middle of the full error report (as the second-last item, just before the macro use site report that is always last). This may make the error report harder to read.

So, if you use nested exceptions:

 - If the original exception is relevant *to the user* of your macro, then it's fine - use `raise ... from ...` to report it, too.
 - If the original exception is internal to your macro implementation (and you don't need its traceback for issue reports against your own code), then just `raise ...`.

In the second case, sometimes, hiding the original exception makes for a clearer traceback. There are two main ways to do this. The first one is to raise the user-relevant exception outside the original `except` block, to break the exception context chain:

```python
success = True
try:
    epic_fail()
except SomeInternalException:
    success = False
if not success:
    raise SomeRelevantException(...)
```

That, however, completely loses the original context. It is better to leave it available for introspection in the exception instance's `__context__` magic attribute (so that it can be accessed by a post-mortem debugger, or logged), but tell Python that you don't want it printed in the traceback:

```python
try:
    epic_fail()
except SomeInternalException:
    err = SomeRelevantException(...)
    err.__suppress_context__ = True
    raise err
```

This makes Python skip printing the `SomeInternalException`, as well as suppresses the *"During handling of the above exception, another exception occurred"* message belonging to that exception. See [the exception docs](https://docs.python.org/3/library/exceptions.html).

`mcpyrate` itself uses this pattern in some places.


## Differences to `macropy`

In `mcpyrate`, `AssertionError` is **not** treated specially; any instance of `Exception` (except `mcpyrate.core.MacroApplicationError`) raised while expanding a macro gets the same treatment.

In `mcpyrate`, all macro-expansion errors are reported immediately at macro expansion time.

The [quasiquote system](quasiquotes.md) **does** report some errors at run time, but it does so only when that's the earliest time possible, e.g. due to needing an unquoted value to become available before its validity can be checked. Note the error is still usually reported at the macro expansion time *of your macro*, which contains the use site of `q`. But it does mean *your macro* must be invoked before such an error can be detected.
