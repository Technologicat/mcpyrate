# Contributing to `mcpyrate`

Code and/or documentation contributions are welcome!

The preferred mechanism is a pull request on GitHub. [New to GitHub?](http://makeapullrequest.com/)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Contributing to `mcpyrate`](#contributing-to-mcpyrate)
    - [Understanding the code](#understanding-the-code)
    - [Code style](#code-style)
    - [Docstring and comment style](#docstring-and-comment-style)

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
       - But we don't want to bump from version `X.Y` to `(X+1).0` just because some names need changing for clarity.
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
