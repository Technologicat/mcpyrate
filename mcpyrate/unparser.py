# -*- coding: utf-8; -*-
"""Back-convert a Python AST into source code. Original formatting is disregarded."""

__all__ = ['UnparserError', 'unparse', 'unparse_with_fallbacks']

import ast
import builtins
from contextlib import contextmanager
import io
import sys

from .astdumper import dump  # fallback
from .colorizer import colorize, ColorScheme
from .markers import ASTMarker

# Large float and imaginary literals get turned into infinities in the AST.
# We unparse those infinities to INFSTR.
INFSTR = "1e" + repr(sys.float_info.max_10_exp + 1)

# for syntax highlighting
_all_public_builtins = {x for x in dir(builtins) if not x.startswith("_")}
builtin_exceptions = {x for x in _all_public_builtins if x.endswith("Error")}
builtin_warnings = {x for x in _all_public_builtins if x.endswith("Warning")}
builtin_exceptions_and_warnings = builtin_exceptions | builtin_warnings
builtin_others = _all_public_builtins - builtin_exceptions_and_warnings


class UnparserError(SyntaxError):
    """Failed to unparse the given AST."""


def interleave(inter, f, seq):
    """Call f on each item in seq, calling inter() in between."""
    seq = iter(seq)
    try:
        f(next(seq))
    except StopIteration:
        pass
    else:
        for x in seq:
            inter()
            f(x)


