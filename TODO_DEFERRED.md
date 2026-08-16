# Deferred TODOs

## Fix TODO list

`todo.md` (lowercase) has old notes that need review — update, reorganize, or replace.

## Audit typing: abstract parameter types, concrete return types

Parameters should use abstract types from `collections.abc` (`Mapping`, `Sequence`, `Iterable`) for widest-possible-accepted semantics. Return types should use concrete lowercase builtins (`tuple[int, int]`, `list[int]`, `dict[str, int]`) — PEP 585, Python 3.9+. The capitalized `typing` forms (`Dict`, `List`, `Tuple`) are deprecated aliases for the builtins and offer no extra width — avoid them. Audit existing type hints across the codebase for consistency.

Discovered during raven-cherrypick compare mode planning (2026-03-30).

## Tier 2 REPL tests (subprocess + pty) for `macropython -i`

Tier 1 coverage for `MacroConsole` lands in `mcpyrate/test/test_126_repl.py` — in-process, scripted input via `builtins.input` monkey-patch, captured stdout/stderr via `io.StringIO`. Fast (milliseconds per test), simple, covers a lot of REPL-logic regressions. **We might never need tier 2.**

**Important framing**: tier 1 is a *REPL-logic test*, not a terminal-UX test.  Monkey-patching `builtins.input` replaces the entire `input()` pathway before `PyOS_Readline` is ever called at the C level, so readline's line editor, history, and tab completion (as rendered to the user via key events) are **not partially covered — they are 0% covered**.  A regression in a `readline.parse_and_bind` call, in a completer registration, or in the SIGINT-during-readline path would pass tier 1 silently.  Tier 2 isn't "a safety net for edge cases" — it's the only place readline actually runs during tests.

A second tier would spawn `python -m mcpyrate.repl.macropython -i` as a real subprocess and drive it through a pseudo-terminal using `pexpect` (or `ptyprocess` directly), with scripted `sendline`/`expect` pairs. This would catch things tier 1 cannot reach:

- Real GNU-readline binding behaviour — tab completion, history recall, multi-line editing as rendered by libreadline/libedit.
- Terminal escape sequences from the colorizer — ANSI colour codes, cursor positioning, prompt-length calculations.
- Signal handling — Ctrl+C interrupting a long-running eval, Ctrl+D at various cursor positions.
- End-to-end entry-point startup — argparse, env-var handling, atexit hook wiring.

Cost:

- ~0.5–1 s startup per test (vs. milliseconds for tier 1). Matters when you want ~50+ REPL tests.
- POSIX-only naturally. Windows would need a ConPTY-based backend — either via `pywinpty` or raw `ctypes` into the Windows API. This is an independent design problem from unpythonic's `unpythonic.net` Windows support, which sidesteps ConPTY entirely by using `socket.socketpair` (sufficient because `unpythonic.net` just needs bidirectional byte streams, not real terminal semantics — whereas tier 2 here *is* testing real terminal semantics and therefore can't substitute a socketpair).
- `pexpect` would become a new dev dep. Not heavy, but non-zero.

**Rough shape if we ever do it:**

```python
import pexpect
child = pexpect.spawn(f"{sys.executable} -m mcpyrate.repl.macropython -i",
                      encoding="utf-8", timeout=5)
child.expect(r">>> ")
child.sendline("1 + 1")
child.expect(r"2\s*\n>>> ")
child.sendline("exit()")
child.expect(pexpect.EOF)
```

**When to actually do it**: only if tier 1 coverage turns out to miss something important (a regression hits production that tier 1 would not have caught). Until then, the presence of tier 1 is the main win; tier 2 is a safety net that may turn out to cost more than it saves.

Added 2026-04-15, alongside the tier 1 bring-up.

## Test `MacroConsole` with macro imports (in-process, without stale-identity contamination)

The tier 1 REPL tests at `mcpyrate/test/test_126_repl.py` deliberately exclude a `test_macro_expansion_in_repl` case that would type `from mcpyrate.quotes import macros, q` into a `MacroConsole` and verify the macro expands.

**The obstacle**: `MacroConsole.runsource` calls `find_macros(..., reload=True)` in `mcpyrate/repl/console.py:164`. That `reload=True` is a deliberate REPL feature — re-importing macros after the user edits their source, without restarting the REPL — and it calls `importlib.reload(mcpyrate.quotes)` (or whatever module was imported) on every `from X import macros, ...` statement.

