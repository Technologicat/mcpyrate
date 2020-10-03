# mcpy

Third-generation macro expander for Python, after the pioneering [macropy](https://github.com/lihaoyi/macropy), and the compact, pythonic [original mcpy](https://github.com/delapuente/mcpy).

The design philosophy follows the original `mcpy`: keep things as explicit and compact as reasonably possible. However, the codebase is larger due to having more features. We also tolerate a small amount of extra complexity, if it improves the programmer [UX](https://en.wikipedia.org/wiki/User_experience).

Supports Python 3.6, 3.7, 3.8, and PyPy3.

## Highlights

This fork adds a lot of features over `mcpy` 2.0.0:

- **Agile development**:
  - Universal bootstrapper `macropython`. **Allows your main program to use macros**.
  - Interactive console: `macropython -i`. Use macros in a console session.
    - Embeddable à la `code.InteractiveConsole`, see `mcpy.repl.console.MacroConsole`.
  - IPython extension `mcpy.repl.iconsole`. Use macros in an IPython session.
- **Testing and debugging**:
  - Correct test coverage reported by tools such as [`Coverage.py`](https://github.com/nedbat/coveragepy/).
  - Macro expansion errors are reported at macro expansion time, with use site traceback.
  - Debug output with a step-by-step expansion breakdown. See macro `mcpy.debug.step_expansion`.
  - Manual expand-once.
- **Advanced quasiquoting**:
  - Hygienically interpolate both regular values **and macro names**.
  - Delayed macro expansion inside quasiquoted code.
    - User-controllable, see macros `expand1` and `expand` in `mcpy.quotes`.
    - Expand when you want, or just leave it to `mcpy` to expand automatically once your macro (that uses quasiquoting) returns.
  - Inverse quasiquote operator. See function `mcpy.quotes.unastify`.
    - Convert a quasiquoted AST back into a direct AST, typically for further processing before re-quoting it.
      - Not an unquote; we have those too, but the purpose of unquotes is to interpolate values into quoted code. The inverse quasiquote instead undoes the quasiquote operation itself, after any unquotes have already been applied.
    - Useful for second-order macros that need to process a quasiquoted code section at macro expansion time, before the quasiquoted tree has a chance to run. (As usual, when it runs, it converts itself into a direct AST.)
- **Identifier (a.k.a. name) macros**
  - Can be used for creating magic variables that may only appear inside specific macro invocations, erroring out at macro expansion time if they appear anywhere else.
  - Opt-in. Declare by using the `@mcpy.namemacro` decorator on your macro function. Place it outermost.
- **Conveniences**:
  - The expander automatically fixes missing `ctx` attributes in the AST, so you don't need to care about those in your macros.
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
pip uninstall mcpy
```

but first, make sure you're not in a folder that has an `mcpy` subfolder - `pip` will think it got a folder name instead of a package name, and become confused.


## Using macros

Due to how `mcpy` works, `mcpy` must be explicitly enabled before importing any module that uses macros. Macros must be defined in a separate module. The following classical 3-file setup works fine:

```python
# run.py
import mcpy.activate
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

For interactive macro-enabled sessions, we provide an mcpy-enabled equivalent for `code.InteractiveConsole`, as well as an IPython extension. See the [REPL system documentation](repl.md).


### Syntax

`mcpy` macros can be used in four forms. The first three follow `macropy` syntax:

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

In `mcpy`, macros are just functions. To use functions from `module` as macros, use a *macro-import statement*:

```python
from module import macros, ...
```

replacing `...` with the macros you want to use. Importing all via `*` won't work. You must declare the macros you want explicitly. This syntax tells the macro expander to register macro bindings. The macro bindings are in scope for the module in which the macro-import statement appears.

`mcpy` prevents you from accidentally using macros as regular functions in your code by transforming the macro-import into:

```python
import module
```

The transformed import is always absolute, even if the original macro-import was relative.

This is part of the public API. If the expanded form of your macro needs to refer to `thing` that exists in (whether is defined in, or has been imported to) the global, top-level scope of the module that defines the macro, you can just refer to `module.thing` in your expanded code. This is the `mcpy` equivalent of MacroPy's `unhygienic_expose` mechanism.

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

No special imports are needed to write your own macros. Just consider a macro as a function accepting an AST tree and returning another AST (i.e., a [syntax transformer](http://www.greghendershott.com/fear-of-macros/)). Refer to [Green Tree Snakes](https://greentreesnakes.readthedocs.io/en/latest/nodes.html) (a.k.a. the missing Python AST docs) for more on the AST node types. The documentation for the [AST module](https://docs.python.org/3/library/ast.html) may also be useful.


```python
def macro(tree, **kw): return tree
```

The `tree` parameter is the only positional parameter the macro is called with. All other parameters are passed by name, so you can easily pick what you need (and let `**kw` gather the ones you don't).

Beside a node, you can return `None` to remove the node, or a list of `AST` nodes. The expanded macros are recursively expanded until no new macros are found.

```python
from ast import *
from mcpy import unparse
def log(expr, **kw):
    '''Replace log[expr] with print('expr: ', expr)'''
    label = unparse(expr) + ': '
    return Call(func=Name(id='print', ctx=Load()),
                args=[Str(s=label), expr], keywords=[],
                starargs=None, kwargs=None)
```

Any missing source locations and `ctx` fields are fixed automatically in a postprocessing step, so you don't need to care about those when writing your AST.

If you get an error saying an AST node is missing the mandatory field `lineno`, the actual error is likely something else. This is due to an unfortunate lack of input validation in Python's compiler. The first thing to check is that your macro is really placing AST nodes where the compiler expects those, instead of accidentally using bare values.

*Changed in v3.0.0.* The named parameter `to_source` has been removed; use the function `mcpy.unparse`.

*Changed in v3.0.0.* The named parameter `expand_macros` has been replaced with `expander`, which grants access to the macro expander instance; use `expander.visit_recursively` or `expander.visit_once`, depending on whether you want expansion to continue until no macros remain. Use `expander.visit` to use current setting for recursive mode.

See [`mcpy.core.BaseMacroExpander`](mcpy/core.py) and [`mcpy.expander.MacroExpander`](mcpy/expander.py) for the expander API; it's just a few methods and attributes.

### Quasiquotes

*New in v3.0.0.* We provide [a quasiquote system](quasiquotes.md) (both classical and hygienic) to make macro code both much more readable and simpler to write. It's similar to MacroPy's, but details of usage differ.

### Walk an AST

*New in v3.0.0.* To bridge the feature gap between [`ast.NodeTransformer`](https://docs.python.org/3/library/ast.html#ast.NodeTransformer) and MacroPy's `Walker`, we provide [`mcpy.walker.Walker`](walker.md), a zen-minimalistic AST walker base class based on `ast.NodeTransformer`, with a state stack and a node collector. If you need a walker that can temporarily change state while in a given subtree, maybe look here.

### Distinguish how the macro is called

A macro can be called in four different ways. The way a macro is called is recorded in the `syntax` named parameter (one of `'block'`, `'expr'`, `'decorator'`, or `'name'`), so you can distinguish the syntax used in the source code and provide different implementations for each one. In other words, the macro function acts as a dispatcher for all types of uses of that macro.

When valid macro invocation syntax for one of the other three types is detected, the name part is skipped, and it **does not** get called as an identifier macro. The identifier macro mechanism is invoked only for appearances of the name *in contexts that are not other types of macro invocations*.

The other three work roughly the same as in MacroPy (except that in `mcpy`, a macro invocation **does not** take arguments using function call syntax), so we'll look at just the fourth one, identifier macros.

#### Identifier macros

Identifier macros are a rarely used feature, but one that is indispensable for that rare use case. To avoid clutter in the dispatch logic of most macros, if a macro function wants to be called as an identifier macro, it must explicitly opt in. Declare by using the `@mcpy.namemacro` decorator on your macro function. Place it outermost.

A basic use case of identifier macros is where you just need to paste some boilerplate code without any parameters.

But the main use case why this feature exists is to create magic variables that are allowed to appear only in certain contexts. Pattern:

```python
from mcpy import namemacro
from mcpy.utilities import NestingLevelTracker

_level = NestingLevelTracker()

# a valid context for `it`
def mymacro(tree, syntax, expander, **kw):
    if syntax != "expr":
        raise SyntaxError("`mymacro` is an expr macro only")
    with _level.changed_by(+1):
        tree = expander.visit_recursively(tree)  # this expands any `it` inside
        # Macro code goes here. You'll want it to define an actual
        # run-time `it` for the invocation site to refer to.
        # (But first check from `expander.bindings` what name
        #  our `it` function is actually bound to!)
    return tree

@namemacro
def it(tree, syntax, **kw):
    if syntax != "name":
        raise SyntaxError("`it` is a name macro only")
    if _level.value < 1:
        raise SyntaxError("`it` may only appear within a `mymacro[...]`")
    return tree
```

This way any invalid, stray mentions of the magic variable `it` are promoted to a compile-time error.

If you want to expand only `it` inside an invocation of `mymacro[...]` (thus checking that the mentions are valid), leaving other nested macro invocations untouched, that's also possible. See below how to temporarily run a second expander with different bindings (so you can omit everything but `it`).

If you want to allow using the macro name (i.e. whatever name it's bound to at the use site) of your identifier macro as a run-time variable name, `return tree` without modifying it. This tells the expander - after checking with you that the use was legal - to treat it as a regular name.

Of course, if that's not what you want, you can return any tree you want to replace the original with - after all, an identifier macro is just a macro.


### Get the source of an AST

`mcpy.unparse` is a function that converts an AST back into Python code.

Because the code is backconverted from the AST representation, the result may differ in minute details of surface syntax, such as parenthesization, whitespace, and which quote syntax is used for quoting string literals.


### Expand macros

Use the named parameter `expander` to access the macro expander. You can call `expander.visit_recursively(tree)` with an AST `tree` to expand all macros in that AST, until no macros remain. This is useful for making inner macro invocations expand first.

To expand only one layer of inner macro invocations, call `expander.visit_once(tree)`. This can be useful during debugging of a macro implementation. You can then convert the result into a printable form using `mcpy.unparse` or `mcpy.dump`.

To use the current setting for recursive mode, use `expander.visit(tree)`. The default mode is recursive.

If you need to temporarily run a second expander with different macro bindings, consult `expander.bindings` to grab what you need, and then use `mcpy.expander.expand_macros(tree, modified_bindings, expander.filename)` to invoke a new expander with the modified bindings.


### Macro expansion error reporting

Any exception raised during macro expansion is reported immediately at compile time, and the program exits.

The error report includes two source locations: the macro use site (which was being expanded, not running yet), and the macro code that raised the exception (that was running and was terminated due to the exception).

The use site source location is reported in a chained exception (`raise from`), so if the second stack trace is long, scroll back in your terminal to see the original exception that was raised by the macro.


### Examples

`mcpy` is a macro expander, not a library containing macros. However, we provide a `demo` folder, to see `mcpy` in action. Navigate to it and run a Python console, then import `run`:

```python
import run
```
