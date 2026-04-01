# CC Brief: mcpyrate Modernization — Phases 2–4 (Implementation)

**Prerequisite**: Phase 1 audit report reviewed and approved. This brief incorporates its findings.

## Goal

Update mcpyrate from Python 3.8–3.12 to 3.10–3.14. This is a **major version bump to 4.0.0** — the floor bump and API removals are breaking changes.

Three phases, each a separate commit (or small group of commits). Don't mix cleanup with compat work — we need clean bisect boundaries.

mcpyrate is a macro expander — critical infrastructure for unpythonic and Raven. **Tread carefully.**

## Reference

- Phase 1 audit report (attached/in context).
- mcpyrate CLAUDE.md (in repo root) — architecture, compat checklist, code conventions.
- Consolidated AST change notes: https://github.com/Technologicat/unpythonic/issues/93
- mcpyrate issue #32: `end_lineno`/`end_col_offset` fields.

---

## Phase 2: Floor bump to 3.10

Drop support for Python 3.8 and 3.9. Remove dead code paths. This is mechanical cleanup.

### astcompat.py — remove deprecated node types and `getconstant()`

**Remove entirely** the deprecated-node imports and their `__all__` entries: `Num`, `Str`, `Bytes`, `NameConstant`, `Ellipsis`, `Index`, `ExtSlice`. These are dead code with floor at 3.10 — no parser emits them. This is a 4.0.0 breaking change; downstream code referencing these names from `astcompat` must update.

**Remove `getconstant()`** — all supported versions have `ast.Constant.value`. No internal callers; downstream users can access `.value` directly.

**Simplify `NamedExpr`**: the try/except can become a direct import (exists since 3.8).

Update the module docstring: "works in language versions 3.10 through 3.14".

### unparser.py — remove dead handlers and deprecated references

Remove dead dispatch handlers for removed node types:
- `_Bytes` (line ~647) — accesses `.s`, dead since 3.8
- `_Str` (line ~650) — accesses `.s`, dead since 3.8
- `_NameConstant` (line ~663) — dead since 3.8
- `_Num` (line ~666) — accesses `.n`, dead since 3.8
- `_Ellipsis` (line ~897) — dead since 3.8
- `_Index` (line ~900) — dead since 3.9
- `_ExtSlice` (line ~913) — dead since 3.9

Remove/simplify inline references to deprecated types:
- Line ~811: `isinstance(v, ast.Num) and isinstance(v.n, int)` → `isinstance(v, ast.Constant) and isinstance(v.value, int)`
- Line ~874: `type(v) is ast.Str` branch in `_JoinedStr_helper` — delete (the `ast.Constant` branch already handles this case)

Remove dead `hasattr` guards that are always `True` with floor ≥ 3.10:
- Lines ~929, ~934: `if hasattr(t, "posonlyargs"):` — `posonlyargs` exists since 3.8

Clean up dead `hasattr` on always-present fields:
- Line ~629: `if hasattr(t, "kind") and t.kind == "u":` → `if t.kind == "u":`
- Line ~919: `if hasattr(t, "annotation") and t.annotation:` → `if t.annotation:`

Update the module header: "Last updated for Python 3.14."

### expander.py — remove `sys.version_info` guards

Three sites checking `sys.version_info >= (3, 9, 0)` for `ast.Index` wrapper removal (lines ~104, ~175, ~452). With floor at 3.10, the `>= 3.9` branch is always taken. Delete the `else` branches and the conditionals.

### quotes.py — remove `sys.version_info` guard

Line ~957: same `ast.Index` wrapper check. Remove the conditional, keep only the 3.9+ branch.

### multiphase.py — replace `ast.Num` and remove version guard

- Lines ~63 and ~116: `type(arg) is ast.Num` / `type(macroarg) is ast.Num` — delete these branches (the `ast.Constant` branches already handle this case). Remove the `# TODO: Python 3.8: remove ast.Num` comments.
- Line ~109: `sys.version_info >= (3, 9, 0)` guard — remove, keep 3.9+ branch only.

### utils.py — simplify `getdocstring()`

Lines ~189–195: the whole block simplifies. Remove `ast.Str` from the outer `if`, then the inner `if`/`else` collapses — it's always `ast.Constant`:
```python
if type(body[0]) is ast.Expr and type(body[0].value) is ast.Constant:
    docstring_node = body[0].value  # Expr -> Expr.value
    return docstring_node.value
```

