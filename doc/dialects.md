**Navigation**

- [Main user manual](main.md)
- [Quasiquotes and `mcpyrate.metatools`](quasiquotes.md)
- [REPL and `macropython`](repl.md)
- [AST walkers](walkers.md)
- **Dialects**
- [Troubleshooting](troubleshooting.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Introduction](#introduction)
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
- [Why dialects?](#why-dialects)
    - [When to make a dialect](#when-to-make-a-dialect)

<!-- markdown-toc end -->


# Introduction

Syntactic macros have two main limitations as to what and how they can transform. As is noted in [The Racket Guide, chapter 17: Creating Languages](https://docs.racket-lang.org/guide/languages.html):

 - *a macro cannot restrict the syntax available in its context or change the meaning of surrounding forms; and*

 - *a macro can extend the syntax of a language only within the parameters of the language’s lexical conventions [...].*

*Dialects* provide infrastructure that can be used to overcome both of these limitations.

Dialects are essentially *whole-module source and AST transformers*. Think [Racket's](https://racket-lang.org/) `#lang`, but for Python. Source transformers are akin to *reader macros* in the Lisp family (*reader extensions* in Racket).

Dialects allow you to define languages that use Python's surface syntax, but change the semantics; or let you plug in a per-module transpiler that (at import time) compiles source code from some other programming language into macro-enabled Python. Also an AST [optimizer](http://compileroptimizations.com/) could be defined as a dialect.


# Using dialects

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


## Code layout (style guidelines)

For dialects that look mostly like Python, the recommended code layout in the spirit of PEP8 is:

```python
# -*- coding: utf-8; -*-
"""Example module using a dialect."""

__all__ = [...]  # public API exports

from ... import dialects, ...  # then dialect-imports

from ... import macros, ...  # then macro-imports

# then regular imports and the rest of the code
```


# Writing dialects

Technically speaking, a dialect is a class that inherits from `mcpyrate.dialects.Dialect`, and has the methods `transform_source`, `transform_ast`, and `postprocess_ast`.

A dialect may implement only those methods it needs. The default implementation for each method returns the value `NotImplemented`, which tells the dialect expander that this dialect does not need that kind of transformation.

See the docstrings in [`mcpyrate.dialects`](../mcpyrate/dialects.py) for details.


## Source transformers

In your dialect, implement the method `transform_source` to add a whole-module source transformer.

Because we don't (yet) have a generic, extensible tokenizer for *"Python-plus"* with extended surface syntax, `transform_source` is currently essentially a per-module hook to plug in a transpiler that compiles source code *from some other programming language into macro-enabled Python*.

The `transform_source` method gets its input as `str` (**not** `bytes`). The input is the full source text of the module. Output should be the transformed full source text, as a string (`str`).

To put it all together, source transformers allow implementing things like:

```python
# -*- coding: utf-8; -*-
"""See https://en.wikipedia.org/wiki/Brainfuck#Examples"""

from mylibrary import dialects, Brainfuck

++++++[>++++++++++++<-]>.
>++++++++++[>++++++++++<-]>+.
+++++++..+++.>++++[>+++++++++++<-]>.
<+++[>----<-]>.<<<<<+++[>+++++<-]>.
>>.+++.------.--------.>>+.
```

while having that source code in a file ending in `.py`, executable by `macropython`.

Implementing the actual BF to Python transpiler is left as an exercise to the reader. Maybe compare [how Matthew Butterick did this in Racket](https://beautifulracket.com/bf/intro.html).

If you want to just extend Python's surface syntax slightly, then as a starting point, maybe look at the implementation of the [`tokenize`](https://docs.python.org/3/library/tokenize.html) module in Python's standard library; or at third-party libraries such as [`LibCST`](https://libcst.readthedocs.io/en/latest/), [`Parso`](https://parso.readthedocs.io/en/latest/), or [`leoAst.py`](http://leoeditor.com/appendices.html#leoast-py). For implementing new languages that compile to Python, maybe look at the [`pyparsing`](https://github.com/pyparsing/pyparsing) library.

Note a source transformer will have to produce *Python source code*, not an AST. If it is more convenient for you to generate a standard (macro-enabled) Python AST, then the `unparse` function of `mcpyrate` may be able to bridge the gap.


## AST transformers

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

To easily splice `tree.body` (the module body) into your dialect code template AST, see the utility [`mcpyrate.splicing.splice_dialect`](../mcpyrate/splicing.py). It lets you specify where to paste the code in your template, while automatically lifting macro-imports, dialect-imports, the magic `__all__`, and the module docstring (from the input module body) into the appropriate places in the transformed module body.

As an example, for now, until we get [`unpythonic`](https://github.com/Technologicat/unpythonic) ported to use `mcpyrate`, see the example dialects in [`pydialect`](https://github.com/Technologicat/pydialect), which are implemented using this exact strategy, but with the older `macropy` macro expander, the older `pydialect` dialect system, and `unpythonic`.

To give a flavor, *Lispython* is essentially Python with automatic TCO, and implicit `return` in tail position:

```python
# -*- coding: utf-8; -*-
"""Lispython example."""

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


## AST postprocessors

A dialect can also provide the method `postprocess_ast`. It works the same as `transform_ast`, but it runs **after** the macro expander.

This is provided separately, because changes in language semantics are best done before macro expansion, but for example an optimizer might want to edit the macro-expanded AST.

Note that `postprocess_ast` receives, and must return, an AST consisting of **regular Python only** (no macro invocations, no dialect-imports!), since by that point macro expansion (and indeed everything but regular Python compilation) has already completed for the tree being compiled.


# Dialect import algorithm

Keep in mind the overall context of [`mcpyrate`'s import algorithm](main.md#the-import-algorithm).

Each [dialect class](#writing-dialects) is instantiated separately for the source and AST transformation steps. The AST postprocessing step reuses the instance that was created for the AST transformation step.

In the **source transformation** step, the dialect expander takes the first not-yet-seen dialect-import statement (by literal string content), and applies the source transformers of its dialects left-to-right.

The expander then repeats (each time rescanning the whole source text from the beginning), until the source transformers of all dialect-imports have been applied.

In the **AST transformation** step, the dialect expander takes the first dialect-import statement at the top level of the module body, transforms it away (into an absolute module import), and applies the AST transformers of its dialects left-to-right. It also records each dialect object instance for later use.

The expander then repeats (each time rescanning the AST of the module body from the beginning), until the AST transformers of all dialect-imports have been applied. Once done, there are no dialect-imports remaining.

In the **AST postprocessing** step, the dialect expander runs the AST postprocessors for all dialect instances the AST transformation step recorded, in the same order their AST transformers ran.

## Notes

A source transformer may edit the full source text of the module being compiled, *including any dialect-imports*. Editing those will change which dialects get applied. If a dialect source transformer removes its own dialect-import, that will cause the dialect expander to skip the AST transformers of any dialects in that dialect-import. If it adds any new dialect-imports, those will get processed in the order they are encountered by the dialect import algorithm.

Similarly, an AST transformer may edit the full module AST, including any remaining dialect-imports. If it removes any, those AST transformers will be skipped. If it adds any, those will get processed as encountered (running their AST transformers only).

No coverage dummy nodes are added, because each dialect-import becomes a regular absolute module import, which executes normally at run time.


# Debugging dialect transformations

To enable debug mode, dialect-import the `StepExpansion` dialect, provided by `mcpyrate.debug`:

```python
from mcpyrate.debug import dialects, StepExpansion
```

When the dialect expander invokes the source transformer of the `StepExpansion` dialect, this causes the dialect expander to enter debug mode from that point on. This dialect has no other effects.

(Note this is different from the `step_expansion` macro, which steps *macro* expansion. Dialects are classes, hence the CamelCase name.)

In debug mode, the dialect expander will show the source code (or unparsed AST, as appropriate) after each transformer.

So, to see the whole chain, place the import for the `StepExpansion` dialect first; its source transformer, after enabling debug mode, just returns the original source, so you'll see the original source code as the first step.

## Automatic syntax highlighting

During **source** transformations, syntax highlighting is **not** available, because the surface syntax could mean anything; strictly speaking, it does not even need to look like Python at all.

During **AST** transformations, we have a (macro-enabled) Python AST, and syntax highlighting for the unparsed source code is enabled, but macro names are not highlighted, because the *macro* expander is not yet running.

During **AST postprocessing**, syntax highlighting is enabled for the unparsed source code; no macro invocations remain.


# Why dialects?

An extension to the Python language doesn't need to make it into the Python core,
*or even be desirable for inclusion* into the Python core, in order to be useful.

Building on functions and syntactic macros, customization of the language itself
is one more tool to extract patterns, at a yet higher level. Beside language
experimentation, such language extensions can be used as a framework that allows
shorter and/or more readable programs. With dialects, [there is no need to hack
Python
itself](http://stupidpythonideas.blogspot.com/2015/06/hacking-python-without-hacking-python.html),
or implement from scratch a custom language (like
[Hy](http://docs.hylang.org/en/stable/) or
[Dogelang](https://pyos.github.io/dg/)) that compiles to Python AST or bytecode.


## When to make a dialect

Often *explicit is better than implicit*. So, most often, don't.

There is however a tipping point with regard to complexity, and/or simply
length, after which implicit becomes better. This already applies to functions
and macros; code in a `with continuations` block (from
[`unpythonic.syntax`](https://github.com/Technologicat/unpythonic/blob/master/doc/macros.md))
is much more readable and maintainable than code manually converted to
[continuation-passing style
(CPS)](https://en.wikipedia.org/wiki/Continuation-passing_style). Such a
code-walking block macro abstracts away the details of that conversion,
allowing us to see the forest for the trees.

There is obviously a tradeoff; as Paul Graham reminds in [On
Lisp](http://paulgraham.com/onlisp.html), each abstraction is another entity for
the reader to learn and remember, so it must save several times its own length
to become an overall win.

So, when to make a dialect depends on how much it will save - in a project or
across several - and on the other hand on how important it is to have a shared
central definition that specifies a *language-level common ground* for some
set of code.

Be aware that, unlike how it was envisioned during the *extensible languages*
movement in the 1960s-70s, language extension is hardly an exercise requiring
only *modest amounts of labor by unsophisticated users* (as quoted and discussed
in [[1]](http://fexpr.blogspot.com/2013/12/abstractive-power.html)). Especially
the interaction between different macros needs a lot of thought, and as the
number of language features grows, the complexity skyrockets.

Seams between parts of the user program that use or do not use some particular
feature (or a combination of features) also require special attention. This is
a language-extension consideration that does not even come into play if you're
designing a new language from scratch.

That said, long live [language-oriented
programming](https://en.wikipedia.org/wiki/Language-oriented_programming),
and have fun!
