# mcpyrate Phase 1 Audit: Python 3.10–3.14 Compatibility

Target version range: **3.10–3.14** (current: 3.8–3.12).

**This update requires a major version bump to 4.0.0** — the floor bump (3.8 → 3.10) and `getconstant()` removal are breaking changes.

---

## 1. AST Constructor Strictness (3.13)

Python 3.13 emits `DeprecationWarning` (error in 3.15) when AST node constructors receive unknown kwargs or are missing required fields.

**Result: No issues found.** All ~70 AST constructor calls across the codebase supply all required fields correctly. Missing `ctx` fields are by design (auto-fixed by `astfixers.py`); in 3.13 they default to `Load()` which is harmless since `astfixers` overwrites anyway.

Files audited: `quotes.py` (31 calls), `splicing.py` (5), `metatools.py` (11), `coreutils.py` (10), `multiphase.py` (3), `compiler.py` (1), `dialects.py` (2), `repl/console.py` (2), `test/test_quotes.py` (3).

---

## 2. `hasattr` Checks on AST Node Fields (3.13)

In 3.13, omitted optional AST fields are set to `None` instead of being absent. `hasattr(node, "field")` now always returns `True`.

### astfixers.py — `fix_locations()` (CRITICAL)

| Line | Code | Severity |
|------|------|----------|
| 143 | `if not (hasattr(reference_node, "lineno") and hasattr(reference_node, "col_offset")):` | **will break** — guard never triggers; invalid nodes proceed |
| 168 | `if not hasattr(tree, "lineno"):` | **will break** — always `True`, never sets missing lineno |
| 172 | `tree.end_lineno if hasattr(tree, "end_lineno") else None` | **will break** — fallback to `None` never executes |
| 177 | `if not hasattr(tree, "col_offset"):` | **will break** — same as 168 |
| 181 | `tree.end_col_offset if hasattr(tree, "end_col_offset") else None` | **will break** — same as 172 |
| 187 | `reference_node.end_lineno if hasattr(reference_node, "end_lineno") else None` | **will break** — same |
| 188 | `reference_node.end_col_offset if hasattr(reference_node, "end_col_offset") else None` | **will break** — same |

Lines 150, 154 use `"end_lineno" in tree._attributes` — this is the **correct** pattern and needs no change.

**Fix pattern:** Replace `hasattr(node, "field")` with `getattr(node, "field", None) is not None` or check `"field" in node._attributes` depending on intent. For lines 168/177, the intent is "does this node have a lineno/col_offset *value*", so `node.lineno is not None` is appropriate.

### expander.py

| Line | Code | Severity |
|------|------|----------|
| 520 | `if not hasattr(macronode, "lineno") and not hasattr(macronode, "col_offset"):` | **will break** — early-return guard never triggers; macro-generated nodes without real location info won't be detected |

### metatools.py

| Line | Code | Severity |
|------|------|----------|
| 141 | `if not (hasattr(invocation, "lineno") and hasattr(invocation, "col_offset")):` | **will break** — `SyntaxError` for missing location info never raised |

### dialects.py

| Line | Code | Severity |
|------|------|----------|
| 440 | `statement.lineno if hasattr(statement, "lineno") else None` | **cleanup** — always `True` now, but fallback value (`None`) matches what you'd get anyway, so behavior is accidentally correct |
| 441 | `statement.col_offset if hasattr(statement, "col_offset") else None` | **cleanup** — same |

### unparser.py

| Line | Code | Severity |
|------|------|----------|
| 153 | `lineno_node.lineno if hasattr(lineno_node, "lineno") else None` | **cleanup** — same accidental correctness as dialects.py |
| 629 | `if hasattr(t, "kind") and t.kind == "u":` | **cleanup** — `kind` is always present on `ast.Constant`; the `hasattr` is dead weight. Replace with `if t.kind == "u":` |
| 919 | `if hasattr(t, "annotation") and t.annotation:` | **cleanup** — `annotation` is always present on `arg` nodes. The `hasattr` is dead weight. Replace with `if t.annotation:` |
| 929, 934 | `if hasattr(t, "posonlyargs"):` | **cleanup** — `posonlyargs` exists on `arguments` since 3.8; always `True` with floor ≥ 3.10. Dead guard. |