The reload replaces the module's function objects (`q`, `u`, `n`, `a`, `s`, `t`, `h`, `first`, `second`, etc.) with fresh copies. Any code elsewhere in the process that still holds references to the pre-reload versions now has stale identities. On the second pass of mcpyrate's two-run test suite (first pass with cache cleared, second reusing bytecode), `test_115_metatools::test_stepr_expr` and `test_120a_quotes` then fail with `_pickle.PicklingError: Can't pickle <function q at 0x...>: it's not the same object as mcpyrate.quotes.q`, because `capture_value` in `mcpyrate.quotes` pickles macro references during `metatools.macro_bindings` and pickle's identity check fires on the stale objects.

**It's not a bug in MacroConsole.** In an interactive session, the user controls what else runs in the same process and the reload semantics are exactly right. The conflict is specifically with *test isolation* — the reload's blast radius crosses a single test's boundary.

**Possible approaches**, none of them trivial:

- **(a) Make `MacroConsole`'s `reload` behaviour configurable.** Add a `reload_on_macro_import: bool = True` parameter to `MacroConsole.__init__` that gets threaded through to `find_macros`. The default preserves the current REPL behaviour; tests can pass `False`. Production-code change, minimal and well-scoped.
- **(b) Subprocess isolation for this specific test.** Matches the tier 2 approach. Expensive (~0.5–1 s per test) but sidesteps the state question entirely.
- **(c) Save/restore `sys.modules['mcpyrate.quotes']` and friends around the test.** Tricky, because the "stale identity" damage propagates through closures, cached references in `expander.bindings`, pickled captures in bytecode, etc. — hard to exhaustively find what to restore.

**My recommendation**: (a). It's a small, principled API addition to `MacroConsole` — a one-shot `MacroConsole` (as used in tests, or embedded in a larger application that doesn't want interactive reloading) is a legitimate use case — and it makes the test clean and cheap. Tier 2 remains an option if the test still needs more isolation afterwards.

Added 2026-04-15 during the tier 1 bring-up; the full investigation notes and the test-case docstring are in `mcpyrate/test/test_126_repl.py` where the stub for the missing test lives.

## Can `runpy` replace part of `import_module_as_main`?

`macropython`'s `import_module_as_main` hand-rolls import semantics — a `sys.meta_path` walk, `module_from_spec`, `__package__` fixing, `__main__.py` resolution for packages. The premise was that nothing in the stdlib will load a module *as* `__main__`. That premise is half true, measured on 3.15.0rc1 with the expander active:

- **`-m` mode: `runpy` works.** `runpy.run_module("demo.promise", run_name="__main__")` expands macros correctly and prints `<__main__.Promise object ...>`, because `run_module` obtains the code via `loader.get_code(mod_name)` (`runpy.py:163`) and so goes through mcpyrate's patched `SourceFileLoader`.
- **Script mode: `runpy` cannot work.** `runpy.run_path("demo/let.py", run_name="__main__")` fails with `ImportError: cannot import name 'macros'`, because `_get_code_from_file` (`runpy.py:255`) reads the file and calls the builtin `compile` directly, bypassing loaders entirely. That is by design and not something a flag can turn off.

So at most the `-m` half is replaceable, and even there the two are not equivalent:

- **`sys.modules["__main__"]` lifetime.** `runpy` installs the module through `_TempModule`, whose `__exit__` **restores** the previous entry (`runpy.py:42`). `import_module_as_main` replaces `sys.modules["__main__"]` permanently, reverting only on error. Anything that looks up `__main__` after the run — pickling, the REPL, macro machinery — would see a different thing.
- **`runpy` runs the code in a fresh `ModuleType`**, not in the object built by `module_from_spec`, and sets `__spec__` / `__loader__` / `__package__` afterwards from the spec.
- **Error presentation.** `import_module_as_main` trims `MacroApplicationError` tracebacks down to the last frame so the chained macro-expansion errors stay readable. `runpy` does nothing of the sort, though this one is wrappable.

A middle option worth weighing for script mode, if the goal is less hackery rather than no hackery: `importlib.util.spec_from_file_location("__main__", path)` plus `module_from_spec` plus `exec_module` routes through the patched loader and is much shorter than the meta_path walk — at the cost of dropping support for whatever non-default finders the walk currently picks up (namespace packages, zipimport, and anything a user has installed).

Not part of the Python 3.15 support work; `import_module_as_main` was verified working as-is on 3.15. Raised 2026-08-16 while checking whether the importlib protocol change had implications for `macropython`.
