"""Dump an AST into a string, with pythonic indentation.

Based on Alex Leone's `astpp.py`, with changes to indentation logic.
    http://alexleone.blogspot.co.uk/2010/01/python-ast-pretty-printer.html
"""

__all__ = ["dump"]

from ast import AST, iter_fields

def dump(tree, *, include_attributes=False, multiline=True):
    """Return a formatted dump of `tree`, as a string.

    `tree` can be an AST node or a statement suite (`list` of AST nodes).

    Attributes such as line numbers and column offsets are not dumped
    by default. If this is wanted, use `include_attributes=True`.

    To use indentation similar to how the code to construct the AST would
    appear as Python source code, use `multiline=True`.

    To put everything on one line, use `multiline=False`.

    Similar to `macropy`'s `real_repr`, but with indentation. The method
    `ast.AST.__repr__` itself can't be monkey-patched, because `ast.AST`
    is a built-in/extension type.
    """
    def recurse(tree, previndent=0):
        def separator():
            if multiline:
                return f",\n{(previndent + moreindent) * ' '}"
            return ", "
        if isinstance(tree, AST):
            moreindent = len(f"{tree.__class__.__name__}(")
            fields = [(k, recurse(v, previndent + moreindent + len(f"{k}="))) for k, v in iter_fields(tree)]
            if include_attributes and tree._attributes:
                fields.extend([(k, recurse(getattr(tree, k, None), previndent + moreindent + len(f"{k}=")))
                               for k in tree._attributes])
            return ''.join([
                tree.__class__.__name__,
                '(',
                separator().join((f'{k}={v}' for k, v in fields)),
                ')'])
        elif isinstance(tree, list):
            moreindent = len("[")
            items = [recurse(elt, previndent + moreindent) for elt in tree]
            if items:
                items[0] = '[' + items[0].lstrip()
                items[-1] = items[-1] + ']'
                return separator().join(items)
            return '[]'
        return repr(tree)

    if not isinstance(tree, (AST, list)):
        raise TypeError(f'expected AST, got {tree.__class__.__name__!r}')
    return recurse(tree)
