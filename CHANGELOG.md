# Changelog

**3.6.4** (in progress, last updated 27 September 2024)

*No user-visible changes yet.*


---

**3.6.3** (27 September 2024) - hotfix:

**Fixed**

- Fix interactive console failing on macro imports.
  - Now `__init__.py` imports `mcpyrate.activate` as soon as possible.
  - Neither in-tree tests nor the CI automation detected this. It was only when running `macropython -i` (or IPython with the `mcpyrate.repl.iconsole` extension) in a separate terminal window, against an installed `mcpyrate`, that this error came up.
  - For those arriving from Google, the error message was: `ImportError: cannot import name 'macros' from 'mcpyrate.quotes'`


---

**3.6.2** (27 September 2024) - *New tree snakes* edition:

**IMPORTANT**:

- Minimum Python language version is now 3.8.
  - We support 3.8, 3.9, 3.10, 3.11, 3.12, and PyPy3 (language versions 3.8, 3.9, and 3.10).
  - Python 3.6 and 3.7 support dropped, as these language versions have officially reached end-of-life. If you need `mcpyrate` for Python 3.6 or 3.7, use version 3.6.1.


**New**:

- **Python 3.12 support**.
  - Support the `type` statement (Python 3.12 type alias) when fixing `ctx` attributes in the global postprocess pass.
  - The unparser now supports the `type` statement (Python 3.12 type alias).
    - Please note that I pretty much don't use the static typing features of Python myself. This is implemented following the spec, but testing has been rather minimal, so bug reports are welcome!
    - For the curious, the relevant parts of the official Python documentation are:
      - https://docs.python.org/3/library/ast.html#type-parameters
      - https://docs.python.org/3/library/ast.html#ast.TypeAlias
      - https://docs.python.org/3/library/ast.html#ast.TypeVar
      - https://docs.python.org/3/library/ast.html#ast.ParamSpec
      - https://docs.python.org/3/library/ast.html#ast.TypeVarTuple
      - https://docs.python.org/3/library/typing.html#typing.TypeVar
      - https://docs.python.org/3/library/typing.html#typing.ParamSpec
      - https://docs.python.org/3/library/typing.html#typing.TypeVarTuple

- **Python 3.11 support**.
  - Consider also `end_lineno` and `end_col_offset` when fixing AST locations in the global postprocess pass.
    - This is literally the only thing we currently do with `end_lineno` and `end_col_offset`.
    - Python 3.11's AST validator (now part of the CPython compiler as of 3.11+) checks e.g. that `end_lineno >= lineno`.
  - The unparser now supports the `try`/`except*` construct (Python 3.11 exception groups).

- New module `mcpyrate.astcompat`, moved from `unpythonic.syntax.astcompat`. This module handles version differences in the `ast` module in various versions of Python.


**Fixed**:

