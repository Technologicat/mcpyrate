# Contributing to `mcpyrate`

Code and/or documentation contributions are welcome!

This document is intended to benefit anyone who wishes to understand the `mcpyrate` codebase and/or documentation better, and/or contribute to the project. We believe the possibility to do so should be available to professional developers, hobby developers, academic researchers (particularly in fields other than [CS](https://en.wikipedia.org/wiki/Computer_science)), and students alike.

The preferred contribution mechanism is a pull request on GitHub. [New to GitHub?](http://makeapullrequest.com/)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Contributing to `mcpyrate`](#contributing-to-mcpyrate)
    - [Understanding the code](#understanding-the-code)
    - [Code style](#code-style)
    - [Docstring and comment style](#docstring-and-comment-style)
    - [Automated tests](#automated-tests)
        - [Layout](#layout)
        - [Why in-tree testing matters](#why-in-tree-testing-matters)
        - [Why other forms of testing matter too](#why-other-forms-of-testing-matter-too)

<!-- markdown-toc end -->


## Understanding the code

We follow the `mcpy` philosophy that macro expanders aren't rocket science. We keep things as explicit and compact as reasonably possible. However, the extra features do cost some codebase size. We also tolerate a small amount of extra complexity, if it improves the programmer [UX](https://en.wikipedia.org/wiki/User_experience).

For a clean overview of the core design, look at [mcpy](https://github.com/delapuente/mcpy), version 2.0.0. Of the parts that come from it, its `visitors` is our [`core`](mcpyrate/core.py) (the `BaseMacroExpander`), its `core` is our [`expander`](mcpyrate/expander.py) (the actual `MacroExpander`), and its `import_hooks` is our [`importer`](mcpyrate/importer.py). (Its `BaseMacroExpander.ismacro` method is our `BaseMacroExpander.isbound`, because that method checks for a raw string name, not an AST structure.) The rest of the module layout should be clear.

Then see our [`importer`](mcpyrate/importer.py). After [`mcpyrate.activate`](mcpyrate/activate.py) has been imported, the importer becomes the top-level entry point whenever a module is imported.

See also [Understanding the quasiquote system](doc/quasiquotes.md#understanding-the-quasiquote-system).


## Code style

 - **Follow [PEP8](https://www.python.org/dev/peps/pep-0008/)**, but not into foolish consistency.
   - Particularly, *a blank line (or a double-blank line when appropriate) is a paragraph break*, to separate logical units. Just like when writing [prose](https://matthewbischoff.com/code-is-prose/), don't break the paragraph inside a logical unit, no matter what `flake8` tells you. This helps make the overall structure explicit and easy to see at a glance.
   - Tools like [black](https://github.com/psf/black) are not really appropriate here; a macro expander is as far from an everyday Python project as, say, [a language extension](https://github.com/Technologicat/unpythonic) is. Prefer to imitate the existing style.

   - Modules vendored from other open-source projects are exempt from code style.
     - This makes them trivial to update, as well as compare to the original version.
     - As of 3.0.0, we have `ansi.py` from [`colorama`](https://github.com/tartley/colorama).

 - **Follow [the Zen of Python](https://www.python.org/dev/peps/pep-0020/)**. Particularly, simple and explicit is often preferable.

 - **Use [semantic versioning](https://semver.org/)**.

 - **Export explicitly.**
   - Any names intended as exports **must** be present in the magic [`__all__`](https://docs.python.org/3/tutorial/modules.html#importing-from-a-package). Although not everyone uses it, this is the official mechanism to declare a module's public API, [recommended by PEP8](https://www.python.org/dev/peps/pep-0008/#public-and-internal-interfaces).
   - We don't currently use this for re-export, but it means we could `from .somemodule import *` in the top-level `__init__.py` to automatically pull in the public API, and *only* the public API of `somemodule`.

 - **Prefer small modules**, each with a clearly defined area of responsibility.
   - Keep code short, but clear.
     - No [golf](https://en.wikipedia.org/wiki/Code_golf).
     - Sometimes a small amount of repetition is harmless, vs. the learning cost of one more abstraction.
   - Each source file should be less than ≈700 lines. That's a lot of Python.
       - Going 10%-ish over the length limit is fine. But no 10k [SLOC](https://en.wikipedia.org/wiki/Source_lines_of_code) source files like often seen in Emacs plugins.
       - If you're doing **simple but tedious things**, exceeding the limit by more than 10% may be fine.
         - `unparser.py` is almost 1000 lines, simply because Python's grammar is so huge. The implementation is pretty much a laundry list of simple instructions for each AST node type. It's clearer if it's all in the same module.
       - If you're doing **complex things**, stick to the limit, and prepare to comment more than usual.
         - *"First, we want to establish the idea that a computer language is not just a way of getting a computer to perform operations but rather that it is a novel formal medium for expressing ideas about methodology. Thus, programs must be written for people to read, and only incidentally for machines to execute. "* --[Abelson, Sussman & Sussman](https://mitpress.mit.edu/sites/default/files/sicp/full-text/book/book.html)
         - `quotes.py` is ≈300 lines of code, ≈500 lines of explanation, to save research and detective work. That's fine.
       - If you're doing a **number of related small things**, place them in the same module. (Python isn't MATLAB.)
         - For example, utility functions; the area of responsibility can then be the category of use cases for that collection of utilities. We have `utils.py` for general use, and `coreutils.py` for things only macro expanders need.
           - If you ever find the need for a `moreutils.py` due to the length limit, consider if there's a category of use cases that could be split off. If not, just keep extending `utils.py`.

 - **Name clearly.**
   - *"There are only two hard things in Computer Science: cache invalidation and naming things."* --[Phil Karlton](https://martinfowler.com/bliki/TwoHardThings.html)
   - Get the code working first. Then think of how to best name and organize things to convey your meaning, and aggressively rename (and possibly move to a different module) anything that hasn't hit a published release yet. Maybe several times, until the result is satisfactory.
     - Really, **anything**: named parameters of functions, functions, classes, modules, even packages.
     - Try to get the names right before publishing a release. This is important.
       - Not getting the names right and then keeping them gave us Common Lisp. `terpri`? `flet`? `letf`? `labels`?
       - But we don't want to bump from version `X.Y` to `(X+1).0` just because some names needed changing for clarity.
   - Avoid reusing the name of a module for a thing inside that module. Hence e.g. `unparser`, which provides `unparse`.
     - [Nick Coghlan: Traps for the Unwary in Python's Import System](http://python-notes.curiousefficiency.org/en/latest/python_concepts/import_traps.html#the-submodules-are-added-to-the-package-namespace-trap)

 - For strings, prefer double quotes.
   - Docstrings should use the triple double quote.

 - When *defining* functions, consider using keyword-only parameters.
   - Remembering argument ordering is *really, really hard*. Avoid the need.
   - Usually we have just one positional parameter (beside `self`, if any), sometimes two.

 - When *calling* functions, pass arguments by name when it improves clarity.


## Docstring and comment style

 - Prefer 80-ish columns; going 10% or so over is ok.
   - Prefer to break the limit, if that allows a much better paragraph fill.

 - No need for full-blown `rst` formatting.

 - Feel free to use plain-text `**bold**` and `*emphasis*`.
   - The preferred wording to describe a usage pitfall is `**CAUTION**: ...`

 - Quote any inline code with backticks: `` `zorblify` is a callable that...``.

 - Indent display-style code snippets. Use a double colon to begin the indented block, like in [`rst`](https://docutils.sourceforge.io/docs/user/rst/quickstart.html):
   ```python
   """Do stuff.

   Example::

       c = dostuff(a, b)
   """
   ```

 - Avoid bureaucracy.
   - Don't repeat the function signature in the docstring.
     - But do mention the return value (type, and what the value means).
   - No need for section headers such as `Parameters:`.
     - Just describe the parameters. Or even omit if blindingly obvious.
   - Write as briefly as reasonably possible. But try not to leave out anything important.

 - When there is a conflict between the two, prefer surgical clarity of expression over conventional usage of English.
   - Use unambiguous wording, even if that makes a sentence a bit longer. Optimally, no sentence can be misinterpreted.
   - Be precise. To define a term, choose a word (or phrase) once, and then use it consistently.
     - E.g. functions have *parameters*, which are filled with *arguments* at call time. (This is PEP8 usage.)
     - Repetitive use of the same word (or phrase) is a non-issue, but lack of precision causes bugs.
   - Quotes belong around the whole quoted thing, whether or not it contains punctuation, and whether or not punctuation immediately follows the quote.
     - "`"Meow, the cat said.", said the docstring.`" is correct.

 - In headings, capitalize the first word only, as well as any proper names. Combined with font styles, this eases [scanning](https://www.teachingenglish.org.uk/article/scanning).
   - Don't capitalize a proper name that officially starts with a lowercase letter. This includes functions and their parameters.
     - Sometimes, this leads to a sentence starting in lowercase. That's ok.
     - If there's a convenient and equally clear alternative wording (which still directs the reader's attention to the important thing), feel free to use that. If not, just accept it.


## Automated tests

 - **Test what** the software should do, **not how** it does it. Avoid testing internal details.
   - Particularly with macros, consider whether you should test the *behavior* of the outputted code, or its *form* as an expanded AST.
   - In some advanced cases, to facilitate tests for behavior, [invoking the compiler at run time](doc/compiler.md#invoking-the-compiler-at-run-time) may help. See [`mcpyrate.test.test_compiler`](../mcpyrate/test/test_compiler.py) and [`mcpyrate.test.test_quotes`](../mcpyrate/test/test_quotes.py) for examples.

 - Aim at clarity. Don't worry too much if you have to make the tests a little [DAMP](https://stackoverflow.com/questions/6453235/what-does-damp-not-dry-mean-when-talking-about-unit-tests).
   - That is, prefer *Descriptive And Meaningful Phrases* over maximal elimination of repetition, because [DRY](https://en.wikipedia.org/wiki/Don't_repeat_yourself) tends to introduce a learning cost. Some repetition is fine, if it lets you omit defining an abstraction that's only needed for those particular tests.
   - But that's not a hard rule, either. For example, if you can fit both the definition and all its uses onto the screen at once, and the result is both shorter and more easily understandable than without making that definition, then feel free to do that.

 - Write tests that can double as usage examples.
   - This yields complete code examples that can be linked to in the user manual, with the machine-checked guarantee that if tests pass, the examples are known to run on the version that was tested.

 - Use common sense to focus test-writing effort where it matters most.
   - Don't bother testing trivial things. For example, a test checking that a constructor assigns the instance attributes correctly is most often a symptom of [*testing like the TSA*](https://signalvnoise.com/posts/3159-testing-like-the-tsa), and causes [software ossification](https://news.ycombinator.com/item?id=19241283).
   - Test nontrivial implementations, and particularly their interactions. Write tests that can double as advanced usage examples.
   - Aim at testing edge and corner cases, particularly ones that could turn up in practice. Features should be orthogonal, and when not reasonably possible, they should interact sensibly (or alternatively, error out with a sensible message) when used together. Test that they do.


### Layout

As of 3.1.0, tests are contained inside the `mcpyrate` package, in `mcpyrate.test`, but they are not installed by `setup.py`. This goes against the commonly accepted wisdom on Python project directory layout: [Pytest's recommendations](https://docs.pytest.org/en/stable/goodpractices.html), and [IonelMC's famous blog post](https://blog.ionelmc.ro/2014/05/25/python-packaging/#the-structure).

Tests are not installed simply because a typical use site does not need them; by the time `mcpyrate` is installed, it has already been tested. As for the tests living in a subpackage, for me this hasn't mattered that much in practice. The original motivation was to be able to change the project name easily during early development (using only relative imports), but that's moot by now.

The important feature is to support some form of in-tree testing.

As of 3.1.0, the tests are placed under a `test` subpackage of the package being tested, and the test modules use relative imports. The REPL subsystem, `mcpyrate.repl`, currently has no automated tests associated with it. If added later, those should be placed in `mcpyrate.repl.test`.

Individual test modules are expected to be invoked from the project top level as `python3 -m mcpyrate.repl.macropython -m mcpyrate.test.test_somemodule`. Here the first `-m` goes to `python3`, whereas the second one goes to `macropython`. Note this explicitly invokes the in-tree `macropython`, instead of an installed copy (if any).

A future possibility is to change the project structure to use a separate test folder, and use absolute imports in the test modules. By invoking the test runner as a script from the project top level, its containing directory will end up as the topmost entry on `sys.path`, thus resolving those absolute imports as pointing to the source tree (instead of to an installed copy, if any).


### Why in-tree testing matters

Quite simply, it allows quick testing of changes to the codebase without installing it, thus speeding up the edit-run cycle.

I think a fast edit-run cycle is crucial. If this cycle is slow, it encourages the bad practice of making many unrelated changes at once, to amortize the (perceived) waiting cost at the *run* step.

By "fast", I mean that the *run* step (including compilation!) should complete in a couple of seconds at most, preferably less. Keep in mind that **one** second is [Nielsen's oft-quoted limit](https://www.nngroup.com/articles/response-times-3-important-limits/) for avoiding interruption of the thought process. In my opinion that's not too much to ask; software development does not need to be that CPU-hungry. Using available machine resources intelligently, it's perfectly achievable in many cases to invoke a relevant testset, and get the results in less than a second.

In my opinion, this level of performance should be the norm. Near-realtime feedback is crucial if the computer is to act as an [intelligence amplifier](http://www.loper-os.org/?p=8). It's all about the *kind* of conversation you can have with your ideas as you elaborate on them, down to the level of detail required to make them machine-executable. Being able to run everything in-tree facilitates, in effect, a face-to-face conversation with the computer. The powerful thing is, you don't need a fully formed idea before you present it to the computer; you can sketch, and experiment on the smallest details, and the machine will respond near-instantly. This is a particularly nice workflow for building any non-trivial design.

This is also the reason why the test modules are designed to be executable individually. There is no point in running the whole (potentially time-expensive) test suite right away, until the module being worked on passes its own unit tests. The full test suite is just the *second* step of verification.

(A variant of the *different kind of conversation* remark was originally famously made by Paul Graham, in [*On Lisp*](http://www.paulgraham.com/onlisp.html). See [relevant quotation](https://www.ics.uci.edu/~pattis/quotations.html#G).)


### Why other forms of testing matter too

The drawbacks of in-tree testing are well known:

 - The developer's machine is far from a standard pristine installation environment. There may be subtle but important differences between what the developer *thinks* they have versus what they actually *do* have; e.g. library versions may differ from the expected ones, or additional libraries may be present.
 - There is no guarantee that the package installs correctly, or at all, because the install step is not tested.
 - There is no guarantee that the installed copy runs correctly, or at all. The project folder may contain important files that are accidentally omitted from the install, or in extreme cases, even from version control.

All three can be addressed by complementing in-tree testing with some form of [CI](https://en.wikipedia.org/wiki/Continuous_integration). As of 3.1.0, `mcpyrate` does not yet have a CI workflow; however, adding one is on the long-term roadmap. See issue [#5](https://github.com/Technologicat/mcpyrate/issues/5).

The reason it's on the *long-term* roadmap is that this will first require extending the test suite toward a reasonable coverage, to avoid a false sense of security. Or in other words, the code shouldn't get an automated stamp of approval until that stamp actually means something. Also, while extending tests, we must consider which parts of the library are stable enough to justify drawing a semi-permanent interface line, because introducing tests also introduces a significant amount of ossification.
