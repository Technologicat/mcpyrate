# mcpy

A small and compact Python 3 library to enable syntactic macros at import time, strongly inspired by [macropy](https://github.com/lihaoyi/macropy).

## Install

Install from PyPI:

```
# pip install mcpy
```

## Using macros

Due to how `mcpy` works, you need to enable `mcpy` before importing any module that uses macros. Macros must be defined in a separate module. The following 3 file setup works fine for most cases:

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

### REPL

For interactive macro-enabled sessions, we provide an mcpy-enabled equivalent for `code.InteractiveConsole`, as well as an IPython extension. See the [REPL system documentation](repl.md).

### Syntax

`mcpy` macros can be used in four forms, the first three following `macropy` syntax:

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

Macros are simple functions. To use functions from a module as macros, use:

```python
from module import macros, ...
```

replacing `...` with the macros you want to use. Importing all via `*` won't work. You must declare the macros you want explicitly. `mcpy` prevents you from accidentally using macros as functions in your code by transforming that import into:

```python
import module
```

This also implies that if the expanded form of your macro needs to refer to `thing` that exists in (whether is defined in, or has been imported to) the global scope of the module that defines the macro, just make your expansion refer to `module.thing`. Hence `mcpy` does not need an `unhygienic_expose` mechanism.

If your expansion needs to refer to some other value from the macro definition site (including local and nonlocal variables), see [the quasiquote system](quasiquotes.md), specifically the `h[]` (hygienic-unquote) operator.

If you want to use some of your macros as regular functions, simply use:

```python
from module import ...
```

Or use fully qualified names for them:

```python
module.macroname
```

If the name of a macro conflicts with a name you can provide an alias for the macro:

```python
from module import macros, macroname as alias
```

## Writing macros

No special imports are needed to write your own macros. Just read the documentation for the [AST module](https://docs.python.org/3/library/ast.html) and consider a macro as a function accepting an AST tree and returning another AST (i.e., a [syntax transformer](http://www.greghendershott.com/fear-of-macros/)). Refer to [Green Tree Snakes](https://greentreesnakes.readthedocs.io/en/latest/nodes.html) (a.k.a. the missing Python AST docs) for more on the AST node types.

```python
def macro(tree, **kw): return tree
```

The `tree` parameter is the only positional parameter the macro is called with. Remaining parameters are called by name and include a set of useful functionality.

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

If you get an error saying an AST node is missing the mandatory field `lineno`, the actual error is likely something else. The first thing to check is that your macro is really inserting AST nodes where the compiler expects those, instead of accidentally inserting bare values.

*Changed in v3.0.0.* The named parameter `to_source` has been removed; use the function `mcpy.unparse`. The named parameter `expand_macros` has been replaced with `expander`, which grants access to the macro expander instance; use `expander.visit_recursively` or `expander.visit_once`, depending on whether you want expansion to continue until no macros remain. (Use `expander.visit` to use current setting for recursive mode.)

See [`mcpy.core.BaseMacroExpander`](mcpy/core.py) and [`mcpy.expander.MacroExpander`](mcpy/expander.py) for the expander API; it's just a few methods and attributes.

### Quasiquotes

*New in v3.0.0.* We provide [a quasiquote system](quasiquotes.md) (both classical and hygienic) to make macro code both much more readable and simpler to write. It's similar to MacroPy's, but details of usage differ.

### Walk an AST

*New in v3.0.0.* To bridge the feature gap between [`ast.NodeTransformer`](https://docs.python.org/3/library/ast.html#ast.NodeTransformer) and MacroPy's `Walker`, we provide [`mcpy.walker.Walker`](walkers.md), a zen-minimalistic AST walker base class based on `ast.NodeTransformer`, with a state stack and a node collector. If you need a walker that can temporarily change state while in a given subtree, maybe look here.

### Distinguish how the macro is called

A macro can be called in three different ways. The way a macro is called is recorded in the `syntax` named parameter (one of `'block'`, `'expr'`, `'decorator'`, or `'name'`), so you can distinguish the syntax used in the source code and provide different implementations for each one. In other words, the macro interface acts as the dispatcher.

### Get the source of an AST

`mcpy.unparse` is a function that converts an AST back into Python code.

Because the code is backconverted from the AST representation, the result may differ in minute details of surface syntax, such as parenthesization, and which quote syntax is used for quoting string literals.

### Expand macros

Use the named parameter `expander` to access the macro expander. You can call `expander.visit_recursively(tree)` with an AST `tree` to expand all macros in that AST, until no macros remain. This is useful for making inner macro invocations expand first.

To expand only one layer of inner macro invocations, call `expander.visit_once(tree)`. This can be useful during debugging of a macro implementation. You can then convert the result into a printable form using `mcpy.unparse` or `mcpy.ast_aware_repr`.

To use the current setting for recursive mode, use `expander.visit(tree)`. The default mode is recursive.

If you need to temporarily run a second expander with different macro bindings, see `expander.bindings`, `expander.filename` and use `mcpy.expander.expand_macros` to instantiate a new expander with the desired bindings. Then use its `visit` method.

### Macro expansion error reporting

An exception raised during macro expansion is reported immediately, and the program exits.

The error report includes two source locations: the macro use site (which was being expanded, not running yet), and the macro code that raised the exception (that was running and was terminated due to the exception).

The use site source location is reported in a chained exception (`raise from`), so if the second stack trace is long, scroll back in your terminal to see the original exception that was raised by the macro.

### Examples

`mcpy` is a macro expander, not a library containing macros. But a `demo` folder is provided, to see `mcpy` in action. Navigate to it and run a Python console, then import `run`:

```python
import run
```
