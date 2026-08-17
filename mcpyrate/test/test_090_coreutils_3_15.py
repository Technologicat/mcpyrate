# -*- coding: utf-8 -*-
"""Tests for macro expander utilities, Python 3.15+ syntax.

Requires Python 3.15+ (the source parsed here won't parse on older versions).

A lazy macro-import is rejected rather than honoured or ignored. PEP 810's `lazy`
defers loading until first use, which cannot mean anything for a macro-import: the
expander consumes the statement at macro-expansion time, so the import has already
had to happen before any deferral could pay off. Accepting it silently would drop
the modifier when the macro-import is rewritten into an ordinary import.
"""

import ast

from ..coreutils import ismacroimport, get_macros


def runtests():
    def test_lazy_macroimport_is_rejected():
        stmt = ast.parse("lazy from mymacros import macros, foo").body[0]
        # It still looks like a macro-import; the rejection is get_macros' job.
        assert ismacroimport(stmt)
        try:
            get_macros(stmt, filename="<test_lazy_macroimport>")
        except SyntaxError as err:
            assert "lazy" in str(err), f"Expected the error to mention lazy, got: {err}"
        else:
            assert False, "Expected a SyntaxError for a lazy macro-import"
    test_lazy_macroimport_is_rejected()

    def test_lazy_dialectimport_is_rejected():
        """Dialect-imports reach the same check, differing only in the magic name."""
        stmt = ast.parse("lazy from mydialect import dialects, MyDialect").body[0]
        assert ismacroimport(stmt, magicname="dialects")
        try:
            get_macros(stmt, filename="<test_lazy_dialectimport>", allow_asname=False)
        except SyntaxError as err:
            assert "lazy" in str(err), f"Expected the error to mention lazy, got: {err}"
        else:
            assert False, "Expected a SyntaxError for a lazy dialect-import"
    test_lazy_dialectimport_is_rejected()

    def test_eager_macroimport_gets_past_the_check():
        """Control: an ordinary macro-import must fail later, for an unrelated reason.

        `mymacros` does not exist, so this reaches the module lookup and fails there —
        which is what shows the lazy check did not swallow the ordinary case.
        """
        stmt = ast.parse("from mymacros import macros, foo").body[0]
        try:
            get_macros(stmt, filename="<test_eager_macroimport>")
        except ModuleNotFoundError:
            pass
        except SyntaxError as err:
            assert False, f"Ordinary macro-import should not raise SyntaxError here: {err}"
        else:
            assert False, "Expected a ModuleNotFoundError for a nonexistent module"
    test_eager_macroimport_gets_past_the_check()


if __name__ == '__main__':
    runtests()
