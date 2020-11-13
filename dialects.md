# Dialects

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Dialects](#dialects)
    - [Overview](#overview)
    - [Using dialects](#using-dialects)
        - [Dialect import algorithm](#dialect-import-algorithm)
        - [Notes](#notes)
        - [Code layout (style guidelines)](#code-layout-style-guidelines)
    - [Writing dialects](#writing-dialects)
        - [Source transformers](#source-transformers)
        - [AST transformers](#ast-transformers)
        - [AST postprocessors](#ast-postprocessors)
    - [Debugging dialect transformations](#debugging-dialect-transformations)

<!-- markdown-toc end -->


## Overview

Dialects are essentially *whole-module source and AST transformations*. Think [Racket's](https://racket-lang.org/) `#lang`, but for Python. Source transformers are akin to *reader macros* in the Lisp family.

Dialects allow you to define languages that use Python's surface syntax, but change the semantics; or to plug in a per-module transpiler that (at import time) compiles source code from some other programming language into macro-enabled Python. Also an AST [optimizer](http://compileroptimizations.com/) could be defined as a dialect.

When a module is imported with `mcpyrate` enabled, the source code is transformed as follows:

 1. All dialect **source** transformers.
 2. All dialect **AST** transformers.
 3. Macro expander.
 4. All dialect **AST postprocessors**.

If the module requests [multi-phase compilation](README.md#multi-phase-compilation), the algorithm is instead:

 1. All dialect **source** transformers.
 2. Extract AST for highest phase remaining.
 3. All dialect **AST** transformers, *for the AST of the current phase*.
 4. Macro expansion, *for the AST of the current phase*.
 5. All dialect **AST postprocessors**, *for the AST of the current phase*.
 6. If not yet at phase `0`, jump back to step 2.

**CAUTION**: As of `mcpyrate` 3.0.0, *code injected by dialect definitions cannot itself use multi-phase compilation*. The client code can; just the code in the dialect code template cannot.

In practice this is not a major obstacle. If the code injected by your dialect definition needs macros, just define them in another module, and make the injected code import them in the usual way. The macros can even live in the module that provides the dialect definition, and that module can also use multi-phase compilation if you want; the only place the macros can't be defined in is the code template itself.


## Using dialects

Dialects are compiled into macro-enabled Python, by `mcpyrate`'s importer. So just like when using macros, `mcpyrate` must first be enabled. This is done in exactly the same way as when using macros.

To enable the dialect compiler for your source file, use one or more *dialect-import statements*:

```python
from module import dialects, ...
```

replacing `...` with the dialects you want to use.

All dialect-import statements must appear at the top level of a module body. Each dialect-import statement **must be on a single line** (it must **not** use parentheses or a line continuation), and **must start at the first column on the line where it appears**.

This is to make it easier to scan for the dialect-import statements before source transformations are complete. When the **source** transformers run, *the input is just text*. It is not parseable by `ast.parse`, because a dialect that has a source transformer may introduce new surface syntax. Similarly, it's not tokenizable by `tokenize`, because a dialect (that has a source transformer) may customize what constitutes a token.

So at that point, the only thing the dialect expander can rely on is the literal text `"from ... import dialects, ..."`, similarly to how Racket heavily constrains the format of its `#lang` line.

When the **AST** transformers run, each dialect-import is transformed into `import ...`, where `...` is the absolute dotted name of the module the dialects (in that dialect-import statement) are being imported from.

Several dialects can be imported by the same source file. Then the dialects will be *chained*, in the order the dialects are imported. All the *source* transformers will run first (in import order), after which all *AST* transformers will run (also in import order). Chaining allows e.g. inserting an AST optimizer as the last whole-module step, before the macro expander runs.

Until we get [`unpythonic`](https://github.com/Technologicat/unpythonic) ported to use `mcpyrate`, see [`pydialect`](https://github.com/Technologicat/pydialect) for old example dialects.


### Dialect import algorithm

The dialect expander takes the first not-yet-seen dialect-import statement (by literal string content), applies its source transformers left-to-right, and repeats (each time rescanning the whole text from the beginning), until the source transformers of all dialect-imports have been applied.

Then the resulting final source text is parsed into a Python AST, using `ast.parse`.

Then, the expander takes the first dialect-import statement at the top level of the module body, transforms it away (into an absolute module import), and applies its AST transformers left-to-right. It then repeats (each time rescanning the AST of the module body from the beginning), until the AST transformers of all dialect-imports have been applied.

The result is an AST that may still use macros, but no more dialects.

Each dialect class is instantiated separately for the source and AST transform phases.


### Notes

A source transformer may edit the full source text of the module being compiled, including any dialect-imports. Editing those will change which dialects get applied. If it removes its own dialect-import, that will cause it to skip its AST transformer. If it adds any new dialect-imports, those will get processed in the order they are encountered by the dialect import algorithm.

Similarly, an AST transformer may edit the full module AST, including any remaining dialect-imports. If it removes any, those AST transformers will be skipped. If it adds any, those will get processed as encountered (running their AST transformers only).

Dialect-imports always apply **to the whole module**. They essentially specify which language the module is written in. Hence, it is **heavily encouraged** to put all dialect-imports near the top.

No coverage dummy nodes are added, because each dialect-import becomes a regular absolute module import, which executes normally at run time.


### Code layout (style guidelines)

For dialects that look mostly like Python, the recommended code layout in the spirit of PEP8 is:

```python
# -*- coding: utf-8; -*-
'''Example module using a dialect.'''

__all__ = [...]  # public API exports

from ... import dialects, ...  # then dialect-imports

from ... import macros, ...  # then macro-imports

# then regular imports and the rest of the code
```


## Writing dialects

Technically speaking, a dialect is a class that inherits from `mcpyrate.dialects.Dialect`, and has the methods `transform_source`, `transform_ast`, and `postprocess_ast`.

It may implement just one of these methods, if the others are not needed. The default implementation for each returns the value `NotImplemented`, which means that the dialect does not need that kind of transformation.

See the docstrings in [`mcpyrate.dialects`](mcpyrate/dialects.py) for details.


### Source transformers

In your dialect, implement the method `transform_source` to add a whole-module source transformer.

This is rarely needed. Because we don't (yet) have a generic, extensible tokenizer for *"Python-plus"* with extended surface syntax, `transform_source` is currently essentially a per-module hook to plug in a transpiler that compiles source code *from some other programming language into macro-enabled Python*.

The dialect system autodetects the text encoding the same way Python itself does. That is, it reads the magic comment at the top of the source file (such as `# -*- coding: utf-8; -*-`), and assumes `utf-8` if this magic comment is not present.

Your `transform_source` method gets its input as `str` (**not** `bytes`). The input is the full source text of the module. Output should be the transformed full source text, as a string (`str`).

To put it all together, source transformations allow implementing things like::

```python
# -*- coding: utf-8; -*-
'''See https://en.wikipedia.org/wiki/Brainfuck#Examples'''

from mylibrary import dialects, Brainfuck

++++++[>++++++++++++<-]>.
>++++++++++[>++++++++++<-]>+.
+++++++..+++.>++++[>+++++++++++<-]>.
<+++[>----<-]>.<<<<<+++[>+++++<-]>.
>>.+++.------.--------.>>+.
```

while having that source code in a file ending in `.py`, executable by `macropython`.

Implementing the actual BF to Python transpiler is left as an exercise to the reader. Maybe compare [how Matthew Butterick did this in Racket](https://beautifulracket.com/bf/intro.html).

If you want to just extend Python's surface syntax slightly, then as a starting point, maybe look at the implementation of the `tokenize` module in Python's standard library. For implementing new languages that just compile to Python, maybe look at the [`pyparsing`](https://github.com/pyparsing/pyparsing) library.

Note a source transformer will have to produce *Python source code*, not an AST. But if you can generate a standard (macro-enabled) Python AST, then the `unparse` function of `mcpyrate` may be able to bridge the gap.


### AST transformers

In your dialect, implement the method `transform_ast` to add a whole-module AST transformer. It runs **before** the macro expander.

Dialect AST transformers can, for example:

 - Lift the whole module body (except macro-imports and further dialect-imports) into a *dialect code template*, wrapping it with some code-walking block macros. If those macros perform extensive AST edits, they can effectively change the language's semantics, while keeping Python's surface syntax.
 - Examine and selectively rewrite the AST of the whole module. Optimizers are a possible use case.
 - Automatically inject imports for things that can be considered "builtins" for that dialect. This should be done with care, if at all - *explicit is better than implicit*.

Input to a dialect AST transformer is the full AST of the module (in standard Python AST format), but with the dialect-import for this dialect already transformed away, into an absolute module import for the module defining the dialect. Output should be the transformed AST.

To easily splice `tree.body` into your dialect code template AST, see the utility [`mcpyrate.splicing.splice_dialect`](mcpyrate/splicing.py); it automatically lifts macro-imports, dialect-imports, the magic `__all__`, and the module docstring into the appropriate places in the transformed module body.

As an example, for now, until we get [`unpythonic`](https://github.com/Technologicat/unpythonic) ported to use `mcpyrate`, see the example dialects in [`pydialect`](https://github.com/Technologicat/pydialect), which are implemented using this exact strategy, but with the older `macropy` macro expander, the older `pydialect` dialect system, and `unpythonic`.

To give a flavor, *Lispython* is essentially Python with automatic TCO, and implicit `return` in tail position:

```python
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
```

### AST postprocessors

A dialect can also provide the method `postprocess_ast`. It works the same as `transform_ast`, but it runs **after** the macro expander.

This is provided separately, because changes in language semantics are best done before macro expansion, but for example an optimizer might want to edit the macro-expanded AST.

Note that `postprocess_ast` receives, and must return, an AST consisting of **regular Python only** (no macro invocations!), since by that point macro expansion has already completed for the tree being compiled.


## Debugging dialect transformations

To enable debug mode, dialect-import the `StepExpansion` dialect, provided by `mcpyrate.debug`:

```python
from mcpyrate.debug import dialects, StepExpansion
```

When the dialect expander invokes the source transformer of `StepExpansion`, this causes the dialect expander to enter debug mode from that point on. This dialect has no other effects.

In debug mode, the dialect expander will show the source code (or unparsed AST, as appropriate) after each transformer.

So, to see the whole chain, place the import for the `StepExpansion` dialect first; its source transformer, after enabling debug mode, just returns the original source, so you'll see the original source code as the first step.

During **source** transformations, syntax highlighting is not available, because the surface syntax could mean anything; it does not necessarily even look like Python. During **AST** transformations, we have a (macro-enabled) Python AST, and syntax highlighting is enabled, but macro names are not highlighted, because the *macro* expander is not yet running. And during **AST postprocessing**, no macro invocations remain.
