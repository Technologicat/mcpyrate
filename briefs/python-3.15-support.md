# CC Brief: Python 3.15 support (mcpyrate and unpythonic)

## Context

CPython 3.15 reached rc1 in August 2026. The fleet-wide support pass is tracked in `~/.claude/TODO_DEFERRED.md` under "Python 3.15 support pass across the fleet", which notes that `mcpyrate` and `unpythonic` track CPython's AST closely enough to set the pace for everything else.

`unpythonic`'s `requires-python = ">=3.10,<3.15"` cap is deliberate and stays until this work lands. A macro expander running against an AST grammar it does not know invites a crash, or worse, a silent misexpansion. Raising the cap is the *last* step, not the first.

Prior art for the analysis shape: unpythonic issue #93 (closed), which tracked the 3.10–3.12 AST changes by asking, per new form, which macro-layer components must learn to detect it. Same question applies here.

## State of things

Everything in this section was verified on 2026-08-16 against CPython sources and local test runs. Items needing work on a real 3.15 are marked **open**.

### Method — diff the grammar, not the prose

The What's New page buries AST changes across four sections and describes none of them precisely. The authoritative delta is the ASDL:

```bash
curl -sO https://raw.githubusercontent.com/python/cpython/3.14/Parser/Python.asdl   # → py314.asdl
curl -sO https://raw.githubusercontent.com/python/cpython/3.15/Parser/Python.asdl   # → py315.asdl
diff -u py314.asdl py315.asdl
```

