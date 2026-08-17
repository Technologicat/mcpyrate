# Changelog

**4.3.1** (in progress):

*No user-visible changes yet.*


---

**4.3.0** (17 August 2026) — *"Weigh anchor"* edition:

Python 3.15 support. Under 3.15 the expander could not be imported at all, so nothing macro-enabled would run; it sails again, and the unparser has learned the two syntax additions that come with the new version.

**New**:

- **Python 3.15 is supported.**
  - **mcpyrate now imports at all under 3.15.** `importlib`'s `SourceFileLoader.source_to_code` — the method the expander replaces in order to hook compilation — gained a positional `fullname` parameter, so the replacement raised `TypeError` and nothing macro-enabled could be imported.
  - **`unparse` handles the new syntax**: lazy imports (`lazy import x`, `lazy from x import y`) and unpacking in comprehensions (`{**mapping for x in xs}`, `[*items for item in xs]`, and the set and generator forms).
  - **Syntax warnings from macro-enabled modules can now be filtered by module name**, through `-W` or `warnings.filterwarnings(..., module=...)`, the same as warnings from ordinary modules. mcpyrate calls the built-in `compile` itself, so it now passes 3.15's new `module=` argument along; without it the warnings machinery falls back to guessing a dotted name from the file path.
  - **A lazy macro-import is an error.** `lazy from mymacros import macros, ...`, and the dialect-import equivalent, now raise `SyntaxError`. The expander consumes a macro-import at macro-expansion time, so deferring one cannot mean anything — and since the statement is rewritten into an ordinary import, accepting it would have discarded the `lazy` without saying so.

**Fixed**:

- **The optimization level the caller asks for is now honoured.** `source_to_xcode` accepted it and then dropped it, which went unnoticed because the import path only ever passes `-1`, meaning "use the interpreter's level". `py_compile` and `compileall -o` pass an explicit level, so ahead-of-time compilation of macro-enabled code silently produced bytecode at the interpreter's level rather than the requested one.
- **`unparse` no longer crashes on a hand-built `ImportFrom` that omits `level`.** The field is optional in the AST, so a node constructed in a macro without it has `level=None`, and unparsing raised `TypeError`. Parsed nodes always carry an int, so this only affected generated code.

**Changed**:

- **`requires-python` now declares an upper bound, `>=3.10,<3.16`.** mcpyrate manipulates the AST and replaces part of the import machinery, so a new Python release can break it in ways a version-agnostic package never sees — as 3.15 did. The ceiling means a future Python has to be tested and released for, rather than silently installed onto.


---

**4.2.0** (12 May 2026) — *"X marks the spot"* edition:

End-to-end support for the Python 3.8+ source-location fields `end_lineno` and `end_col_offset`, across the macro-expander surface. The four-field source range is now propagated through dialect-templates, run-time `fix_locations` plumbing, the multi-phase compiler's `__phase__` injection, and the source-location validator. PEP 657 precise tracebacks now point at the right thing.

**New**:

- **`mcpyrate.utils.get_end_lineno`**: end-of-region counterpart of `get_lineno`. Recursively searches an AST node, list of nodes, or AST marker, returning the first `end_lineno` value found (or `None` if none). Useful when a macro needs the source-text end of a tree, e.g. to construct a `SyntaxError` that highlights the offending region precisely.
- **`Dialect.end_lineno`** / **`Dialect.end_col_offset`**: new instance attributes on the dialect base class, populated by `DialectExpander` from the dialect-import statement (both the AST-based and text-based finders extract them). Mirrors the existing `Dialect.lineno` / `Dialect.col_offset`.
- **`Dialect.location_ref`**: synthetic AST node (an `ast.Constant`) bundling the four source-location fields. Produced by `DialectExpander` for every dialect instance. Suitable for passing to `splice_dialect` via the new `reference=` kwarg as a more compact alternative to enumerating the four fields by name.
- **`mcpyrate.splicing.splice_dialect`** accepts new optional `end_lineno=` and `end_col_offset=` keyword arguments. Source-transformer dialects that already pass `lineno` / `col_offset` should also pass the new fields so spliced template code carries complete source-location info.
- **`mcpyrate.splicing.splice_dialect`** also accepts a new optional `reference=` keyword argument: an AST node whose source-location fields supply all four values at once. The recommended idiom is `splice_dialect(body, template, reference=self.location_ref)`. The `reference=` form and the four explicit kwargs are mutually exclusive; passing both raises `TypeError`.

**Changed**:

