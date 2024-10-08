# -*- coding: utf-8 -*-
"""Conditionally import AST node types only supported by certain versions of Python.

Any node type that does not exist in the running version of Python is set to
a dummy type that inherits from `ast.AST`. This is guaranteed to not match any type
that actually exists in a parsed AST.

This module currently works in language versions 3.6 through 3.12.
"""

__all__ = ["NamedExpr",
           "Match", "match_case", "MatchValue", "MatchSingleton", "MatchSequence", "MatchStar", "MatchMapping", "MatchClass", "MatchAs", "MatchOr",
           "TryStar",
           "TypeAlias", "TypeVar", "ParamSpec", "TypeVarTuple",
           "Num", "Str", "Bytes", "NameConstant", "Ellipsis",
           "Index", "ExtSlice",
           "getconstant"]

import ast

class _NoSuchNodeType(ast.AST):
    pass

# --------------------------------------------------------------------------------
# New AST node types

# No new AST node types in Python 3.7.

try:  # Python 3.8+: `:=` (assignment expression, a.k.a. walrus operator)
    from ast import NamedExpr
except ImportError:  # pragma: no cover
    NamedExpr = _NoSuchNodeType

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

# --------------------------------------------------------------------------------
# Deprecated AST node types

try:  # Python 3.8+, https://docs.python.org/3/whatsnew/3.8.html#deprecated
    from ast import Num, Str, Bytes, NameConstant, Ellipsis
except ImportError:  # pragma: no cover
    Num = Str = Bytes = NameConstant = Ellipsis = _NoSuchNodeType

try:  # Python 3.9+, https://docs.python.org/3/whatsnew/3.9.html#deprecated
    from ast import Index, ExtSlice
    # We ignore the internal classes Suite, Param, AugLoad, AugStore,
    # which were never used in Python 3.x.
except ImportError:  # pragma: no cover
    Index = ExtSlice = _NoSuchNodeType

# --------------------------------------------------------------------------------
# Compatibility functions

def getconstant(tree):
    """Given an AST node `tree` representing a constant, return the contained raw value.

    This encapsulates the AST differences between Python 3.8+ and older versions.

    There are no `setconstant` or `makeconstant` counterparts, because you can
    just create an `ast.Constant` in Python 3.6 and later. The parser doesn't
    emit them until Python 3.8, but Python 3.6+ compile `ast.Constant` just fine.
    """
    if type(tree) is ast.Constant:  # Python 3.8+
        return tree.value
    # up to Python 3.7
    elif type(tree) is ast.NameConstant:  # up to Python 3.7  # pragma: no cover
        return tree.value
    elif type(tree) is ast.Num:  # pragma: no cover
        return tree.n
    elif type(tree) in (ast.Str, ast.Bytes):  # pragma: no cover
        return tree.s
    elif type(tree) is ast.Ellipsis:  # `ast.Ellipsis` is the AST node type, `builtins.Ellipsis` is `...`.  # pragma: no cover
        return ...
    raise TypeError(f"Not an AST node representing a constant: {type(tree)} with value {repr(tree)}")  # pragma: no cover
