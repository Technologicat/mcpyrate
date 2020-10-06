# -*- coding: utf-8; -*-
'''Expander core; essentially, how to apply a macro invocation.'''

__all__ = ['format_location',
           'MacroExpansionError',
           'MacroExpanderMarker',
           'Done',
           'BaseMacroExpander',
           'global_postprocess']

from ast import NodeTransformer, AST, copy_location, fix_missing_locations
from contextlib import contextmanager
from collections import ChainMap
from .ctxfixer import fix_missing_ctx
from .markers import ASTMarker
from .unparser import unparse_with_fallbacks
from .utilities import flatten_suite, NodeTransformerListMixin

# Hygienically captured macro functions.
# Global registry (across all modules being expanded) with unique keys, filled in by `mcpy.quotes`.
_hygienic_bindings = {}

def format_location(filename, tree, sourcecode):
    '''Format a source code location in a standard way, for error messages.'''
    lineno = tree.lineno if hasattr(tree, 'lineno') else None
    sep = " " if "\n" not in sourcecode else "\n"
    return f'at {filename}:{lineno}:{sep}{sourcecode}'

class MacroExpansionError(Exception):
    '''Error during macro expansion.'''

class MacroExpanderMarker(ASTMarker):
    '''Base class for AST markers used by the macro expander itself.'''

class Done(MacroExpanderMarker):
    '''A subtree that is done. Any further visits by the expander will skip it.

    Emitted by `BaseMacroExpander.visit_once`, to protect the once-expanded form
    from further expansion.
    '''