### test/test_quotes.py — simplify assertions

- Line ~43: `type(quoted[0].value) in (ast.Constant, ast.Num)` → `type(quoted[0].value) is ast.Constant`.
- Lines ~46–47: Remove `else: # ast.Num` branch and `.n` access.
- Line ~131: Remove alternative assertion string containing `ast.Num(n=42)`.

### pyproject.toml

- Bump version to `4.0.0`.
- Update `python_requires` to `>=3.10`.
- Update classifiers: remove 3.8, 3.9; add 3.13, 3.14.

### CI (.github/workflows/python-package.yml)

- Update matrix: remove 3.8, 3.9; add 3.13, 3.14.
- Update PyPy versions: remove pypy-3.8, pypy-3.9; keep/update pypy-3.10.

### Version metadata — docs and docstrings

Update version ranges in:
- `astcompat.py` docstring (line ~8): "3.6 through 3.12" → "3.10 through 3.14"
- `unparser.py` header (line ~8): "Last updated for Python 3.12" → "Last updated for Python 3.14"
- `quotes.py` (line ~831): "at least in Pythons 3.6, 3.7, 3.8, 3.9, 3.10" → update range
- `repl/macropython.py` (lines ~7–8): update TODO version list
- `README.md`: update supported versions (search for any mentions of 3.8, 3.9, or version ranges)
- `CLAUDE.md`: "Python 3.8–3.12" → "Python 3.10–3.14"

---

## Phase 3: Python 3.13 compatibility

### `hasattr` pattern fix — CRITICAL (10 sites)

In Python 3.13, omitted optional AST fields are set to `None` instead of being absent. `hasattr(node, "field")` now always returns `True`, breaking guards that relied on absence to detect "not set".

**Fix pattern depends on intent:**

For fields where `None` means "not set" (source location fields):
```python
# Before (broken on 3.13):
end_lineno = tree.end_lineno if hasattr(tree, "end_lineno") else None

# After:
end_lineno = getattr(tree, "end_lineno", None)
```

For guards that check "does this node have a meaningful value":
```python
# Before (broken on 3.13):
if not hasattr(tree, "lineno"):

# After:
if getattr(tree, "lineno", None) is None:
```

For guards that check multiple fields:
```python
# Before (broken on 3.13):
if not (hasattr(node, "lineno") and hasattr(node, "col_offset")):

# After:
if getattr(node, "lineno", None) is None or getattr(node, "col_offset", None) is None:
```

**Sites to fix (will break / silently malfunction on 3.13):**

**astfixers.py** `fix_locations()` — 7 sites:
- Line ~143: `hasattr(reference_node, "lineno") and hasattr(reference_node, "col_offset")` — guard never triggers
- Line ~168: `if not hasattr(tree, "lineno"):` — never sets missing lineno
- Line ~172: `tree.end_lineno if hasattr(tree, "end_lineno") else None` — fallback never executes
- Line ~177: `if not hasattr(tree, "col_offset"):` — same as 168
- Line ~181: `tree.end_col_offset if hasattr(tree, "end_col_offset") else None` — same as 172
- Line ~187: `reference_node.end_lineno if hasattr(reference_node, "end_lineno") else None`
- Line ~188: `reference_node.end_col_offset if hasattr(reference_node, "end_col_offset") else None`

**expander.py** — 1 site:
- Line ~520: `if not hasattr(macronode, "lineno") and not hasattr(macronode, "col_offset"):` — early-return guard never triggers

**metatools.py** — 1 site:
- Line ~141: `if not (hasattr(invocation, "lineno") and hasattr(invocation, "col_offset")):` — SyntaxError for missing location info never raised

**debug.py** — 1 site:
- Line ~260: `present = [hasattr(tree, x) for x in self.check_fields]` — fix: `[getattr(tree, x, None) is not None for x in self.check_fields]`

**Cleanup sites (accidentally correct, but should still be fixed for consistency):**

**dialects.py**:
- Lines ~440–441: `statement.lineno if hasattr(statement, "lineno") else None` → `getattr(statement, "lineno", None)`

**unparser.py**:
- Line ~153: `lineno_node.lineno if hasattr(lineno_node, "lineno") else None` → `getattr(lineno_node, "lineno", None)`

**utils.py**:
- Line ~210: `if hasattr(tree, "lineno"):` in `get_lineno()` → `if getattr(tree, "lineno", None) is not None:`

