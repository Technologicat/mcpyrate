# -*- coding: utf-8; -*-
"""Alternative file layout for the anaphoric if and let examples. Demo script.

Invoke as `macropython demo/anaphoric_if_revisited/demo.py` (needs `aif.py` and `let.py`).
"""

from mcpyrate.debug import macros, step_expansion  # noqa: F811

from aif import macros, aif, it  # noqa: F811, F401
from let import macros, let, letseq  # noqa: F811, F401

def demo():
    with step_expansion:
        assert aif[2 * 21,
                   f"it is {it}",
                   "it is False"] == "it is 42"

    with step_expansion:
        assert let[[x, 2], [y, 3]][x * y] == 6  # noqa: F821, `x` and `y` are defined by the `let`.

    with step_expansion:
        assert letseq[[x, 21], [x, 2 * x]][x] == 42  # noqa: F821

if __name__ == '__main__':
    demo()
