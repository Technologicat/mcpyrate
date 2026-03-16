# -*- coding: utf-8 -*-
"""Smoke tests for the macropython CLI."""

import subprocess
import sys


def runtests():
    def macropython(*args):
        """Run macropython as a subprocess, return CompletedProcess."""
        cmd = [sys.executable, '-m', 'mcpyrate.repl.macropython', *args]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_command_mode():
        # Basic -c: run a snippet and capture output.
        result = macropython('-c', 'print("hello")')
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "hello"

        # -c can import modules normally.
        result = macropython('-c', 'import mcpyrate; print(mcpyrate.__version__)')
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip()  # just check it printed something

    def test_version():
        result = macropython('-v')
        assert result.returncode == 0
        assert 'mcpyrate' in result.stdout

    def test_clean_dry_run():
        # -C with -n (dry run) should list cache dirs without error.
        result = macropython('-C', '.', '-n')
        assert result.returncode == 0

    def test_conflicting_options():
        result = macropython('-c', 'pass', '-i')
        assert result.returncode != 0
        assert "Please specify only one" in result.stderr

    def test_no_args_shows_help():
        result = macropython()
        assert result.returncode == 0
        assert 'usage' in result.stdout.lower() or 'usage' in result.stderr.lower()

    test_command_mode()
    test_version()
    test_clean_dry_run()
    test_conflicting_options()
    test_no_args_shows_help()
