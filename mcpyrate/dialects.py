# -*- coding: utf-8; -*-
'''Find and expand dialects, i.e. whole-module source and AST transformations.'''

__all__ = ["Dialect",
           "expand_dialects"]

import ast
import importlib
import importlib.util
import re
from sys import stderr

from .coreutils import ismacroimport, get_macros
from .unparser import unparse_with_fallbacks


class Dialect:
    '''Base class for dialects.'''
    def __init__(self, expander):
        '''`expander`: the `DialectExpander` instance. The expander provides this automatically.'''
        self.expander = expander

    def transform_source(self, text):
        '''Override this to add a whole-module source transformer to your dialect.

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
            """See https://en.wikipedia.org/wiki/Brainfuck#Examples"""

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
        '''
        return NotImplemented

    def transform_ast(self, tree):
        '''Override this to add a whole-module AST transformer to your dialect.

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
            """Lispython example."""

            from mylibrary import dialects, Lispython

            def fact(n):
                def f(k, acc):
                    if k == 1:
                        return acc
                    f(k - 1, k*acc)
                f(n, acc=1)
            assert fact(4) == 24
            fact(5000)  # no crash
        '''
        return NotImplemented


_message_header = "**StepExpansion: "
class StepExpansion(Dialect):  # actually part of public API of mcpyrate.debug, for discoverability
    """[dialect] Show each step of expansion while dialect-expanding the module.

    Usage::

        from mcpyrate.debug import dialects, StepExpansion

    When the dialect expander invokes the source transformer of this dialect,
    it causes the expander to enter debug mode from that point on. It will show
    the source code (or unparsed AST, as appropriate) after each transformation.
    So, to see the whole chain, place the import for this dialect first.

    This dialect has no other effects.
    """
    def transform_source(self, text):
        self.expander.debugmode = True
        print(f"{_message_header}{self.expander.filename} enabled DialectExpander debug mode while taking step {self.expander._step + 1}.", file=stderr)
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
    '''The dialect expander.'''

    def __init__(self, filename):
        '''`filename`: full path to `.py` file being expanded, for module name resolution and error messages.'''
        self.filename = filename
        self.debugmode = False  # to enable, `from mcpyrate.debug import dialects, StepExpansion`
        self._step = 0
        self._seen = set()

    def expand(self, data):
        '''Expand dialects in `data` (bytes) corresponding to `self.filename`. Top-level entrypoint.

        Dialects are expanded until no dialects remain.

        Return value is an AST for the module.
        '''
        text = importlib.util.decode_source(data)
        text = self.transform_source(text)
        try:
            tree = ast.parse(data, filename=self.filename, mode="exec")
        except Exception as err:
            raise ImportError(f"Failed to parse {self.filename} as Python after applying all dialect source transformers.") from err
        return self.transform_ast(tree)

    def transform_source(self, text):
        '''Apply all whole-module source transformers.'''
        return self._transform(text, kind="source",
                               find_dialectimport=self.find_dialectimport_source,
                               transform="transform_source",
                               format_for_display=lambda text: text)

    def transform_ast(self, tree):
        '''Apply all whole-module AST transformers.'''
        return self._transform(tree, kind="AST",
                               find_dialectimport=self.find_dialectimport_ast,
                               transform="transform_ast",
                               format_for_display=unparse_with_fallbacks)

    def _transform(self, content, *, kind, find_dialectimport, transform, format_for_display):
        if self.debugmode:
            plural = "s" if self._step != 1 else ""
            print(f"{_message_header}{self.filename} before dialect {kind} transformers ({self._step} step{plural} total):\n", file=stderr)
            print(format_for_display(content), file=stderr)
            print("-" * 79, file=stderr)

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

                if result is NotImplemented:
                    continue  # no step taken; proceed to next binding

                if not result:
                    raise ImportError(f"Dialect transformer `{module_absname}.{dialectname}.{transform}` returned an empty result.")
                content = result
                self._step += 1

                if self.debugmode:
                    print(f"{_message_header}{self.filename} after {module_absname}.{dialectname}.{transform} (step {self._step}):\n", file=stderr)
                    print(format_for_display(content), file=stderr)
                    print("-" * 79, file=stderr)

        if self.debugmode:
            plural = "s" if self._step != 1 else ""
            print(f"{_message_header}All dialect {kind} transformers completed for {self.filename} ({self._step} step{plural} total).", file=stderr)
            print("-" * 79, file=stderr)

        return content

    def find_dialectimport_source(self, text):
        '''Find the first dialect-import statement by scanning source code `text`.

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
        '''
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
        '''Find the first dialect-import statement by scanning the AST `tree`.

        Transform the dialect-import into `import ...`, where `...` is the absolute
        module name the dialects are being imported from. As a side effect, import
        the dialect definition module.

        Primarily meant to be called with `tree` the AST of a module that
        uses dialects, but works with any `tree` that has a `body` attribute.

        A dialect-import is a statement of the form::

            from ... import dialects, ...

        Return value is a dict `{dialectname: class, ...}` with all collected bindings
        from that one dialect-import. Each binding is a dialect, so usually there is
        just one.
        '''
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

# --------------------------------------------------------------------------------

def expand_dialects(data, *, filename):
    '''Find and expand dialects, i.e. whole-module source and AST transformers.

    The algorithm works as follows.

    We take the first not-yet-seen dialect-import statement (by literal string
    content), apply its source transformers left-to-right, and repeat (each
    time rescanning the text from the beginning) until the source transformers
    of all dialect-imports have been applied.

    Then, we take the first dialect-import statement at the top level of the
    module, transform it away (into a module import), and apply its AST
    transformers left-to-right. We then repeat (each time rescanning the AST
    from the beginning) until the AST transformers of all dialect-imports have
    been applied.

    Then we return `tree`; it may still have macros, but no more dialects.

    Each dialect class is instantiated separately for the source and AST
    transform phases.

    Note that a source transformer may edit the full source, including any
    dialect-imports. This will change which dialects get applied. If it removes
    its own dialect-import, that will cause it to skip its AST transformer.
    If it adds any new dialect-imports, those will get processed as encountered.

    Similarly, an AST transformer may edit the full module AST, including any
    remaining dialect-imports. If it removes any, those AST transformers will
    be skipped. If it adds any, those will get processed as encountered.

    **CAUTION**: Dialect-imports always apply to the whole module. They
    essentially specify which language the module is written in. Hence,
    it is heavily encouraged to put all dialect-imports near the top.

    If the dialect looks mostly like Python, the recommended layout in the
    spirit of PEP8 is::

        # -*- coding: utf-8; -*-
        """Example module using a dialect."""

        __all__ = [...]

        from ... import dialects, ...  # dialect-imports

        from ... import macros, ...  # then macro-imports

        # then regular imports and the rest of the code
    '''
    dexpander = DialectExpander(filename)
    return dexpander.expand(data)