class BaseMacroExpander(NodeTransformerListMixin, NodeTransformer):
    '''Expander core. Base class for macro expanders.

    After identifying valid macro syntax, each `visit` method of the actual
    expander should return the result of calling the `expand()` method with
    the proper arguments.

    Constructor parameters:

        bindings: dictionary of macro name/function pairs
        filename: full path to `.py` file being expanded, for error reporting
    '''

    def __init__(self, bindings, filename):
        self._bindings = bindings
        self.bindings = ChainMap(self._bindings, _hygienic_bindings)
        self.filename = filename
        self.recursive = True

    def visit(self, tree):
        '''Expand macros in `tree`, using current setting for recursive mode.

        No-op if no macro bindings, or if `tree` is marked as `Done`.

        Treat `visit(stmt_suite)` as a loop for individual elements.

        This is the standard visitor method; it continues an ongoing visit.
        '''
        if not self.bindings or type(tree) is Done:
            return tree
        return super().visit(tree)

    def visit_recursively(self, tree):
        '''Entrypoint. Expand macros in `tree`, in recursive mode.

        That is, iterate the expansion process until no macros are left.
        Recursive mode is temporarily enabled even if currently inside the
        dynamic extent of a `visit_once`.

        This starts a new visit. The dynamic extents of visits may be nested.
        '''
        with self._recursive_mode(True):
            return self.visit(tree)

    def visit_once(self, tree):
        '''Entrypoint. Expand macros in `tree`, in non-recursive mode.

        That is, make just one pass, regardless of whether there are macros
        remaining in the output. Then mark `tree` as `Done`, so the rest of
        the macro expansion process will leave it alone. Recursive mode is
        temporarily disabled even if currently inside the dynamic extent
        of a `visit_recursively`.

        This starts a new visit. The dynamic extents of visits may be nested.
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

    def expand(self, syntax, target, macroname, tree, fill_root_location, kw=None):
        '''Expand a macro invocation.

        This is a hook for actual macro expanders. Macro libraries typically
        don't need to care about this; you'll want one of the `visit` methods
        instead.

        Transform the `target` node, replacing it with the expansion result
        of applying `macroname` on `tree`. Then postprocess locally, by
        `_visit_expansion`.

        `syntax` is the type of macro invocation detected by the actual macro
        expander, such as `expr` or `block`. What invocation types exist and
        what values of `syntax` represent them are defined by the actual macro
        expander. The value of `syntax` and its type can be anything; we don't
        even look at it, but just pass it on.

        `fill_root_location` sets whether to fill the source location info at
        the top level of the expansion from the AST node `target`.

        When calling the macro function, we pass the following named arguments:

          - `syntax`:     Our `syntax` argument, as-is.
          - `expander`:   The expander instance.
          - `invocation`: The `target` AST node as-is, for introspection if you
                          need to see not only the destructured `tree` and `args`,
                          but the macro invocation itself, without any processing.
                          Very rarely needed; if you need it, you'll know.
                          **CAUTION**: does not make a copy.

        To send additional named arguments from the actual expander to the
        macro function, place them in a dictionary and pass that dictionary
        as `kw`.
        '''
        macro = self.bindings[macroname]
        kw = kw or {}
        kw.update({
            'syntax': syntax,
            'expander': self,
            'invocation': target})

        approx_sourcecode_before_expansion = unparse_with_fallbacks(target)
        loc = format_location(self.filename, target, approx_sourcecode_before_expansion)

        # Expand the macro.
        try:
            expansion = _apply_macro(macro, tree, kw)
        except Exception as err:
            msg = loc
            if isinstance(err, MacroExpansionError) and err.__cause__:  # telescope nested use site reports
                oldmsg = err.args[0]
                if oldmsg[0] == "\n":
                    oldmsg = oldmsg[1:]
                msg = f'\n{msg}\n{oldmsg}'
                err = err.__cause__
            raise MacroExpansionError(msg) from err

        # Convert possible iterable result to `list`, then typecheck macro output.
        try:
            if expansion is not None and not isinstance(expansion, AST):
                expansion = list(expansion)
            if isinstance(expansion, AST) or expansion is None:
                pass  # ok
            elif isinstance(expansion, list):
                if not all(isinstance(elt, AST) for elt in expansion):
                    raise MacroExpansionError
            else:
                raise MacroExpansionError
        except Exception:
            reason = f"expected macro to return AST, iterable or None; got {type(expansion)} with value {repr(expansion)}"
            msg = f"{loc}\n{reason}"
            raise MacroExpansionError(msg)

        return self._visit_expansion(expansion, target, fill_root_location)

    def _visit_expansion(self, expansion, target, fill_root_location):
        '''Perform local postprocessing.

        Add in missing source location info and `ctx`.

        Then, if in recursive mode, recurse into (`visit`) the once-expanded
        macro output. That will cause the actual expander to `expand` again
        if it detects any more macro invocations.

        `fill_root_location` sets whether to fill the source location info at
        the top level of the expansion from the AST node `target`. Whether that
        should be done depends on the type of macro invocation.
        '''
        if expansion is not None:
            is_node = isinstance(expansion, AST)
            expansion = [expansion] if is_node else expansion
            if fill_root_location:
                expansion = map(lambda n: copy_location(n, target), expansion)
            expansion = map(fix_missing_locations, expansion)
            expansion = map(fix_missing_ctx, expansion)
            if self.recursive:
                expansion = map(self.visit, expansion)
            expansion = list(expansion).pop() if is_node else list(expansion)

        return expansion

    def isbound(self, name):
        '''Return whether the string `name` has been bound to a macro in this expander.'''
        return name in self.bindings or name in _hygienic_bindings

def _apply_macro(macro, tree, kw):
    '''Execute `macro` on `tree`, with the dictionary `kw` unpacked into macro's named arguments.'''
    return macro(tree, **kw)

# Final postprocessing for the top-level walk can't be done at the end of the
# entrypoints `visit_once` and `visit_recursively`, because it is valid for a
# macro to call those for a subtree.
def global_postprocess(tree):
    '''Perform global postprocessing for the top-level expansion.

    Delete any AST markers emitted by the macro expander that it uses to talk
    with itself during expansion.

    Call this after macro expansion is otherwise done, before sending `tree`
    to Python's `compile`.
    '''
    class MacroExpanderMarkerDeleter(NodeTransformer):
        def visit(self, tree):
            if isinstance(tree, list):
                return flatten_suite(self.visit(elt) for elt in tree)
            self.generic_visit(tree)
            if isinstance(tree, MacroExpanderMarker):
                return tree.body
            return tree
    return MacroExpanderMarkerDeleter().visit(tree)
