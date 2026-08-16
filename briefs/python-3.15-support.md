# CC Brief: Python 3.15 support (mcpyrate and unpythonic)

## Context

CPython 3.15 reached rc1 in August 2026. The fleet-wide support pass is tracked in `~/.claude/TODO_DEFERRED.md` under "Python 3.15 support pass across the fleet", which notes that `mcpyrate` and `unpythonic` track CPython's AST closely enough to set the pace for everything else.

`unpythonic`'s `requires-python = ">=3.10,<3.15"` cap is deliberate and stays until this work lands. A macro expander running against an AST grammar it does not know invites a crash, or worse, a silent misexpansion. Raising the cap is the *last* step, not the first.

**mcpyrate itself declares `>=3.10` with no upper bound, and should have the same cap.** It is the expander — the project the argument for capping applies to most directly — and on 3.15 it does not import at all (item 1 below). Of the three AST users only `unpythonic` is currently protected; `mcpyrate` and `pyan` both advertise support for the version that breaks them. Same timing caveat as pyan's brief records: a cap only reaches users through a release, and adding one locally obstructs setting up the 3.15 venv this work needs, so land it with the fix rather than ahead of it.

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

**Read the scope of that deprecation run carefully: it was on 3.14, and 3.14 cannot parse any of the new forms.** It establishes that no AST-constructor deprecation remains; it establishes nothing whatever about behaviour on 3.15. Treating "the suite is green on 3.14" as evidence about 3.15 is how the import-hook blocker below went unnoticed through an otherwise thorough grammar survey.

### Measured on 3.15.0rc1, with the import-hook fix applied

Unparser round-trip, run against a patched scratch copy:

| Input | Result | |
|---|---|---|
| `[*L for L in lists]` | `[*L for L in lists]` | correct |
| `(*L for L in lists)` | `(*L for L in lists)` | correct |
| `{k: v for k, v in p}` | `{k: v for (k, v) in p}` | correct, unchanged |
| `lazy import json` | `import json` | **silently wrong** — laziness dropped, no error |
| `lazy from pathlib import Path` | `from pathlib import Path` | **silently wrong** |
| `{**d for d in dicts}` | `UnparserError` | fails loudly, degrades to an AST dump |

The two `lazy` rows are the dangerous ones. Unparsed output is what a macro's expansion becomes, so dropping the modifier turns a deferred import into an eager one with nothing raised anywhere. The `DictComp` case at least announces itself — `unparse_with_fallbacks` catches it and the message already guesses the cause ("or a new AST node type from a recent Python").

## Work items

Ordered by dependency: mcpyrate is unpythonic's dependency, so it goes first.

### 0. Get a 3.15 to test on

- Install from deadsnakes (`python3.15`, candidate `3.15.0~rc1-1+jammy1`), plus `-venv` and `-dev`.
- Record it in `NEW-MACHINE-SETUP.md` in dotclaude, alongside the other deadsnakes versions.
- Nothing below is finished until it has run on a real 3.15. The static analysis above is solid on *what changed*; it cannot confirm *how our code reacts*.

### 1. mcpyrate: the import hook — **blocker, and not an AST issue at all**

**On 3.15, mcpyrate does not import.** Nothing else in this brief can be tested until this is fixed, and unpythonic is blocked behind it too.

```
TypeError: source_to_xcode() takes 3 positional arguments but 4 were given
```

`importer.py:21` defines `source_to_xcode(self, data, path, *, _optimize=-1)`, monkey-patched into `importlib.machinery.SourceFileLoader.source_to_code`. In 3.15 that method gained a third positional parameter and the caller passes it:

```python
# /usr/lib/python3.15/importlib/_bootstrap_external.py
def source_to_code(self, data, path, fullname=None, *, _optimize=-1):    # :801
code_object = self.source_to_code(source_bytes, source_path, fullname)   # :877
```

This is the "many functions related to compiling or parsing Python code now allow the module name to be passed" item in the What's New — which reads like an additive convenience and is in fact a breaking protocol change for anyone overriding the method.

