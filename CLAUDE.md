# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is mcpyrate

Advanced macro expander and language lab for Python. MIT-licensed. Provides:

- **Syntactic macros** via import hooks — macros look like function calls/decorators/blocks but transform AST at import time.
- **Quasiquotes** — build AST using mostly-normal Python syntax.
- **Dialects** — whole-module source and AST transformers.
- **Multi-phase compilation** — a module can define and use macros in the same file.
- **REPL** — `macropython` CLI with macro support (IPython and standard console).

Single external dependency: `colorama`. This constraint is intentional — keep it that way.

## Build and Development

Uses PDM with `pdm-backend`. Python 3.10–3.14.

```bash
pdm install
pdm use --venv in-project
source .venv/bin/activate
```

The project venv is managed by PDM (`pdm venv create`, `pdm use --venv in-project`). To switch Python versions, remove the old venv and create a new one:

```bash
pdm venv remove in-project
pdm config venv.in_project true
pdm venv create 3.14   # or whichever version
pdm use --venv in-project
pdm install
```

**Critical**: Never precompile bytecode (`--compile`). Precompiled `.pyc` without the macro import hooks breaks macro imports.

Entry point: `macropython` (macro-enabled Python REPL/runner).

## Running Tests

Custom test runner (not pytest). Each test module exports a `runtests()` function. Tests live in `test/` (singular) subdirectories.

```bash
# Run all tests and demos (from repo root, with venv activated)
python runtests.py

# Run a single test module
python -c "import mcpyrate.activate; from mcpyrate.test.test_compiler import runtests; runtests()"
```

Test discovery: `runtests.py` walks subdirectories named `test/`, finds `test_*.py` files. Also runs demos from `demo/`.

**Test layering**: Test modules are numbered with zero-padded 3-digit BASIC-style gaps (005, 010, 020, ..., 130) so that lower-layer infrastructure is tested first and string sort gives the right execution order. The layer map is in `mcpyrate/test/__init__.py`.

**Macro-enabled tests**: Tests for macros should use real macro imports (`from ..quotes import macros, q, u, ...`) and invoke macros as macros — don't simulate the macro context by calling the function directly unless testing error paths that fire before the expansion machinery is needed. To run a macro-enabled test module standalone:

```bash
python -c "import mcpyrate.activate; from mcpyrate.test.test_120a_quotes import runtests; runtests()"
```

**Tests as API documentation**: Tests double as detailed API documentation. When a function return value documents an API contract, keep the `result = ...` assignment even if the value isn't used later, and annotate with `# noqa: F841, documents API return`.

**Linting new tests**: Lint any new or modified test files with `flake8 --select=F401,F841,F821`. Pay attention to:
  - **F841** (assigned but never used): Use `# noqa: F841, documents API return` when the assignment documents the API contract. Otherwise, remove.
  - **F821** (undefined name): Can legitimately occur in quoted code (`q[...]`). Use `# noqa: F821, only quoted` when the name only appears inside a quasiquote.
  - **F401** (unused import): Should almost always be cleaned up. The only exception is when the import documents a complete set of related names for the reader's benefit (e.g. importing all quasiquote operators `q, u, n, a, s, t, h` even if some aren't used in that file). Use `# noqa: F401` with a brief reason.

## Linting

```bash
# Hard errors (syntax errors, undefined names)
flake8 . --config=flake8rc --select=E9,F63,F7,F82 --show-source

# Soft warnings
flake8 . --config=flake8rc --exit-zero --max-line-length=127
```

## Documentation

Detailed documentation in `doc/`: `main.md` (comprehensive reference), `compiler.md`, `quasiquotes.md`, `dialects.md`, `walkers.md`, `repl.md`, `troubleshooting.md`. Consult these when working on specific subsystems — they cover semantics, edge cases, and design rationale that this file only summarizes.

## Architecture

### Pipeline: Source → AST → Bytecode

1. **`activate.py`** — Installs import hooks that intercept `.py` loading.
2. **`importer.py`** — Custom finder/loader. Injects dialect and macro expanders into the import process.
3. **`dialects.py`** — Source-level and AST-level whole-module transforms, applied before macro expansion.
4. **`expander.py`** — Finds and expands macro invocations in AST. The core loop.
5. **`core.py`** — How to apply a single macro invocation (name resolution, argument handling, error wrapping).
6. **`compiler.py`** — Compile macro-enabled code. Orchestrates the full pipeline. Also provides `run` and `create_module` for dynamic compilation.
7. **`multiphase.py`** — Multi-phase compiler: allows a module to define macros in an early phase and use them in a later phase.

### Macro Authoring Tools