Note: `astfixers.py` lines ~150, ~154 use `"end_lineno" in tree._attributes` — this is the correct pattern and needs no change (`_attributes` is a class-level tuple).

### AST constructor strictness

The audit found **no issues** — all ~70 constructor calls supply required fields correctly. Missing `ctx` is by design (auto-fixed by `astfixers.py`); 3.13 defaults it to `Load()` which is harmless. No action needed.

### TypeVar/ParamSpec/TypeVarTuple `default_value` field

Added in 3.13. Surface syntax: `type Response[T = str] = dict[str, T]`.

**astcompat.py**: No changes needed — the types themselves exist since 3.12, only the field is new.

**unparser.py**: Three handlers need updating:
- `_TypeVar` (line ~1154): currently emits `name` and `: bound`. Add ` = default_value` when present.
- `_ParamSpec` (line ~1161): currently emits `**name`. Add ` = default_value`.
- `_TypeVarTuple` (line ~1166): currently emits `*name`. Add ` = default_value`.

Check how CPython's `ast.unparse` handles this for reference. Guard with `getattr(t, "default_value", None) is not None` so it's safe on 3.12 where the field doesn't exist. Add a `# Python 3.13+` comment at the guard.

### `ast.parse(optimize=...)`

No code changes needed. mcpyrate's compiler already passes `optimize` to `builtins.compile()`, which is the right place. Macros need the unoptimized AST. Document this decision in the commit message.

### New tests for Phase 3 changes

**`astfixers.fix_locations()`** — the `hasattr` fixes change the core location propagation engine. Add tests that:
- Construct AST nodes with missing location fields, run `fix_locations`, verify they get filled in.
- Construct AST nodes with `lineno=None` (the 3.13 "omitted" representation), verify they're treated as "not set" and get overwritten. Comment in the test code why `None` is the relevant value to test — it's how 3.13 represents omitted optional fields.
- Construct AST nodes with valid location fields, verify they're preserved.
- Verify `end_lineno`/`end_col_offset` propagation (both present and absent).

These are pure functions — no import hooks needed.

**`debug.py` field checker** — the `hasattr` fix changes what "present" means. Add a test with a node that has `lineno=None` vs `lineno=42`, verify the checker correctly reports presence/absence.

---

## Phase 4: Python 3.14 compatibility

### Removal of deprecated AST nodes — verify Phase 2 cleanup

In 3.14, `ast.Num`, `ast.Str`, `ast.Bytes`, `ast.NameConstant`, and `ast.Ellipsis` are fully removed. `ast.Index` and `ast.ExtSlice` still exist but are deprecated.

After Phase 2, there should be no remaining references to these types. **Verify** with a grep. Also verify no `.n` or `.s` property access remains on `ast.Constant` nodes.

### New AST nodes: `TemplateStr` and `Interpolation` (t-strings, PEP 750)

**astcompat.py**: Add conditional imports:
```python
try:  # Python 3.14+: t-strings (PEP 750)
    from ast import TemplateStr, Interpolation
except ImportError:
    TemplateStr = Interpolation = _NoSuchNodeType
```

Add to `__all__`.

**unparser.py**: Add `_TemplateStr` and `_Interpolation` handlers, always present (matching existing convention).

Structure mirrors f-strings. `TemplateStr` contains a `values` list of `Interpolation` and `Constant` nodes (`JoinedStr` uses `FormattedValue` and `Constant`). Use `t` prefix instead of `f`.

`Interpolation` has fields: `value` (expression node), `str` (original source text), `conversion` (int), `format_spec` (optional `JoinedStr`).

