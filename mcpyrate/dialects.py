# -*- coding: utf-8; -*-
"""Find and expand dialects, i.e. whole-module source and AST transformers."""

__all__ = ["Dialect", "DialectExpander"]

import ast
import functools
import re
from sys import stderr

from .colorizer import setcolor, colorize, ColorScheme
from .coreutils import ismacroimport, get_macros
from .unparser import unparse_with_fallbacks
from .utils import format_macrofunction


class Dialect:
    """Base class for dialects."""
    def __init__(self, expander):
        """`expander`: the `DialectExpander` instance. The expander provides this automatically."""
        self.expander = expander

    def transform_source(self, text):
        """Override this to add a whole-module source transformer to your dialect.

        If not overridden, the default is to return `NotImplemented`, which
        tells the expander this dialect does not provide a source transformer.

        Rarely needed. Because we don't (yet) have a generic, extensible
        tokenizer for "Python-plus" with extended surface syntax, this is
        currently essentially a per-module hook to plug in a transpiler
        that compiles source code from some other programming language
        into macro-enabled Python.

        The dialect system autodetects the text encoding the same way Python itself
        does. That is, it reads the magic comment at the top of the source file
        (such as `# -*- coding: utf-8; -*-`), and assumes `utf-8` if not present.
        So your source transformer gets its input as `str` (**not** `bytes`).

        The input is the full source text of the module, as a string (`str`).

        Output should be the transformed source text, as a string (`str`).

        To put it all together, this allows implementing things like::

            # -*- coding: utf-8; -*-
            '''See https://en.wikipedia.org/wiki/Brainfuck#Examples'''

            from mylibrary import dialects, Brainfuck

            ++++++[>++++++++++++<-]>.
            >++++++++++[>++++++++++<-]>+.
            +++++++..+++.>++++[>+++++++++++<-]>.
            <+++[>----<-]>.<<<<<+++[>+++++<-]>.
            >>.+++.------.--------.>>+.

        while having that source code in a file ending in `.py`, executable by
        `macropython`.

        Implementing the actual BF->Python transpiler is left as an exercise
        to the reader. Maybe compare how Matthew Butterick did this in Racket:
            https://beautifulracket.com/bf/intro.html
        """
        return NotImplemented

    def transform_ast(self, tree):
        """Override this to add a whole-module AST transformer to your dialect.

        Dialect AST transformers run before the macro expander.

        If not overridden, the default is to return `NotImplemented`, which
        tells the expander this dialect does not provide an AST transformer.

        This is useful to define custom dialects that use Python's surface syntax,
        but with different semantics. Another use case is to plug in an AST optimizer.

        Input is the full AST of the module (in standard Python AST format),
        but with the dialect-import for this dialect already transformed away,
        into an absolute module import for the module defining the dialect.
        Output should be the transformed AST.

        To easily splice `tree.body` into your template, see the utility
        `mcpyrate.splicing.splice_dialect` (it automatically handles macro-imports,
        dialect-imports, the magic `__all__`, and the module docstring).

        As an example, for now, until `unpythonic` is ported to `mcpyrate`, see the
        example dialects in `pydialect`, which are implemented using this exact
        strategy, but with the older `macropy` macro expander, the older `pydialect`
        dialect system, and `unpythonic`.

            https://github.com/Technologicat/pydialect

        To give a flavor; once we get that ported, we'll have *Lispython*, which is
        essentially Python with TCO, and implicit `return` in tail position::

            # -*- coding: utf-8; -*-
            '''Lispython example.'''

            from mylibrary import dialects, Lispython

            def fact(n):
                def f(k, acc):
                    if k == 1:
                        return acc
                    f(k - 1, k * acc)
                f(n, acc=1)
            assert fact(4) == 24
            fact(5000)  # no crash
        """
        return NotImplemented

    def postprocess_ast(self, tree):
        """Like `transform_ast`, but runs after the macro expander."""
        return NotImplemented


_message_header = colorize("**StepExpansion: ", ColorScheme.HEADING)
class StepExpansion(Dialect):  # actually part of public API of mcpyrate.debug, for discoverability
    """[dialect] Show each step of expansion while dialect-expanding the module.

    Usage::

        from mcpyrate.debug import dialects, StepExpansion

    When the dialect expander invokes the source transformer of this dialect,
    it causes the expander to enter debug mode from that point on. It will show
    the source code (or unparsed AST, as appropriate) after each transformer.
    So, to see the whole chain, place the import for this dialect first.

    This dialect has no other effects.
    """
    def transform_source(self, text):
        self.expander.debugmode = True
        c, CS = setcolor, ColorScheme
        msg = f"{c(CS.SOURCEFILENAME)}{self.expander.filename} {c(CS.HEADING)}enabled {c(CS.ATTENTION)}DialectExpander debug mode {c(CS.HEADING)}while taking step {self.expander._step + 1}.{c()}"
        print(_message_header + msg, file=stderr)
        # Pass through the input (instead of returning `NotImplemented`) to
        # consider this as having taken a step, thus triggering the debug mode
        # output printer. (If this was the first dialect applied, our output is
        # actually the original input; but there's no way to know to show it
        # before this dialect has run.)
        return text