- **`quotes.py`** (~1220 lines) — Quasiquote system. `q[]` captures AST, `u[]` unquotes values, `n[]` unquotes names, `a[]` splices ASTs, `h[]` hygienic captures. Macro hygiene implemented via UUID-tagged bindings. Note: `u[]` only accepts built-in types (numbers, strings, bytes, booleans, None) and containers (`list`, `dict`, `set`) thereof — use `h[]` for general values (object instances, functions). See `doc/quasiquotes.md` for full details.
- **`metatools.py`** — Macros for macro authors:
  - `macro_bindings` — Snapshot current macro bindings at expansion time, return as dict at run time.
  - `expand*` family — Expand macros programmatically. Suffixes `1srq` mean: `1` = one layer only, `s` = statically (at macro expansion time), `r` = dynamically (at run time), `q` = quote first. You'll most likely want `expandr` or `expand1r`. See `mcpyrate/test/test_quotes.py` for usage examples.
  - `stepr` — Like `debug.step_expansion`, but at run time.
  - `expand_first` — Force specific macros to expand before others.
  - `fill_location` — Fill missing source location info, recursively.
- **`walkers.py`** — AST walker base classes (`ASTVisitor`, `ASTTransformer`) with collector and state features.
- **`splicing.py`** — Utilities for splicing code into AST templates.
- **`markers.py`** — `ASTMarker` base class for inter-macro communication. Markers are AST-node-like objects that co-operating macros use to pass information to each other during expansion (e.g. the quasiquote system uses them internally, and downstream macro libraries can define their own). Postcondition: no markers may remain after expansion completes. New marker types can be added by subclassing `ASTMarker`. Utilities: `get_markers`, `delete_markers`, `check_no_markers_remaining`.

### Support Modules

- **`astcompat.py`** — Version-conditional AST node imports. Central contact point for Python version compatibility. Maps new/deprecated node types to dummies on versions that lack them.
- **`unparser.py`** (~1220 lines) — AST back to source code, with syntax highlighting and debug rendering of invisible nodes. Must be updated for each new Python grammar. Last updated for Python 3.12.
- **`astfixers.py`** — Fix `ctx` attributes and source location info after AST transforms.
- **`coreutils.py`** — Utilities for writing macro expanders and meta-metaprogramming.
- **`debug.py`** — Macro debugging: step expansion, AST dump, show bindings.
- **`colorizer.py`** — ANSI syntax highlighting for source code and AST dumps. Also usable as a standalone utility by downstream projects.
- **`bunch.py`** — `Bunch`: attribute-access dict implementing `MutableMapping`. Richer than `types.SimpleNamespace` (mapping protocol, zero-copy `bunchify()`, `copy`/`replace`). Used internally.
- **`utils.py`** — Assorted utilities:
  - `gensym` — Generate unique identifier string via UUID (e.g. `gensym("x")` → `"x_65cc5638..."`). Returns plain `str`, not an AST node.
  - `scrub_uuid` — Strip UUID suffix from a gensym'd name.
  - `rename` — Rename all occurrences of a name in an AST. Looks in all name-like slots (identifiers, attribute names, function/class names, parameter names, import names, etc.), not just `Name` nodes.
  - `extract_bindings` — Filter a macro bindings dict to only the given macro functions (by function identity, not name — handles as-imports). Used for selective macro expansion.
  - `flatten` — Flatten a nested list (used for AST statement suites).
  - `getdocstring` — Extract docstring from a body, if present.
  - `format_location`, `format_macrofunction`, `format_context` — Error message formatting.
- **`ansi.py`** — Lightweight POSIX-only ANSI escape codes, API-compatible with `colorama`. Used as fallback if `colorama` is unavailable (e.g. minimal Docker environments without full dependency install).
- **`pycachecleaner.py`** — Delete `__pycache__` directories. Used by the test runner and `macropython` (CLI option).

### REPL (`mcpyrate/repl/`)

- **`macropython.py`** — CLI entry point. Launches macro-enabled Python (IPython or standard console).
- **`console.py`** — Embeddable macro-enabled console (built on `code.InteractiveConsole`).
- **`iconsole.py`** — Embeddable macro-enabled IPython console.

## Python Version Compatibility

`astcompat.py`, `unparser.py`, and `utils.py` (`rename`) are the files most affected by Python version changes. When adding support for a new Python version:

1. Check for new/changed/removed AST node types → update `astcompat.py`.
2. Check for new syntax → update `unparser.py` to handle new node types.
3. Check for new name-like AST slots → update `rename` in `utils.py`.
4. Check for changes to `compile()`, `ast.parse()`, or import machinery → update `compiler.py` and `importer.py`.
5. Run the full test suite and all demos.

## Code Conventions

- **No external dependencies** besides `colorama`. This is a hard constraint.
- **Import style**: `from ... import ...` (consistent with unpythonic).
- **Line width** ~110 characters. Docstrings in reStructuredText.
- **Module size target**: ~100–300 SLOC, rough max ~700 lines. Some modules are longer when appropriate (e.g. `unparser.py` and `quotes.py` at ~1220 lines each — the grammar is large and the quasiquote system is inherently complex). Never split just because the line count was exceeded.

## Key Cross-Cutting Concerns

- The quasiquote system (`quotes.py`) is deeply intertwined with the expander — changes to expansion order or hygiene affect quasiquotes.
- `unparser.py` has a circular import workaround (`quotes = None` at module level, late-imported) to handle rendering of quasiquote markers.
- Multi-phase compilation (`multiphase.py`) builds on the compiler — understand `compiler.py` first.
- Dialect support runs *before* macro expansion — dialects can generate code that contains macro invocations.