Model the handlers on the existing `_JoinedStr`/`_JoinedStr_helper` and `_FormattedValue`/`_FormattedValue_helper` pattern (lines ~834–879). Key differences from f-strings:
- Use `t'...'` prefix instead of `f'...'`.
- `Interpolation.str` holds the original expression source text. When unparsing, prefer `Interpolation.str` if available (preserves original formatting), fall back to unparsing `Interpolation.value` if `str` is `None` (for programmatically constructed nodes). See CPython issue [#138774](https://github.com/python/cpython/issues/138774) for edge cases.
- `Interpolation.conversion` and `Interpolation.format_spec` work the same as `FormattedValue.conversion` and `FormattedValue.format_spec`. Factor the conversion/format_spec rendering out of `_FormattedValue_helper` into a shared helper if not already separate, and reuse it for `_Interpolation`.

**utils.py `rename`**: No changes needed (confirmed by audit). `Interpolation.str` is expression source text, not an identifier. The generic `ast.iter_fields()` recursion handles any name-containing sub-nodes.

### New tests for Phase 4 changes

**Unparser round-trip for new syntax** — add tests that parse snippets containing the new constructs, unparse them, and verify the output:
- Type parameter defaults (3.13): `type Response[T = str] = dict[str, T]`
- T-strings (3.14): `t"hello {name}"`, `t"{value!r:>10}"`

Use bare `assert` (mcpyrate can't use `pytest` — pytest installs its own import hook to rewrite `assert`, which clobbers mcpyrate's import hook that's vital to the macro expander).

Tests containing new surface syntax **must go in separate modules** — the file won't even parse on older Pythons, so a version guard inside the module is too late. Use a version suffix in the filename: e.g. `test_unparser_3_13.py`, `test_unparser_3_14.py`. Update `runtests.py` to parse the suffix and skip modules whose version exceeds the running Python. Log skipped modules with a message like "Skipping test_unparser_3_14.py (requires Python 3.14+, running 3.13.x)". Convention: `test_*_3_NN.py` means "requires Python 3.NN+".

---

## Changelog

After all phases are complete, update `CHANGELOG.md` with a 4.0.0 entry covering:
- Python version support: 3.10–3.14 (dropped 3.8, 3.9; added 3.13, 3.14)
- Breaking: removed `getconstant()`, `Num`, `Str`, `Bytes`, `NameConstant`, `Ellipsis`, `Index`, `ExtSlice` from `astcompat` public API — use `ast.Constant.value` directly
- Updated AST field presence checks for Python 3.13 optional field defaults (`hasattr` → `getattr`)
- Added: unparser support for type parameter defaults (3.13), t-strings (3.14)
- Note for downstream macro authors: `visit_Num`/`visit_Str`/etc. on `NodeVisitor`/`NodeTransformer` are no longer called in Python 3.14 — use `visit_Constant` instead

---

## Testing

Run the full test suite and all demos **after each phase**, on all supported versions:
- Python 3.10 (floor, known working)
- Python 3.11 (supported, not explicitly tested)
- Python 3.12 (known working)
- Python 3.13
- Python 3.14

```bash
python runtests.py
```

Additionally, on 3.13, catch AST constructor warnings that would become errors in 3.15:

```bash
python -W error::DeprecationWarning runtests.py
```

---

## Files affected (summary)

| File | Phase 2 (floor bump) | Phase 3 (3.13 compat) | Phase 4 (3.14 compat) |
|------|---------------------|----------------------|----------------------|
| `astcompat.py` | remove deprecated types, `getconstant()`, simplify `NamedExpr` | — | add `TemplateStr`, `Interpolation` |
| `unparser.py` | remove 7 dead handlers, fix 2 inline refs, remove 4 dead guards | fix `hasattr` (1), add `default_value` to 3 type param handlers | add `_TemplateStr`, `_Interpolation` |
| `astfixers.py` | — | fix `hasattr` (7 sites, **critical**) | — |
| `expander.py` | remove 3 `sys.version_info` guards | fix `hasattr` (1) | — |
| `metatools.py` | — | fix `hasattr` (1) | — |
| `debug.py` | — | fix `hasattr` (1) | — |
| `dialects.py` | — | fix `hasattr` (2, cleanup) | — |
| `utils.py` | simplify `getdocstring()` | fix `hasattr` (1, cleanup) | — |
| `multiphase.py` | `ast.Num` → `ast.Constant`, remove version guard | — | — |
| `quotes.py` | remove version guard | — | — |
| `test/test_quotes.py` | simplify 3 assertions | — | — |
| `runtests.py` | — | — | version-suffix gating for test modules |
| `pyproject.toml` | version 4.0.0, `python_requires`, classifiers | — | — |
| CI workflow | update matrix | — | — |
| `README.md`, `CLAUDE.md` | update version ranges | — | — |
| `CHANGELOG.md` | — | — | add 4.0.0 entry (after all phases) |

## Style notes

Follow existing mcpyrate conventions: `from ... import ...` style, ~110 char line width, reStructuredText docstrings. See CLAUDE.md in repo root for full conventions.

The unparser is 1220 lines and tracks the Python grammar closely. When adding new node handlers, follow the existing dispatch pattern (method named `_NodeType`, registered via the dispatch dict at class level). Handlers are always present regardless of Python version (matching existing convention).