Accepting the parameter — `def source_to_xcode(self, data, path, fullname=None, *, _optimize=-1)` — is enough to make mcpyrate import again; verified on a scratch copy on 3.15.0rc1. But stopping there would leave the *feature* the change exists to deliver silently broken, so it is the smaller half of the job.

**What `fullname` is for, and why mcpyrate currently swallows it.** CPython 3.15 threads the name into `compile(..., module=fullname)`, and `module=` sets the name that syntax warnings are attributed to, so that `-W` and `warnings.filterwarnings(..., module=...)` can select by module. Measured on 3.15.0rc1, filtering `SyntaxWarning` on `module=r"mypkg\..*"`:

| `compile(..., module=)` | warnings seen |
|---|---|
| `"mypkg.mymod"` | 0 (filtered) |
| `"other.mod"` | 1 |

mcpyrate calls `builtins.compile` itself (`compiler.py:277`), and passes no `module=`. So on 3.15 **every macro-enabled module loses module-based syntax-warning filtering** — silently, since nothing errors and the warnings still appear, merely unfilterable. That is the regression worth fixing; the `TypeError` is just what makes it visible.

**Which name to use.** `fullname` and `self.name` normally agree, and mcpyrate goes out of its way to keep them agreeing: `macropython.py:82` sets `spec.loader.name = "__main__"` alongside `spec.name`, precisely because `importer.py:27` reads `self.name`. They can still diverge, because `get_code(fullname)` takes the name as a parameter while `self.name` is fixed at loader construction.

Prefer `fullname`, falling back to `self.name` when it is `None` (an older-style caller may omit it):

- `fullname` is the name the module is being loaded *as*, on this call, and `exec_module` derives it from `module.__name__` — which is the name the module will occupy in `sys.modules`. That is what a self-macro-import has to resolve against.
- `self.name` is a cached copy of the same thing from construction time.
- CPython itself now treats `fullname` as authoritative, routing it into `compile`.

Once `fullname` is preferred, the `spec.loader.name` assignment in `macropython.py` is no longer load-bearing *for this purpose*. Leave it — check what else reads it before touching it.

**Threading `module=` through.** `self_module` is already passed the whole way down (`compile` → `_compile` → the `builtins.compile` call), so no new parameter is needed: pass `module=self_module` at `compiler.py:277`. It needs a guard, since mcpyrate supports 3.10–3.14 where the kwarg does not exist — either `sys.version_info >= (3, 15)` or feature detection, whichever fits house style. `module=None` is accepted and is CPython's default, so the dynamically-generated-code path (where `self_module` is `None`) needs no special case.

**One design question worth a decision.** `compiler.compile` advertises itself as a near-drop-in for the builtin and documents the ways it differs. The builtin has now gained a parameter it lacks, so either it gains one too, or the docstring's difference list gains a fourth entry.

Recommendation: derive `module=` from `self_module` rather than adding a separate parameter. The two are distinct concepts — macro self-reference versus warning attribution — but they coincide for every caller that has a module at all, and a second parameter that must almost always equal the first is an invitation for the two to drift. Note the deviation in the docstring instead.

Note what this says about method: the ASDL diff is the right tool for *grammar* changes and it found every one of them, but it cannot see a change like this. An interpreter bump can break an AST consumer through the import machinery, the bytecode format, or a stdlib protocol, none of which the grammar mentions. **Import the package under the new interpreter early** — it is one command and it would have found this before any of the AST analysis.

### 2. mcpyrate: the unparser

All four sites are in `mcpyrate/unparser.py`.

- `_Import` (line 329) — emit `lazy import ` when `t.is_lazy` is truthy.
- `_ImportFrom` (line 333) — emit `lazy from ` likewise.
- `_DictComp` (line 690) — emit `**` followed by `key` when `value` is `None`; otherwise the existing `key: value`.
- `_ImportFrom` (line 335) — **bug, unrelated to 3.15**: it writes `"." * t.level`, which raises on a constructed node that left `level` unset. CPython writes `t.level or 0`. Fix while in the file; separate commit.

`_ListComp` / `_SetComp` / `_GeneratorExp` (lines 669–690) should need no change, since `_Starred` (line 923) already writes the `*`. Confirm by test rather than by reading.