### debug.py

| Line | Code | Severity |
|------|------|----------|
| 260 | `present = [hasattr(tree, x) for x in self.check_fields]` | **will break** — default use case checks source location info, where `None` is invalid and should be flagged. In macro authoring the most likely error is forgetting to provide the field at all, and in 3.13 the field exists as `None`. Fix: `getattr(tree, x, None) is not None` to treat `None` as "not meaningfully present". |

### utils.py

| Line | Code | Severity |
|------|------|----------|
| 210 | `if hasattr(tree, "lineno"):` | **cleanup** — in `get_lineno()`, always `True` on AST nodes with `lineno` in `_attributes`. Returns `None` if value is `None`, which propagates correctly. |

---

## 3. Deprecated/Removed AST Nodes (3.14)

`ast.Num`, `ast.Str`, `ast.Bytes`, `ast.NameConstant`, `ast.Ellipsis` are **removed** in 3.14. Also removed: `.n` and `.s` compat properties on `ast.Constant`.

### astcompat.py (compat layer — remove deprecated types)

Lines 56–59 import `Num`, `Str`, `Bytes`, `NameConstant`, `Ellipsis` with fallback. Lines 61–66 import `Index`, `ExtSlice` with fallback. Lines 82–90 in `getconstant()` have fallback branches for all of these.

With floor at 3.10, these deprecated types are all dead code — the compiler hasn't emitted `Num`/`Str`/`Bytes`/`NameConstant`/`Ellipsis` since 3.6, and `Index`/`ExtSlice` since 3.9. **Remove** the deprecated type imports (lines 53–66), their `__all__` entries (line 15–16), and `getconstant()` entirely (lines 71–91). With the fallback branches gone, the function reduces to `return tree.value` with a type check — not worth an abstraction. It has no internal callers; it's only exported as a public API convenience. Downstream users can just access `.value` directly.

**Breaking change:** `getconstant()`, `Num`, `Str`, `Bytes`, `NameConstant`, `Ellipsis`, `Index`, and `ExtSlice` are all part of the public API (exported in `__all__`). Removing them requires a **major version bump to 4.0.0**. This fits naturally alongside the floor bump (3.8 → 3.10), which is itself a breaking change.

### multiphase.py (WILL BREAK on 3.14)

| Line | Code | Category |
|------|------|----------|
| 63 | `elif type(arg) is ast.Num:` + `n = arg.n` | 3.14 compat — dead branch (CPython 3.8+ uses `ast.Constant`), but references removed type |
| 116 | `elif type(macroarg) is ast.Num:` + `macroarg.n -= 1` | 3.14 compat — same |

Both have `# TODO: Python 3.8: remove ast.Num` — the TODO comment is misleading (should say "remove when floor ≥ 3.8", which it now is).

### unparser.py (WILL BREAK on 3.14)

| Line | Code | Category |
|------|------|----------|
| 647–648 | `def _Bytes(self, t):` — accesses `t.s` | 3.14 compat — dead handler (3.8+ uses `Constant`) |
| 650–651 | `def _Str(self, tree):` — accesses `tree.s` | 3.14 compat — dead handler |
| 663–664 | `def _NameConstant(self, t):` — accesses `t.value` | 3.14 compat — dead handler |
| 666–669 | `def _Num(self, t):` — accesses `t.n` | 3.14 compat — dead handler |
| 810–811 | `isinstance(v, ast.Num) and isinstance(v.n, int)` | 3.14 compat — fallback in `_Attribute` |
| 874–875 | `elif type(v) is ast.Str:` — accesses `v.s` | 3.14 compat — fallback in `_JoinedStr_helper` |
| 897–898 | `def _Ellipsis(self, t):` | 3.14 compat — dead handler |
| 900–901 | `def _Index(self, t):` | floor bump cleanup — dead since 3.9 |
| 913–914 | `def _ExtSlice(self, t):` | floor bump cleanup — dead since 3.9 |

### utils.py (WILL BREAK on 3.14)

| Line | Code | Category |
|------|------|----------|
| 189 | `type(body[0].value) in (ast.Constant, ast.Str)` | 3.14 compat — `ast.Str` ref in `getdocstring()` |
| 194–195 | `else:  # ast.Str` + `return docstring_node.s` | 3.14 compat — accesses `.s` property |

