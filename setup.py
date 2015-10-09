#!/usr/bin/python

from distutils.core import setup

setup(
    name = "mcpy",
    packages = ["mcpy"],
    version = "1.0.0",
    description = "A small and compact Python 3 library to enable syntactic macros at importing time",
    author = "Salvador de la Puente González",
    author_email = "salva@unoyunodiez.com",
    url = "https://github.com/lodr/mcpy",
    download_url = "https://github.com/lodr/mcpy/tarball/1.0.0",
    keywords = ["macros", "import", "importer", "github"],
    classifiers = [
        "Programming Language :: Python",
        "Programming Language :: Python :: 3 :: Only",
        "Development Status :: 4 - Beta",
        "Environment :: Other Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities"
    ]
)
