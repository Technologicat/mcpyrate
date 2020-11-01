# Authors

- Based on [`mcpy`](https://github.com/delapuente/mcpy) 2.0.0 by Salvador de la Puente González (@delapuente), 2015. Used under the MIT license.

- Rewritten and significantly extended into [`mcpyrate`](https://github.com/Technologicat/mcpyrate) 3.0.0 by Juha Jeronen (@Technologicat), 2020.
  - `macropython` bootstrapper, REPL functionality, and dialect functionality taken and upgraded from [`imacropy`](https://github.com/Technologicat/imacropy) and [`pydialect`](https://github.com/Technologicat/pydialect) by the same author.
  - `bunch` simplified from `unpythonic.env`, from [`unpythonic`](https://github.com/Technologicat/unpythonic) by the same author.
  - `deactivate` mechanism and making `colorama` optional contributed by Salvador E. Tropea (@set-soft).
    - `ansi.py`, used for syntax highlighting on *nix OSs when `colorama` is not installed, is a vendored module from [`colorama`](https://github.com/tartley/colorama) by Jonathan Hartley, 2013. Used under the BSD 3-Clause license.

- Quasiquote system based on the approach pioneered by [`macropy`](https://github.com/azazel75/macropy), by Li Haoyi, Justin Holmgren, Alberto Berti and all other `macropy` contributors, 2013-2018. MIT license.
  - The code itself was rewritten and extended, but shares many parts of the core design.

- `mcpyrate.dump` function based on [`astpp.py`](https://alexleone.blogspot.com/2010/01/python-ast-pretty-printer.html) by Alex Leone, 2010. That code in turn originally came from `ast.dump` in Python's stdlib, so it's covered by the PSF license.

- `%%dump_ast` IPython cell magic based on Thomas Kluyver's [version of `astpp.py`](https://bitbucket.org/takluyver/greentreesnakes/src/master/astpp.py) in the Green Tree Snakes source repository.
