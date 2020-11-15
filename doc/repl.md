# REPL system for mcpyrate

`mcpyrate`'s REPL system is a more advanced development based on the prototype that appeared as [`imacropy`](https://github.com/Technologicat/imacropy).

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [REPL system for mcpyrate](#repl-system-for-mcpyrate)
    - [`mcpyrate.repl.iconsole`, the IPython extension](#mcpyraterepliconsole-the-ipython-extension)
        - [Loading the extension](#loading-the-extension)
    - [`mcpyrate.repl.console.MacroConsole`, the macro-enabled embeddable REPL](#mcpyratereplconsolemacroconsole-the-macro-enabled-embeddable-repl)
    - [`macropython`, the universal bootstrapper](#macropython-the-universal-bootstrapper)
        - [Starting a macro-enabled REPL from the shell](#starting-a-macro-enabled-repl-from-the-shell)
        - [Running a macro-enabled main program](#running-a-macro-enabled-main-program)
    - [Questions & Answers](#questions--answers)
        - [`@macro` is convenient, why is it only available in the REPL?](#macro-is-convenient-why-is-it-only-available-in-the-repl)

<!-- markdown-toc end -->


## `mcpyrate.repl.iconsole`, the IPython extension

The extension **macro-enables the IPython REPL**.

For example:

```ipython
In [1]: from mcpyrate.quotes import q

In [2]: q[42]
Out[2]: <ast.Num object at 0x7f4c97230e80>
```

Macro docstrings and source code can be viewed using ``?`` and ``??``, as usual.

The line magic `%macros` shows the current macro bindings in the session.

The cell magic `%%dump_ast` shows the AST representation of a whole input cell.

The magic function `macro(f)` binds function `f` as a macro in the current REPL session, so you can interactively develop macros right there in the REPL. It works also as a decorator. The new macro will be available from the **next** REPL input onward. You can also use the *self-macro-import* syntax, `from __self__ import macros, f`, to achieve the same effect.

Each time a ``from module import macros, ...`` (when `module` is anything other than the literal `__self__`) is executed in the REPL, just before invoking the macro expander, the system reloads ``module``, to always import the latest macro definitions.

Hence, semi-live updates to macro definitions are possible: hack on your macros, re-import the macros, and try out the new version in the REPL. No need to restart the REPL session in between.

But note that only the macros you explicitly import again will be refreshed in the session.

Each time after importing macros, the macro functions are automatically imported as regular Python objects. Note only the REPL does this; normally, in `mcpyrate` macros are not imported as run-time objects.

The intention is to allow viewing macro docstrings and source code easily in the REPL session, using ``some_macro?``, ``some_macro??``.

This does not affect using the macros in the intended way, as macros.


### Loading the extension

To load the extension once, ``%load_ext mcpyrate.repl.iconsole``.

To autoload it when IPython starts, add the string ``"mcpyrate.repl.iconsole"`` to the list ``c.InteractiveShellApp.extensions`` in your ``ipython_config.py``. To find the config file, ``ipython profile locate``.

In your IPython configuration, make sure `c.TerminalInteractiveShell.autocall = 0`. Expression macro invocations will not work in the REPL if autocall is enabled, because in `mcpyrate` macros are functions, and the REPL imports those functions so you can easily view their docstrings.

Currently **no startup banner is printed**, because extension loading occurs after IPython has already printed its own banner. We cannot manually print a banner, because some tools (notably ``importmagic.el`` for Emacs, included in [Spacemacs](http://spacemacs.org/)) treat the situation as a fatal error in Python interpreter startup if anything is printed.


## `mcpyrate.repl.console.MacroConsole`, the macro-enabled embeddable REPL

This is a derivative of, and drop-in replacement for, ``code.InteractiveConsole``, which allows you to **embed a REPL that supports macros**. This offers the same semantics as the IPython extension.

For example:

```python
from mcpyrate.repl.console import MacroConsole
m = MacroConsole()
m.interact()
```

Now we're inside a macro-enabled REPL:

```python
from mcpyrate.quotes import macros, q
q[42]  # --> <ast.Num object at 0x7f4c97230e80>
```

Just like in `code.InteractiveConsole`, exiting the REPL (Ctrl+D) returns from the `interact()` call.

Similarly to IPython, `obj?` shows obj's docstring, and `obj??` shows its source code. We define two utility functions for this: `doc` and `sourcecode`. The syntax ``obj?`` is shorthand for ``mcpyrate.repl.utils.doc(obj)``, and ``obj??`` is shorthand for ``mcpyrate.repl.utils.sourcecode(obj)``. If the information is available, these operations also print the filename and the starting line number of the definition of the queried object in that file.

The command `macros?` shows the current macro bindings in the session. This shadows the `obj?` docstring lookup syntax if you happen to define anything called `macros` (`mcpyrate` itself doesn't), but that's likely not needed. That can still be invoked manually, using `mcpyrate.repl.utils.doc(macros)`.

The magic function `macro(f)` binds function `f` as a macro in the current REPL session, so you can interactively develop macros right there in the REPL. It works also as a decorator. The new macro will be available from the **next** REPL input onward. You can also use the *self-macro-import* syntax, `from __self__ import macros, f`, to achieve the same effect.

Each time a ``from module import macros, ...`` (when `module` is anything other than the literal `__self__`) is executed in the REPL, just before invoking the macro expander, the system reloads ``module``, to always import the latest macro definitions.

Hence, semi-live updates to macro definitions are possible: hack on your macros, re-import the macros, and try out the new version in the REPL. No need to restart the REPL session in between.

But note that only the macros you explicitly import again will be refreshed in the session.

Each time after importing macros, the macro functions are automatically imported
as regular Python objects. Note only the REPL does this; normally, in `mcpyrate`
macros are not imported as run-time objects.

The intention is to allow viewing macro docstrings and source code easily in the
REPL session, using ``some_macro?``, ``some_macro??``.

This does not affect using the macros in the intended way, as macros.


## `macropython`, the universal bootstrapper

The bootstrapper has two roles:

 - It allows starting a **macro-enabled interactive Python interpreter** directly from the shell.
 - It **allows your main program to use macros**.


### Starting a macro-enabled REPL from the shell

Interactive mode (`macropython -i`) starts a **macro-enabled interactive Python interpreter**, using `mcpyrate.repl.console.MacroConsole`. The [readline](https://docs.python.org/3/library/readline.html) and [rlcompleter](https://docs.python.org/3/library/rlcompleter.html) modules are automatically activated and connected to the REPL session, so the command history and tab completion features work as expected, pretty much like in the standard interactive Python interpreter.

The point of this feature is to conveniently allow starting a macro-enabled REPL directly from the shell. In interactive mode, the filename and module command-line arguments are ignored.

If `-p` is given in addition to `-i`, as in `macropython -pi`, the REPL starts in **pylab mode**. This automatically performs `import numpy as np`, `import matplotlib.pyplot as plt`, and activates matplotlib's interactive mode, so plotting won't block the REPL. This is somewhat like IPython's pylab mode, but we keep stuff in separate namespaces. This is a convenience feature for scientific interactive use.

Command history of `macropython -i` is saved in the folder `~/.config/mcpyrate/`, in a file named `macropython_history`.


### Running a macro-enabled main program

In this mode, the bootstrapper imports the specified file or module, pretending its ``__name__`` is ``"__main__"``. **This allows your main program to use macros**.

For example, ``example.py``:

```python
from mcpyrate.quotes import macros, q

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

A relative path is ok, it *should* be interpreted the same way Python itself does.

We also support the ``-m module_name`` variant:

```bash
macropython -m example
```

A dotted module path under the current directory is ok.

If you need to set other Python command-line options:

```bash
python3 <your options here> $(which macropython) -m example
```

This way the rest of the options go to the Python interpreter itself, and the ``-m example`` to the ``macropython`` bootstrapper.


## Questions & Answers

### `@macro` is convenient, why is it only available in the REPL?

The answer is twofold:

 1. Welcome to the through-the-looking-glass world of the REPL, where every time
    a complete input is entered is macro-expansion time.

    The `@macro` utility hooks into the REPL session's macro expander. The same
    simple trick does not work in a source file, because that `macro(f)` call is
    technically a run-time thing. When a module reaches run-time, the macro
    expander has already exited, and no more macro invocations remain.

    Allowing to invoke a macro in the same source file where it is defined
    requires a multi-phase compilation strategy. `mcpyrate` **does** support
    this, but the syntax is a bit different; see [multi-phase
    compilation](../README.md#multi-phase-compilation) (a.k.a. `with phase`).

    The *self-macro-import* syntax, `from __self__ import macros, ...`,
    which is used by `with phase`, is also available in the REPL, but that's
    a bit long to type in an interactive session.

    So in the spirit of *practicality beats purity* - just as
    `from ... import *` is considered ok for interactive use - the `@macro`
    decorator is a shorthand that achieves the effect of a self-macro-import
    (via a different mechanism, but that's an implementation detail).

 2. Syntactic conventions. It is a macropythonic tradition, started by the
    original `macropy`, that in macro-enabled Python, macros must be explicitly
    imported at the use site. In Python, *explicit is better than implicit*,
    so it was very pythonic to make the design choice this way.

    `mcpy` took the idea further, by making macro definitions into regular
    functions - so that the definition site has no indication for a function
    actually being a macro (other than its slightly curious choice of
    parameters). This has a number of advantages; the bare syntax transformer
    becomes easily accessible (it's simply the function itself!), and
    importantly, a hiding place for magic vanishes. In `mcpy`, **there is no
    macro registry**; there are only the current expander instance's macro
    bindings. Upon a closer look, that's just a `dict` that maps strings (the
    macro names) to regular functions (the macro definitions).

    At the macro definition site, the absence of a special marker itself very
    strongly suggests there is no magic going on. *What you see is what you
    get.* `mcpyrate` has chosen to follow this tradition.

    Hence a `@macro` decorator is not really an appropriate solution, because
    that's a *definition-site* thing; and in `mcpyrate`, just like in `mcpy`, a
    function actually being a macro is a *use-site* thing. So, what we actually
    need is a syntax to indicate - at the use site - that we want to bind a
    specific function as a macro. In `mcpyrate`, the *macro-import* fulfills
    this role, just like it does in `macropy` and in `mcpy`.

    There's the minor problem that in the REPL, there is no module name that
    represents the session itself. So from which module to import macros defined
    in the REPL? We recognize this situation from multi-phase compilation:
    it is completely analogous with a source file importing macros from itself,
    with the collection of already entered REPL inputs playing the role of the
    previous phase. This is a general solution that fits the macropythonic
    tradition.

    So rather than add a `@macro` decorator to the rest of the system, we have
    made the REPL support the *self-macro-import* syntax, and provided `@macro`
    as a convenient shorthand for interactive use.
