# mcpyrate

Advanced macro expander and language lab for Python. The focus is on correctness, feature-completeness for serious macro-enabled work, and simplicity, in that order. We support Python 3.6, 3.7, 3.8, and PyPy3.

We aim at developer-friendliness. `mcpyrate` yields correct [coverage](https://github.com/nedbat/coveragepy/) for macro-enabled code, reports errors as early as possible, and makes it easy to display the steps of any macro expansion - with syntax highlighting, use site filename, and source line numbers:

![mcpyrate stepping through expansion of `letseq` from demos](step_expansion.png)
**Figure 1.** *`mcpyrate` stepping through `letseq` from the demos.*

`mcpyrate` builds on [`mcpy`](https://github.com/delapuente/mcpy), with a similar explicit and compact approach, but with a lot of new features. Some of our features are strongly inspired by [`macropy`](https://github.com/lihaoyi/macropy), such as quasiquotes, macro arguments, and expansion tracing. Features original to `mcpyrate` include a universal bootstrapper, integrated REPL system (including an IPython extension) and support for chainable whole-module source and AST transformers, developed from the earlier prototypes [`imacropy`](https://github.com/Technologicat/imacropy) and [`pydialect`](https://github.com/Technologicat/pydialect); plus multi-phase compilation, and identifier macros.

We use [semantic versioning](https://semver.org/). `mcpyrate` is almost-but-not-quite compatible with `mcpy` 2.0.0, hence the initial release is 3.0.0. There are some differences in the named parameters the expander provides to the macro functions; for details, search [the main user manual](doc/main.md) for *differences to mcpy*.

![100% Python](https://img.shields.io/github/languages/top/Technologicat/mcpyrate) 
![open issues](https://img.shields.io/github/issues/Technologicat/mcpyrate) 
[![contributions welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](http://makeapullrequest.com/)


<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [mcpyrate](#mcpyrate)
    - [First example](#first-example)
    - [Features](#features)
    - [Documentation](#documentation)
    - [Install & uninstall](#install--uninstall)
    - [Understanding the implementation](#understanding-the-implementation)
    - [Why macros?](#why-macros)

<!-- markdown-toc end -->

## First example

`mcpyrate` gives you macro-enabled Python with just two source files:

```python
# mymacros.py with your macro definitions
def echo(expr, **kw):
    print('Echo')
    return expr

# application.py
from mymacros import macros, echo
echo[6 * 7]
```

Or even with just one source file:

```python
# application.py
from mcpyrate.multiphase import macros, phase

with phase[1]:
    def echo(expr, **kw):
        print('Echo')
        return expr

from __self__ import macros, echo
echo[6 * 7]
```

To run either example, `macropython -m application`, or `macropython application.py`. For more examples, see the [`demo/`](demo/) subfolder.


## Features

- **Agile development tools**.
  - [Multi-phase compilation](doc/main.md#multi-phase-compilation): Use macros also in the same module where they are defined.
  - Universal bootstrapper: `macropython`. Import and use macros in your main program.
  - Interactive console: `macropython -i`. Import, define and use macros in a console session.
    - Embeddable à la `code.InteractiveConsole`. See `mcpyrate.repl.console.MacroConsole`.
  - IPython extension `mcpyrate.repl.iconsole`. Import, define and use macros in an IPython session.
  - See [full documentation of the REPL system](doc/repl.md).

- **Testing and debugging**.
  - Statement coverage is correctly reported by tools such as [`Coverage.py`](https://github.com/nedbat/coveragepy/).
  - Macro expansion errors are reported at macro expansion time, with use site traceback.
  - Debug output **with a step-by-step expansion breakdown**. See macro [`mcpyrate.debug.step_expansion`](mcpyrate/debug.py).
    - Has both expr and block modes. Use `step_expansion[...]` or `with step_expansion` as appropriate.
    - The output is **syntax-highlighted**, and **line-numbered** based on `lineno` fields from the AST.
      - Also names of macros currently bound in the expander are highlighted by `step_expansion`.
      - Line numbers are taken from *statement* AST nodes.
    - The invisible nodes `ast.Module` and `ast.Expr` are shown, since especially `ast.Expr` is a common trap for the unwary.
    - To step the expansion of a run-time AST value, see the macro [`mcpyrate.metatools.stepr`](mcpyrate/metatools.py). [Documentation](doc/quasiquotes.md#the-expand-family-of-macros).
  - Manual expand-once. See `expander.visit_once`; get the `expander` as a named argument of your macro. See also the `expand1s` and `expand1r` macros in [`mcpyrate.metatools`](mcpyrate/metatools.py).

- **Lightning speed**.
  - Bytecode caches (`.pyc`) are created and kept up-to-date. Saves macro expansion cost at startup for unchanged modules. Makes `mcpyrate` fast [on average](https://en.wikipedia.org/wiki/Amortized_analysis).

    Beside a `.py` source file itself, we look at any macro definition files
    it imports macros from, recursively, in a `make`-like fashion.

    The mtime is the latest of those of the source file and its macro-dependencies,
    considered recursively, so that if any macro definition anywhere in the
    macro-dependency tree of a source file is changed, Python will treat that
    source file as "changed", thus re-expanding and recompiling it (hence,
    updating the corresponding `.pyc`).
  - **CAUTION**: [PEP 552 - Deterministic pycs](https://www.python.org/dev/peps/pep-0552/) is not supported; we support only the default *mtime* invalidation mode, at least for now.

- **Quasiquotes**, with advanced features.
  - Hygienically interpolate both regular values **and macro names**.
  - Delayed macro expansion inside quasiquoted code. User-controllable.
  - Inverse quasiquote operator. See function [`mcpyrate.quotes.unastify`](mcpyrate/quotes.py).
    - Convert a quasiquoted AST back into a direct AST, typically for further processing before re-quoting it.
      - Not an unquote; we have those too, but the purpose of unquotes is to interpolate values into quoted code. The inverse quasiquote, instead, undoes the quasiquote operation itself, after any unquotes have already been applied.
  - See [full documentation of the quasiquote system](doc/quasiquotes.md).

- **Macro arguments**.
  - Opt-in. Declare by using the [`@parametricmacro`](mcpyrate/expander.py) decorator on your macro function.
  - Use brackets to invoke, e.g. `macroname[arg0, ...][expr]`. If no args, just leave that part out, e.g. `macroname[expr]`.
  - The `macroname[arg0, ...]` syntax works in `expr`, `block` and `decorator` macro invocations in place of a bare `macroname`.
  - The named parameter `args` is a raw `list` of the macro argument ASTs. Empty if no args were sent, or if the macro function is not parametric.

- **Identifier (a.k.a. name) macros**.
  - Opt-in. Declare by using the [`@namemacro`](mcpyrate/expander.py) decorator on your macro function.
  - Can be used for creating magic variables that may only appear inside specific macro invocations.

- **Dialects, i.e. whole-module source and AST transforms**.
  - Think [Racket's](https://racket-lang.org/) `#lang`, but for Python.
  - Define languages that use Python's surface syntax, but change the semantics; or plug in a per-module transpiler that (at import time) compiles source code from some other programming language into macro-enabled Python. Also an AST [optimizer](http://compileroptimizations.com/) could be defined as a dialect. Dialects can be chained.
  - Sky's the limit, really. Until we get [`unpythonic`](https://github.com/Technologicat/unpythonic) ported to use `mcpyrate`, see [`pydialect`](https://github.com/Technologicat/pydialect) for old example dialects.
  - For debugging, `from mcpyrate.debug import dialects, StepExpansion`.
  - If writing a full-module AST transformer that splices the whole module into a template, see [`mcpyrate.splicing.splice_dialect`](mcpyrate/splicing.py).
  - See [full documentation of the dialect system](doc/dialects.md).

- **Conveniences**.
  - Relative macro-imports (for code in packages), e.g. `from .other import macros, kittify`.
  - The expander automatically fixes missing `ctx` attributes in the AST, so you don't need to care about those in your macros.
  - In most cases, the expander also fills in correct source location information automatically (for coverage reporting). If you're discarding nodes from the input, then you may have to be [slightly careful](doc/main.md#writing-macros) and use `ast.copy_location` appropriately.
  - Several block macros can be invoked in the same `with` (equivalent to nesting them, with leftmost outermost).
  - [AST visitor and transformer](mcpyrate/walkers.py) à la `macropy`'s `Walker`, to easily context-manage state for subtrees, and collect items across the whole walk. [Full documentation](doc/walkers.md).
  - AST [markers](mcpyrate/markers.py) (pseudo-nodes) for communication in a set of co-operating macros (and with the expander).
  - [`gensym`](mcpyrate/utils.py) to create a fresh, unused lexical identifier.
  - [`unparse`](mcpyrate/unparser.py) to convert an AST to the corresponding source code, optionally with syntax highlighting (for terminal output).
  - [`dump`](mcpyrate/astdumper.py) to look at an AST representation directly, with (mostly) PEP8-compliant indentation, optionally with syntax highlighting (node types, field names, bare values).


## Documentation

The full documentation of `mcpyrate` lives in the [`doc/`](doc/) subfolder. Some quick links:

- [Main user manual](doc/main.md) - start here
  - [Using macros](doc/main.md#using-macros)
  - [Writing macros](doc/main.md#writing-macros) - starting with a short tour of useful modules in `mcpyrate`.
  - [Multi-phase compilation](doc/main.md#multi-phase-compilation)
  - [The import algorithm](doc/main.md#the-import-algorithm) - how macros, dialects and multi-phase compilation interact.
- [Quasiquotes and `mcpyrate.metatools`](doc/quasiquotes.md)
- [REPL and `macropython`](doc/repl.md)
- [AST walkers](doc/walkers.md)
- [Dialects](doc/dialects.md)
- [Troubleshooting](doc/troubleshooting.md)

*We aim at complete documentation.* If you find something is missing, please [file an issue](https://github.com/Technologicat/mcpyrate/issues/new) to ask a question.


## Install & uninstall

### From PyPI

```bash
pip install mcpyrate
```

possibly with `--user`, if your OS is a *nix, and you feel lucky enough to use the system Python. If not, activate your venv first; the `--user` flag is then not needed.

### From source

Clone the repo from GitHub. Then, navigate to it in a terminal, and:

```bash
python -m setup install
```

possibly with `--user`, if your OS is a *nix, and you feel lucky enough to use the system Python. If not, activate your venv first; the `--user` flag is then not needed.

To uninstall:

```bash
pip uninstall mcpyrate
```

but first, make sure you're not in a folder that has an `mcpyrate` subfolder - `pip` will think it got a folder name instead of a package name, and become confused.


## Understanding the implementation

We follow the `mcpy` philosophy that macro expanders aren't rocket science. See [`CONTRIBUTING.md`](CONTRIBUTING.md).


## Why macros?

Despite their [fearsome](http://www.greghendershott.com/fear-of-macros/) reputation, [syntactic](https://en.wikipedia.org/wiki/Macro_(computer_science)#Syntactic_macros) macros are a clean solution to certain classes of problems. Main use cases of macros fall into a few (not necessarily completely orthogonal) categories:

  1. **Syntactic abstraction**, to extract a pattern that cannot be extracted as a regular run-time function. Regular function definitions are a tool for extracting certain kinds of patterns; macros are another such tool. Both these tools aim at eliminating boilerplate, by allowing the definition of reusable abstractions.

     [Macros can replace design patterns](http://wiki.c2.com/?AreDesignPatternsMissingLanguageFeatures), especially patterns that work around a language's limitations. See Norvig's [classic presentation on design patterns](https://norvig.com/design-patterns/ppframe.htm). For a concrete example, see [Seibel](http://www.gigamonkeys.com/book/practical-building-a-unit-test-framework.html).

  2. **Source code access**. Any operation that needs to get a copy of the source code of an expression (or of a code block) as well as run that same code is a prime candidate for a macro. This is useful for implementing tooling for e.g. debug-logging and testing.

  3. **Evaluation order manipulation**. By editing code, macros can change the order in which it gets evaluated, as well as decide whether a particular expression or statement runs at all.

     As an example, macros allow properly abstracting [`delay`/`force`](https://docs.racket-lang.org/reference/Delayed_Evaluation.html) in a [strict](https://en.wikipedia.org/wiki/Evaluation_strategy#Strict_evaluation) language. `force` is just a regular function, but `delay` needs to be a macro.

  4. **Language-level features** inspired by other programming languages. For example, [`unpythonic`](https://github.com/Technologicat/unpythonic) provides expression-local variables (`let`), automatic tail call optimization (TCO), autocurry, lazy functions, and multi-shot continuations.

     As [the Racket guide notes](https://docs.racket-lang.org/guide/pattern-macros.html), this is especially convenient for language-level features not approved by some other language designer. Macros allow users to [extend](https://docs.racket-lang.org/guide/languages.html) the language. [Dialects](doc/dialects.md) take that idea one step further.

  5. **[Embedded domain-specific languages (eDSLs)](https://en.wikipedia.org/wiki/Domain-specific_language#External_and_Embedded_Domain_Specific_Languages)**.

     Here *embedded* means the DSL seamlessly integrates into the surrounding programming language (the host language). With embedded DSLs, there is no need to implement a whole new parser for the DSL, and many operations can be borrowed from the host language.

     This approach significantly decreases the effort needed to implement a DSL, thus making small DSLs an attractive solution for a class of design problems. A language construction kit [can be much more useful](https://beautifulracket.com/appendix/why-racket-why-lisp.html#a_pwJR1) than how it may sound at first.

  6. **[Mobile code](https://macropy3.readthedocs.io/en/latest/discussion.html#mobile-code)**, as pioneered by `macropy`. Shuttle code between domains, while still allowing it to be written together in a single code base.

That said, [*macros are the 'nuclear option' of software development*](https://www.factual.com/blog/thinking-in-clojure-for-java-programmers-part-2/). Often a good strategy is to implement as much as regular functions as reasonably possible, and then a small macro on top, for the parts that would not be possible (or overly verbose, or overly complex, or just overly hacky) otherwise. [Our delayed evaluation demo](demo/promise.py) is a small example of this strategy.

More extensive examples are the macro-enabled test framework [`unpythonic.test.fixtures`](https://github.com/Technologicat/unpythonic/blob/master/doc/macros.md#testing-and-debugging), and the [`let` constructs in `unpythonic.syntax`](https://github.com/Technologicat/unpythonic/blob/master/doc/macros.md#bindings) (though in that case the macros are rather complex, to integrate with Python's lexical scoping). If curious about the *"overly hacky"* remark, compare the implementations of [`unpythonic.amb`](https://github.com/Technologicat/unpythonic/blob/master/unpythonic/amb.py) and [`unpythonic.syntax.forall`](https://github.com/Technologicat/unpythonic/blob/master/unpythonic/syntax/forall.py) - the macro version is much cleaner.

For examples of borrowing language features, look at [Graham](http://paulgraham.com/onlisp.html), [Python's `with` in Clojure](http://eigenhombre.com/macro-writing-macros.html), [`unpythonic.syntax`](https://github.com/Technologicat/unpythonic/blob/master/doc/macros.md), and these creations from the Racket community [[1]](https://lexi-lambda.github.io/blog/2017/08/12/user-programmable-infix-operators-in-racket/) [[2]](https://lexi-lambda.github.io/blog/2015/12/21/adts-in-typed-racket-with-macros/) [[3]](https://github.com/tonyg/racket-monad). But observe also that macros are not always needed for this: [pattern matching](https://github.com/santinic/pampy), [resumable exceptions](https://github.com/Technologicat/unpythonic/blob/master/doc/features.md#handlers-restarts-conditions-and-restarts), multiple dispatch [[1]](https://github.com/mrocklin/multipledispatch) [[2]](https://github.com/Technologicat/unpythonic/blob/master/doc/features.md#generic-typed-isoftype-multiple-dispatch).