class Unparser:
    """Convert an AST into source code.

    Methods in this class recursively traverse an AST and output source code
    for the abstract syntax. Original formatting is disregarded.
    """

    def __init__(self, tree, *, file=sys.stdout, debug=False, color=False):
        """Print the source for `tree` to `file`.

        `debug`: bool, print invisible nodes (`Module`, `Expr`).

                 The output is then not valid Python, but may better show
                 the problem when code produced by a macro mysteriously
                 fails to compile (even though a non-debug unparse looks ok).

        `color`: bool, use Colorama to color output. For syntax highlighting
                 when printing into a terminal.
        """
        self.debug = debug
        self.color = color
        self._color_override = False  # to syntax highlight decorators
        self.f = file
        self._indent = 0
        self.dispatch(tree)
        print("", file=self.f)
        self.f.flush()

    def maybe_colorize(self, text, *colors):
        "Colorize text if color is enabled."
        if self._color_override:
            return text
        if not self.color:
            return text
        return colorize(text, *colors)

    def python_keyword(self, text):
        "Shorthand to colorize a language keyword such as `def`, `for`, ..."
        return self.maybe_colorize(text, ColorScheme.LANGUAGEKEYWORD)

    def nocolor(self):
        """Context manager. Temporarily prevent coloring.

        Useful for syntax highlighting decorators (so that the method rendering
        the decorator may force a particular color, instead of allowing
        auto-coloring based on the data in the decorator AST node).
        """
        @contextmanager
        def _nocolor():
            old_color_override = self._color_override
            self._color_override = True
            try:
                yield
            finally:
                self._color_override = old_color_override
        return _nocolor()

    def fill(self, text="", *, lineno_node=None):
        "Indent a piece of text, according to the current indentation level."
        self.write("\n")
        if self.debug and isinstance(lineno_node, ast.AST):
            lineno = lineno_node.lineno if hasattr(lineno_node, "lineno") else None
            # In `mcpyrate.debug.step_expansion`, `textwrap.dedent` will strip
            # leading space, so it's better to use something else to always
            # have fixed width.
            #
            # Assume line numbers usually have at most 4 digits, but
            # degrade gracefully for those crazy 5-digit source files.
            self.write(self.maybe_colorize(f"L{lineno:5d} " if lineno else "L ---- ",
                                           ColorScheme.LINENUMBER))
        self.write("    " * self._indent + text)

    def write(self, text):
        "Append a piece of text to the current line."
        self.f.write(text)

    def enter(self):
        "Print ':', and increase the indentation level."
        self.write(":")
        self._indent += 1

    def leave(self):
        "Decrease the indentation level."
        self._indent -= 1

    def dispatch(self, tree):
        "Dispatcher. Dispatch tree type `T` to method `_T`."
        if isinstance(tree, list):
            for t in tree:
                self.dispatch(t)
            return
        if isinstance(tree, ASTMarker):  # mcpyrate and macro communication internal
            self.astmarker(tree)
            return
        methodname = "_" + tree.__class__.__name__
        if not hasattr(self, methodname):
            raise UnparserError(f"Don't know how to unparse AST node type {tree.__class__.__name__}")
        method = getattr(self, methodname)
        method(tree)

    # --------------------------------------------------------------------------------
    # Unparsing methods
    #
    # There should be one method per concrete grammar type.
    # Constructors should be grouped by sum type. Ideally,
    # this would follow the order in the grammar, but
    # currently doesn't.

    def astmarker(self, tree):
        def write_field_value(v):
            if isinstance(v, ast.AST):
                self.dispatch(v)
            else:
                self.write(repr(v))
        self.fill(self.maybe_colorize(f"$ASTMarker", ColorScheme.ASTMARKER),
                  lineno_node=tree)  # markers cannot be eval'd
        clsname = self.maybe_colorize(tree.__class__.__name__,
                                      ColorScheme.ASTMARKERCLASS)
        self.write(f"<{clsname}>")
        self.enter()
        self.write(" ")
        if len(tree._fields) == 1 and tree._fields[0] == "body":
            write_field_value(tree.body)
        else:
            for k, v in ast.iter_fields(tree):
                self.fill(k)
                self.enter()
                self.write(" ")
                write_field_value(v)
                self.leave()
        self.leave()

    def _Module(self, t):
        # TODO: Python 3.8 type_ignores. Since we don't store the source text, maybe ignore that?
        if self.debug:
            self.fill(self.maybe_colorize("$Module", ColorScheme.INVISIBLENODE),
                      lineno_node=t)
            self.enter()
            for stmt in t.body:
                self.dispatch(stmt)
            self.leave()
        else:
            for stmt in t.body:
                self.dispatch(stmt)

    # stmt
    def _Expr(self, t):
        if self.debug:
            self.fill(self.maybe_colorize("$Expr", ColorScheme.INVISIBLENODE),
                      lineno_node=t)
            self.enter()
            self.write(" ")
            self.dispatch(t.value)
            self.leave()
        else:
            self.fill()
            self.dispatch(t.value)

    def _Import(self, t):
        self.fill(self.python_keyword("import "), lineno_node=t)
        interleave(lambda: self.write(", "), self.dispatch, t.names)

    def _ImportFrom(self, t):
        self.fill(self.python_keyword("from "), lineno_node=t)
        self.write("." * t.level)
        if t.module:
            self.write(t.module)
        self.write(self.python_keyword(" import "))
        interleave(lambda: self.write(", "), self.dispatch, t.names)

    def _Assign(self, t):
        self.fill(lineno_node=t)
        for target in t.targets:
            self.dispatch(target)
            self.write(" = ")
        self.dispatch(t.value)

    def _AnnAssign(self, t):
        self.fill(lineno_node=t)
        if not t.simple:
            self.write("(")
        self.dispatch(t.target)
        if not t.simple:
            self.write(")")
        self.write(": ")
        self.dispatch(t.annotation)
        if t.value:
            self.write(" = ")
            self.dispatch(t.value)
        # TODO: Python 3.8 type_comment, ignore it?

    def _AugAssign(self, t):
        self.fill(lineno_node=t)
        self.dispatch(t.target)
        self.write(" " + self.binop[t.op.__class__.__name__] + "= ")
        self.dispatch(t.value)

    def _Return(self, t):
        self.fill(self.python_keyword("return"), lineno_node=t)
        if t.value:
            self.write(" ")
            self.dispatch(t.value)

    def _Pass(self, t):
        self.fill(self.python_keyword("pass"), lineno_node=t)

    def _Break(self, t):
        self.fill(self.python_keyword("break"), lineno_node=t)

    def _Continue(self, t):
        self.fill(self.python_keyword("continue"), lineno_node=t)

    def _Delete(self, t):
        self.fill(self.python_keyword("del "), lineno_node=t)
        interleave(lambda: self.write(", "), self.dispatch, t.targets)

    def _Assert(self, t):
        self.fill(self.python_keyword("assert "), lineno_node=t)
        self.dispatch(t.test)
        if t.msg:
            self.write(", ")
            self.dispatch(t.msg)

    def _Global(self, t):
        self.fill(self.python_keyword("global "), lineno_node=t)
        interleave(lambda: self.write(", "), self.write, t.names)

    def _Nonlocal(self, t):
        self.fill(self.python_keyword("nonlocal "), lineno_node=t)
        interleave(lambda: self.write(", "), self.write, t.names)

    def _Await(self, t):  # expr
        self.write("(")
        self.write(self.python_keyword("await"))
        if t.value:
            self.write(" ")
            self.dispatch(t.value)
        self.write(")")

    def _Yield(self, t):  # expr
        self.write("(")
        self.write(self.python_keyword("yield"))
        if t.value:
            self.write(" ")
            self.dispatch(t.value)
        self.write(")")

    def _YieldFrom(self, t):  # expr
        self.write("(")
        self.write(self.python_keyword("yield from"))
        if t.value:
            self.write(" ")
            self.dispatch(t.value)
        self.write(")")

    def _Raise(self, t):
        self.fill(self.python_keyword("raise"), lineno_node=t)
        if not t.exc:
            assert not t.cause
            return
        self.write(" ")
        self.dispatch(t.exc)
        if t.cause:
            self.write(self.python_keyword(" from "))
            self.dispatch(t.cause)

    def _Try(self, t):
        self.fill(self.python_keyword("try"), lineno_node=t)
        self.enter()
        self.dispatch(t.body)
        self.leave()
        for ex in t.handlers:
            self.dispatch(ex)
        if t.orelse:
            self.fill(self.python_keyword("else"))
            self.enter()
            self.dispatch(t.orelse)
            self.leave()
        if t.finalbody:
            self.fill(self.python_keyword("finally"))
            self.enter()
            self.dispatch(t.finalbody)
            self.leave()

    def _ExceptHandler(self, t):
        self.fill(self.python_keyword("except"), lineno_node=t)
        if t.type:
            self.write(" ")
            self.dispatch(t.type)
        if t.name:
            self.write(self.python_keyword(" as "))
            self.write(t.name)
        self.enter()
        self.dispatch(t.body)
        self.leave()

    def _ClassDef(self, t):
        self.write("\n")

        for deco in t.decorator_list:
            self.fill(self.maybe_colorize("@", ColorScheme.DECORATOR),
                      lineno_node=deco)
            self.write(ColorScheme.DECORATOR)
            with self.nocolor():
                self.dispatch(deco)
            self.write(ColorScheme._RESET)

        class_str = (self.python_keyword("class ") +
                     self.maybe_colorize(t.name, ColorScheme.DEFNAME))
        self.fill(class_str, lineno_node=t)
        self.write("(")
        comma = False
        for e in t.bases:
            if comma:
                self.write(", ")
            else:
                comma = True
            self.dispatch(e)
        for e in t.keywords:
            if comma:
                self.write(", ")
            else:
                comma = True
            self.dispatch(e)
        self.write(")")

        self.enter()
        self.dispatch(t.body)
        self.leave()

    def _FunctionDef(self, t):
        self.__FunctionDef_helper(t, "def")

    def _AsyncFunctionDef(self, t):
        self.__FunctionDef_helper(t, "async def")

    def __FunctionDef_helper(self, t, fill_suffix):
        self.write("\n")

        for deco in t.decorator_list:
            self.fill(self.maybe_colorize("@", ColorScheme.DECORATOR),
                      lineno_node=deco)
            self.write(ColorScheme.DECORATOR)
            with self.nocolor():
                self.dispatch(deco)
            self.write(ColorScheme._RESET)

        def_str = (self.python_keyword(fill_suffix) +
                   " " + self.maybe_colorize(t.name, ColorScheme.DEFNAME) + "(")
        self.fill(def_str, lineno_node=t)
        self.dispatch(t.args)
        self.write(")")
        if t.returns:
            self.write(" -> ")
            self.dispatch(t.returns)
        self.enter()
        self.dispatch(t.body)
        self.leave()
        # TODO: Python 3.8 type_comment, ignore it?

    def _For(self, t):
        self.__For_helper(self.python_keyword("for "), t)

    def _AsyncFor(self, t):
        self.__For_helper(self.python_keyword("async for "), t)

    def __For_helper(self, fill, t):
        self.fill(fill, lineno_node=t)
        self.dispatch(t.target)
        self.write(self.python_keyword(" in "))
        self.dispatch(t.iter)
        self.enter()
        self.dispatch(t.body)
        self.leave()
        if t.orelse:
            self.fill(self.python_keyword("else"))
            self.enter()
            self.dispatch(t.orelse)
            self.leave()
        # TODO: Python 3.8 type_comment, ignore it?

    def _If(self, t):
        self.fill(self.python_keyword("if "), lineno_node=t)
        self.dispatch(t.test)
        self.enter()
        self.dispatch(t.body)
        self.leave()
        # collapse nested ifs into equivalent elifs.
        while (t.orelse and len(t.orelse) == 1 and
               isinstance(t.orelse[0], ast.If)):
            t = t.orelse[0]
            self.fill(self.python_keyword("elif "))
            self.dispatch(t.test)
            self.enter()
            self.dispatch(t.body)
            self.leave()
        # final else
        if t.orelse:
            self.fill(self.python_keyword("else"))
            self.enter()
            self.dispatch(t.orelse)
            self.leave()

    def _While(self, t):
        self.fill(self.python_keyword("while "), lineno_node=t)
        self.dispatch(t.test)
        self.enter()
        self.dispatch(t.body)
        self.leave()
        if t.orelse:
            self.fill(self.python_keyword("else"))
            self.enter()
            self.dispatch(t.orelse)
            self.leave()

    def _With(self, t):
        self.fill(self.python_keyword("with "), lineno_node=t)
        interleave(lambda: self.write(", "), self.dispatch, t.items)
        self.enter()
        self.dispatch(t.body)
        self.leave()
        # TODO: Python 3.8 type_comment, ignore it?

    def _AsyncWith(self, t):
        self.fill(self.python_keyword("async with "), lineno_node=t)
        interleave(lambda: self.write(", "), self.dispatch, t.items)
        self.enter()
        self.dispatch(t.body)
        self.leave()

    # expr
    def _NamedExpr(self, t):  # Python 3.8+
        self.write("(")
        self.dispatch(t.target)
        self.write(" := ")
        self.dispatch(t.value)
        self.write(")")

    def _Constant(self, t):  # Python 3.8+
        # Actually added in 3.6, but Python's parser only produces them starting with 3.8.
        # Replaces the node types Bytes, Str, Num, NameConstant, and Ellipsis.
        if hasattr(t, "kind") and t.kind == "u":  # 3.8+: u"..." vs. "..."
            self.write("u")
        if type(t.value) in (int, float, complex):
            # Represent AST infinity as an overflowing decimal literal.
            v = repr(t.value).replace("inf", INFSTR)
            v = self.maybe_colorize(v, ColorScheme.NUMBER)
        elif t.value is Ellipsis:
            v = "..."
        else:
            v = repr(t.value)
            if t.value in (True, False, None):
                v = self.maybe_colorize(v, ColorScheme.NAMECONSTANT)
            elif type(t.value) in (str, bytes):
                v = self.maybe_colorize(v, ColorScheme.STRING)
        self.write(v)

    def _Bytes(self, t):  # up to Python 3.7
        self.write(self.maybe_colorize(repr(t.s), ColorScheme.STRING))

    def _Str(self, tree):  # up to Python 3.7
        self.write(self.maybe_colorize(repr(tree.s), ColorScheme.STRING))

    def _Name(self, t):
        v = t.id
        if v in builtin_exceptions_and_warnings:
            v = self.maybe_colorize(v, ColorScheme.BUILTINEXCEPTION)
        elif v in builtin_others:
            v = self.maybe_colorize(v, ColorScheme.BUILTINOTHER)
        self.write(v)

    def _NameConstant(self, t):  # up to Python 3.7
        self.write(self.maybe_colorize(repr(t.value), ColorScheme.NAMECONSTANT))

    def _Num(self, t):  # up to Python 3.7
        # Represent AST infinity as an overflowing decimal literal.
        v = repr(t.n).replace("inf", INFSTR)
        self.write(self.maybe_colorize(v, ColorScheme.NUMBER))

    def _List(self, t):
        self.write("[")
        interleave(lambda: self.write(", "), self.dispatch, t.elts)
        self.write("]")

    def _ListComp(self, t):
        self.write("[")
        self.dispatch(t.elt)
        for gen in t.generators:
            self.dispatch(gen)
        self.write("]")

    def _GeneratorExp(self, t):
        self.write("(")
        self.dispatch(t.elt)
        for gen in t.generators:
            self.dispatch(gen)
        self.write(")")

    def _SetComp(self, t):
        self.write("{")
        self.dispatch(t.elt)
        for gen in t.generators:
            self.dispatch(gen)
        self.write("}")

    def _DictComp(self, t):
        self.write("{")
        self.dispatch(t.key)
        self.write(": ")
        self.dispatch(t.value)
        for gen in t.generators:
            self.dispatch(gen)
        self.write("}")

    def _comprehension(self, t):
        if t.is_async:
            self.write(self.python_keyword(" async"))
        self.write(self.python_keyword(" for "))
        self.dispatch(t.target)
        self.write(self.python_keyword(" in "))
        self.dispatch(t.iter)
        for if_clause in t.ifs:
            self.write(self.python_keyword(" if "))
            self.dispatch(if_clause)

    def _IfExp(self, t):
        self.write("(")
        self.dispatch(t.body)
        self.write(self.python_keyword(" if "))
        self.dispatch(t.test)
        self.write(self.python_keyword(" else "))
        self.dispatch(t.orelse)
        self.write(")")

    def _Set(self, t):
        assert(t.elts)  # should be at least one element
        self.write("{")
        interleave(lambda: self.write(", "), self.dispatch, t.elts)
        self.write("}")

    def _Dict(self, t):
        self.write("{")
        def write_pair(pair):
            (k, v) = pair
            self.dispatch(k)
            self.write(": ")
            self.dispatch(v)
        interleave(lambda: self.write(", "), write_pair, zip(t.keys, t.values))
        self.write("}")

    def _Tuple(self, t):
        self.write("(")
        if len(t.elts) == 1:
            (elt,) = t.elts
            self.dispatch(elt)
            self.write(",")
        else:
            interleave(lambda: self.write(", "), self.dispatch, t.elts)
        self.write(")")

    unop = {"Invert": "~", "Not": "not", "UAdd": "+", "USub": "-"}
    def _UnaryOp(self, t):
        self.write("(")
        self.write(self.unop[t.op.__class__.__name__])
        self.write(" ")
        self.dispatch(t.operand)
        self.write(")")

    binop = {"Add": "+", "Sub": "-", "Mult": "*", "MatMult": "@", "Div": "/", "Mod": "%",
                    "LShift": "<<", "RShift": ">>", "BitOr": "|", "BitXor": "^", "BitAnd": "&",
                    "FloorDiv": "//", "Pow": "**"}
    def _BinOp(self, t):
        self.write("(")
        self.dispatch(t.left)
        self.write(" " + self.binop[t.op.__class__.__name__] + " ")
        self.dispatch(t.right)
        self.write(")")

    cmpops = {"Eq": "==", "NotEq": "!=", "Lt": "<", "LtE": "<=", "Gt": ">", "GtE": ">=",
                        "Is": "is", "IsNot": "is not", "In": "in", "NotIn": "not in"}
    def _Compare(self, t):
        self.write("(")
        self.dispatch(t.left)
        for o, e in zip(t.ops, t.comparators):
            self.write(" " + self.cmpops[o.__class__.__name__] + " ")
            self.dispatch(e)
        self.write(")")

    boolops = {ast.And: 'and', ast.Or: 'or'}
    def _BoolOp(self, t):
        self.write("(")
        s = self.python_keyword(self.boolops[t.op.__class__])
        s = f" {s} "
        interleave(lambda: self.write(s), self.dispatch, t.values)
        self.write(")")

    def _Attribute(self, t):
        v = t.value
        self.dispatch(v)
        # Special case: 3.__abs__() is a syntax error, so if t.value
        # is an integer literal then we need to either parenthesize
        # it or add an extra space to get 3 .__abs__().
        if ((isinstance(v, ast.Constant) and isinstance(v.value, int)) or
                (isinstance(v, ast.Num) and isinstance(v.n, int))):
            self.write(" ")
        self.write(".")
        self.write(t.attr)

    def _Call(self, t):
        self.dispatch(t.func)
        self.write("(")
        comma = False
        for e in t.args:
            if comma:
                self.write(", ")
            else:
                comma = True
            self.dispatch(e)
        for e in t.keywords:
            if comma:
                self.write(", ")
            else:
                comma = True
            self.dispatch(e)
        self.write(")")

    def _FormattedValue(self, t):
        # Node representing a single formatting field in an f-string. If the
        # string contains a single formatting field and nothing else the node
        # can be isolated otherwise it appears in `JoinedStr`.
        self.write("f'")
        self._FormattedValue_helper(t)
        self.write("'")

    def _FormattedValue_helper(self, t):
        def c(text):
            return self.maybe_colorize(text, ColorScheme.STRING)
        self.write(c("{"))
        self.dispatch(t.value)
        if t.conversion == 115:
            self.write(c("!s"))
        elif t.conversion == 114:
            self.write(c("!r"))
        elif t.conversion == 97:
            self.write(c("!a"))
        elif t.conversion == -1:  # no formatting
            pass
        else:
            raise ValueError(f"Don't know how to unparse conversion code {t.conversion}")
        if t.format_spec:
            self.write(c(":"))
            self._JoinedStr_helper(t.format_spec)
        self.write(c("}"))

    def _JoinedStr(self, t):
        self.write("f" + self.maybe_colorize("'", ColorScheme.STRING))
        self._JoinedStr_helper(t)
        self.write(self.maybe_colorize("'", ColorScheme.STRING))

    def _JoinedStr_helper(self, t):
        def escape(s):
            return s.replace("'", r"\'").replace("\n", r"\n")
        for v in t.values:
            # Omit the surrounding quotes in string snippets
            if type(v) is ast.Constant:
                self.write(self.maybe_colorize(escape(v.value), ColorScheme.STRING))
            elif type(v) is ast.Str:  # up to Python 3.7
                self.write(self.maybe_colorize(escape(v.s), ColorScheme.STRING))
            elif type(v) is ast.FormattedValue:
                self._FormattedValue_helper(v)
            else:
                raise ValueError(f"Don't know how to unparse {t!r} inside an f-string")

    def _Subscript(self, t):
        self.dispatch(t.value)
        self.write("[")
        self.dispatch(t.slice)
        self.write("]")

    def _Starred(self, t):
        self.write("*")
        self.dispatch(t.value)

    # slice
    def _Ellipsis(self, t):  # up to Python 3.7
        self.write("...")

    def _Index(self, t):
        self.dispatch(t.value)

    def _Slice(self, t):
        if t.lower:
            self.dispatch(t.lower)
        self.write(":")
        if t.upper:
            self.dispatch(t.upper)
        if t.step:
            self.write(":")
            self.dispatch(t.step)

    def _ExtSlice(self, t):
        interleave(lambda: self.write(', '), self.dispatch, t.dims)

    # argument
    def _arg(self, t):
        self.write(t.arg)
        if t.annotation:
            self.write(": ")
            self.dispatch(t.annotation)

    # others
    def _arguments(self, t):
        first = True

        # positional-only, and positional-or-keyword arguments
        nposargs = len(t.args)
        if hasattr(t, "posonlyargs"):
            nposonlyargs = len(t.posonlyargs)
            nposargs += nposonlyargs
        defaults = [None] * (nposargs - len(t.defaults)) + t.defaults

        if hasattr(t, "posonlyargs"):
            args_sets = [t.posonlyargs, t.args]
            defaults_sets = [defaults[:nposonlyargs], defaults[nposonlyargs:]]
            set_separator = ', /'
        else:
            args_sets = [t.args]
            defaults_sets = [defaults]
            set_separator = ''

        for args, defaults in zip(args_sets, defaults_sets):
            for a, d in zip(args, defaults):
                if first:
                    first = False
                else:
                    self.write(", ")
                self.dispatch(a)
                if d:
                    self.write("=")
                    self.dispatch(d)
            self.write(set_separator)

        # varargs, or bare '*' if no varargs but keyword-only arguments present
        if t.vararg or t.kwonlyargs:
            if first:
                first = False
            else:
                self.write(", ")
            self.write("*")
            if t.vararg:
                self.write(t.vararg.arg)
                if t.vararg.annotation:
                    self.write(": ")
                    self.dispatch(t.vararg.annotation)

        # keyword-only arguments
        if t.kwonlyargs:
            for a, d in zip(t.kwonlyargs, t.kw_defaults):
                if first:
                    first = False
                else:
                    self.write(", ")
                self.dispatch(a),
                if d:
                    self.write("=")
                    self.dispatch(d)

        # kwargs
        if t.kwarg:
            if first:
                first = False
            else:
                self.write(", ")
            self.write("**" + t.kwarg.arg)
            if t.kwarg.annotation:
                self.write(": ")
                self.dispatch(t.kwarg.annotation)

    def _keyword(self, t):
        if t.arg is None:
            self.write("**")
        else:
            self.write(t.arg)
            self.write("=")
        self.dispatch(t.value)

    def _Lambda(self, t):
        self.write("(")
        self.write(self.python_keyword("lambda "))
        self.dispatch(t.args)
        self.write(": ")
        self.dispatch(t.body)
        self.write(")")

    def _alias(self, t):
        self.write(t.name)
        if t.asname:
            self.write(self.python_keyword(" as ") + t.asname)

    def _withitem(self, t):
        self.dispatch(t.context_expr)
        if t.optional_vars:
            self.write(self.python_keyword(" as "))
            self.dispatch(t.optional_vars)


