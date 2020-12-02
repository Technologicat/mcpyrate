# -*- coding: utf-8; -*-
"""Delete Python bytecode (`.pyc`) caches inside given directory, recursively.

This removes the `__pycache__` directories, too.

This facilitates testing `mcpyrate` and programs that use it, because the
expander only runs when the `.pyc` cache for the module being imported is out
of date or does not exist. For any given module, once the expander is done,
Python's import system will then write the `.pyc` cache for that module.
"""

__all__ = ["getpycachedirs", "deletepycachedirs"]

import argparse
import os
import textwrap

__version__ = "3.0.0"


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


def main():
    parser = argparse.ArgumentParser(description=textwrap.dedent(
        """
        Delete Python bytecode (`.pyc`) caches inside given directory, recursively.

        This removes the `__pycache__` directories, too.

        This facilitates testing `mcpyrate` and programs that use it, because the
        expander only runs when the `.pyc` cache for the module being imported is out
        of date or does not exist. For any given module, once the expander is done,
        Python's import system will then write the `.pyc` cache for that module.
        """),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-v', '--version', action='version', version=('%(prog)s ' + __version__))
    parser.add_argument(dest="path", type=str, metavar="path", help="directory path to start in (absolute or relative)")
    parser.add_argument("-n", "--dry-run", dest="dry_run", action="store_true", default=False,
                        help="scan for and print the .pyc cache directory paths, and exit.")

    opts = parser.parse_args()

    if not opts.dry_run:
        deletepycachedirs(opts.path)
    else:
        for x in getpycachedirs(opts.path):
            print(x)


if __name__ == "__main__":
    main()
