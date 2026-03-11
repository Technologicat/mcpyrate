# -*- coding: utf-8 -*-
"""Conditionally import AST node types only supported by certain versions of Python.

Any node type that does not exist in the running version of Python is set to
a dummy type that inherits from `ast.AST`. This is guaranteed to not match any type
that actually exists in a parsed AST.

This module currently works in language versions 3.10 through 3.14.
"""

__all__ = ["NamedExpr",
           "Match", "match_case", "MatchValue", "MatchSingleton", "MatchSequence", "MatchStar", "MatchMapping", "MatchClass", "MatchAs", "MatchOr",
           "TryStar",
           "TypeAlias", "TypeVar", "ParamSpec", "TypeVarTuple"]

import ast

class _NoSuchNodeType(ast.AST):
    pass

# --------------------------------------------------------------------------------
# New AST node types

from ast import NamedExpr  # Python 3.8+: `:=` (assignment expression, a.k.a. walrus operator)

# No new AST node types in Python 3.9.

try:  # Python 3.10+: `match`/`case` (pattern matching)
    from ast import (Match, match_case,
                     MatchValue, MatchSingleton, MatchSequence, MatchStar,
                     MatchMapping, MatchClass, MatchAs, MatchOr)
except ImportError:  # pragma: no cover
    Match = match_case = MatchValue = MatchSingleton = MatchSequence = MatchStar = MatchMapping = MatchClass = MatchAs = MatchOr = _NoSuchNodeType

try:  # Python 3.11+: `try`/`except*` (exception groups)
    from ast import TryStar
except ImportError:  # pragma: no cover
    TryStar = _NoSuchNodeType

try:  # Python 3.12+: `type` statement (type alias)
    from ast import TypeAlias, TypeVar, ParamSpec, TypeVarTuple
except ImportError:  # pragma: no cover
    TypeAlias = TypeVar = ParamSpec = TypeVarTuple = _NoSuchNodeType