def unparse(tree, *, debug=False, color=False):
    """Convert the AST `tree` into source code. Return the code as a string.

    `debug`: bool, print invisible nodes (`Module`, `Expr`).

             The output is then not valid Python, but may better show
             the problem when code produced by a macro mysteriously
             fails to compile (even though the unparse looks ok).

    Upon invalid input, raises `UnparserError`.
    """
    try:
        with io.StringIO() as output:
            Unparser(tree, file=output, debug=debug, color=color)
            code = output.getvalue().strip()
        return code
    except UnparserError as err:  # fall back to an AST dump
        try:
            astdump = dump(tree, multiline=True)
            sep = " " if "\n" not in astdump else "\n"
            msg = f"unparse failed, likely invalid AST; here's an AST dump instead:{sep}{astdump}"
            raise UnparserError(msg) from err
        except TypeError:  # fall back to repr
            representation = repr(tree)
            sep = " " if "\n" not in representation else "\n"
            msg = f"unparse failed, fallback AST dump failed, likely not an AST; here's the type and repr instead:{sep}{type(tree)}{sep}{representation}"
            raise UnparserError(msg) from err


def unparse_with_fallbacks(tree, *, debug=False, color=False):
    """Like `unparse`, but upon error, don't raise; return the error message.

    Usually you'll want the exception to be raised. This is mainly useful to
    compactly express "just give me something to work with" (e.g. for including
    source code into an error message) without having to care about exceptions
    at the receiving end.
    """
    try:
        text = unparse(tree, debug=debug, color=color)
    except UnparserError as err:
        text = err.args[0]
    except Exception as err:
        # This can only happen if there is a bug in the unparser, but we don't
        # want to lose the macro use site filename and line number if this
        # occurs during macro expansion, because having that information makes
        # it much easier to create a minimal example for filing a bug report.
        # TODO: maybe use `traceback.format_exception` here?
        text = f"Internal error in unparser: {type(err)}: {str(err)}"
    return text
