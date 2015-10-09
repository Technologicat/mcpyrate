# mcpy
A small and compact Python 3 library to enable syntactic macros at importing time strongly inspired by [macropy](https://github.com/lihaoyi/macropy).

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

# mymacros.py with your macros definitions
def echo(expr, **):
  print('Echo')
  return expr

# application.py 
from mymacros import macros, echo
echo[6*7]
```

### Syntax
`mcpy` macros can be used in three forms following `macropy` syntax:

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

For each case, the macro will receive `...` as input and will replace the invokation with the expanded content. Expansion occurs first for innermost nodes.

### Importing macros
Macros are simple functions. To use functions from a module as macros, use:

```python
from module import macros, ...
```

Replacing `...` with the macros you want to use. Importing all via `*` won't work. You must declare the macros you want explicitely. `mcpy` prevents you from accidentally using macros as functions in your code by transforming that import into:

```pyhon
import module
```

If you want to use some of your macros as regular functions, simply use:

```python
form module import ...
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
No special imports are needed to write your own macros. Just read the documentation for the [AST module](https://docs.python.org/3.5/library/ast.html) and consider a macro as a function accepting an AST and returning another AST.

```python
from ast import *
from mcpy import unparse
def log(expr, **kw):
    '''Replaces log[expr] with print('expr: ', expr)'''
    label = unparse(expr) + ': '
    return Call(func=Name(id='print', ctx=Load()),
                args=[Str(s=label), expr], keywords=[], starargs=None,
                kwargs=None)
```

Instead of a node, you can return `None` to remove the node or a list of `AST` nodes. The expanded macros are recursively expanded until no new macros are found.

### Examples
`mcpy` focuses on the mechanisms to expand macros, not in authoring tools or macros libraries. Anyway, a `demo` folder is provided to see `mcpy` in actions. Simply navigate to it and run a Python console, then import `run`:

```python
import run
```
