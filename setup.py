#!/usr/bin/env python

import os
from setuptools import setup

def read(*relpath, **kwargs):
    with open(os.path.join(os.path.dirname(__file__), *relpath),
              encoding=kwargs.get("encoding", "utf8")) as fh:
        return fh.read()

# Extract __version__ from the package __init__.py
# (since it's not a good idea to actually run __init__.py during the build process).
#
# http://stackoverflow.com/questions/2058802/how-can-i-get-the-version-defined-in-setup-py-setuptools-in-my-package
import ast
init_py_path = os.path.join("mcpyrate", "__init__.py")
version = None
try:
    with open(init_py_path) as f:
        for line in f:
            if line.startswith("__version__"):
                module = ast.parse(line)
                expr = module.body[0]
                v = expr.value
                if type(v) is ast.Constant:
                    version = v.value
                elif type(v) is ast.Str:  # TODO: Python 3.8: remove ast.Str
                    version = v.s
                break
except FileNotFoundError:
    pass
if not version:
    raise RuntimeError(f"Version information not found in {init_py_path}")

setup(
    name="mcpyrate",
    version=version,
    packages=["mcpyrate", "mcpyrate.repl"],
    provides=["mcpyrate"],
    keywords=["macros", "syntactic-macros", "macro-expander", "metaprogramming", "import", "importer"],
    install_requires=["colorama>=0.4.4"],
    python_requires=">=3.6",
    author="Juha Jeronen and Salvador de la Puente González",
    author_email="juha.m.jeronen@gmail.com",
    url="https://github.com/Technologicat/mcpyrate",
    description="Advanced macro expander and language lab for Python",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    license="MIT",
    platforms=["Any"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Other Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities"
    ],
    entry_points={"console_scripts": ["macropython=mcpyrate.repl.macropython:main"]},
    zip_safe=False  # macros are not zip safe, because the zip importer fails to find sources.
)
