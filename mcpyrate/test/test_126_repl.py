# -*- coding: utf-8 -*-
"""Tier 1 REPL tests: drive `MacroConsole` in-process via scripted input.

This exercises the REPL loop itself — monkey-patching `builtins.input`
to feed pre-scripted lines, capturing `stdout`/`stderr` via in-memory
`StringIO`, and running `MacroConsole().interact()` directly.  No
subprocess, no real terminal — tests run in milliseconds.

Why tier 1 uses `builtins.input` rather than `sys.stdin`: `input()`
does **not** read from `sys.stdin`.  It goes through `PyOS_Readline`
at the C level, which reads from file descriptor 0 directly.  Setting
`sys.stdin = io.StringIO(...)` silently does not work; the REPL just
hangs waiting for real keyboard input.  Monkey-patching `builtins.
input` is the layer that actually intercepts correctly.

A plausible tier 2 (subprocess + pty driven by `pexpect`) is sketched
in `TODO_DEFERRED.md` as D5 for when we need it.  We might never need
it — tier 1 covers the vast majority of REPL regressions in-process
at milliseconds per test.
"""

import builtins
import contextlib
import io
import sys
import types

from ..repl.console import MacroConsole


@contextlib.contextmanager
def scripted_repl(script):
    """Drive an interactive REPL through a pre-scripted input sequence.

    `script` is an iterable of strings, each representing one line the
    user would type (no trailing newlines).  When the script is
    exhausted, the next `input()` call raises `EOFError` — which is
    how a normal REPL exits on Ctrl+D.

    On exit from the `with` block, `captured.stdout` and
    `captured.stderr` are materialized to plain strings, so assertions
    can use them directly.  This materialization happens in `finally`,
    so it runs even on test failure and the interface is consistent
    between the success and failure paths.

    Usage::

        with scripted_repl(["1 + 1"]) as captured:
            MacroConsole().interact(banner="", exitmsg="")
        assert "2" in captured.stdout
    """
    lines = iter(script)
    def fake_input(prompt=""):
        # Echo the prompt into the captured stream so tests that care
        # about prompt text can see it.  A real tty would also echo.
        sys.stdout.write(prompt)
        sys.stdout.flush()
        try:
            line = next(lines)
        except StopIteration:
            raise EOFError  # REPL's normal exit path (Ctrl+D)
        # Echo the "typed" line too, matching real tty behaviour.
        sys.stdout.write(line + "\n")
        return line

    captured = types.SimpleNamespace(
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    orig_input = builtins.input
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    try:
        # State changes grouped inside the try: if any of the three
        # assignments fails, the finally still runs and restores what
        # we had.  Atomic from the caller's perspective.
        builtins.input = fake_input
        sys.stdout = captured.stdout
        sys.stderr = captured.stderr
        yield captured
    finally:
        builtins.input = orig_input
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr
        # Materialize captured values (live StringIO → plain str) so
        # assertions after the `with` see strings, not file-like
        # objects.  Runs on the failure path too.
        captured.stdout = captured.stdout.getvalue()
        captured.stderr = captured.stderr.getvalue()


def runtests():
    def test_basic_arithmetic_eval():
        """The most basic REPL test: evaluate an expression and see the result."""
        with scripted_repl(["1 + 1"]) as captured:
            MacroConsole().interact(banner="", exitmsg="")
        assert "2" in captured.stdout, \
            f"expected '2' in stdout, got: {captured.stdout!r}"
    test_basic_arithmetic_eval()

    def test_multiline_function_definition():
        """Define a function over multiple lines, then call it.

        A blank line ends the compound statement — that's how
        `code.InteractiveConsole` tells a multi-line input is done.
        """
        with scripted_repl([
            "def f():",
            "    return 42",
            "",
            "f()",
        ]) as captured:
            MacroConsole().interact(banner="", exitmsg="")
        assert "42" in captured.stdout, \
            f"expected '42' in stdout, got: {captured.stdout!r}"
    test_multiline_function_definition()

    def test_syntax_error_recovery():
        """A syntax error should not kill the REPL; subsequent input should still work.

        `code.InteractiveConsole` reports syntax errors via
        `showsyntaxerror()`, which prints to `sys.stderr`, then returns
        to the prompt.  The next line should eval normally.
        """
        with scripted_repl([
            "this is : not valid python $$$",
            "1 + 1",
        ]) as captured:
            MacroConsole().interact(banner="", exitmsg="")
        # Syntax error is reported — on stdout or stderr depending on
        # the console's choice.  `code.InteractiveConsole` writes it
        # via `self.write()` which goes to stderr, but join both for
        # robustness against future refactors.
        combined = captured.stdout + captured.stderr
        assert "SyntaxError" in combined, \
            f"expected SyntaxError report, got stdout={captured.stdout!r} stderr={captured.stderr!r}"
        # Recovery: the good line after the bad one still evaluates.
        assert "2" in captured.stdout, \
            f"expected '2' (from recovery eval), got: {captured.stdout!r}"
    test_syntax_error_recovery()

    def test_exit_via_eof():
        """Empty script: first `input()` raises `EOFError`, REPL exits cleanly without hanging.

        The test PASSES by reaching the assertions after `interact()`
        returns.  If the REPL were to hang instead (e.g. because
        input-replacement didn't actually intercept the C-level
        readline), this test would time out.
        """
        with scripted_repl([]) as captured:
            MacroConsole().interact(banner="", exitmsg="")
        # We reached this line → the REPL exited cleanly.  Two
        # sanity checks: the REPL actually called `input()` at least
        # once (so the prompt appears in captured stdout), and no
        # traceback escaped to stderr (a hung or broken exit would
        # typically leave error traces).
        assert ">>>" in captured.stdout, \
            f"expected a prompt in stdout (REPL should call input()), got: {captured.stdout!r}"
        assert "Traceback" not in captured.stderr, \
            f"expected clean exit, got stderr: {captured.stderr!r}"
    test_exit_via_eof()

    # -- Intentionally NOT included in tier 1: testing macro imports in the REPL.
    #
    # A natural fifth test would be:
    #
    #     def test_macro_expansion_in_repl():
    #         with scripted_repl(["from mcpyrate.quotes import macros, q",
    #                             "type(q[1 + 2]).__name__"]) as captured:
    #             MacroConsole().interact(banner="", exitmsg="")
    #         assert "BinOp" in captured.stdout
    #
    # But it can't run cleanly in the in-process tier 1 framework.
    # Root cause: `MacroConsole.runsource` calls `find_macros(..., reload=True)`
    # in `mcpyrate/repl/console.py:164`.  This is a deliberate REPL feature —
    # re-importing macros after the user edits the source — which triggers
    # `importlib.reload(mcpyrate.quotes)` on every macro-import statement typed.
    #
    # The reload replaces the functions in `sys.modules['mcpyrate.quotes']`
    # (q, u, n, a, s, t, h, first, second, etc.) with fresh function objects,
    # breaking object identity for any code that already holds references to
    # the pre-reload versions.  On the second pass of mcpyrate's two-run test
    # suite, test_115_metatools and test_120a_quotes then hit:
    #
    #     _pickle.PicklingError: Can't pickle <function q at 0x...>:
    #     it's not the same object as mcpyrate.quotes.q
    #
    # …because `capture_value` (in `mcpyrate.quotes`) pickles macro references
    # during `metatools.macro_bindings`, and pickle's identity check fails for
    # the now-stale `q` function object.
    #
    # This is *not* a mcpyrate bug: in an interactive REPL session where the
    # user presumably controls what else runs in the same process, the reload
    # behaviour is exactly what you want.  It just doesn't compose with in-
    # process test isolation, because the reload's blast radius crosses the
    # boundary of a single test.
    #
    # To cover this properly would need one of:
    #   (1) a way to construct a `MacroConsole` with `reload=False`
    #       (production-code change — not purely test-side);
    #   (2) subprocess isolation (tier 2 — see TODO_DEFERRED D5);
    #   (3) a save/restore of the relevant `sys.modules` entries around the
    #       test, which is tricky because the "damage" can propagate through
    #       closures and cached references that are hard to find exhaustively.
    #
    # Tracked in TODO_DEFERRED as D6.  For now, the four tier-1 tests above
    # already cover the core REPL mechanics (eval, multi-line, syntax error
    # recovery, clean EOF exit) — which is the main win.  Macro-expansion
    # coverage can come from tier 2 or from existing non-REPL tests like
    # test_120a_quotes, which exercise the same quote machinery through the
    # normal compile path.
