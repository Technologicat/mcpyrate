# -*- coding: utf-8; -*-
"""Clear (delete) .pyc caches inside given directory, recursively.

This makes it easier to test `mcpyrate`, because the expander only runs when
the `.pyc` cache for the module being imported is out of date or does not
exist. Python's import system will then write the `.pyc` cache for that module.
"""

import argparse
import os
import textwrap

__version__ = "3.0.0"

def getpycachedirs(path):
    paths = []
    for root, dirs, files in os.walk(path):
        if "__pycache__" in dirs:
            paths.append(os.path.join(root, "__pycache__"))
    return paths

def rmrf(path):
    for root, dirs, files in os.walk(path, topdown=False, followlinks=False):
        for x in files:
            try:
                os.unlink(os.path.join(root, x))
            except FileNotFoundError:
                pass

    try:
        os.rmdir(path)
    except FileNotFoundError:
        pass

def clean(path, dry_run=False):
    if not os.path.isdir(path):
        raise OSError(f"No such directory: '{path}'")

    pycachedirs = getpycachedirs(path)
    if dry_run:
        for x in pycachedirs:
            print(x)
        return
    else:
        for x in pycachedirs:
            rmrf(x)

def main():
    parser = argparse.ArgumentParser(description=textwrap.dedent(
        """
        Clear (delete) .pyc caches inside given directory, recursively.

        This makes it easier to test `mcpyrate`, because the expander only runs when
        the `.pyc` cache for the module being imported is out of date or does not
        exist. Python's import system will then write the `.pyc` cache for that module.
        """),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-v', '--version', action='version', version=('%(prog)s ' + __version__))
    parser.add_argument(dest="path", type=str, metavar="path", help="directory path (can be relative)")
    parser.add_argument("-n", "--dry-run", dest="dry_run", action="store_true", default=False,
                        help="only show the .pyc cache directory names; don't clear them.")

    opts = parser.parse_args()

    clean(opts.path, opts.dry_run)

if __name__ == "__main__":
    main()