New test module `mcpyrate/test/test_020_unparser_3_15.py`, following the existing `test_020_unparser_3_13.py` / `_3_14.py` pattern — the version suffix is what gates it off on older interpreters. Round-trip at minimum: `lazy import x`, `lazy from x import y`, `{**d for d in dicts}`, `[*L for L in lists]`, `{*s for s in sets}`, `(*L for L in lists)`, and an async generator form.

### 3. mcpyrate: reject lazy macro-imports

**Decision taken 2026-08-16: a lazy macro-import is an error, not a silently-ignored modifier.**

A macro-import is consumed at expansion time, so deferring it is meaningless. Today `ismacroimport` (`coreutils.py:84`) tests only `isinstance(statement, ast.ImportFrom)`, so `lazy from mymacros import macros, ...` would be accepted as an ordinary macro-import and then rewritten to a plain `import mymacros` (`expander.py:643`, `dialects.py:609`), quietly discarding the `lazy`. Raise instead, with the source location, following whatever mcpyrate's established idiom is for a malformed macro-import — check what `get_macros` already raises for its error cases and match it rather than inventing a new failure mode.

Guard the whole thing on the attribute existing, so the code still runs on 3.10–3.14.

### 4. unpythonic: the open questions

These are the ones that need a live 3.15 and cannot be settled by reading.

- **open — `lazify` with a `Starred` comprehension element.** `lazify.py` has no comprehension-specific handling at all, and its `Starred` handling is scoped to call arguments (line 537) and container literals (line 770). A `Starred` in `elt` position is a new shape reaching the generic path. The hazard is wrapping the `Starred`'s value in a promise, since `*promise` fails at unpacking. Test `with lazify:` over each of the four new comprehension forms.
- **open — `autocurry` and `tailtools` over the same forms.** Same question, same reason; `tailtools.py:1011,1026` already reasons about `Starred` in a different context.
- **open — any macro that reads `DictComp.value` assuming a node.** The walkers are safe (verified above), but a macro that dereferences the field directly is not. Grep again once 3.15 is installed and the new forms can actually be parsed into test fixtures.
- **Raise the cap last.** `pyproject.toml`: `>=3.10,<3.15` → `>=3.10,<3.16`, plus the `Programming Language :: Python :: 3.15` classifier. Only after the above are green. Note the fleet TODO's warning: an *unbounded* floor makes the resolver seek a version valid for every future Python and silently fall back to an ancient release, so keep the upper bound, just move it.

### 5. pyan, the third AST user

Tracked separately in `pyan/briefs/python-3.15-support.md`, and independent of this work — no dependency either way, so it can be done first, last, or in parallel.

Worth knowing while reading this brief: **pyan is the only one of the three that actually crashes on 3.15.** Its `analyze_comprehension` visits `DictComp.value` unconditionally, so a `{**d for ...}` anywhere in the analyzed codebase raises `AttributeError`. It also declares no upper `requires-python` bound, so it installs happily on the version that breaks it. The macro layer, by contrast, is cap-protected and has no known crash.

### 6. Fleet follow-on

Out of scope for this brief, but unblocked by it: CI matrices everywhere, the `cp315-*` cibuildwheel pins in pylu / pydgq / python-wlsqm, and the stale-coverage-Python item that the fleet TODO says to fold into the same pass.

## Adjacent findings

Surfaced by the deprecation run; neither is an AST issue and neither blocks this work.

- `unpythonic/tests/test_typecheck.py:205` errors under `-W error::DeprecationWarning` because `isinstance` against `typing.ByteString` reaches `collections.abc.ByteString`, deprecated and slated for removal in 3.17. 3.15 widens the warning to mere import or attribute access. Needs version gating before 3.17 regardless.
- `unpythonic/dialects/tests/test_pytkell.py:50` still uses the `return` form inside `with test:`, which unpythonic itself deprecates in favour of `expect[]`. It will break when the `return` form is un-hijacked in a future major release.

Both were found because `-W error::DeprecationWarning` promotes *every* deprecation, not only CPython's — which is the point of running it that way.