Two further files settle how each change is actually represented — `Lib/_ast_unparse.py` (CPython's own unparser, the reference implementation for ours) and `Grammar/python.gram` (which node a given surface syntax builds). Worth keeping as the recipe for every future minor.

### The grammar delta, in full

```
-          | Import(alias* names)
-          | ImportFrom(identifier? module, alias* names, int? level)
+          | Import(alias* names, int? is_lazy)
+          | ImportFrom(identifier? module, alias* names, int? level, int? is_lazy)
-         | DictComp(expr key, expr value, comprehension* generators)
+         | DictComp(expr key, expr? value, comprehension* generators)
```

That is the entire change. No new node types; three changed fields, arising from two PEPs.

1. **PEP 810, explicit lazy imports.** `lazy import json`, `lazy from pathlib import Path`. Sets `is_lazy` on `Import` / `ImportFrom`.
   - Parsed nodes always carry `0` or `1` (`python.gram:228`, `_PyAST_Import(a, lazy ? 1 : 0, EXTRA)`); hand-constructed nodes get `None`, since the field is optional. Both are handled by branching on truthiness, which is what CPython's unparser does.
   - `lazy` is a genuine soft keyword, admitted only before `import` / `from` (`python.gram:124`). It does **not** collide with unpythonic's `lazy` macro: `lazy[...]`, `from unpythonic.syntax import macros, lazy`, and `lazy = 5` all still parse as before.
   - Lazy imports are legal only at module scope. Not in a function, class body, or `try` block; not `lazy from x import *`; not `lazy from __future__ import ...`.
2. **PEP 798, unpacking in comprehensions** — two distinct AST consequences, and they are not alike.
   - `{**d for d in dicts}` builds `DictComp(key=d, value=None)` (`python.gram:1071`, `_PyAST_DictComp(a, NULL, b, EXTRA)`). The mapping goes in `key`; `value` being `None` *is* the marker. This is the change most likely to fail silently, since `value` was previously always a node.
     - **The convention is mirrored from the one `Dict` already uses, so reasoning by analogy gives the wrong answer.** A dict *literal* `{**a}` is `Dict(keys=[None], values=[Name('a')])` — the `None` sits in *keys* and the mapping in *values*. A dict *comprehension* `{**d for ...}` puts the `None` in *value* and the mapping in *key*. Opposite halves, same idea. Anyone who knows the literal encoding and guesses the comprehension one will get it backwards.
     - `ast.dump` omits a `None` field entirely at default settings, so the dump of an unpacking `DictComp` shows no `value` at all rather than `value=None`. Easy to misread as the field being absent when it is present and `None`; pass `show_empty=True` when inspecting.
   - `[*L for L in lists]`, `{*s for s in sets}`, `(*L for L in lists)` need no grammar change: `listcomp` and `setcomp` take `star_named_expression` and `genexp` admits `starred_expression`, so `elt` is simply a `Starred`. CPython added no unparser code for these — existing `Starred` handling suffices.

### Behavioral changes

- **AST constructors now raise `TypeError`** on a missing required argument or an unknown keyword argument, promoted from the `DeprecationWarning` that has run since 3.13.
- **Instantiating an abstract AST node** (`ast.AST`, `ast.expr`) now warns; error in 3.20. **This does not affect our marker classes.** `Python-ast.c:5266` tests `PySet_Contains(state->abstract_types, Py_TYPE(self))` — exact type identity, not `issubclass` — so `ASTMarker(ast.AST)` and its subclasses are outside it. Neither project instantiates an abstract node directly.
- `ast.parse()` gained `module=`, and `ast.dump()` gained `color=`. Neither is required of us.

### What our own code already survives

- **No AST-constructor deprecations remain in either project.** Verified by running both suites on 3.14.6 under `-W error::DeprecationWarning`, with bytecode caches cleared first so every macro actually re-expands (a warm cache skips expansion and the check silently passes — clear it or the run proves nothing):
  - `mcpyrate`: full suite, exit 0, no warnings.
  - `unpythonic`: 3830 pass, 0 fail, 2 errors, neither AST-related (see "Adjacent findings").
  The 3.13-era constructor cleanup therefore holds, and the promotion to `TypeError` should be a non-event.
- **A value-less `DictComp` traverses safely through every mcpyrate-based walker.** `ASTVisitor` and `ASTTransformer` (`walkers.py:129,173`) inherit CPython's `generic_visit`, which skips a field whose value is neither a list nor an `AST` — so `value=None` is left alone rather than crashing.
- **unpythonic's `scopeanalyzer` needs no change.** Its comprehension branch (`scopeanalyzer.py:242`) reads only `generators`, and its import branch (`:337`) reads only `names` — so neither the new `is_lazy` field nor a value-less `DictComp` reaches it.

## Work items

Ordered by dependency: mcpyrate is unpythonic's dependency, so it goes first.

### 0. Get a 3.15 to test on

- Install from deadsnakes (`python3.15`, candidate `3.15.0~rc1-1+jammy1`), plus `-venv` and `-dev`.
- Record it in `NEW-MACHINE-SETUP.md` in dotclaude, alongside the other deadsnakes versions.
- Nothing below is finished until it has run on a real 3.15. The static analysis above is solid on *what changed*; it cannot confirm *how our code reacts*.

### 1. mcpyrate: the unparser

All four sites are in `mcpyrate/unparser.py`.

- `_Import` (line 329) — emit `lazy import ` when `t.is_lazy` is truthy.
- `_ImportFrom` (line 333) — emit `lazy from ` likewise.
- `_DictComp` (line 690) — emit `**` followed by `key` when `value` is `None`; otherwise the existing `key: value`.
- `_ImportFrom` (line 335) — **bug, unrelated to 3.15**: it writes `"." * t.level`, which raises on a constructed node that left `level` unset. CPython writes `t.level or 0`. Fix while in the file; separate commit.

`_ListComp` / `_SetComp` / `_GeneratorExp` (lines 669–690) should need no change, since `_Starred` (line 923) already writes the `*`. Confirm by test rather than by reading.

New test module `mcpyrate/test/test_020_unparser_3_15.py`, following the existing `test_020_unparser_3_13.py` / `_3_14.py` pattern — the version suffix is what gates it off on older interpreters. Round-trip at minimum: `lazy import x`, `lazy from x import y`, `{**d for d in dicts}`, `[*L for L in lists]`, `{*s for s in sets}`, `(*L for L in lists)`, and an async generator form.

### 2. mcpyrate: reject lazy macro-imports

**Decision taken 2026-08-16: a lazy macro-import is an error, not a silently-ignored modifier.**

A macro-import is consumed at expansion time, so deferring it is meaningless. Today `ismacroimport` (`coreutils.py:84`) tests only `isinstance(statement, ast.ImportFrom)`, so `lazy from mymacros import macros, ...` would be accepted as an ordinary macro-import and then rewritten to a plain `import mymacros` (`expander.py:643`, `dialects.py:609`), quietly discarding the `lazy`. Raise instead, with the source location, following whatever mcpyrate's established idiom is for a malformed macro-import — check what `get_macros` already raises for its error cases and match it rather than inventing a new failure mode.

Guard the whole thing on the attribute existing, so the code still runs on 3.10–3.14.

### 3. unpythonic: the open questions

These are the ones that need a live 3.15 and cannot be settled by reading.

- **open — `lazify` with a `Starred` comprehension element.** `lazify.py` has no comprehension-specific handling at all, and its `Starred` handling is scoped to call arguments (line 537) and container literals (line 770). A `Starred` in `elt` position is a new shape reaching the generic path. The hazard is wrapping the `Starred`'s value in a promise, since `*promise` fails at unpacking. Test `with lazify:` over each of the four new comprehension forms.
- **open — `autocurry` and `tailtools` over the same forms.** Same question, same reason; `tailtools.py:1011,1026` already reasons about `Starred` in a different context.
- **open — any macro that reads `DictComp.value` assuming a node.** The walkers are safe (verified above), but a macro that dereferences the field directly is not. Grep again once 3.15 is installed and the new forms can actually be parsed into test fixtures.
- **Raise the cap last.** `pyproject.toml`: `>=3.10,<3.15` → `>=3.10,<3.16`, plus the `Programming Language :: Python :: 3.15` classifier. Only after the above are green. Note the fleet TODO's warning: an *unbounded* floor makes the resolver seek a version valid for every future Python and silently fall back to an ancient release, so keep the upper bound, just move it.

### 4. pyan, the third AST user

Tracked separately in `pyan/briefs/python-3.15-support.md`, and independent of this work — no dependency either way, so it can be done first, last, or in parallel.

Worth knowing while reading this brief: **pyan is the only one of the three that actually crashes on 3.15.** Its `analyze_comprehension` visits `DictComp.value` unconditionally, so a `{**d for ...}` anywhere in the analyzed codebase raises `AttributeError`. It also declares no upper `requires-python` bound, so it installs happily on the version that breaks it. The macro layer, by contrast, is cap-protected and has no known crash.

### 5. Fleet follow-on

Out of scope for this brief, but unblocked by it: CI matrices everywhere, the `cp315-*` cibuildwheel pins in pylu / pydgq / python-wlsqm, and the stale-coverage-Python item that the fleet TODO says to fold into the same pass.

## Adjacent findings

Surfaced by the deprecation run; neither is an AST issue and neither blocks this work.

- `unpythonic/tests/test_typecheck.py:205` errors under `-W error::DeprecationWarning` because `isinstance` against `typing.ByteString` reaches `collections.abc.ByteString`, deprecated and slated for removal in 3.17. 3.15 widens the warning to mere import or attribute access. Needs version gating before 3.17 regardless.
- `unpythonic/dialects/tests/test_pytkell.py:50` still uses the `return` form inside `with test:`, which unpythonic itself deprecates in favour of `expect[]`. It will break when the `return` form is un-hijacked in a future major release.

Both were found because `-W error::DeprecationWarning` promotes *every* deprecation, not only CPython's — which is the point of running it that way.
