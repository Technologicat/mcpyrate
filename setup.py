#!/usr/bin/env python

import os
from setuptools import setup

def read(*relpath, **kwargs):
    with open(os.path.join(os.path.dirname(__file__), *relpath),
              encoding=kwargs.get('encoding', 'utf8')) as fh:
        return fh.read()

setup(
    name="mcpy",
    version="2.1.0",
    packages=["mcpy"],
    provides=["mcpy"],
    keywords=["macros", "syntactic-macros", "import", "importer", "github"],
    python_requires=">=3.6",
    author="Salvador de la Puente González and Juha Jeronen",
    author_email="salva@unoyunodiez.com",
    url="https://github.com/delapuente/mcpy",
    description="A small and compact Python 3 library to enable syntactic macros at import time",
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
    zip_safe=False  # macros are not zip safe, because the zip importer fails to find sources.
)
