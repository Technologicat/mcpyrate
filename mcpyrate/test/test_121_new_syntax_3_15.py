# -*- coding: utf-8 -*-
"""Python 3.15's new syntax, through the rest of the AST machinery.

Requires Python 3.15+. The syntax lives in string literals parsed at run time, so
this file itself stays readable by older Pythons and by linters that cannot parse
it yet; the version suffix is what keeps the module from running on 3.14 and below.

`test_020_unparser_3_15.py` covers the unparser. This module covers everything else
that reads or rebuilds arbitrary AST, where the two new shapes could bite: a
`Starred` in the element position of a comprehension, and a `DictComp` whose `value`
is `None` because the mapping expression sits in `key` instead.
"""

import ast
import sys

from ..astfixers import fix_ctx
from ..compiler import run
from ..quotes import astify, unastify
from ..unparser import unparse

# One of each new form. The imports are here too: `is_lazy` is a new field on
# `Import`/`ImportFrom`, so it travels through the same machinery.
NEW_FORMS = ["{**d for d in dicts}",
             "[*L for L in lists]",
             "{*L for L in lists}",
             "(*L for L in lists)",
             "lazy import json",
             "lazy from pathlib import Path"]

STARRED_COMPREHENSIONS = ["[*L for L in lists]",
                          "{*L for L in lists}",
                          "(*L for L in lists)"]


def runtests():
    def test_astify_roundtrip():
        """`q[...]` rebuilds a tree from its fields, so both new shapes must survive it.

        `unastify` is astify's inverse, so this asserts the quoting machinery neither
        drops the empty `DictComp.value` nor mangles a `Starred` element.
        """
        for src in NEW_FORMS:
            result = unparse(unastify(astify(ast.parse(src)))).strip()
            assert result == src, f"astify round-trip: expected {src!r}, got {result!r}"
    test_astify_roundtrip()

    def test_fix_ctx_on_starred_element():
        """A macro building a starred comprehension by hand leaves `ctx` unset."""
        for src in STARRED_COMPREHENSIONS:
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if "ctx" in getattr(node, "_fields", ()):
                    node.ctx = None
            fix_ctx(tree, copy_seen_nodes=False)
            starreds = [node for node in ast.walk(tree) if isinstance(node, ast.Starred)]
            assert starreds, f"no Starred found in {src!r}"
            for node in starreds:
                assert isinstance(node.ctx, ast.Load), f"{src!r}: Starred got ctx={node.ctx}"
            result = unparse(tree).strip()
            assert result == src, f"after fix_ctx: expected {src!r}, got {result!r}"
    test_fix_ctx_on_starred_element()

    def test_dump_handles_empty_dictcomp_value():
        """`dump` feeds error messages, so it must not choke on the empty field."""
        from .. import dump  # noqa: PLC0415 -- keep the import next to its only use
        text = dump(ast.parse("{**d for d in dicts}"))
        assert "DictComp" in text, f"expected a DictComp in the dump, got {text!r}"
    test_dump_handles_empty_dictcomp_value()

    def test_laziness_survives_expansion():
        """A lazy import must still be lazy after the module has been expanded.

        `run` compiles a *dynamically generated* module, whose filename does not end
        in `.py`, so the compiler unparses and re-parses it on the way. That is the
        path where a dropped `lazy` would vanish without any error — the module would
        simply import eagerly, and nothing would say so.

        `colorsys` is the guinea pig because nothing else here imports it; it is
        evicted first so that the "not yet loaded" half of the test means something.
        """
        sys.modules.pop("colorsys", None)
        module = run("lazy import colorsys\nresult = 42\n")
        assert module.result == 42, f"expected the module to run, got {module.result!r}"
        assert "colorsys" not in sys.modules, "the import was not deferred; `lazy` was lost in expansion"
        assert module.colorsys.rgb_to_hls(0.0, 0.0, 0.0) == (0.0, 0.0, 0.0)
        assert "colorsys" in sys.modules, "using the name should have triggered the deferred import"
    test_laziness_survives_expansion()


if __name__ == '__main__':
    runtests()