### test/test_quotes.py (WILL BREAK on 3.14)

| Line | Code | Category |
|------|------|----------|
| 43 | `assert type(quoted[0].value) in (ast.Constant, ast.Num)` | 3.14 compat |
| 46–47 | `else:  # ast.Num` + `assert quoted[0].value.n == 42` | 3.14 compat — accesses `.n` |
| 131 | `f"...ast.Num(n=42)..."` in assertion expected string | 3.14 compat — string will never match |

---

## 4. New AST Node Types

### 4a. Type parameter defaults — `default_value` field (3.13)

`TypeVar`, `ParamSpec`, `TypeVarTuple` gain a `default_value` field in 3.13 (PEP 696).

**astcompat.py** (lines 48–51): Already imports these nodes for 3.12+. No change needed for the import.

**unparser.py** — handlers exist but don't emit `default_value`:

| Line | Handler | Gap |
|------|---------|-----|
| 1154–1159 | `_TypeVar` — emits `name` and `: bound` | **Missing** ` = default_value` |
| 1161–1164 | `_ParamSpec` — emits `**name` | **Missing** ` = default_value` |
| 1166–1169 | `_TypeVarTuple` — emits `*name` | **Missing** ` = default_value` |

**Category:** 3.13 compat. **Severity:** will produce incorrect output for type params with defaults.

### 4b. T-strings — `TemplateStr` and `Interpolation` (3.14)

PEP 750 adds t-strings with new AST nodes `TemplateStr` and `Interpolation`.

**Current f-string handling** — only in `unparser.py`:

| Line | Handler | What it does |
|------|---------|-------------|
| 834–840 | `_FormattedValue` | Wraps single `{expr}` in `f'...'` |
| 842–860 | `_FormattedValue_helper` | Emits `{expr!conv:spec}` |
| 862–865 | `_JoinedStr` | Wraps f-string in `f'...'` |
| 867–879 | `_JoinedStr_helper` | Iterates `values` — `Constant` or `FormattedValue` |

**Confirmed:** `JoinedStr`/`FormattedValue` appear **only** in `unparser.py`. The quasiquote system, walkers, and expander treat them as opaque expression nodes. This means t-string support needs:

1. **astcompat.py** — Add `TemplateStr`, `Interpolation` with `try/except ImportError` fallback
2. **unparser.py** — Add `_TemplateStr` and `_Interpolation` handlers (mirror the f-string pattern)

**utils.py `rename`** (lines 84–147): No changes needed. `Interpolation.conversion` is an integer, not a name-like field. The generic `ast.iter_fields()` recursion handles any name-containing sub-nodes.

**Category:** 3.14 compat. **Severity:** will crash on t-string ASTs.

---

## 5. Version Metadata

### pyproject.toml

- `requires-python = ">=3.8"` — needs update to `">=3.10"`
- Classifiers list 3.8, 3.9, 3.10, 3.11, 3.12 — needs 3.13, 3.14 added; 3.8, 3.9 removed

### CI (.github/workflows/python-package.yml)

- Matrix: `["3.8", "3.9", "3.10", "3.11", "3.12", pypy-3.8, pypy-3.9, pypy-3.10]`
- Needs: add 3.13, 3.14; remove 3.8, 3.9; update PyPy versions

### sys.version_info checks (all `>= (3, 9, 0)` — floor bump cleanup)

| File | Line | Code |
|------|------|------|
| expander.py | 104 | `if sys.version_info >= (3, 9, 0):` — `ast.Index` wrapper |
| expander.py | 175 | `if sys.version_info >= (3, 9, 0):` — same |
| expander.py | 452 | `if sys.version_info >= (3, 9, 0):` — same |
| quotes.py | 957 | `if sys.version_info >= (3, 9, 0):` — same |
| multiphase.py | 109 | `if sys.version_info >= (3, 9, 0):` — same |

All five check for the `ast.Index` wrapper removal in 3.9. With floor at 3.10, the `>= 3.9` branch is always taken — delete the `else` branches and the conditionals.

### Version-gating in unparser.py (floor bump cleanup)

