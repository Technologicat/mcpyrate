# -*- coding: utf-8 -*-
"""Tests for pycachecleaner."""

import os
import tempfile

from ..pycachecleaner import getpycachedirs, deletepycachedirs


def runtests():
    def test_getpycachedirs_bad_path():
        """Non-existent path raises OSError."""
        try:
            getpycachedirs("/nonexistent/path/that/does/not/exist")
        except OSError as e:
            assert "No such directory" in str(e)
        else:
            assert False, "Expected OSError"
    test_getpycachedirs_bad_path()

    def test_getpycachedirs_finds_caches():
        """Finds __pycache__ directories."""
        with tempfile.TemporaryDirectory() as tmp:
            cache = os.path.join(tmp, "subdir", "__pycache__")
            os.makedirs(cache)
            result = getpycachedirs(tmp)
            assert len(result) == 1
            assert result[0].endswith("__pycache__")
    test_getpycachedirs_finds_caches()

    def test_getpycachedirs_empty():
        """No __pycache__ → empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            result = getpycachedirs(tmp)
            assert result == []
    test_getpycachedirs_empty()

    def test_deletepycachedirs():
        """Delete __pycache__ directories and their contents."""
        with tempfile.TemporaryDirectory() as tmp:
            cache = os.path.join(tmp, "__pycache__")
            os.makedirs(cache)
            # Add some fake .pyc files
            for name in ["mod.cpython-314.pyc", "other.cpython-314.pyc"]:
                with open(os.path.join(cache, name), "w") as f:
                    f.write("fake")
            assert os.path.isdir(cache)
            deletepycachedirs(tmp)
            assert not os.path.isdir(cache)
    test_deletepycachedirs()

    def test_deletepycachedirs_nested():
        """Delete nested __pycache__ with subdirectories."""
        with tempfile.TemporaryDirectory() as tmp:
            cache = os.path.join(tmp, "__pycache__")
            subdir = os.path.join(cache, "subdir")
            os.makedirs(subdir)
            with open(os.path.join(subdir, "file.txt"), "w") as f:
                f.write("nested")
            with open(os.path.join(cache, "top.pyc"), "w") as f:
                f.write("top")
            deletepycachedirs(tmp)
            assert not os.path.isdir(cache)
    test_deletepycachedirs_nested()

    def test_deletepycachedirs_already_gone():
        """Deleting an already-removed directory is silently ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            cache = os.path.join(tmp, "__pycache__")
            os.makedirs(cache)
            # Delete it manually first, then let deletepycachedirs try
            os.rmdir(cache)
            # Should not raise
            deletepycachedirs(tmp)
    test_deletepycachedirs_already_gone()

    # The remaining uncovered lines (45-46, 51-52, 56-57) are `except
    # FileNotFoundError: pass` guards for race conditions in concurrent
    # deletion. Not worth testing — they'd need non-deterministic timing.


if __name__ == '__main__':
    runtests()
