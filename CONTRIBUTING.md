# Contributing to `mcpyrate`

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Contributing to `mcpyrate`](#contributing-to-mcpyrate)
    - [Understanding the code](#understanding-the-code)
    - [Guidelines](#guidelines)

<!-- markdown-toc end -->


## Understanding the code

We follow the `mcpy` philosophy that macro expanders aren't rocket science. We keep things as explicit and compact as reasonably possible. However, the extra features do cost some codebase size. We also tolerate a small amount of extra complexity, if it improves the programmer [UX](https://en.wikipedia.org/wiki/User_experience).

For a clean overview of the core design, look at [mcpy](https://github.com/delapuente/mcpy), version 2.0.0. Of the parts that come from it, its `visitors` is our [`core`](mcpyrate/core.py) (the `BaseMacroExpander`), its `core` is our [`expander`](mcpyrate/expander.py) (the actual `MacroExpander`), and its `import_hooks` is our [`importer`](mcpyrate/importer.py). Its `BaseMacroExpander.ismacro` method is our `BaseMacroExpander.isbound`, because that method checks for a raw string name, not an AST structure. The rest should be clear.

Then see our [`importer`](mcpyrate/importer.py). After [`mcpyrate.activate`](mcpyrate/activate.py) has been imported, the importer becomes the top-level entry point whenever a module is imported.

See also [Understanding the quasiquote system](quasiquotes.md#understanding-the-quasiquote-system).


## Guidelines

 - Follow [the Zen of Python](https://www.python.org/dev/peps/pep-0020/). Particularly, simple and explicit is often preferable.

 - Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/), but not into foolish consistency.
   - Particularly, *a blank line (or a double-blank line when appropriate) is a paragraph break*, to separate logical units. Just like when writing [prose](https://matthewbischoff.com/code-is-prose/), don't break the paragraph inside a logical unit, no matter what `flake8` tells you. This helps make the overall structure explicit and easy to see at a glance.
   - Tools like [black](https://github.com/psf/black) are not really appropriate here; a macro expander is as far from an everyday Python project as, say, [a language extension](https://github.com/Technologicat/unpythonic) is. Prefer to follow the existing style of the codebase.

 - **For future maintainers**: use [semantic versioning](https://semver.org/).
