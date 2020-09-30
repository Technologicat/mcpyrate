# REPL system for mcpy

We provide:

- [``mcpy.repl.iconsole``](#ipython-extension), IPython extension. **Use macros in the IPython REPL**.

- [``mcpy.repl.console.MacroConsole``](#macroconsole), a macro-enabled equivalent of ``code.InteractiveConsole``. **Embed a REPL that supports macros**.

- [``macropython``](#bootstrapper), a generic bootstrapper for macro-enabled Python programs. **Use macros in your main program**.

These are based on [`imacropy`](https://github.com/Technologicat/imacropy).


## IPython extension

The extension allows to **use macros in the IPython REPL**. (*Defining* macros in the REPL is currently not supported.)

For example:

```ipython
In [1]: from mcpy.quotes import q

In [2]: q[42]
Out[2]: <ast.Num object at 0x7f4c97230e80>
```

Macro docstrings and source code can be viewed using ``?`` and ``??``, as usual.

The line magic `%macros` shows macros currently imported to the session (or says that no macros are imported, if so).

Each time a ``from module import macros, ...`` is executed in the REPL, just before invoking the macro expander, the system reloads ``module``, to always import the latest macro definitions.

Hence, semi-live updates to macro definitions are possible: hack on your macros, re-import the macros, and try out the new version in the REPL. No need to restart the REPL session in between.

But note that only the macros you explicitly import again will be refreshed in the session.


### Loading the extension

To load the extension once, ``%load_ext mcpy.repl.iconsole``.

To autoload it when IPython starts, add the string ``"mcpy.repl.iconsole"`` to the list ``c.InteractiveShellApp.extensions`` in your ``ipython_config.py``. To find the config file, ``ipython profile locate``.

When the extension loads, it imports ``mcpy`` into the REPL session. You can use this to debug whether it is loaded, if necessary.

Currently **no startup banner is printed**, because extension loading occurs after IPython has already printed its own banner. We cannot manually print a banner, because some tools (notably ``importmagic.el`` for Emacs, included in [Spacemacs](http://spacemacs.org/)) treat the situation as a fatal error in Python interpreter startup if anything is printed (and ``ipython3 --no-banner`` is rather convenient to have as the python-shell, to run IPython in Emacs's inferior-shell mode).


## MacroConsole

This is a derivative of, and drop-in replacement for, ``code.InteractiveConsole``, which allows you to **embed a REPL that supports macros**. This offers the same semantics as the IPython extension.

Main features of `mcpy.repl.console.MacroConsole`:

 - IPython-like `obj?` and `obj??` syntax to view the docstring and source code of `obj`.
 - The command `macros?` shows macros currently imported to the session.
 - Catches and reports import errors when importing macros.
 - Allows importing the same macros again in the same session, to refresh their definitions.
   - When you `from module import macros, ...`, this console automatically first reloads `module`, so that a macro import always sees the latest definitions.
 - Makes viewing macro docstrings easy.
   - When you import macros, beside loading them into the macro expander, the console automatically imports the macro functions as regular runtime objects. They're functions, so just look at their `__doc__`.

Example:

```python
from mcpy.repl.console import MacroConsole
m = MacroConsole()
m.interact()
```

Now we're inside a macro-enabled REPL:

```python
from mcpy.quotes import macros, q
q[42]  # --> <ast.Num object at 0x7f4c97230e80>
```

Just like in `code.InteractiveConsole`, exiting the REPL (Ctrl+D) returns from the `interact()` call.

Macro docstrings and source code can be viewed like in IPython:

```python
q?
q??
```

If the information is available, these operations also print the filename and the starting line number of the definition of the queried object in that file.

The ``obj?`` syntax is shorthand for ``mcpy.repl.util.doc(obj)``, and ``obj??`` is shorthand for ``mcpy.repl.util.sourcecode(obj)``.

The literal command `macros?` shows macros currently imported to the session (or says that no macros are imported, if so). This shadows the `obj?` docstring lookup syntax if you happen to define anything called `macros` (`mcpy` itself doesn't), but that's likely not needed. That can still be invoked manually, using `mcpy.repl.util.doc(macros)`.


## Bootstrapper

The bootstrapper has two roles:

 - It allows starting a **macro-enabled interactive Python interpreter** directly from the shell.
 - It **allows your main program to use macros**.


### Interactive mode

Interactive mode (command-line option `-i`) starts a **macro-enabled interactive Python interpreter**, using `mcpy.repl.console.MacroConsole`. The [readline](https://docs.python.org/3/library/readline.html) and [rlcompleter](https://docs.python.org/3/library/rlcompleter.html) modules are automatically activated and connected to the REPL session, so the command history and tab completion features work as expected, pretty much like in the standard interactive Python interpreter.

The point of this feature is to conveniently allow starting a macro-enabled REPL directly from the shell. In interactive mode, the filename and module command-line arguments are ignored.

If `-p` is given in addition to `-i`, as in `macropython -pi`, the REPL starts in **pylab mode**. This automatically performs `import numpy as np`, `import matplotlib.pyplot as plt`, and activates matplotlib's interactive mode, so plotting won't block the REPL. This is somewhat like IPython's pylab mode, but we keep stuff in separate namespaces. This is a convenience feature for scientific interactive use.

**CAUTION**: As of v3.0.0, history is not saved between sessions. This may or may not change in a future release.


### Bootstrapping a script or a module

In this mode, the bootstrapper imports the specified file or module, pretending its ``__name__`` is ``"__main__"``. **This allows your main program to use macros**.

For example, ``example.py``:

```python
from mcpy.quotes import macros, q

def main():
    x = q[42]
    print("All OK")

if __name__ == "__main__":
    main()
```

Start it as:

```bash
macropython example.py
```

A relative path is ok, as long as it is under the current directory. Relative paths including ``..`` are **not** supported. We also support the ``-m module_name`` variant:

```bash
macropython -m example
```

A dotted module path under the current directory is ok.

If you need to set other Python command-line options:

```bash
python3 <your options here> $(which macropython) -m example
```

This way the rest of the options go to the Python interpreter itself, and the ``-m example`` to the ``macropython`` bootstrapper.