# --------------------------------------------------------------------------------

_dialectimport = re.compile(r"^from\s+([.0-9a-zA-z_]+)\s+import dialects,\s+([^(\\]+)\s*$",
                            flags=re.MULTILINE)
class DialectExpander:
    """The dialect expander.

    Due to modularity requirements introduced by `mcpyrate`'s support for
    multi-phase compilation (see the module `mcpyrate.multiphase`), this
    class is a bit technical to use. See `mcpyrate.importer`. Roughly,
    for a single-phase compile::

        dexpander = DialectExpander(filename=...)
        text = dexpander.transform_source(text)
        ... # parse `text` into an AST `tree` here
        tree, dialect_instances = dexpander.transform_ast(tree)
        ... # macro-expand `tree` here
        tree = dexpander.postprocess_ast(tree, dialect_instances)
    """

    def __init__(self, filename):
        """`filename`: full path to `.py` file being expanded, for module name resolution and error messages."""
        self.filename = filename
        self.debugmode = False  # to enable, `from mcpyrate.debug import dialects, StepExpansion`
        self._step = 0
        self._seen = set()

    def transform_source(self, text):
        """Apply all whole-module source transformers.

        Return value is the transformed text.
        """
        new_text, _ = self._transform(text, kind="source",
                                      find_dialectimport=self.find_dialectimport_source,
                                      transform="transform_source",
                                      format_for_display=lambda text: text)
        return new_text

    def transform_ast(self, tree):
        """Apply all whole-module AST transformers.

        Return value is `transformed_tree, dialect_instances`.

        `dialect_instances` is a `list` of the `Dialect` instances that ran,
        in the order in which they ran. That list can be passed to `postprocess_ast`
        to run their AST postprocessors.
        """
        formatter = functools.partial(unparse_with_fallbacks, debug=True, color=True)
        return self._transform(tree, kind="AST",
                               find_dialectimport=self.find_dialectimport_ast,
                               transform="transform_ast",
                               format_for_display=formatter)

    def _transform(self, content, *, kind, find_dialectimport, transform, format_for_display):
        c, CS = setcolor, ColorScheme
        if self.debugmode:
            plural = "s" if self._step != 1 else ""
            msg = f"{c(CS.SOURCEFILENAME)}{self.filename} {c(CS.HEADING)}before dialect {c(CS.TRANSFORMERKIND)}{kind} {c(CS.HEADING)}transformers ({self._step} step{plural} total):{c()}\n"
            print(_message_header + msg, file=stderr)
            print(format_for_display(content), file=stderr)

        # We collect and return the dialect object instances so that both
        # `transform_ast` and `postprocess_ast` can use the same instances. The
        # dialect-imports vanish at `transform_ast`, so the information about
        # which dialects ran (and hence should have their postprocessors run)
        # must be preserved separately from `tree` itself.
        #
        # We could store this data in `self`, but keeping nontrivial mutable
        # state is so last decade.
        dialect_instances = []
        while True:
            module_absname, bindings = find_dialectimport(content)
            if not module_absname:  # no more dialects
                break
            if not bindings:
                continue

            for dialectname, cls in bindings.items():
                if not (isinstance(cls, type) and issubclass(cls, Dialect)):
                    raise TypeError(f"{self.filename}: {module_absname}.{dialectname} is not a `Dialect`, got {repr(cls)}")

                try:
                    dialect = cls(expander=self)
                except Exception as err:
                    raise ImportError(f"Unexpected exception while instantiating dialect `{module_absname}.{dialectname}`") from err

                try:
                    transformer_method = getattr(dialect, transform)
                except AttributeError as err:
                    raise ImportError(f"Dialect `{module_absname}.{dialectname}` missing required transformer method `{transform}`") from err

                try:
                    result = transformer_method(content)
                except Exception as err:
                    raise ImportError(f"Unexpected exception in dialect transformer `{module_absname}.{dialectname}.{transform}`") from err

                # We should run the corresponding `postprocess_ast` even if the
                # dialect doesn't use `transform_ast`.
                dialect_instances.append(dialect)

                if result is NotImplemented:
                    continue  # no step taken; proceed to next binding

                if not result:
                    raise ImportError(f"Dialect transformer `{module_absname}.{dialectname}.{transform}` returned an empty result.")
                content = result
                self._step += 1

                if self.debugmode:
                    msg = f"{c(CS.SOURCEFILENAME)}{self.filename} {c(CS.HEADING)}after {c(CS.DIALECTTRANSFORMERNAME)}{module_absname}.{dialectname}.{transform} {c(CS.HEADING)}(step {self._step}):{c()}\n"
                    print(_message_header + msg, file=stderr)
                    print(format_for_display(content), file=stderr)

        if self.debugmode:
            plural = "s" if self._step != 1 else ""
            msg = f"{c(CS.SOURCEFILENAME)}{self.filename} {c(CS.HEADING)}completed all dialect {c(CS.TRANSFORMERKIND)}{kind} {c(CS.HEADING)}transforms ({self._step} step{plural} total).{c()}"
            print(_message_header + msg, file=stderr)

        return content, dialect_instances

    def postprocess_ast(self, tree, dialect_instances):
        """Apply AST postprocessors of dialect objects in `dialect_instances`.

        Return value is the postprocessed tree.
        """
        format_for_display = functools.partial(unparse_with_fallbacks, debug=True, color=True)

        c, CS = setcolor, ColorScheme
        if self.debugmode:
            plural = "s" if self._step != 1 else ""
            msg = f"{c(CS.SOURCEFILENAME)}{self.filename} {c(CS.HEADING)}before dialect {c(CS.TRANSFORMERKIND)}AST postprocessors {c(CS.HEADING)}({self._step} step{plural} total):{c()}\n"
            print(_message_header + msg, file=stderr)
            print(format_for_display(tree), file=stderr)

        content = tree
        for dialect in dialect_instances:
            try:
                transformer_method = dialect.postprocess_ast
            except AttributeError as err:
                raise ImportError(f"Dialect `{format_macrofunction(dialect)}` missing required transformer method `postprocess_ast`") from err

            try:
                result = transformer_method(content)
            except Exception as err:
                raise ImportError(f"Unexpected exception in dialect transformer `{format_macrofunction(dialect)}.postprocess_ast`") from err

            if result is NotImplemented:
                continue  # no step taken; proceed to next dialect

            if not result:
                raise ImportError(f"Dialect transformer `{format_macrofunction(dialect)}.postprocess_ast` returned an empty result.")
            content = result
            self._step += 1

            if self.debugmode:
                msg = f"{c(CS.SOURCEFILENAME)}{self.filename} {c(CS.HEADING)}after {c(CS.DIALECTTRANSFORMERNAME)}{format_macrofunction(dialect)}.postprocess_ast {c(CS.HEADING)}(step {self._step}):{c()}\n"
                print(_message_header + msg, file=stderr)
                print(format_for_display(content), file=stderr)

        if self.debugmode:
            plural = "s" if self._step != 1 else ""
            msg = f"{c(CS.SOURCEFILENAME)}{self.filename} {c(CS.HEADING)}completed all dialect {c(CS.TRANSFORMERKIND)}AST postprocessors {c(CS.HEADING)}({self._step} step{plural} total).{c()}"
            print(_message_header + msg, file=stderr)

        return content

    def find_dialectimport_source(self, text):
        """Find the first dialect-import statement by scanning source code `text`.

        As a side effect, import the dialect definition module.

        A dialect-import is a statement of the form::

            from ... import dialects, ...

        To keep the search simple, the dialect-import **must**:

          - Be on a single line; not use parentheses or a line continuation.
          - Start at the first column on the line where it appears.

        When this runs, the input is just text. It is not parseable by `ast.parse`,
        because a dialect that has a source transformer may introduce new surface
        syntax. Similarly, it's not tokenizable by `tokenize`, because a dialect
        may customize what constitutes a token.

        So we can only rely on the literal text "from ... import dialects, ...",
        similarly to how Racket heavily constrains the format of its `#lang` line.

        Return value is a dict `{dialectname: class, ...}` with all collected bindings
        from that one dialect-import. Each binding is a dialect, so usually there is
        just one.
        """
        matches = _dialectimport.finditer(text)
        try:
            while True:
                match = next(matches)
                statement = match.group(0).strip()
                if statement not in self._seen:  # apply each unique dialect-import once
                    self._seen.add(statement)
                    break
        except StopIteration:
            return "", {}

        dummy_module = ast.parse(statement, filename=self.filename, mode="exec")
        dialectimport = dummy_module.body[0]
        module_absname, bindings = get_macros(dialectimport, filename=self.filename,
                                              reload=False, allow_asname=False)
        return module_absname, bindings

    def find_dialectimport_ast(self, tree):
        """Find the first dialect-import statement by scanning the AST `tree`.

        Transform the dialect-import into `import ...`, where `...` is the absolute
        module name the dialects are being imported from. As a side effect, import
        the dialect definition module.

        Primarily meant to be called with `tree` the AST of a module that
        uses dialects, but works with any `tree` that has a `body` attribute,
        where that `body` is a `list` of statement AST nodes.

        A dialect-import is a statement of the form::

            from ... import dialects, ...

        Return value is a dict `{dialectname: class, ...}` with all collected bindings
        from that one dialect-import. Each binding is a dialect, so usually there is
        just one.
        """
        for index, statement in enumerate(tree.body):
            if ismacroimport(statement, magicname="dialects"):
                break
        else:
            return "", {}

        module_absname, bindings = get_macros(statement, filename=self.filename,
                                              reload=False, allow_asname=False)
        # Remove all names to prevent dialects being used as regular run-time objects.
        # Always use an absolute import, for the unhygienic expose API guarantee.
        tree.body[index] = ast.copy_location(ast.Import(names=[ast.alias(name=module_absname, asname=None)]),
                                             statement)
        return module_absname, bindings