- **`mcpyrate.metatools.fill_location`** now extracts `end_lineno` and `end_col_offset` from the invocation node (when present) and propagates them through the run-time `fix_locations` call. When the invocation carries no end-of-region fields, they are omitted; otherwise the resulting reference Constant has all four source-location fields set.
- **`mcpyrate.multiphase.multiphase_expand`** now attributes the injected `__phase__ = k` introspection helper to the first `with phase[...]` statement in the module — using `ast.copy_location` to pick up all four source-location fields — instead of the previous hardcoded `lineno=1, col_offset=1`. Debuggers and traceback formatters now point at the `with phase[...]` line (which is what introduced multi-phase compilation to the module) rather than at line 1 in the absence of a real source-text origin.
- **`mcpyrate.debug.SourceLocationInfoValidator`** default `check_fields` now includes `end_lineno` and `end_col_offset` alongside `lineno` / `col_offset`. The validator's `examine` method also filters `check_fields` against each node's `_attributes` so that nodes without source-text regions (e.g. `ast.Module`, `ast.Store`, `ast.Load`) are no longer falsely reported as missing source-location info. Closes #32.


---

**4.1.1** (8 May 2026) - hotfix:

**Fixed**:

- **`mcpyrate.importer.path_stats`** now handles source-level dialect files (e.g. brainfuck, Befunge) on first import. Previously, `path_stats` always called `ast.parse` on the full source text to discover macro-imports and dialect-imports for cache invalidation. For a source-level dialect file the body after the dialect-import line is in another language (not Python), so `ast.parse` raised `SyntaxError` before any dialect transformer had a chance to run, and `macropython hello_bf.py` (or plain `import`) failed with that error. The fix: catch `SyntaxError`, truncate the source at the failing line (which Python tells us via `exc.lineno`), and `ast.parse` just the Python prologue. The existing AST-based scan then finds macro-imports and dialect-imports normally — including multi-line parenthesized `from X import (macros, a, b, c)` in the prologue. AST-level dialect files and ordinary Python files take the original path and are unaffected.


---

**4.1.0** (23 April 2026) - *Splice the mainbrace* edition:

**New**:

- **`mcpyrate.dialects.split_at_dialectimport`**: helper for authors of source-transformer dialects. Given the full source text and the calling dialect's name, returns the triple `(prologue, other, body)` — the parts to concatenate in that order to form the transformer output. `prologue` is the text before the dialect-import line, `other` is a list of dialect-import lines to re-emit so subsequent dialect processing can still find them, and `body` is the text after. Correctly handles sharing a single `from X import dialects, A, B` line between a source-transformer dialect and other dialects (the calling dialect's name is stripped from the bindings list; the rewritten line goes into `other`).

**Fixed**:

- **Dialect-import scanner regex** now excludes newlines from the bindings-list character class, enforcing the documented "import must be on a single line" constraint. Latent bug, triggered only by source-transformer dialects whose body contains no `(` or `\` character (e.g. a brainfuck dialect): the regex previously ate the dialect-import line plus the entire module body as a single match, which then failed to parse as a Python statement. Ordinary Python dialects were unaffected because real Python code contains `(` very early.
- **Windows support for the `macropython` CLI**: `macropython` now forces UTF-8 on stdout and stderr at startup, so macro-enabled scripts can print any Unicode character on Windows. Previously, Windows defaulted to the `cp1252` code page, and any script that printed a non-Latin-1 character (e.g. `\u2015` HORIZONTAL BAR, or any box-drawing or non-Western glyph) crashed with `UnicodeEncodeError` inside Colorama's stdout writer. POSIX shells are UTF-8 by default, so this is a no-op on Linux and macOS.
- **`macropython --interactive` no longer crashes on Windows.** Previously, starting the interactive REPL with `macropython -i` would fail at the `import readline` line because Python's stdlib `readline` module is POSIX-only. The fix is a three-tier hybrid load: try stdlib `readline` first (Linux/macOS), fall back to `pyreadline3` (a drop-in Windows replacement; `pip install pyreadline3` to get the full experience), and finally degrade gracefully if neither is available — the REPL still starts through plain `input()`, you just lose command history and tab completion, and a startup notice explains how to restore them. Also covers `rlcompleter` the same way.
- **Tab completion now works on macOS** in `macropython --interactive`. Previously, `readline.parse_and_bind("tab: complete")` was issued unconditionally, but macOS ships `readline` backed by `libedit` (not GNU readline), which speaks a different `parse_and_bind` dialect — so tab completion silently did nothing on Macs. Now detects `platform.system() == "Darwin"` and issues `readline.parse_and_bind("bind ^I rl_complete")` on macOS instead.
- **Test suite now passes on Windows**, enabling Windows CI coverage. Three dev-side issues were blocking it:
  - `runtests.py` test discovery crashed on Windows with `re.error: bad escape (end of pattern) at position 0`, because `re.sub(os.path.sep, ...)` treated the backslash path separator as an incomplete regex escape. Fixed by using `str.replace`.
  - `runtests.py` demo runner crashed with `FileNotFoundError` because `rundemos()` hardcoded `/usr/bin/env python3` as the subprocess command. Fixed by using `sys.executable` (which is also strictly better on POSIX: it guarantees the demos run under the same interpreter as the test runner).
  - `test_120a_quotes.py` had an assertion that interpolated `__file__` into a Python-source-code string via f-string, which worked by accident on POSIX but mismatched on Windows (where `unparse()` properly escapes the path's backslashes). Fixed by using `{__file__!r}` on both sides.


---

**4.0.0** (16 March 2026) - *New snakes on a ship* edition:

**IMPORTANT**:

- **Python version support changed**: 3.10–3.14 (dropped 3.8, 3.9; added 3.13, 3.14).
  - If you need `mcpyrate` for Python 3.8 or 3.9, use version 3.6.x.

**Breaking**:

- Removed `getconstant()`, `Num`, `Str`, `Bytes`, `NameConstant`, `Ellipsis`, `Index`, `ExtSlice` from the `astcompat` public API. These deprecated AST node types no longer exist in Python 3.14. Use `ast.Constant.value` directly.
- Note for downstream macro authors: `visit_Num`/`visit_Str`/etc. on `NodeVisitor`/`NodeTransformer` are no longer called in Python 3.14 — use `visit_Constant` instead.
- `ASTMarker._fields` is now a class attribute (list) instead of being set only in `__init__`. Subclasses should define `_fields` at the class level — see the `ASTMarker` docstring for the recommended pattern. `mcpyrate`'s own quasiquote markers (`quotes.py`) have been updated accordingly. Downstream projects that subclass `ASTMarker` and use `self._fields += ["myfield"]` in `__init__` should migrate to the class-level idiom, but the old pattern still works.

**Fixed**:

- Updated AST field presence checks for Python 3.13 optional field defaults (`hasattr` → `getattr`). In Python 3.13, omitted optional AST fields are set to `None` instead of being absent, so `hasattr` always returns `True`. The `fix_locations()` engine, debug field checker, and related guards now use `getattr(..., None)` to correctly detect unset fields.
- Fix unparser crash on `Expression` nodes (`ast.parse(..., mode="eval")`). `Expression.body` is a single node, not a list — the unparser incorrectly tried to iterate it.
- Fix `splice_dialect` docstring concatenation: combined docstring was a bare `ast.Constant` instead of `ast.Expr(ast.Constant(...))`, producing an invalid module body.
- Fix `expand1sq` and `expandsq` block mode (`with expand1sq as quoted:`). Block-mode `q` produces an `Assign` wrapper that `expand1s`/`expands` could not handle, causing a `TypeError` from `unastify`. Block mode now handles the unastify-expand-requote cycle directly.

**New**:

- `macropython -c 'code'` — run a macro-enabled code snippet from the command line, like `python -c`. The code is compiled and run through `mcpyrate`, so macros work.
- Unparser support for type parameter defaults (Python 3.13, PEP 696): `type Response[T = str] = dict[str, T]`.
- Unparser support for t-strings (Python 3.14, PEP 750): `t"hello {name}"`. New AST node types `TemplateStr` and `Interpolation` added to `astcompat`.
- Test runner now supports version-suffixed test modules (`test_*_3_NN.py`), automatically skipping modules that require a newer Python than the running version.

**Changed**:

- **Breaking**: `macropython -c` (clean bytecode caches) renamed to `macropython -C`. The `-c` flag now runs a code snippet, matching Python's standard `-c` behavior. The `--clean` long form is unchanged.


---

**3.6.4** (16 April 2025) - hotfix:

**IMPORTANT REMINDER**:

When installing `mcpyrate`, pass the `--no-compile` flag to `pip`.

It is not possible to customize the compile command in the package metadata. Python's default (without the `--no-compile`) incorrectly precompiles `mcpyrate` into bytecode *without enabling macro support*. This will cause any package that depends on `mcpyrate` and attempts to use macros from `mcpyrate` (e.g. quasiquotes) to mysteriously fail.

See [README](README.md) and [troubleshooting](doc/troubleshooting.md) for details.

**Fixed**

- Fix text colorization mechanism so that `setcolor` and `colorize` now work correctly in the input prompt supplied to `input` when using `readline`. While `mcpyrate` itself doesn't use the feature in this particular way, it's part of the public API, so it has been fixed as part of obsessive correctness.


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
