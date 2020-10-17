#!/usr/bin/env python

import os
from setuptools import setup

def read(*relpath, **kwargs):
    with open(os.path.join(os.path.dirname(__file__), *relpath),
              encoding=kwargs.get('encoding', 'utf8')) as fh:
        return fh.read()

setup(
    name="mcpyrate",
    version="3.0.0",
    packages=["mcpyrate", "mcpyrate.repl"],
    provides=["mcpyrate"],
    keywords=["macros", "syntactic-macros", "macro-expander", "metaprogramming", "import", "importer"],
    install_requires=["colorama>=0.4.4"],
    python_requires=">=3.6",
    author="Juha Jeronen and Salvador de la Puente González",
    author_email="salva@unoyunodiez.com",
    url="https://github.com/Technologicat/mcpyrate",
    description="A 3rd-generation macro expander for Python",
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