- Fix https://github.com/Technologicat/mcpyrate/issues/41. The unparser now supports `match`/`case` (Python 3.10 pattern matching).
- Fix bug in unparser: a class definition with no bases or keywords should not emit parentheses after the class name.
- Fix bug in `rename`: rename also in `global` and `nonlocal` declarations, and (Python 3.10+) in `match`/`case` captures.
- Update links in relevant parts of `mcpyrate` documentation to point to Python's official AST documentation instead of GTS (Green Tree Snakes).
  - Nowadays Python has proper [AST documentation](https://docs.python.org/3/library/ast.html).
  - Thus the separate GTS resource is no longer needed, and is effectively dead as of September 2024.


---

**3.6.1** (25 September 2024)

**Fixed**:

- Fix https://github.com/Technologicat/mcpyrate/issues/33, with thanks to @set-soft. That is, `distutils` is no longer required.


---

**3.6.0** (28 January 2022) *New Year's edition*:

**Added**:

- Python 3.10 support.
- Add block macro `mcpyrate.metatools.expand_first`. This can be used to force, within the `with expand_first[macro0, ...]:` block, the given macros to expand before others. Macros can be specified either by name (will be looked up in the current expander's bindings) or by hygienic capture. See [examples in unit tests](mcpyrate/test/test_quotes.py).
- Add function `mcpyrate.utils.get_lineno` to conveniently extract a `lineno` from an AST-node-ish thing, no matter if that thing is an actual AST node, a list of AST nodes (i.e. statement suite), or an AST marker containing either of those, possibly recursively.
- Facilitate programmatic inspection of the whole public API of `mcpyrate`. See the recipes in [troubleshooting](doc/troubleshooting.md).
  - This is an interim solution while we decide whether to start supporting [Sphinx](https://www.sphinx-doc.org/en/master/) at some point, so that we could auto-generate proper API docs from the docstrings (which are carefully maintained, and already contain all the necessary content).


**Fixed**:

- Fix https://github.com/Technologicat/mcpyrate/issues/29, with thanks to @set-soft and @brathis for reporting. **`mcpyrate` should now support Python 3.10.**
- Dialect subsystem fixes.
  - Fix https://github.com/Technologicat/mcpyrate/issues/30, thus extending the fix of #28 (in the previous release) into the dialect subsystem, too.
    - `__future__` imports are accounted for both the dialect template and in user code that invokes the template.
    - This is implemented in the utility function `mcpyrate.splicing.splice_dialect`, so if your dialect definition uses that function in its AST transformer, now your dialect should not choke when the template and/or the user code have `__future__` imports.
  - Fix https://github.com/Technologicat/mcpyrate/issues/31; the dialect machinery now has the infrastructure to pass in the source location info of the dialect-import statement.
    - This allows dialects to mark any lines coming from the dialect template as effectively coming from the line that contains the dialect-import. If you import one dialect per line, this makes it easy to see which lines of the expanded code were injected by which dialect, for debugging purposes. (Recall that you can use the `StepExpansion` dialect from `mcpyrate.debug` to see the line numbers before and after dialect expansion.)
    - During dialect expansion, `DialectExpander` automatically makes this info available in `self.lineno` and `self.col_offset` of your dialect definition (i.e. in the instance of your subclass of `Dialect`, which has the transformer methods). In your AST transformer, you can pass these to `mcpyrate.splicing.splice_dialect`.
    - See updated example dialects in [`unpythonic.dialects`](https://github.com/Technologicat/unpythonic/tree/master/unpythonic/dialects).
  - Fix handling of rare case where the dialect template consists of a single statement that is not wrapped in a list.
- Docstring of `mcpyrate.utils.NestingLevelTracker` now has usage examples.


---

**3.5.3** (14 November 2021):

**Fixed**:

- Fix https://github.com/Technologicat/mcpyrate/issues/28, with thanks to @geezmolycos for reporting. Using `__future__` imports when multiphase compilation is enabled no longer causes `SyntaxError`.


---


**3.5.2** (22 June 2021) - *Midsummer's eve edition*:

**Changed**:

- Small improvements to unparser:
  - No space after unary `+`, `-` or `~`.
  - Future-proofing: yell if an unsupported constant value type is encountered.

- Add a new troubleshooting item on another [Heisenbug](https://en.wikipedia.org/wiki/Heisenbug) that can occur when buggy macros are used inside a `with step_expansion`.


---

**3.5.1** (26 May 2021) - *Detailed logbook* edition:

**Changed**:

- Documentation improved. Particularly, AST markers are now documented (in the main user manual).


---

**3.5.0** (9 May 2021):

**New**:

- Add `temporary_module`, a context manager that uses `create_module`, and automatically removes the temporary module from `sys.modules` when the context exits.

- Add a global postprocessor hook facility. Hooks are called, in the order registered, by `global_postprocess` when the macro expansion of a module is otherwise done. This e.g. allows a macro library to use its own `ASTMarker` subclasses for internal communication between macros, and delete (only) its own markers when done. See `add_postprocessor` and `remove_postprocessor` in `mcpyrate.core`.

**Fixed**:

- Run-time part of `n[]`: upon a parse error, make it clearer in the error message that what was being compiled was an invocation of `n[]`, not the whole source file. (Because these expressions are often one-liners, usually `lineno` will be `1`, which otherwise looks confusing.)

- Fix error message in run-time typecheck of `a` (ast-unquote). Now it mentions correctly what was expected.

- Now `ASTMarker` may contain a statement suite (`list` of AST nodes) as its `body`.
  - The debug mode of `mcpyrate.unparse` now renders such bodies correctly.
  - `mcpyrate.markers.delete_markers` now deletes such markers correctly, splicing in the `list` of AST nodes where the marker was.


---

**3.4.1** (4 May 2021):

**Changed**:

- Update docs: as of `unpythonic` 0.15, it runs on `mcpyrate`, and provides fully functional example dialects based on a whole-module AST transformation.
- The colorizer now injects some styles to `Style` that are missing from `colorama` 0.4.4, particularly `ITALIC`.

**Fixed**:

- Now we pass a filename to `ast.parse` everywhere. This allows e.g. `SyntaxError` during macro-import scanning (in the macro-import dependency graph analyzer), and possible internal errors in the interactive consoles, to report the filename correctly.


---

**3.4.0** (2 May 2021) - *Quasiquotes ahoy* edition:

**New**:

- The unparser now recognizes hygienic captures and destructures them in debug mode. This makes the result much more readable when you unparse an AST that uses a lot of hygienic unquotes.
  - To see it in action, use `mcpyrate.debug.step_expansion` macro on [`unpythonic.syntax.tests.test_lazify`](https://github.com/Technologicat/unpythonic/blob/master/unpythonic/syntax/tests/test_lazify.py). See particularly the *HasThon* test; both the autocurry and the lazifier produce many hygienic captures.

    Without this helpful destructuring, the macro-expanded code is completely unreadable, but with this, it only exhibits mild symptoms of parenthesitis. For example, this snippet:
    ```python
    filename=callsite_filename()
    ```
    becomes, after autocurry and lazification,
    ```python
    filename=$h[Lazy]((lambda: $h[maybe_force_args]($h[force]($h[currycall]),
                                                    $h[Lazy]((lambda: $h[force]($h[callsite_filename]))))))
    ```
    Here each `$h[...]` is a hygienic capture. That's seven captures for this very simple input! Compare this notation to the actual AST representation of, e.g., `$h[Lazy]`:
    ```python
    __import__('mcpyrate.quotes', globals(), None, (), 0).quotes.lookup_value(('Lazy',
        b'\x80\x04\x95 \x00\x00\x00\x00\x00\x00\x00\x8c\x13unpythonic.lazyutil\x94\x8c\x04Lazy\x94\x93\x94.'))
    ```


**Fixed**:

- The importer now reports the source location if destructuring a macro invocation candidate fails.
  - Some internal functions, including `mcpyrate.expander.destructure_candidate`, now take a mandatory `filename` kwarg for this purpose.

- Fix detection of globally bound macro invocations (hygienic macro captures) in the helper method `mcpyrate.expander.ismacrocall`.

- Fix syntax analysis for detecting `expr` macro invocations in `mcpyrate.expander.destructure_candidate`. Version 3.3.0 (and only that version) errored out on the AST for `f()[...]` even if `f` was not bound as a macro.


---

**3.3.0** (29 April 2021) - *Captain Debughook* edition:

**New**:

- Debug hook added to `mcpyrate.core.BaseMacroExpander` to see what the macro expander is doing. The `step_expansion` macro now uses it (which see for usage), but you can also hook your own functions to it.

- Public function `mcpyrate.quotes.is_captured_value` for advanced macrology. This allows your own macros to detect expansions of `q[h[somename]]` in the AST, and grab `somename` (original name, no name mangling) as well as the corresponding value. (There is also `is_captured_macro`, but the use cases of that are much more limited.) Detailed explanation in docstrings for now. Usage examples in the tests for the `quotes` module.

- `mcpyrate.walkers.ASTTransformer` and `ASTVisitor` now have a method `generic_withstate`, to temporarily replace the state when visiting the direct children of the given node. (This is a closer equivalent for `macropy`'s `set_ctx`, sometimes useful for writing custom walkers.)

- Improve documentation on creating magic variables: add another major strategy, and explain both strategies in more detail.


**Changed**:

- `step_expansion` and `stepr` now accept the string `"detailed"` as a macro argument (in addition to the earlier `"dump"` that selects the AST dump renderer).

  When `"detailed"` is given, they will report every macro expansion using the debug hook. This facilitates debugging of macros that expand inside-out (using explicit recursion). The definition of *step* remains the same: the `step` counter is incremented whenever the debug stepper gets control back. Just as previously, **inside-out expansion therefore occurs within one step**, but now you can see the subtree of each inner macro invocation just before and after that macro expands.

  In block mode `with step_expansion`, one complete step is defined as expanding each statement in the suite by one step.

  The macro arguments for `step_expansion` and `stepr` can be passed in any order.


**Fixed**:

- Fix subscript slice handling in unparser for Python 3.9 and later. Now that `ast.Index` and `ast.ExtSlice` are gone, an `ast.Tuple` may appear directly in the slice position, representing multi-dimensional indexing. Such a tuple must be rendered without surrounding parentheses, because the notation `a[1,2:5]` is fine, but `a[(1,2:5)]` is a syntax error. See https://bugs.python.org/issue34822

- Fix bug in quasiquoting of constants: support also `...` (the `Ellipsis` singleton).

- Fix bug in `splice_ast_literals` (a.k.a. run-time part of `q`) that made it crash on `ast.Nonlocal` and `ast.Global` nodes.

- Fix bug in type preservation of empty list in `ASTTransformer`.

- Fix bug in copy support of `ASTMarker` objects. Now it is possible to deepcopy ASTs that contain markers.

- Fix bug that caused the `mcpyrate.debug.show_bindings` macro or the REPL consoles to crash upon a specific kind of broken imports in user code. (E.g. accidentally binding a macro name to a module object instead of a function object.) 

- Fix bug failing to honor possible overrides to `sys.stderr` in various debug-printing facilities. Always `import sys` and refer to `sys.stderr` to resolve the current value, never `from sys import stderr`.

- Up to Python 3.8, items in the decorator list cannot be subscripted, so decorator macros could not take macro arguments. In 3.9 this has been fixed, as implied by [the grammar](https://docs.python.org/3/reference/grammar.html). To work around this issue in earlier supported Python versions (3.6, 3.7, 3.8), we now support parentheses as an alternative syntax for passing macro arguments, like in `macropy`. Note that macro arguments must in any case be passed positionally! (Reasons documented in the comments of `mcpyrate.expander`.)


---


**3.2.1** (10 April 2021)

- Fix version metadata in `__init__.py`.

---


**3.2.0** (10 April 2021) - *X marks the spot* edition:

**New**:

- Documentation: [the staging compiler](doc/compiler.md) is now documented.
- Documentation: [contribution guidelines](CONTRIBUTING.md) now include a section on automated tests.
- Add command-line option to `macropython` to delete bytecode caches:
  - Use `macropython -c yourdirectory` (equivalent: `macropython --clean yourdirectory`), where `yourdirectory` is a path (can be relative or absolute).
  - For a dry run, use `macropython -c yourdirectory -n` (equivalent: `macropython --clean yourdirectory --dry-run`), which just prints the full paths to the directories it would delete.
  - If you need programmatic access to this functionality, see `mcpyrate.pycachecleaner`.


**Fixed**:

- Fix https://github.com/Technologicat/mcpyrate/issues/20, with thanks to @thirtythreeforty for reporting. **`mcpyrate` should now support Python 3.9.**
- Fix bug in `mcpyrate.splicing.splice_expression`. (Only affected that function; the expression mode of `a[]` uses a different code path.)
- Fix a crash in the generation of some error messages in `mcpyrate.coreutils.get_macros`. Particularly, the crash could occur if the module is not found in `sys.modules`, or if an as-import of a macro is attempted with a concrete expander type that doesn't support that feature.


---

**3.1.0** (12 February 2021) - *Compiling on the high seas* edition:

**New**:

- The `mcpyrate` compiler (implementing [the import algorithm](doc/compiler.md#the-import-algorithm)) is now exposed in `mcpyrate.compiler` for run-time use.
  - You can just `expand`, or both expand and `compile` code, as needed.
  - It is now convenient to compile and run macro-enabled quoted code snippets (or source code) at run time, see the functions `mcpyrate.compiler.run` and `mcpyrate.compiler.create_module`.
    - This makes it easier to test macros that are best tested via the behavior of the run-time code they output. (It also makes macro-enabled Python into a poor man's staged language  [[1]](https://www.researchgate.net/publication/221024597_A_Gentle_Introduction_to_Multi-stage_Programming) [[2]](https://cs.stackexchange.com/questions/2869/what-are-staged-functions-conceptually).)
    - The system allows dynamically creating modules (for executing code snippets in) at run time, as well as running code in the namespace of an existing module.
      - These features combine, so you can let `run` automatically create a module the first time, and then re-use that module if you want.
      - You can also create a module with a specific dotted name in `sys.modules`. The multi-phase compiler itself uses this feature.
    - Source code input supports dialects, macros, and multi-phase compilation. The source code represents a module.
    - Quoted AST input supports macros and multi-phase compilation. No source transforms for this kind of input, because the input is already an AST. (Dialect AST transformers and postprocessors should work.) The top level of the quoted block (i.e. the body of a `with q as quoted:`) is seen by the compiler as the top level of a module.
    - While the code snippet is running, the module's `__file__` and `__name__` attributes are available, as usual.
    - For extracting results into the surrounding context, just assign them to variables inside the code snippet. The top level of the code snippet is the module's top level. You have that module object available in the surrounding context (where you call `run`), so you can access those variables as its attributes.
  - Full documentation is in docstrings for now, see [`mcpyrate.compiler`](mcpyrate/compiler.py). Usage examples can be found in [`mcpyrate.test.test_compiler`](mcpyrate/test/test_compiler.py).

- Add support for [PEP 582 - Python local packages directory](https://www.python.org/dev/peps/pep-0582/) in the `macropython` bootstrapper.

- The unparser now supports all three [top-level node types](https://greentreesnakes.readthedocs.io/en/latest/nodes.html#top-level-nodes), and supports also a `list` of AST nodes (e.g. a statement suite in an AST) as input.

- The `StepExpansion` dialect now works in AST-only mode, too.
  - It will enable `DialectExpander` debug mode in the source transform step, if that runs. If the AST transform step is reached and debug mode is still off, it will now enable debug mode at that time. Only one copy of the unprocessed code is printed regardless.

- README: add instructions to configure Emacs syntax highlighting.

- Add `unpyrate.bunch.bunchify` to convert an existing mapping instance into a `Bunch`.


**Changed**:

- Nested quasiquotes now work properly.

  Unquoting now only occurs when quote level hits zero. Inner quotes and unquotes are detected, for tracking the quote level, but are then left in the output as-is.

  Note as-is means *"as unexpanded macro invocations"*. Because the quasiquote operators are just macros, and in macro-enabled Python, the tradition is that a function actually being a macro is a property of the *use site*, not of its definition site, it follows that there's no guarantee whether the quote operators are in the expander's bindings at any later time. Even if they are, there is no guarantee whether they still have the names they had at the time when the outermost quote expanded.

  What we have now is the result of taking the current design to its logical extreme. A better solution (for next-next-gen) may need a break from tradition, in that maybe a function being a macro should be a property of its definition site, not of its use site. Also, maybe the quasiquote operators should be considered core functionality, and not be renameable (like regular macros are).

  However, the current solution does give useful level separation that has real practical applications; see the dynamically generated module example in [`mcpyrate.test.test_compiler`](mcpyrate/test/test_compiler.py).

  This is not considered a breaking change, because the previous behavior of nested quasiquotes didn't make any sense, so nothing useful could be built on it.


**Fixed**:

- Fix https://github.com/INTI-CMNB/KiBot/issues/29, with thanks to @skorokithakis and @set-soft.
- Fix https://github.com/Technologicat/mcpyrate/issues/21, with thanks to @thirtythreeforty for reporting.
- Fix bug in `unastify`: drop the run-time part of `q`.
- Fix bug in `rename`: handle also module name in `ImportFrom` nodes.
- Fix `SourceLocationInfoValidator`.
- `macropython` now reports `mcpyrate` version separately from the version of the `macropython` script itself when run with the `-v` (`--version`) command-line option.


---

**3.0.1** (27 November 2020)

- Fix project metadata in `setup.py`.

---

**3.0.0** (27 November 2020) - *Arrr!* edition:

Initial release of **`mcpyrate`**, the advanced, third-generation macro expander for Python, after the pioneering [macropy](https://github.com/lihaoyi/macropy), and the compact, pythonic [mcpy](https://github.com/delapuente/mcpy). The emphasis is on correctness, feature-completeness for serious macro-enabled work, and simplicity, in that order.

We build on `mcpy` 2.0.0, but add a lot of new features.

**New**:

- **Agile development tools**.
  - [Multi-phase compilation](doc/compiler.md#multi-phase-compilation): Use macros also in the same module where they are defined.
  - Universal bootstrapper: `macropython`. Import and use macros in your main program.
  - Interactive console: `macropython -i`. Import, define and use macros in a console session.
    - Embeddable à la `code.InteractiveConsole`. See `mcpyrate.repl.console.MacroConsole`.
  - IPython extension `mcpyrate.repl.iconsole`. Import, define and use macros in an IPython session.
  - See [full documentation of the REPL system](doc/repl.md).

- **Testing and debugging**.
  - Statement coverage is correctly reported by tools such as [`Coverage.py`](https://github.com/nedbat/coveragepy/).
  - Macro expansion errors are reported at macro expansion time, with use site traceback.
  - Debug output **with a step-by-step expansion breakdown**. See macro [`mcpyrate.debug.step_expansion`](mcpyrate/debug.py).
    - Has both expr and block modes. Use `step_expansion[...]` or `with step_expansion` as appropriate.
    - The output is **syntax-highlighted**, and **line-numbered** based on `lineno` fields from the AST.
      - Also names of macros currently bound in the expander are highlighted by `step_expansion`.
      - Line numbers are taken from *statement* AST nodes.
    - The invisible nodes `ast.Module` and `ast.Expr` are shown, since especially `ast.Expr` is a common trap for the unwary.
    - To step the expansion of a run-time AST value, see the macro [`mcpyrate.metatools.stepr`](mcpyrate/metatools.py).
  - Manual expand-once. See `expander.visit_once`; get the `expander` as a named argument of your macro. See also the `expand1s` and `expand1r` macros in [`mcpyrate.metatools`](mcpyrate/metatools.py).

- **Lightning speed**.
  - Bytecode caches (`.pyc`) are created and kept up-to-date. Saves macro expansion cost at startup for unchanged modules. Makes `mcpyrate` fast [on average](https://en.wikipedia.org/wiki/Amortized_analysis).

    Beside a `.py` source file itself, we look at any macro definition files
    it imports macros from, recursively, in a `make`-like fashion.

    The mtime is the latest of those of the source file and its macro-dependencies,
    considered recursively, so that if any macro definition anywhere in the
    macro-dependency tree of a source file is changed, Python will treat that
    source file as "changed", thus re-expanding and recompiling it (hence,
    updating the corresponding `.pyc`).
  - **CAUTION**: [PEP 552 - Deterministic pycs](https://www.python.org/dev/peps/pep-0552/) is not supported; we support only the default *mtime* invalidation mode, at least for now.

- **Quasiquotes**, with advanced features.
  - Hygienically interpolate both regular values **and macro names**.
  - Delayed macro expansion inside quasiquoted code. User-controllable.
  - Inverse quasiquote operator. See function [`mcpyrate.quotes.unastify`](mcpyrate/quotes.py).
    - Convert a quasiquoted AST back into a direct AST, typically for further processing before re-quoting it.
      - Not an unquote; we have those too, but the purpose of unquotes is to interpolate values into quoted code. The inverse quasiquote, instead, undoes the quasiquote operation itself, after any unquotes have already been applied.
  - See [full documentation of the quasiquote system](doc/quasiquotes.md).

- **Macro arguments**.
  - Opt-in. Declare by using the [`@parametricmacro`](mcpyrate/expander.py) decorator on your macro function.
  - Use brackets to invoke, e.g. `macroname[arg0, ...][expr]`. If no args, just leave that part out, e.g. `macroname[expr]`.
  - The `macroname[arg0, ...]` syntax works in `expr`, `block` and `decorator` macro invocations in place of a bare `macroname`.
  - The named parameter `args` is a raw `list` of the macro argument ASTs. Empty if no args were sent, or if the macro function is not parametric.

- **Identifier (a.k.a. name) macros**.
  - Opt-in. Declare by using the [`@namemacro`](mcpyrate/expander.py) decorator on your macro function.
  - Can be used for creating magic variables that may only appear inside specific macro invocations.

- **Dialects, i.e. whole-module source and AST transforms**.
  - Think [Racket's](https://racket-lang.org/) `#lang`, but for Python.
  - Define languages that use Python's surface syntax, but change the semantics; or plug in a per-module transpiler that (at import time) compiles source code from some other programming language into macro-enabled Python. Also an AST [optimizer](http://compileroptimizations.com/) could be defined as a dialect. Dialects can be chained.
  - Sky's the limit, really. Until we get [`unpythonic`](https://github.com/Technologicat/unpythonic) ported to use `mcpyrate`, see [`pydialect`](https://github.com/Technologicat/pydialect) for old example dialects.
  - For debugging, `from mcpyrate.debug import dialects, StepExpansion`.
  - If writing a full-module AST transformer that splices the whole module into a template, see [`mcpyrate.splicing.splice_dialect`](mcpyrate/splicing.py).
  - See [full documentation of the dialect system](doc/dialects.md).

- **Conveniences**.
  - Relative macro-imports (for code in packages), e.g. `from .other import macros, kittify`.
  - The expander automatically fixes missing `ctx` attributes in the AST, so you don't need to care about those in your macros.
  - In most cases, the expander also fills in correct source location information automatically (for coverage reporting). If you're discarding nodes from the input, then you may have to be [slightly careful](doc/main.md#writing-macros) and use `ast.copy_location` appropriately.
  - Several block macros can be invoked in the same `with` (equivalent to nesting them, with leftmost outermost).
  - [AST visitor and transformer](mcpyrate/walkers.py) à la `macropy`'s `Walker`, to easily context-manage state for subtrees, and collect items across the whole walk. [Full documentation](doc/walkers.md).
  - AST [markers](mcpyrate/markers.py) (pseudo-nodes) for communication in a set of co-operating macros (and with the expander).
  - [`gensym`](mcpyrate/utils.py) to create a fresh, unused lexical identifier.
  - [`unparse`](mcpyrate/unparser.py) to convert an AST to the corresponding source code, optionally with syntax highlighting (for terminal output).
  - [`dump`](mcpyrate/astdumper.py) to look at an AST representation directly, with (mostly) PEP8-compliant indentation, optionally with syntax highlighting (node types, field names, bare values).
