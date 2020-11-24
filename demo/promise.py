# -*- coding: utf-8 -*-
"""Delayed evaluation.

Inspired by Racket's promises and `macropy.quick_lambda.lazy`.

See:
    https://docs.racket-lang.org/reference/Delayed_Evaluation.html
    https://macropy3.readthedocs.io/en/latest/lazy.html
"""

__all__ = ["delay", "force"]

from mcpyrate.multiphase import macros, phase

with phase[1]:
    from mcpyrate.quotes import macros, q, a  # noqa: F811, F401

    _uninitialized = object()
    class Promise:
        """Delayed evaluation, with memoization."""

        def __init__(self, thunk):
            """`thunk`: 0-argument callable to be stored for delayed evaluation."""
            if not callable(thunk):
                raise TypeError(f"`thunk` must be a callable, got {type(thunk)} with value {repr(thunk)}")
            self.thunk = thunk
            self.value = _uninitialized
            self.thunk_returned_normally = _uninitialized

        def force(self):
            """Compute and return the value of the promise.

            If `self.thunk` is not already evaluated, evaluate it now, and cache
            its return value. If it raises, cache the exception instance instead.

            Then in any case, return the cached value, or raise the cached exception.
            """
            if self.value is _uninitialized:
                try:
                    self.value = self.thunk()
                    self.thunk_returned_normally = True
                except Exception as err:
                    self.value = err
                    self.thunk_returned_normally = False
            if self.thunk_returned_normally:
                return self.value
            else:
                raise self.value

    def delay(tree, *, syntax, **kw):
        """[syntax, expr] Delay an expression."""
        if syntax != "expr":
            raise SyntaxError("`delay` is an expr macro only")
        return q[Promise(lambda: a[tree])]

    def force(x):
        """Evaluate a delayed expression, at most once, and return its value.

        For convenience, for any non-promise value, return that value itself.
        """
        return x.force() if isinstance(x, Promise) else x


from __self__ import macros, delay  # noqa: F811, F401

def demo():
    promise1 = delay[2 * 21]
    print(f"Promise is {promise1}, its value is {force(promise1)}.")

    promise2 = delay[1 / 0]
    try:
        force(promise2)
    except ZeroDivisionError:
        pass
    else:
        assert False

if __name__ == '__main__':
    demo()
