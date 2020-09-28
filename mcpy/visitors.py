# -*- coding: utf-8; -*-
'''Expander core; essentially, how to apply a macro invocation.'''

__all__ = ['BaseMacroExpander',
           'MacroExpansionError',
           'MacroExpanderMarker',
           'global_postprocess']

from ast import NodeTransformer, AST, fix_missing_locations
from contextlib import contextmanager
from .ctxfixer import fix_missing_ctx
from .markers import ASTMarker
from .unparse import unparse
from .utilities import flatten_suite

class MacroExpansionError(Exception):
    '''Error during macro expansion.'''

class MacroExpanderMarker(ASTMarker):
    '''Base class for AST markers used by the macro expander itself.'''

class Done(MacroExpanderMarker):
    '''A subtree that is done. Any further visits by the expander will skip it.

    Emitted by `BaseMacroExpander.visit_once`, to protect the once-expanded form
    from further expansion.
    '''

class BaseMacroExpander(NodeTransformer):
    '''
    A base class for macro expanders. After identifying valid macro syntax, the
    actual expander should return the result of calling the `expand()` method
    with the proper arguments.
    '''

    def __init__(self, bindings, filename):
        '''
        bindings: dict of macro name/function pairs
        filename: full path to `.py` file being expanded, for error reporting
        '''
        self.bindings = bindings
        self.filename = filename
        self.recursive = True

    def visit(self, tree):
        '''Expand macros in `tree`, using current setting for recursive mode.

        Treat `visit(stmt_suite)` as a loop for individual elements.

        No-op if no macro bindings, or if `tree` is marked as `Done`.

        This is the standard visitor method; it continues an ongoing visit.
        '''
        if not self.bindings or type(tree) is Done:
            return tree
        supervisit = super().visit
        if isinstance(tree, list):
            return flatten_suite(supervisit(elt) for elt in tree)
        return supervisit(tree)

    def visit_recursively(self, tree):
        '''Expand macros in `tree`, in recursive mode.

        That is, iterate the expansion process until no macros are left.
        Recursive mode is used even if currently inside the dynamic extent
        of a `visit_once`.

        This is an entrypoint that starts a new visit. The dynamic extents of
        visits may be nested.
        '''
        with self._recursive_mode(True):
            return self.visit(tree)

    def visit_once(self, tree):
        '''Expand macros in `tree`, in non-recursive mode. Useful for debugging.

        That is, make just one pass, regardless of whether there are macros
        remaining in the output. Then mark `tree` as `Done`, so the rest of the
        macro expansion process will leave it alone. Non-recursive mode is used
        even if currently inside the dynamic extent of a `visit_recursively`.

        This is an entrypoint that starts a new visit. The dynamic extents of
        visits may be nested.
        '''
        with self._recursive_mode(False):
            return Done(self.visit(tree))

    def _recursive_mode(self, isrecursive):
        '''Context manager. Change recursive mode, restoring the old mode when the context exits.'''
        @contextmanager
        def recursive_mode():
            wasrecursive = self.recursive
            try:
                self.recursive = isrecursive
                yield
            finally:
                self.recursive = wasrecursive
        return recursive_mode()

    def expand(self, syntax, target, macroname, tree, kw=None):
        '''
        Hook for actual macro expanders. Macro libraries typically don't need
        to care about this; you'll want one of the `visit` methods instead.

        Transform `target` node, replacing it with the expansion result of
        applying `macroname` on `tree`. Then postprocess by `_visit_expansion`.

        `syntax` is the type of macro invocation detected by the actual macro
        expander. It is sent to the macro implementation as a named argument,
        to allow it to dispatch on the type. (We don't care what it is; that's
        between the actual expander and the macro implementations to agree on.)

        The `expander` named argument is automatically filled in with a
        reference to the expander instance.

        If the actual expander wants to send additional named arguments to
        the macro implementation, place them in a dictionary and pass that
        dictionary as `kw`.
        '''
        macro = self.bindings[macroname]
        kw = kw or {}
        kw.update({
            'syntax': syntax,
            'expander': self})

        approx_sourcecode_before_expansion = unparse(target)
        try:
            expansion = _apply_macro(macro, tree, kw)
        except Exception as err:
            lineno = target.lineno if hasattr(target, 'lineno') else None
            sep = " " if "\n" not in approx_sourcecode_before_expansion else "\n"
            msg = f'use site was at {self.filename}:{lineno}:{sep}{approx_sourcecode_before_expansion}'
            raise MacroExpansionError(msg) from err

        return self._visit_expansion(expansion, target)

    def _visit_expansion(self, expansion, target):
        '''
        Perform local postprocessing fix-ups such as adding in missing
        source location info and `ctx`.

        Then, if in recursive mode, recurse into (`visit`) the once-expanded
        macro output. That will cause the actual expander to `expand` again
        if it detects any more macro invocations.
        '''
        if expansion is not None:
            is_node = isinstance(expansion, AST)
            expansion = [expansion] if is_node else expansion
            expansion = map(fix_missing_locations, expansion)
            expansion = map(fix_missing_ctx, expansion)
            if self.recursive:
                expansion = map(self.visit, expansion)
            expansion = list(expansion).pop() if is_node else list(expansion)

        return expansion

    def ismacro(self, name):
        '''Return whether the string `name` has been bound to a macro in this expander.'''
        return name in self.bindings

def _apply_macro(macro, tree, kw):
    '''Execute `macro` on `tree`, with the dictionary `kw` unpacked into macro's named arguments.'''
    return macro(tree, **kw)

# Final postprocessing for the top-level walk can't be done at the end of the
# entrypoints `visit_once` and `visit_recursively`, because it is valid for a
# macro to call those for a subtree.
def global_postprocess(tree):
    '''Perform final postprocessing fix-ups for the top-level expansion.

    Call this after macro expansion is otherwise done, before sending `tree`
    to Python's `compile`.

    This deletes any AST markers emitted by the macro expander that it uses
    to talk with itself during expansion.
    '''
    class InternalMarkerDeleter(NodeTransformer):
        def visit(self, tree):
            if isinstance(tree, list):
                return flatten_suite(self.visit(elt) for elt in tree)
            self.generic_visit(tree)
            if isinstance(tree, MacroExpanderMarker):
                return tree.body
            return tree
    return InternalMarkerDeleter().visit(tree)