| Line | Code | Notes |
|------|------|-------|
| 929, 934 | `if hasattr(t, "posonlyargs"):` | `posonlyargs` exists since 3.8 — always `True`. Remove guard. |

### Docstrings/comments mentioning version ranges

| File | Line | Current text | Action |
|------|------|-------------|--------|
| astcompat.py | 8 | "works in language versions 3.6 through 3.12" | update |
| unparser.py | 8 | "Last updated for Python 3.12" | update |
| quotes.py | 831 | "at least in Pythons 3.6, 3.7, 3.8, 3.9, 3.10" | update |
| README.md | — | "We support 3.8, 3.9, 3.10, 3.11, 3.12" | update |
| CLAUDE.md | — | "Python 3.8–3.12" | update |
| repl/macropython.py | 7–8 | TODO: test on CPython 3.11, 3.12 / PyPy 3.8–3.10 | update to 3.10–3.14 + current PyPy versions. Consider adding automated tests for `macropython` to reduce manual testing burden. |

---

## Summary by File

### astfixers.py
- 7 `hasattr` sites that **will break** in 3.13 (lines 143, 168, 172, 177, 181, 187, 188)

### expander.py
- 1 `hasattr` site that **will break** in 3.13 (line 520)
- 3 `sys.version_info` guards to remove (floor bump, lines 104, 175, 452)

### multiphase.py
- 2 `ast.Num` references to remove (lines 63, 116) — 3.14 compat / floor bump
- 1 `sys.version_info` guard to remove (floor bump, line 109)

### unparser.py
- 7 dead dispatch handlers for removed node types (lines 647, 650, 663, 666, 897, 900, 913) — remove
- 2 inline references to removed types (lines 811, 874) — simplify
- 3 `_TypeVar`/`_ParamSpec`/`_TypeVarTuple` handlers missing `default_value` — 3.13 compat
- 2 new handlers needed: `_TemplateStr`, `_Interpolation` — 3.14 compat
- 2 `hasattr` guards that are dead code with floor ≥ 3.10 (lines 929, 934) — cleanup

### utils.py
- 2 `ast.Str` references to remove in `getdocstring()` (lines 189, 194–195) — 3.14 compat / floor bump
- 1 `hasattr` in `get_lineno()` — cleanup (line 210)

### metatools.py
- 1 `hasattr` site that **will break** in 3.13 (line 141)

### dialects.py
- 2 `hasattr` sites — cleanup only (lines 440, 441)

### quotes.py
- 1 `sys.version_info` guard to remove (floor bump, line 957)

### astcompat.py
- **Remove** deprecated type imports (`Num`, `Str`, `Bytes`, `NameConstant`, `Ellipsis`, `Index`, `ExtSlice`), their `__all__` entries, and `getconstant()` — all dead code with floor at 3.10
- Add `TemplateStr`, `Interpolation` for 3.14
- Update docstring version range

### debug.py
- 1 `hasattr` site that **will break** in 3.13 (line 260) — `None` is invalid for source location info, needs to be flagged

### test/test_quotes.py
- 3 sites referencing `ast.Num` (lines 43, 46–47, 131) — simplify

### pyproject.toml, CI, README, CLAUDE.md
- Version metadata updates

---

## Priority Order

1. **`hasattr` fixes (3.13)** — 10 sites that will silently malfunction: astfixers.py (7), expander.py (1), metatools.py (1), debug.py (1)
2. **Removed AST node references (3.14)** — 11 code sites + 3 test sites referencing `ast.Num`/`ast.Str` etc., will crash
3. **Floor bump cleanup (3.10)** — 5 `sys.version_info` guards, dead `hasattr` guards in unparser.py (lines 629, 919, 929, 934), dead unparser handlers (`_Index`, `_ExtSlice`, `_Bytes`, `_Str`, `_Num`, `_NameConstant`, `_Ellipsis`)
4. **astcompat.py cleanup** — remove deprecated type imports/exports (`Num`, `Str`, `Bytes`, `NameConstant`, `Ellipsis`, `Index`, `ExtSlice`) and `getconstant()`
5. **New node support** — `default_value` on type params (3.13), `TemplateStr`/`Interpolation` (3.14)
6. **Version metadata** — pyproject.toml, CI, docs
7. **macropython automated tests** — currently manual-only; bottleneck for version validation
