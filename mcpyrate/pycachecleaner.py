#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Python bytecode cache (`.pyc`) cleaner. Deletes `__pycache__` directories."""

__all__ = ["getpycachedirs", "deletepycachedirs"]

import os


def getpycachedirs(path):
    """Return a list of all `__pycache__` directories under `path` (str).

    Each of the entries starts with `path`.
    """
    if not os.path.isdir(path):
        raise OSError(f"No such directory: '{path}'")

    paths = []
    for root, dirs, files in os.walk(path):
        if "__pycache__" in dirs:
            paths.append(os.path.join(root, "__pycache__"))
    return paths


def deletepycachedirs(path):
    """Delete all `__pycache__` directories under `path` (str).

    Ignores `FileNotFoundError`, but other errors raise. If an error occurs,
    some `.pyc` cache files and their directories may already have been deleted.
    """
    for x in getpycachedirs(path):
        _delete_directory_recursively(x)


def _delete_directory_recursively(path):
    """Delete a directory recursively, like 'rm -rf' in the shell.

    Ignores `FileNotFoundError`, but other errors raise. If an error occurs,
    some files and directories may already have been deleted.
    """
    for root, dirs, files in os.walk(path, topdown=False, followlinks=False):
        for x in files:
            try:
                os.unlink(os.path.join(root, x))
            except FileNotFoundError:
                pass

        for x in dirs:
            try:
                os.rmdir(os.path.join(root, x))
            except FileNotFoundError:
                pass

    try:
        os.rmdir(path)
    except FileNotFoundError:
        pass
