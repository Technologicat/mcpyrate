# Changelog

**3.0.0** (in progress; updated 1 November 2020) - *Arrr!* edition:

Initial release of **`mcpyrate`**, the advanced, third-generation macro expander for Python, after the pioneering [macropy](https://github.com/lihaoyi/macropy), and the compact, pythonic [mcpy](https://github.com/delapuente/mcpy). The emphasis is on correctness, feature-completeness for serious macro-enabled work, and simplicity, in that order.

We build on `mcpy` 2.0.0, but add a lot of new features.

**New**:

- **Agile development tools**.
  - [Multi-phase compilation](README.md#multi-phase-compilation): Use macros also in the same module where they are defined.
  - Universal bootstrapper: `macropython`. Import and use macros in your main program.
  - Interactive console: `macropython -i`. Import, define and use macros in a console session.
    - Embeddable à la `code.InteractiveConsole`. See `mcpyrate.repl.console.MacroConsole`.
  - IPython extension `mcpyrate.repl.iconsole`. Import, define and use macros in an IPython session.
  - See [full documentation of the REPL system](repl.md).

- **Testing and debugging**.
  - Statement coverage is correctly reported by tools such as [`Coverage.py`](https://github.com/nedbat/coveragepy/).
  - Macro expansion errors are reported at macro expansion time, with use site traceback.
  - Debug output **with a step-by-step expansion breakdown**. See macro [`mcpyrate.debug.step_expansion`](mcpyrate/debug.py).
    - Has both expr and block modes. Use `step_expansion[...]` or `with step_expansion` as appropriate.
    - The output is **syntax-highlighted**, and **line-numbered** based on `lineno` fields from the AST.
      - Also names of macros currently bound in the expander are highlighted by `step_expansion`.
    - The invisible nodes `ast.Module` and `ast.Expr` are shown, since especially `ast.Expr` is a common trap for the unwary.
    - To step the expansion of a run-time AST value, see the macro [`mcpyrate.metatools.stepr`](mcpyrate/metatools.py).
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
  - See [full documentation of the quasiquote system](quasiquotes.md).

- **Macro arguments**.
  - Opt-in. Declare by using the [`@parametricmacro`](mcpyrate/expander.py) decorator on your macro function.
  - Use brackets to invoke, e.g. `macroname[arg0, ...][expr]`. If no args, just leave that part out, e.g. `macroname[expr]`.
  - The `macroname[arg0, ...]` syntax works in `expr`, `block` and `decorator` macro invocations in place of a bare `macroname`.
  - The named parameter `args` is a raw `list` of the macro argument ASTs. Empty if no args were sent, or if the macro function is not parametric.

- **Identifier (a.k.a. name) macros**.
  - Can be used for creating magic variables that may only appear inside specific macro invocations.
  - Opt-in. Declare by using the [`@namemacro`](mcpyrate/expander.py) decorator on your macro function.

- **Dialects, i.e. whole-module source and AST transforms**.
  - Think [Racket's](https://racket-lang.org/) `#lang`, but for Python.
  - Define languages that use Python's surface syntax, but change the semantics; or plug in a per-module transpiler that (at import time) compiles source code from some other programming language into macro-enabled Python. Also an AST [optimizer](http://compileroptimizations.com/) could be defined as a dialect. Dialects can be chained.
  - Sky's the limit, really. Until we get [`unpythonic`](https://github.com/Technologicat/unpythonic) ported to use `mcpyrate`, see [`pydialect`](https://github.com/Technologicat/pydialect) for old example dialects.
  - For documentation, see the docstrings in [`mcpyrate.dialects`](mcpyrate/dialects.py).
  - For debugging, `from mcpyrate.debug import dialects, StepExpansion`.
  - If writing a full-module AST transformer that splices the whole module into a template, see [`mcpyrate.splicing.splice_dialect`](mcpyrate/splicing.py).
  - See [full documentation of the dialect system](dialects.md).

- **Conveniences**.
  - Relative macro-imports (for code in packages), e.g. `from .other import macros, kittify`.
  - The expander automatically fixes missing `ctx` attributes (and source locations) in the AST, so you don't need to care about those in your macros.
  - Several block macros can be invoked in the same `with` (equivalent to nesting them, with leftmost outermost).
  - [AST visitor and transformer](mcpyrate/walkers.py) à la `macropy`'s `Walker`, to easily context-manage state for subtrees, and collect items across the whole walk. [Full documentation](walkers.md).
  - AST [markers](mcpyrate/markers.py) (pseudo-nodes) for communication in a set of co-operating macros (and with the expander).
  - [`gensym`](mcpyrate/utils.py) to create a fresh, unused lexical identifier.
  - [`unparse`](mcpyrate/unparser.py) to convert an AST to the corresponding source code, optionally with syntax highlighting (for terminal output).
  - [`dump`](mcpyrate/astdumper.py) to look at an AST representation directly, with (mostly) PEP8-compliant indentation, optionally with syntax highlighting (node types, field names, bare values).
