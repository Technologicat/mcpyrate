# mcpy

A small and compact Python 3 library to enable syntactic macros at import time, strongly inspired by [macropy](https://github.com/lihaoyi/macropy).

## Install

Install from PyPI:

```
# pip install mcpy
```

## Using macros
Due to mcpy macro extension procedure, you need to enable `mcpy` before importing the modules using macros and in a separated file. The following 3 file setup works fine for most of the cases:

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

### Syntax

`mcpy` macros can be used in three forms, following `macropy` syntax:

```python
# block form
with macro:
  ...

# expression form
macro[...]

# decorator form
@macro
...
```

In each case, the macro will receive `...` as input and will replace the invocation with the expanded content. Expansion occurs first for outermost nodes. I.e, from outside to inside.

### Importing macros

Macros are simple functions. To use functions from a module as macros, use:

```python
from module import macros, ...
```

replacing `...` with the macros you want to use. Importing all via `*` won't work. You must declare the macros you want explicitly. `mcpy` prevents you from accidentally using macros as functions in your code by transforming that import into:

```pyhon
import module
```

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
No special imports are needed to write your own macros. Just read the documentation for the [AST module](https://docs.python.org/3.5/library/ast.html) and consider a macro as a function accepting an AST tree and returning another AST.

```python
def macro(tree, **kw): return tree
```

The `tree` parameter is the only positional parameter the macro is called with. Remaining parameters are called by name and includes a set of useful functionality.

Beside a node, you can return `None` to remove the node, or a list of `AST` nodes. The expanded macros are recursively expanded until no new macros are found.

```python
from ast import *
def log(expr, to_source, **kw):
    '''Replaces log[expr] with print('expr: ', expr)'''
    label = to_source(expr) + ': '
    return Call(func=Name(id='print', ctx=Load()),
                args=[Str(s=label), expr], keywords=[],
                starargs=None, kwargs=None)
```

### Distinguish how the macro is called

A macro can be called in three different ways. The way a macro is called is recorded in the `syntax` named parameter (one of `'block'`, `'expr'` or '`decorator`'), so you can distinguish the syntax used in the source code and provide different implementations for each one.

### Getting the source of an AST

A macro is passed a named parameter `to_source`, which is a function able to get the Python code for an AST.

### Expand macros

Use the named parameter `expand_macros` with an AST to expand the macros in that AST. This is useful to expand innermost macros first.

### Examples

`mcpy` focuses on the mechanisms to expand macros, not in authoring tools or macro libraries. Anyway, a `demo` folder is provided to see `mcpy` in action. Simply navigate to it and run a Python console, then import `run`:

```python
import run
```
