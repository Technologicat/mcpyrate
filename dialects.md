# Dialects

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Dialects](#dialects)
    - [Overview](#overview)
    - [Using dialects](#using-dialects)
        - [Code layout (style guidelines)](#code-layout-style-guidelines)
    - [Writing dialects](#writing-dialects)
        - [Source transformers](#source-transformers)
        - [AST transformers](#ast-transformers)
        - [AST postprocessors](#ast-postprocessors)
    - [Dialect import algorithm](#dialect-import-algorithm)
        - [Notes](#notes)
    - [Debugging dialect transformations](#debugging-dialect-transformations)
        - [Automatic syntax highlighting](#automatic-syntax-highlighting)

<!-- markdown-toc end -->


## Overview

Dialects are essentially *whole-module source and AST transformers*. Think [Racket's](https://racket-lang.org/) `#lang`, but for Python. Source transformers are akin to *reader macros* in the Lisp family.

Dialects allow you to define languages that use Python's surface syntax, but change the semantics; or let you plug in a per-module transpiler that (at import time) compiles source code from some other programming language into macro-enabled Python. Also an AST [optimizer](http://compileroptimizations.com/) could be defined as a dialect.

`mcpyrate`'s dialect system is a more advanced development based on the prototype that appeared as [`pydialect`](https://github.com/Technologicat/pydialect).


## Using dialects

Dialects are compiled into macro-enabled Python, by `mcpyrate`'s importer. So just like when using macros, `mcpyrate` must first be enabled. This is done in exactly the same way as when using macros: import the module `mcpyrate.activate` (and then import your module that uses dialects), or run your program through the `macropython` bootstrapper.

To enable the dialect compiler for your source file, use one or more *dialect-import statements*:

```python
from module import dialects, ...
```

replacing `...` with the dialects you want to use.

Several dialects can be imported by the same source file, in either the same dialect-import (if those dialects are provided by the same module) or in separate dialect-imports.

Dialect-imports always apply **to the whole module**. They essentially specify which language the module is written in. Hence, it is **heavily encouraged** to put all dialect-imports near the top.

All dialect-import statements must in any case appear at the top level of a module body. Each dialect-import statement **must be on a single line** (it must **not** use parentheses or a line continuation), and **must start at the first column on the line where it appears**.

This is to make it easier to scan for the dialect-import statements before source transformations are complete. When the **source** transformers run, *the input is just text*. It is not parseable by `ast.parse`, because a dialect that has a source transformer may introduce new surface syntax. Similarly, it's not tokenizable by `tokenize`, because a dialect (that has a source transformer) may customize what constitutes a token.

So at that point, the only thing the dialect expander can rely on is the literal text `"from ... import dialects, ..."`, similarly to how Racket heavily constrains the format of its `#lang` line.

When the **AST** transformers run, each dialect-import is transformed into `import ...`, where `...` is the absolute dotted name of the module the dialects (in that dialect-import statement) are being imported from.

Until we get [`unpythonic`](https://github.com/Technologicat/unpythonic) ported to use `mcpyrate`, see [`pydialect`](https://github.com/Technologicat/pydialect) for old example dialects.


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

Because we don't (yet) have a generic, extensible tokenizer for *"Python-plus"* with extended surface syntax, `transform_source` is currently essentially a per-module hook to plug in a transpiler that compiles source code *from some other programming language into macro-enabled Python*.

Your `transform_source` method gets its input as `str` (**not** `bytes`). The input is the full source text of the module. Output should be the transformed full source text, as a string (`str`).

To put it all together, source transformers allow implementing things like:

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

If you want to just extend Python's surface syntax slightly, then as a starting point, maybe look at the implementation of the `tokenize` module in Python's standard library. For implementing new languages that compile to Python, maybe look at the [`pyparsing`](https://github.com/pyparsing/pyparsing) library.

Note a source transformer will have to produce *Python source code*, not an AST. But if you can generate a standard (macro-enabled) Python AST, then the `unparse` function of `mcpyrate` may be able to bridge the gap.


### AST transformers

In your dialect, implement the method `transform_ast` to add a whole-module AST transformer. It runs **before** the macro expander.

Dialect AST transformers can, for example:

 - Lift the whole module body (except macro-imports and further dialect-imports) into a *dialect code template AST*, wrapping the original module body with some code-walking block macros.
   - A dialect can extract the pattern of a "standardized" set of block macro invocations.
   - Such macros can significantly change the language's semantics, while keeping Python's surface syntax. See [`unpythonic.syntax`](https://github.com/Technologicat/unpythonic/blob/master/doc/macros.md) for ideas.
 - Examine and selectively rewrite the AST of the whole module. AST optimizers are a possible use case.
 - Inject imports for things that can be considered "builtins" for that dialect. For example, inject a `product` function to complement Python's builtin `sum`; or in a lispy dialect, inject `cons`/`car`/`cdr`.
   - This should be done with care, if at all - *explicit is better than implicit*.

Input to a dialect AST transformer is the full AST of the module (in standard Python AST format), but with the dialect's own dialect-import (and any previous ones) already transformed away, into an absolute module import for the module defining the dialect. Output should be the transformed AST.

Injecting code that invokes macros, and injecting macro-imports, **is** allowed.

To easily splice `tree.body` (the module body) into your dialect code template AST, see the utility [`mcpyrate.splicing.splice_dialect`](mcpyrate/splicing.py). It lets you specify where to paste the code in your template, while automatically lifting macro-imports, dialect-imports, the magic `__all__`, and the module docstring (from the input module body) into the appropriate places in the transformed module body.

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

The dialect works by automatically invoking the `autoreturn` and `tco` code-walking block macros from `unpythonic.syntax`. TCO, in turn, is implemented on top of a layer of regular functions.


### AST postprocessors

A dialect can also provide the method `postprocess_ast`. It works the same as `transform_ast`, but it runs **after** the macro expander.

This is provided separately, because changes in language semantics are best done before macro expansion, but for example an optimizer might want to edit the macro-expanded AST.

Note that `postprocess_ast` receives, and must return, an AST consisting of **regular Python only** (no macro invocations, no dialect-imports!), since by that point macro expansion (and indeed everything but regular Python compilation) has already completed for the tree being compiled.


## Dialect import algorithm

Keep in mind the overall context of [`mcpyrate`'s import algorithm](README.md#mcpyrates-import-algorithm).

Each [dialect class](#writing-dialects) is instantiated separately for the source and AST transformation steps. The AST postprocessing step reuses the instance that was created for the AST transformation step.

In the **source transformation** step, the dialect expander takes the first not-yet-seen dialect-import statement (by literal string content), and applies the source transformers of its dialects left-to-right.

The expander then repeats (each time rescanning the whole source text from the beginning), until the source transformers of all dialect-imports have been applied.

In the **AST transformation** step, the dialect expander takes the first dialect-import statement at the top level of the module body, transforms it away (into an absolute module import), and applies the AST transformers of its dialects left-to-right. It also records each dialect object instance for later use.

The expander then repeats (each time rescanning the AST of the module body from the beginning), until the AST transformers of all dialect-imports have been applied. Once done, there are no dialect-imports remaining.

In the **AST postprocessing** step, the dialect expander runs the AST postprocessors for all dialect instances the AST transformation step recorded, in the same order their AST transformers ran.

### Notes

A source transformer may edit the full source text of the module being compiled, *including any dialect-imports*. Editing those will change which dialects get applied. If a dialect source transformer removes its own dialect-import, that will cause the dialect expander to skip the AST transformers of any dialects in that dialect-import. If it adds any new dialect-imports, those will get processed in the order they are encountered by the dialect import algorithm.

Similarly, an AST transformer may edit the full module AST, including any remaining dialect-imports. If it removes any, those AST transformers will be skipped. If it adds any, those will get processed as encountered (running their AST transformers only).

No coverage dummy nodes are added, because each dialect-import becomes a regular absolute module import, which executes normally at run time.


## Debugging dialect transformations

To enable debug mode, dialect-import the `StepExpansion` dialect, provided by `mcpyrate.debug`:

```python
from mcpyrate.debug import dialects, StepExpansion
```

When the dialect expander invokes the source transformer of the `StepExpansion` dialect, this causes the dialect expander to enter debug mode from that point on. This dialect has no other effects.

(Note this is different from the `step_expansion` macro, which steps *macro* expansion. Dialects are classes, hence the CamelCase name.)

In debug mode, the dialect expander will show the source code (or unparsed AST, as appropriate) after each transformer.

So, to see the whole chain, place the import for the `StepExpansion` dialect first; its source transformer, after enabling debug mode, just returns the original source, so you'll see the original source code as the first step.

### Automatic syntax highlighting

During **source** transformations, syntax highlighting is **not** available, because the surface syntax could mean anything; strictly speaking, it does not even need to look like Python at all.

During **AST** transformations, we have a (macro-enabled) Python AST, and syntax highlighting for the unparsed source code is enabled, but macro names are not highlighted, because the *macro* expander is not yet running.

During **AST postprocessing**, syntax highlighting is enabled for the unparsed source code; no macro invocations remain.
