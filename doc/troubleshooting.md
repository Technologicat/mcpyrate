**Navigation**

- [Main user manual](main.md)
- [Quasiquotes and `mcpyrate.metatools`](quasiquotes.md)
- [REPL and `macropython`](repl.md)
- [The `mcpyrate` compiler](compiler.md)
- [AST walkers](walkers.md)
- [Dialects](dialects.md)
- **Troubleshooting**

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [General issues](#general-issues)
    - [ImportError: cannot import name 'macros' from ...](#importerror-cannot-import-name-macros-from-)
    - [I just ran my program again and no macro expansion is happening?](#i-just-ran-my-program-again-and-no-macro-expansion-is-happening)
    - [How to debug macro transformations?](#how-to-debug-macro-transformations)
    - [Macro expansion time where exactly?](#macro-expansion-time-where-exactly)
    - [My macro needs to fill in `lineno` recursively, any recommendations?](#my-macro-needs-to-fill-in-lineno-recursively-any-recommendations)
- [Expansion stepping](#expansion-stepping)
    - [My own macros are working, but I'm not seeing any output from `step_expansion` (or `show_bindings`)?](#my-own-macros-are-working-but-im-not-seeing-any-output-from-step_expansion-or-show_bindings)
    - [`step_expansion` is treating the `expands` family of macros as a single step?](#step_expansion-is-treating-the-expands-family-of-macros-as-a-single-step)
    - [Can I use the `step_expansion` macro to report steps with `expander.visit(tree)`?](#can-i-use-the-step_expansion-macro-to-report-steps-with-expandervisittree)
    - [`step_expansion` and `stepr` report different results?](#step_expansion-and-stepr-report-different-results)
    - [My macro crashes with a call stack overflow, but the error goes away if I `step_expansion` it?](#my-macro-crashes-with-a-call-stack-overflow-but-the-error-goes-away-if-i-step_expansion-it)
- [Compile-time errors](#compile-time-errors)
    - [Error in `compile`, an AST node is missing the required field `lineno`?](#error-in-compile-an-ast-node-is-missing-the-required-field-lineno)
        - [Unexpected bare value](#unexpected-bare-value)
        - [Wrong type of list](#wrong-type-of-list)
        - [Wrong type of AST node](#wrong-type-of-ast-node)
        - [The notorious invisible `ast.Expr` statement](#the-notorious-invisible-astexpr-statement)
        - [Wrong unquote operator](#wrong-unquote-operator)
        - [Failing all else](#failing-all-else)
    - [Expander says it doesn't know how to `astify` X?](#expander-says-it-doesnt-know-how-to-astify-x)
    - [Expander says it doesn't know how to `unastify` X?](#expander-says-it-doesnt-know-how-to-unastify-x)
- [Coverage reporting](#coverage-reporting)
    - [Why do my block and decorator macros generate extra do-nothing nodes?](#why-do-my-block-and-decorator-macros-generate-extra-do-nothing-nodes)
    - [`Coverage.py` says some of the lines inside my block macro invocation aren't covered?](#coveragepy-says-some-of-the-lines-inside-my-block-macro-invocation-arent-covered)
    - [`Coverage.py` says my quasiquoted code block is covered? It's quoted, not running, so why?](#coveragepy-says-my-quasiquoted-code-block-is-covered-its-quoted-not-running-so-why)
    - [My line numbers aren't monotonically increasing, why is that?](#my-line-numbers-arent-monotonically-increasing-why-is-that)
- [Packaging](#packaging)
    - [I tried making a PyPI package with `setuptools` out of an app that uses `mcpyrate`, and it's not working?](#i-tried-making-a-pypi-package-with-setuptools-out-of-an-app-that-uses-mcpyrate-and-its-not-working)
    - [I tried making a Debian package out of an app that uses `mcpyrate`, and it's not working?](#i-tried-making-a-debian-package-out-of-an-app-that-uses-mcpyrate-and-its-not-working)

<!-- markdown-toc end -->


# General issues

## ImportError: cannot import name 'macros' from ...

This occurs when trying to run a macro-enabled program without macro support enabled, such as when trying to run a macro-enabled script from the command line with regular `python`.

 - If you did `python myscript.py` or similar, retry with `macropython myscript.py`.
 - If only a part of your code uses macros, and your main program is intended to be run with regular `python`, the problem could be that some module of your program is importing a module that uses macros, without first enabling macro support. Check if you have accidentally forgotten to `import mcpyrate.activate`.
 - If you're using the advanced functions `deactivate` and `activate` from the module `mcpyrate.activate`, the likely reason is that macro support has been manually disabled by calling `deactivate`. Find the offending import, and call `mcpyrate.activate.activate` before invoking that import to re-enable macro support. If you don't need macro support after that import completes, it's then safe to again call `mcpyrate.activate.deactivate` (to make any remaining imports run slightly faster).


## I just ran my program again and no macro expansion is happening?

This is normal. The behavior is due to bytecode caching (`.pyc` files). When `mcpyrate` processes a source file, it will run the expander only if that file, or the source file of at least one of its macro-dependencies, has changed on disk. This is detected from the *mtime* (modification time) of the source files. The macro-dependencies are automatically considered recursively in a `make`-like fashion.

Even if you use [`sys.dont_write_bytecode = True`](https://docs.python.org/3/library/sys.html#sys.dont_write_bytecode) or the environment variable [`PYTHONDONTWRITEBYTECODE=1`](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONDONTWRITEBYTECODE), Python will still **use** existing `.pyc` files if they are up to date.

If you want to force all of your code to be macro-expanded again, delete your bytecode cache (`.pyc`) files; they'll be re-generated automatically. Typically, they can be found in a folder named `__pycache__`, at each level of your source tree.

To delete bytecode caches conveniently, you can use the shell command `macropython -c yourdirectory` (equivalent: `macropython --clean yourdirectory`), where `yourdirectory` is a path (can be relative or absolute). If you're wary of allowing a script to delete directories, you can first use `macropython -c yourdirectory -n` (equivalent: `macropython --clean yourdirectory --dry-run`), which just prints the full paths to the directories it would delete. If you need programmatic access to this functionality, see `mcpyrate.pycachecleaner`.

Normally there is no need to delete bytecode caches manually.

However, there is an edge case. If you hygienically capture a value that was imported (to the macro definition site) from another module, and that other module is not a macro-dependency, then - if the class definition of the hygienically captured value changes on disk, that is not detected.

This can be a problem, because hygienic value storage uses `pickle`, which in order to unpickle the value, expects to be able to load the original (or at least a data-compatible) class definition from the same place where it was defined when the value was pickled. If this happens, then delete the bytecode cache (`.pyc`) files, and the program should work again once the macros re-expand.


## How to debug macro transformations?

We provide several utilities that show the steps of macro transformations, to help debugging them. See the module [`mcpyrate.debug`](../mcpyrate/debug.py).

 - To troubleshoot **regular macro expansion**, see `step_expansion` in `mcpyrate.debug`. It is both an `expr` and `block` macro. This is the one you'll likely need most often.

 - To troubleshoot **macro expansion of a run-time AST value** (such as quasiquoted code), see the module [`mcpyrate.metatools`](../mcpyrate/metatools.py), particularly the macro `stepr`. It is an `expr` macro that takes in a run-time AST value. (In Python, values are always referred to by expressions. Hence no block mode.) This one you'll likely need second-most often.

   Also, use `print(unparse(tree, debug=True, color=True))` if there's a particular `tree` whose source code representation you'd like to look at, or even `print(dump(tree, color=True))`. Look at the docstrings of those functions for other possibly useful parameters. Both functions are available in the top-level namespace of `mcpyrate`.

 - To troubleshoot **multi-phase compilation**, see `step_phases` in `mcpyrate.debug`. Just macro-import it (`from mcpyrate.debug import macros, step_phases`). It will show you the unparsed source code of each phase just after AST extraction.

 - To troubleshoot **dialect transformations**, see the dialect `StepExpansion` in `mcpyrate.debug`; just dialect-import it (`from mcpyrate.debug import dialects, StepExpansion`). It will step source and AST transformers as well as AST postprocessors in the dialect compiler, one step per transformer.

When interpreting the output, keep in mind in which order various kinds of transformations occur; see [`mcpyrate`'s import algorithm](compiler.md#the-import-algorithm).


## Macro expansion time where exactly?

The "time", as in *macro expansion time* vs. *run time*, is fundamentally a local concept, not a global one. As the old saying goes, *it's always five'o'clock **somewhere***.

As an example, consider a macro `mymacro`, which uses `mcpyrate.quotes.q` to define an AST using the quasiquote notation. When `mymacro` reaches run time, any macro invocations used as part of its own implementation (such as the `q`) are already long gone. On the other hand, the use site of `mymacro` has not yet reached run time - for that use site, it is still macro expansion time.

Any macros that `mymacro` invokes in its output AST are just data, to be spliced in to the use site. By default, they'll expand (run!) after `mymacro` has returned.

So the "time" must be considered separately for each source file.

Furthermore, if you use [multi-phase compilation](compiler.md#multi-phase-compilation) (a.k.a. `with phase`), then in a particular source file, each phase will have its own macro-expansion time as well as its own run time. For any `k >= 0`, the run time of phase `k + 1` is the macro expansion time of phase `k`.

This is something to keep in mind when developing macros where the macro implementation itself is macro-enabled code (vs. just emitting macro invocations in the output AST). Since the [quasiquote system](quasiquotes.md) is built on macros, this includes any macros that use `q`.


## My macro needs to fill in `lineno` recursively, any recommendations?

See [`mcpyrate.astfixers.fix_locations`](../mcpyrate/astfixers.py), which is essentially an improved `ast.fix_missing_locations`. You'll likely want either `mode="overwrite"` or `mode="reference"`, depending on what your macro does.

```python
from mcpyrate.astfixers import fix_locations

fix_locations(tree, reference_node, mode="reference")
```

There's also the stdlib barebones solution:

```python
from ast import walk, copy_location

for node in walk(tree):
    copy_location(node, reference_node)
```


# Expansion stepping

## My own macros are working, but I'm not seeing any output from `step_expansion` (or `show_bindings`)?

The most likely cause is that the bytecode cache (`.pyc`) for your `.py` source file is up to date. Hence, the macro expander was skipped.

Unlike most macros, the whole point of `step_expansion` and `show_bindings` are their side effects - which occur at macro expansion time. So you'll get output from them only if the expander runs.

Your own macros do indeed work; but Python is loading the bytecode, which was macro-expanded during an earlier run. Your macros didn't run this time, but the expanded code from the previous run is still there in the bytecode cache (and, since it is up to date, it matches the output the macros would have, were they to run again).

Force an *mtime* update on your source file (`touch` it, or just save it again in a text editor), so the expander will then run again (seeing that the source file has been modified).


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
**Tree 0x7f61fddf7a90 (<interactive input>) before macro expansion:
  q[42]
**Tree 0x7f61fddf7a90 (<interactive input>) after step 1:
  mcpyrate.quotes.splice_ast_literals(mcpyrate.quotes.ast.Num(n=42))
**Tree 0x7f61fddf7a90 (<interactive input>) macro expansion complete after 1 step.
<_ast.Num object at 0x7f61fe7c7b38>
```

Keep in mind each piece of source code shown is actually the unparse of an AST. So the source code `q[42]` actually stands for an `ast.Subscript`, while the expanded result is an `ast.Call` that, **once it is compiled and run**, will call `ast.Num`. (If you're not convinced, try `step_expansion["dump"][q[42]]`, which pretty-prints the raw AST instead of unparsed source code.)

The invocation `stepr[q[42]]`, on the other hand, produces:

```
**Tree 0x7f61fe84fd68 (<interactive input>) before macro expansion:
  42
**Tree 0x7f61fe84fd68 (<interactive input>) macro expansion complete after 0 steps.
<_ast.Num object at 0x7f61fe84fd68>
```

or in other words, an `ast.Num` object. (Again, if not convinced, try `stepr["dump"][q[42]]`.)

So the **run-time result** of both invocations is an `ast.Num` object (or `ast.Constant`, if running on Python 3.8+). But they see the expansion differently, because `step_expansion` operates at macro expansion time, while `stepr` operates at run time.

Whereas unquotes are processed at run time of the use site of `q` (see [the quasiquote system docs](quasiquotes.md)), the `q` itself is processed at macro expansion time. Hence, `step_expansion` will see the `q`, but when `stepr` expands the tree at run time, it will already be gone.


## My macro crashes with a call stack overflow, but the error goes away if I `step_expansion` it?

That's some deep recursion right there! The reason it works with `step_expansion` is that `step_expansion` converts the recursive calls to the expander into a while loop in expand-once mode.

If you need to do the same, look at [its source code](../mcpyrate/debug.py).


# Compile-time errors

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


## Expander says it doesn't know how to `unastify` X?

Most likely, the input to `expands` or `expand1s` wasn't a quasiquoted tree.

See `expandsq`, `expand1sq`, `expandrq`, `expand1rq`, or just `expander.visit(tree)`, depending on what you want.


# Coverage reporting

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


# Packaging

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
