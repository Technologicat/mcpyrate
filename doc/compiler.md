**Navigation**

- [Main user manual](main.md)
- [Quasiquotes and `mcpyrate.metatools`](quasiquotes.md)
- [REPL and `macropython`](repl.md)
- **The `mcpyrate` compiler**
- [AST walkers](walkers.md)
- [Dialects](dialects.md)
- [Troubleshooting](troubleshooting.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [The import algorithm](#the-import-algorithm)
- [Multi-phase compilation](#multi-phase-compilation)
    - [Displaying the source code for each phase](#displaying-the-source-code-for-each-phase)
    - [The phase level countdown](#the-phase-level-countdown)
    - [Notes](#notes)
- [Invoking the compiler at run time](#invoking-the-compiler-at-run-time)
    - [Overview](#overview)
    - [Modules and the compiler](#modules-and-the-compiler)
    - [Roles of the compiler functions](#roles-of-the-compiler-functions)
        - [`expand`](#expand)
        - [`compile`](#compile)
        - [`run`](#run)

<!-- markdown-toc end -->


# The import algorithm

When a module is imported with `mcpyrate` enabled, the importer calls the `mcpyrate` compiler. Here's what the compiler does to the source code:

 1. Decode the content of the `.py` source file into a unicode string (i.e. `str`).
    - Character encoding is detected the same way Python itself does. That is, the importer reads the magic comment at the top of the source file (such as `# -*- coding: utf-8; -*-`), and assumes `utf-8` if this magic comment is not present.
 2. Apply [dialect](dialects.md) **source** transformers to the source text.
 3. Parse the source text into a (macro-enabled) Python AST, using `ast.parse`.
 4. Detect the number of [phases](#multi-phase-compilation) by scanning the top level of the module body AST.
    - If the AST does **not** request multi-phase compilation, there is just one phase, namely phase `0`.
 5. Extract the AST for the highest-numbered remaining phase. Then, for the extracted AST:
    1. Apply dialect **AST** transformers.
    2. Apply the macro expander.
    3. Apply dialect **AST postprocessors**.
 6. If the phase that was just compiled was not phase `0`, reify the current temporary module into `sys.modules`, and jump back to step 5.
 7. Restore the original state of `sys.modules`.
    - The temporary module is deleted from `sys.modules`.
    - If there was an entry for this module in `sys.modules` before we began multi-phase-compiling this module, reinstate that entry. (There usually is; Python's import system creates the module object and injects it into `sys.modules` before calling the loader's `source_to_code` method. It then execs the obtained code in that module object's namespace.)
 8. Apply the builtin `compile` function to the resulting AST. Hand the result over to Python's standard import system.

**CAUTION**: As of `mcpyrate` 3.0.0, *code injected by dialect AST transformers cannot itself use multi-phase compilation*. The client code can; just the dialect code template AST cannot.

In practice this is not a major limitation. If the code injected by your dialect definition needs macros, just define them somewhere outside that injected code, and make the injected code import them in the usual way. The macros can even live in the module that provides the dialect definition, and that module can also use multi-phase compilation if you want; the only place the macros can't be defined in is the code template itself.


# Multi-phase compilation

*Multi-phase compilation*, a.k.a. *staging*, allows to use macros in the
same module where they are defined. In `mcpyrate`, this is achieved with the
`with phase` syntactic construct. To tell `mcpyrate` to enable the multi-phase
compiler for your module, add the following macro-import somewhere in the top
level of the module body:

```python
from mcpyrate.multiphase import macros, phase
```

Actually `with phase` is a feature of `mcpyrate`'s importer, not really a
regular macro, but its docstring must live somewhere, and it's nice if `flake8`
is happy. This macro-import mainly acts as a flag for the importer, but it does
also import a dummy macro that will trigger a syntax error if the `with phase`
construct is used improperly (i.e. in a position where it is not compiled away
by the importer, and slips through to the macro expander).

When multi-phase compilation is enabled, use the `with phase[n]` syntactic
construct to define which parts of your module should be compiled before which
other ones. The phase number `n` must be a positive integer literal.

**Phases count down**, run time is phase `0`. For any `k >= 0`, the run time of
phase `k + 1` is the macro-expansion time of phase `k`. Phase `0` is defined
implicitly. All code that is **not** inside any `with phase` block belongs to
phase `0`.

```python
# application.py
from mcpyrate.multiphase import macros, phase

with phase[1]:
    # macro definitions here

# everything not inside a `with phase` is implicitly phase 0

# use the magic module name __self__ to import macros from a higher phase of the same module
from __self__ import macros, ...

# then just code as usual
```

To run, `macropython application.py` or `macropython -m application`. For a full example, see [`demo/multiphase_demo.py`](../demo/multiphase_demo.py).

The `with phase` construct may only appear at the top level of the module body.
Appearing anywhere else, it is a syntax error. It is a block macro only; using
any other invocation type for it is a syntax error. It is basically just data
for the importer that is compiled away before the macro expander runs. Thus,
macros cannot inject `with phase` invocations.

Multiple `with phase` blocks with the same phase number **are** allowed; the code
from each of them is considered part of that phase.

The syntax `from __self__ import macros, ...` is a *self-macro-import*, which
imports macros from any higher-numbered phase of the same module it appears in.
Self-macro-imports vanish during macro expansion (leaving just a [coverage dummy
node](#why-do-my-block-and-decorator-macros-generate-extra-do-nothing-nodes)),
because a module does not need to really import itself. This is just the closest
possible adaptation of the traditional macropythonic syntax to register macro
bindings, when the macros come from the same module. The `__self__` as a module
name in a from-import just tells `mcpyrate`'s importer that we want to refer to
*this module*, whatever its absolute dotted name happens to be; there is no
run-time object named `__self__`.

If you need to write helper macros to define your phase 1 macros, you can define
them in phase 2 (and so on):

```python
from mcpyrate.multiphase import macros, phase

with phase[2]:
    # define macros used by phase 1 here

with phase[1]:
    # macro-imports (also self-macro-imports) may appear
    # at the top level of a `with phase`.
    from __self__ import macros, ...

    # define macros used by phase 0 here

# everything not inside a `with phase` is implicitly phase 0

# you can import macros from any higher phase, not just phase 1
from __self__ import macros, ...

# then just code as usual
```

Macro-imports must usually appear at the top level of the module body. Doing
that in a module that uses multi-phase compilation causes the macros to be
imported at phase `0`. If you need to import some macros earlier, it is allowed
to place macro-imports at the top level of the body of a `with phase[n]`. This
will make those macros available at phase `n` and at any later (lower-numbered)
phases, including at the implicit phase `0`.

Finally, there is an implicit magic variable in the module's top-level scope,
`__phase__`, which contains the number of the current compilation phase, as an
integer. This can be useful if you want to include a certain piece of code in
all phases, but do different things in different phases (or skip doing something
until a certain phase is reached). The `__phase__` magic variable is only present
if the module enables the multi-phase compiler.


## Displaying the source code for each phase

To display the unparsed source code for the AST of each phase before macro
expansion, you can enable the multi-phase compiler's debug mode, with this
additional macro-import (somewhere in the top level of the module body):

```python
from mcpyrate.debug import macros, step_phases
```

This allows to easily see whether the definition of each phase looks the way
you intended.

Similarly to `with phase`, `step_phases` is not really a macro at all; the
presence of that macro-import acts as a flag for the multi-phase compiler.
Trying to actually use the imported `step_phases` macro is considered
a syntax error. (It's a `@namemacro`, so even accessing the bare name
will trigger the syntax error.)

The macro expansion itself will **not** be stepped; this debug tool is
orthogonal to that. For that, use the `step_expansion` macro, as usual.

There is a limitation, to keep the implementation reasonably simple: because
`with_phase` must appear at the top level of the module body, it is not
conveniently possible to `with step_expansion` across multiple phase
definitions.

You must macro-import `step_expansion` inside the earliest (highest-number)
phase where you need it, and then `with step_expansion` separately inside each
`with phase` whose expansion you want to step. Be careful to leave the phase's
macro-imports, if any, *outside* the `with step_expansion`. The debug mode of
the multi-phase compiler does **not** need to be enabled to use `step_expansion`
like this.


## The phase level countdown

Phases higher than `0` only exist during module initialization, locally for each
module. Once a module finishes importing, it has reached phase `0`, and that's
all that the rest of the program sees. This means that another module that wants
to import macros from `mymodule` doesn't need to care which phase the macros
were defined in `mymodule.py`. The macros will be present in the final phase-`0`
module. Phase is important only for invoking those macros inside `mymodule` itself.

During module initialization, for `k >= 1`, each phase `k` is reified into a
temporary module, placed in `sys.modules`, with **the same absolute dotted name**
as the final one. This allows the next phase to import macros from it, using the
self-macro-import syntax.

When the macro expander and bytecode compiler are done with phase `k`, that
phase is reified, completely overwriting the module from phase `k + 1`.

All code from phase `k + 1` is automatically lifted into the code for phase `k`.
Phase `k` then lifts it to phase `k - 1`, and the chain continues all the way
down to the implicit phase `0`. So `with phase[n]` actually means that code is
present *starting from phase `n`*.

Once phase `0` has been macro-expanded, the temporary module is removed from
`sys.modules`. The resulting final phase-`0` module is handed over to Python's
import machinery. Thus Python will perform any remaining steps of module
initialization, such as placing the final module into `sys.modules`. (We don't
do it manually, because the machinery may need to do something else, too, and
the absence from `sys.modules` may act as a trigger.)

The **ordering** of the `with phase` code blocks **is preserved**. The code will
always execute at the point where it appears in the source file. Like a receding
tide, each phase will reveal increasing subsets of the original source file,
until (at the implicit phase `0`) all of the file is processed.

**Mutable state**, if any, **is not preserved** between phases, because each phase
starts as a new module instance. There is no way to transmit information to a
future phase, except by encoding it in macro output (so it becomes part of the
next phase's AST, before that phase reaches run time).

Phases are mainly a convenience feature to allow using macros defined in the
same module, but if your use case requires to transmit information to a future
phase, you could define a `@namemacro` that expands into an AST for the data you
want to transmit. (Then maybe use `q[u[...]]` in its implementation, to generate
the expansion easily.)


## Notes

Multi-phase compilation is applied interleaved with dialect AST transformers,
so that modules that need multi-phase compilation can be written using a dialect.
For details, see [`mcpyrate`'s import algorithm](compiler.md#the-import-algorithm).

In the REPL, explicit multi-phase compilation is neither needed nor supported.
Conceptually, just consider the most recent state of the REPL (i.e. its state
after the last completed REPL input) as the content of *the previous phase*.
You can `from __self__ import macros, ...` in the REPL, and it'll just work.
There's also a REPL-only shorthand to declare a function as a macro, namely
the `@macro` decorator.

Multi-phase compilation was inspired by Racket's [phase level
tower](https://docs.racket-lang.org/guide/phases.html), but is much simpler.
Racketeers should observe that in `mcpyrate`, phase separation is not strict.
Code from **all** phases will be available in the final phase-`0` module. Also,
due to the automatic code lifting, it is not possible to have different definitions
for the same name in different phases; the original definition will "cascade down"
via the lifting process, at the point in the source file where it appears.

This makes `mcpyrate`'s phase level into a module initialization detail,
local to each module. Other modules don't need to care at which phase a thing was
defined when they import that thing - for them, all definitions exist at phase `0`.

This is a design decision; it's more pythonic that macros don't "disappear" from
the final module just because they were defined in a higher phase. The resulting
system is simple, and `with phase` affects Python's usual scoping rules as
little as possible. This is a minimal extension of the Python language, to make
it possible to use macros in the same source file where they are defined.


# Invoking the compiler at run time

*Added in v3.1.0.*

The `mcpyrate` compiler, which implements [the import algorithm](#the-import-algorithm), is exposed for run-time use, in the module `mcpyrate.compiler`. With it, one can compile and run macro-enabled quoted code snippets (or source code) at run time. This is particularly useful for testing macros that are best tested via the *behavior* of the expanded code they output (in contrast to the *shape* of that code, as an AST).

(This and quasiquotes also make macro-enabled Python into a poor man's staged language  [[1]](https://www.researchgate.net/publication/221024597_A_Gentle_Introduction_to_Multi-stage_Programming) [[2]](https://cs.stackexchange.com/questions/2869/what-are-staged-functions-conceptually), so this may also be useful if you wish to experiment with such ideas in Python.)

You can `expand`, expand-and-`compile`, or expand-compile-and-`run` macro-enabled code snippets at run time, as desired. For details, see the docstrings of those functions, as well as the function `create_module`, in the module [`mcpyrate.compiler`](../mcpyrate/compiler.py). Usage examples, including advanced usage, can be found in [`mcpyrate.test.test_compiler`](../mcpyrate/test/test_compiler.py).


## Overview

The `mcpyrate` compiler always executes code in the context of a module. Here *module* is meant in the sense of the type of thing that lives in `sys.modules`. This differs from the builtin `exec`, which uses a bare dictionary as the namespace for the globals. The reason for this design choice is that by always using a module, we unify the treatment of code imported from `.py` source files and code dynamically created at run time.

A code snippet can be executed in a new module, dynamically created at run time, or in the namespace of an existing module. These features combine, so you can let `mcpyrate.compiler.run` automatically create a module the first time, and then re-use that module if you want.

It is also possible to create a module with a specific dotted name in `sys.modules`. (The multi-phase compiler itself uses this feature.)

With **source code input** (i.e. text), the compiler supports **dialects, macros, and multi-phase compilation**. The top level of the source code represents the top level of a module, just as if that code was read from the top level of a `.py` source file.

With **quasiquoted AST input**, the compiler supports **macros and multi-phase compilation**. No source transforms are possible for this kind of input, because the input is already a (macro-enabled) Python AST. The top level of the quoted block (i.e. the body of a `with q as quoted:`) is seen by the compiler as the top level of a module, just as if that quoted code was read from the top level of a `.py` source file.

In a quasiquoted AST input, dialect **AST** transformers and postprocessors should work as usual. If you import a dialect at the top level of the quasiquoted code snippet, the dialect's AST transformer and AST postprocessor will run, but the source transformer will be skipped.

For both input types, having the top level treated as the top level of a module has exactly the expected implication: any `mcpyrate` features that are only available at the top level of a module, such as macro-imports, and the `with phase` construct for multi-phase compilation, **do actually work** at the top level of any code snippet that you send to the compiler using the run-time access facilities in `mcpyrate.compiler`.

While a code snippet is running, its module's `__file__` and `__name__` are available, as usual. Please be aware that the values will generally differ from those of the actual file that contains the quasiquoted source code block, because the binding between the code snippet and the module only exists dynamically (when you call `mcpyrate.compiler.run`).

In order to extract values into the surrounding context, you can simply assign the data to top-level variables inside the code snippet. The top level of the code snippet is the module's top level. That module object is available in the surrounding context (where you call `mcpyrate.compiler.run`), so you can access those variables as the module object's attributes.

Examples can be found in [`mcpyrate.test.test_compiler`](../mcpyrate/test/test_compiler.py).


## Modules and the compiler

There are two different things that in Python, are termed a *module*:

 1. `ast.Module`, one of the three top-level AST node types in Python. This kind of top-level node is produced by `ast.parse(..., mode="exec")`. It represents a sequence of statements.
 2. `types.ModuleType`, the type of thing that lives in `sys.modules`. Usually represents the top-level scope of a `.py` file, and has some magic attributes (e.g. `__name__` and `__file__`) automatically set by the importer.
 
The common factor between the two senses of the word is that a `.py` file essentially consists of a sequence of statements.

`mcpyrate` stirs this picture up a bit. We always parse in `"exec"` mode, so we always have a module (sense 1). But also, because macro bindings are established by macro-imports, the principle of least astonishment requires that macros are looked up in a module (sense 2) - and that module must be (or at least will have to become) available in `sys.modules`.

What this means in practice is that in `mcpyrate`, to run a code snippet generated at run time, there has to be a module to run the code in. The function `mcpyrate.compiler.run` will auto-create one for you if needed, but in case you want more control, you can create a module object explicitly with `create_module`, and then pass that in to `run`. The name for the auto-created module is gensymmed; but if you use `create_module`, the provided name is used as-is.

Having the code snippet contained inside a module implies that, if you wish, you can first define one module at run time that defines some macros, and then in another run-time code snippet, import those macros from that dynamically generated module. Just use `create_module` to create the first module, to give it a known dotted name in `sys.modules`:

```python
from mcpyrate.quotes import macros, q
from mcpyrate.compiler import create_module, run

mymacros = create_module("mymacros")
with q as quoted:
    ...
run(quoted, mymacros)

with q as quoted:
    from mymacros import macros, ...
    ...
module = run(quoted)
```

This may, however, lead to module name collisions. The proper solution is to manually gensym a custom name for the module, as shown below. Since the module name in an import statement must be literal, you'll then have to edit the second code snippet after it was generated (if you generated it via quasiquotes) to splice in the correct name for the first module to import the macros from:

```python
from mcpyrate.quotes import macros, q
from mcpyrate import gensym
from mcpyrate.compiler import create_module, run
from mcpyrate.utils import rename

modname = gensym("mymacros")
mymacros = create_module(modname)
with q as quoted:
    ...
run(quoted, mymacros)

with q as quoted:
    from _xxx_ import macros, ...
    ...
rename("_xxx_", modname, quoted)
module = run(quoted)
```


## Roles of the compiler functions

To begin with: **`run` and maybe also `create_module` are what you want 99% of the time.** For the remaining 1%, see `expand` and `compile`. In this section, we will explain all four functions.

For clarity of exposition, let us start by considering the **standard Python compilation workflow** (no macros):

```
┌──────────┐   ┌─────┐   ┌─────────────────┐ 
│  source  │ → │ AST │ → │ Python bytecode │ 
└──────────┘   └─────┘   └─────────────────┘ 
```

The Python language comes with the builtins `compile`, `exec` and `eval`, and the standard library provides `ast.parse`. The difference between `exec` and `eval` is the context; `exec` executes statements, whereas `eval` evaluates an expression. Because the `mcpyrate` compiler mainly deals with complete modules, and always uses `ast.parse` in `exec` mode, in this document we will not consider `eval` further.

The standard functions `parse`, `compile` and `exec` hook into the standard workflow as follows:

```
┌──────────┐   ┌─────┐   ┌─────────────────┐ 
│  source  │ → │ AST │ → │ Python bytecode │ 
└──────────┘   └─────┘   └─────────────────┘ 

   parse   ───────┤

   compile ──────────────────────┤
               compile ──────────┤

   exec    ─────────────────────────────...  <run-time execution>
               exec    ─────────────────...  <run-time execution>
                                exec ───...  <run-time execution>
```

In the diagram, time flows from left to right. The function name appears below each box that represents a valid input type. The stop marker `┤` indicates the output of the function. The `exec` function does not have a meaningful return value; instead, it executes its input.

Adding a macro expander inserts one more step. In `mcpyrate`, the **macro-enabled Python compilation workflow** is:

```
┌──────────┐   ┌───────────────────┐   ┌──────────────┐   ┌─────────────────┐ 
│  source  │ → │ macro-enabled AST │ → │ expanded AST │ → │ Python bytecode │ 
└──────────┘   └───────────────────┘   └──────────────┘   └─────────────────┘ 
```

The module `mcpyrate.compiler` exports four important public functions: `expand`, `compile`, `run`, and `create_module`. The last one is a utility that will be explained further below. The first three functions - namely `expand`, `compile`, and `run` - hook into the macro-enabled compilation workflow as follows:

```
┌──────────┐   ┌───────────────────┐   ┌──────────────┐   ┌─────────────────┐ 
│  source  │ → │ macro-enabled AST │ → │ expanded AST │ → │ Python bytecode │ 
└──────────┘   └───────────────────┘   └──────────────┘   └─────────────────┘ 

   expand  ───────────────────────────────────┤
                       expand  ───────────────┤

   compile ───────────────────────────────────────────────────────┤
                       compile ───────────────────────────────────┤
                                           compile ───────────────┤

   run     ──────────────────────────────────────────────────────────────...  <run-time execution>
                       run     ──────────────────────────────────────────...  <run-time execution>
                                           run     ──────────────────────...  <run-time execution>
                                                                 run ────...  <run-time execution>
```


### `expand`

The `expand` function can be thought of as a macro-enabled `parse`, but with support also for dialects and multi-phase compilation. The return value is an expanded AST. Observe that because dialects may define source transformers, the input might not be meaningful for `ast.parse` until after all dialect source transformations have completed. Only at that point, `expand` calls `ast.parse` to produce the macro-enabled AST.

Interaction between the compiler features - multi-phase compilation, dialects, and macros - makes the exact `expand` algorithm unwieldy to describe in a few sentences. The big picture is that then the [phase level countdown](#the-phase-level-countdown), [dialect AST transformations](dialects.md#ast-transformers), macro expansion, and [dialect AST postprocessors](dialects.md#ast-postprocessors), are interleaved in a very particular way to produce the expanded AST, which is the output of `expand`.

For some more detail, see [the import algorithm](#the-import-algorithm) and [multi-phase compilation](#multi-phase-compilation); with the difference that unlike the importer, `expand` does not call the built-in `compile` on the result. For the really nitty, gritty details, the definitive reference is the compiler source code itself; see [mcpyrate/compiler.py](../mcpyrate/compiler.py) and [mcpyrate/multiphase.py](../mcpyrate/multiphase.py). (As of version 3.1.0, these files make up about 1000 lines in total.)


### `compile`

The `compile` function first calls `expand`, and then proceeds to compile the result into Python bytecode. Important differences to the builtin `compile` are that `mcpyrate` always parses in `"exec"` mode, `dont_inherit` is always `True`, and flags (to the built-in `compile`) are not supported. The return value is a code object (representing Python bytecode).

**For dynamically generated AST input, `compile` triggers line number generation.** If you just `expand` your dynamically generated AST, semantically that means you might still want to perform further transformations on it later. However, `compile` means that it's final, so it's safe to populate line numbers.

As of `mcpyrate` 3.1.0, if the input to `compile` is an AST that did not come directly from a `.py` source file (i.e. it is a dynamically generated AST), it will be unparsed and re-parsed (before calling `expand`) to autogenerate the source location info. This is the most convenient way to do it, because in the standard compilation workflow, `ast.parse` is the step that produces the line numbers.

So strictly speaking, also in `mcpyrate` it is `ast.parse` that actually produces the line numbers. But because it only does that for source code input (not ASTs), then, to enable its line number generator, our `compile` temporarily converts the AST back into source code.

If you need to examine the source code corresponding to your dynamically generated AST (e.g. with regard to a stack trace), note that the autogenerated line numbers correspond to `unparse(tree)`, with no options. This snippet (where `tree` is the AST) will show them:

```python
from mcpyrate import unparse
for lineno, code in enumerate(unparse(tree).split("\n"), start=1):
    print(f"L{lineno:5d} {code}")
```


### `run`

The `run` function calls `compile`, and then executes the resulting bytecode in a module's `__dict__`. The return value is the module object, after the code has been executed in its `__dict__`.

If a module object (as in the values that live in `sys.modules`) or a dotted module name (as in the keys of `sys.modules`) was provided, that module is used.

If no module was specified, a new module with a gensymmed name is automatically created and placed into `sys.modules`. This is done by automatically calling the fourth exported function, `create_module`, with no arguments.

There is one further important detail concerning module docstring processing.

When the input to `run` is not yet compiled (i.e. is source code, a macro-enabled AST, or an expanded AST), and the first statement in it is a static string (i.e. no f-strings or string arithmetic), this string is assigned to the docstring (i.e. the `__doc__` attribute) of the module ([sense 2, above](#modules-and-the-compiler)) the code runs in. Otherwise the module docstring is set to `None`.

The docstring extraction is performed as part of compilation by using an internal function named `_compile` (as of version 3.1.0). Thus, calling `run` on a not-yet-compiled input does **not** have exactly the same effect as first calling `compile`, and then `run` on the bytecode result.

**Therefore, prefer directly using `run` when possible**, so that `mcpyrate` will auto-assign the module docstring. This ensures that if your dynamically generated code happens to begin with a module docstring, the docstring will Just Work™ as expected.
