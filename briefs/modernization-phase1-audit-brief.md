# CC Brief: mcpyrate Modernization — Phase 1 (Audit)

## Context

mcpyrate is being updated from Python 3.8–3.12 to 3.10–3.14. Before making any code changes, we need an audit of the codebase to identify everything that needs attention.

mcpyrate is a macro expander — critical infrastructure. No code changes in this phase, only a report.

## Reference

- mcpyrate CLAUDE.md (in repo root) — architecture, compat checklist.
- mcpyrate issue #32: `end_lineno`/`end_col_offset` fields (opened 2022, still open).
- unpythonic issue #93: consolidated AST change notes across projects.

## What to audit

### 1. AST constructor strictness (3.13)

In 3.13, omitting required fields or passing unknown kwargs on `ast.*` node constructors emits `DeprecationWarning`; this becomes an error in 3.15.

**Scan every AST node constructor call** in the codebase. For each, verify all required fields are passed. The files with the most AST construction:

- `quotes.py` (~1220 lines) — heavy AST construction for quasiquotes
- `splicing.py` — code splicing utilities
- `astfixers.py` — ctx and location fixers
- `metatools.py` — macro-authoring tools
- `coreutils.py` — expander utilities
- `multiphase.py` — multi-phase compiler
- `test/dialects.py` — test dialect implementations

Common patterns to check:
- `ast.Call(func, args, keywords)` — three positional args, fine.
- `ast.Constant(value=...)` — fine (value is the only required field).
- Any node construction that passes extra keyword args not in the node's `_fields` — this now warns.

**Exception — `ctx` fields**: Many AST node constructors in mcpyrate intentionally omit `ctx` (e.g. `ast.Name(id=...)`). This is by design — `astfixers.py` infers and auto-injects the correct `ctx` after macro expansion. In 3.13, omitted `ctx` defaults to `Load()`, which is harmless since `astfixers` overwrites it anyway. **Do not flag missing `ctx` as an issue.**

### 2. `hasattr` checks on AST node fields (3.13)

In 3.13, omitted optional fields are set to `None` (not absent). Code that uses `hasattr(node, "field")` to detect absence will now always get `True`.

**Known `hasattr` instances in `astfixers.py`** (source location handling, issue #32):
- Line ~172: `tree.end_lineno if hasattr(tree, "end_lineno") else None`
- Line ~181: `tree.end_col_offset if hasattr(tree, "end_col_offset") else None`
- Lines ~187–188: `hasattr(reference_node, "end_lineno")`, `hasattr(reference_node, "end_col_offset")`

Also scan `expander.py`, `dialects.py`, `unparser.py`, and anywhere else for `hasattr` checks on optional AST fields.

Note: `astfixers.py` also has `"end_lineno" in tree._attributes` checks (lines ~150, ~154). These are fine — `_attributes` is a class-level tuple, unaffected by the 3.13 change. But review the surrounding code anyway to make sure nothing nearby depends on the old `hasattr` semantics.

### 3. Direct references to deprecated/removed AST nodes (3.14)

`ast.Num`, `ast.Str`, `ast.Bytes`, `ast.NameConstant`, `ast.Ellipsis` are removed in 3.14. Find all references outside `astcompat.py`:

**Known instances** (but verify — there may be more):
- `unparser.py`: `_Str` method, `_Num` method, `isinstance(v, ast.Num)`, `type(v) is ast.Str`
- `multiphase.py`: `type(arg) is ast.Num` (two sites)
- `utils.py`: `type(body[0].value) in (ast.Constant, ast.Str)`
- `test_quotes.py`: `ast.Constant, ast.Num` checks, `ast.Num(n=42)` in assertion string

Also check for `.n` and `.s` property access on `ast.Constant` nodes — these compat properties are removed in 3.14. Use `.value` instead.

### 4. New AST node types to support

- **3.13**: `TypeVar`/`ParamSpec`/`TypeVarTuple` gain `default_value` field. Check whether the unparser handles these node types at all — it's unclear whether mcpyrate currently supports type parameter syntax in any capacity. If it does, the unparser needs to emit ` = <default>` when `default_value` is not `None`. Either way, flag the current state.

- **3.14**: New `TemplateStr` and `Interpolation` nodes (t-strings, PEP 750). These need `astcompat.py` entries and `unparser.py` handlers.

  To determine the scope of t-string support needed, **scan the codebase for existing f-string handling** — specifically, references to `JoinedStr` and `FormattedValue` (the f-string AST nodes). These appear in:
  - `unparser.py` (known: `_JoinedStr`, `_FormattedValue`, helper methods)
  - Anywhere else? Check `quotes.py`, `walkers.py`, `expander.py`, `utils.py`.

  Preliminary finding: f-strings appear to be handled only in the unparser — the quasiquote system, walkers, and expander treat them as opaque expression nodes. If this is confirmed, t-strings need only `unparser.py` + `astcompat.py` work. But the audit should verify this.

Check `utils.py` `rename` for any name-like fields on `Interpolation` that might need handling.

### 5. Version metadata

- `pyproject.toml`: current `python_requires` and classifiers.
- Any version-gated logic (e.g. `sys.version_info` checks).
- Module docstrings that mention version ranges.

## Deliverable

A report (markdown) listing all sites that need attention, grouped by file. For each site, note:
- File and line number
- What the issue is
- Category: floor bump cleanup (dead code for < 3.10) / 3.13 compat / 3.14 compat
- Severity (will break / will warn / cleanup only)

No code changes.
