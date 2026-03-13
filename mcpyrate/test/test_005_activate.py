# -*- coding: utf-8 -*-
"""Tests for the import hook activation/deactivation machinery."""

from importlib.machinery import SourceFileLoader

from ..activate import activate, deactivate, stdlib_source_to_code, stdlib_path_stats
from ..importer import source_to_xcode, path_xstats


def runtests():
    def test_activate_installs_hooks():
        """After activation, SourceFileLoader uses mcpyrate's methods."""
        # activate() was already called at import time, so hooks should be in place.
        assert SourceFileLoader.source_to_code is source_to_xcode
        assert SourceFileLoader.path_stats is path_xstats
    test_activate_installs_hooks()

    def test_deactivate_restores_stdlib():
        """deactivate() restores original stdlib methods."""
        deactivate()
        try:
            assert SourceFileLoader.source_to_code is stdlib_source_to_code
            assert SourceFileLoader.path_stats is stdlib_path_stats
            assert SourceFileLoader.source_to_code is not source_to_xcode
            assert SourceFileLoader.path_stats is not path_xstats
        finally:
            # Always re-activate so the rest of the test suite works.
            activate()

    test_deactivate_restores_stdlib()

    def test_reactivate_after_deactivate():
        """activate() can re-install hooks after deactivate()."""
        deactivate()
        activate()
        assert SourceFileLoader.source_to_code is source_to_xcode
        assert SourceFileLoader.path_stats is path_xstats
    test_reactivate_after_deactivate()

    print("    test_activate: all passed")


if __name__ == '__main__':
    runtests()
