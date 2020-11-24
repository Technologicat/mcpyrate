# -*- coding: utf-8; -*-
"""Expander core; essentially, how to apply a macro invocation."""

__all__ = ["MacroExpansionError", "MacroExpanderMarker", "Done",
           "BaseMacroExpander", "global_postprocess"]

from ast import NodeTransformer, AST
from contextlib import contextmanager
from collections import ChainMap

from .astfixers import fix_ctx, fix_locations
from .markers import ASTMarker, delete_markers
from .utils import flatten, format_location

# Global macro bindings shared across all expanders in the current process.
# This is used by `mcpyrate.quotes` for hygienically captured macro functions.
global_bindings = {}

class MacroExpansionError(Exception):
    """Base class for errors specific to macro expansion.

    For errors detected **at macro expansion time**, we recommend raising:

     - `SyntaxError` with a descriptive message, if there's something wrong
       with how the macro was invoked, or with the AST layout of the `tree`
       (or `args`) it got vs. what it was expecting.

     - `TypeError` or `ValueError` as appropriate, if there is a problem in
       the macro arguments meant for the macro itself. (As opposed to macro
       arguments such as in the `let` demo, where `args` is just another
       place to send in an AST to be transformed.)

     - `MacroExpansionError`, or a custom descendant of it, if something else
       macro-related went wrong.

    Some operations represented by a macro may inject a call to a run-time part
    of that operation itself (e.g. the quasiquote system does this). For errors
    detected **at run time of the use site**:

     - Use whichever exception type you would in regular Python code that
       doesn't use macros. For example, a `TypeError`, `ValueError` or
       `RuntimeError` may be appropriate.
    """

class MacroApplicationError(MacroExpansionError):
    """The expander core caught an exception while applying a macro function.

    The expander uses this type to automatically telescope use site reports
    for nested macro invocations (which occur when a macro opts to expand
    inside-out).

    The `macropython` wrapper also strips most of the traceback when it catches
    an exception of this type. We know that for the internal uses of this type,
    the traceback speaks of things such as `macropython` itself, the importer,
    and the macro expander, and it is typically very long. The linked ("direct
    cause") exceptions contain the actually relevant, client code tracebacks.

    **CAUTION**: This type is for internal use only.
    """

class MacroExpanderMarker(ASTMarker):
    """Base class for AST markers used by the macro expander itself."""

class Done(MacroExpanderMarker):
    """A subtree that is done. Any further visits by the expander will skip it.

    Emitted by `BaseMacroExpander.visit_once`, to protect the once-expanded form
    from further expansion.
    """

# --------------------------------------------------------------------------------

class BaseMacroExpander(NodeTransformer):
    """Expander core. Base class for macro expanders.

    After identifying valid macro syntax, each `visit` method of the actual
    expander should return the result of calling the `expand()` method with
    the proper arguments.

    Constructor parameters:

        bindings: dictionary of macro name/function pairs
        filename: full path to `.py` file being expanded, for error reporting
    """

    def __init__(self, bindings, filename):
        self.local_bindings = bindings
        self.bindings = ChainMap(self.local_bindings, global_bindings)
        self.filename = filename
        self.recursive = True

    def visit(self, tree):
        """Expand macros in `tree`, using current setting for recursive mode.

        No-op if no macro bindings, or if `tree` is marked as `Done`.

        Treat `visit(stmt_suite)` as a loop for individual elements.
        No-op if `tree is None`.

        This is the standard visitor method; it continues an ongoing visit.
        """
        if not self.bindings or type(tree) is Done:
            return tree
        if tree is None:
            return None
        if isinstance(tree, list):
            new_tree = flatten(self.visit(elt) for elt in tree)
            if new_tree:
                tree[:] = new_tree
                return tree
            return None
        return super().visit(tree)

    def visit_recursively(self, tree):
        """Entrypoint. Expand macros in `tree`, in recursive mode.

        That is, iterate the expansion process until no macros are left.
        Recursive mode is temporarily enabled even if currently inside the
        dynamic extent of a `visit_once`.

        This starts a new visit. The dynamic extents of visits may be nested.
        """
        with self._recursive_mode(True):
            return self.visit(tree)

    def visit_once(self, tree):
        """Entrypoint. Expand macros in `tree`, in non-recursive mode.

        That is, make just one pass, regardless of whether there are macros
        remaining in the output. Then mark `tree` as `Done`, so the rest of
        the macro expansion process will leave it alone. Recursive mode is
        temporarily disabled even if currently inside the dynamic extent
        of a `visit_recursively`.

        This starts a new visit. The dynamic extents of visits may be nested.
        """
        with self._recursive_mode(False):
            return Done(self.visit(tree))

    def _recursive_mode(self, isrecursive):
        """Context manager. Change recursive mode, restoring the old mode when the context exits."""
        @contextmanager
        def recursive_mode():
            wasrecursive = self.recursive
            try:
                self.recursive = isrecursive
                yield
            finally:
                self.recursive = wasrecursive
        return recursive_mode()

    def expand(self, syntax, target, macroname, tree, sourcecode, kw=None):
        """Expand a macro invocation.

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

        `sourcecode` is a source code dump (or unparsed backconversion from AST)
        for error messages. It is a parameter, because the actual expander may
        edit the `target` node (e.g. to pop a block macro) before we get control.

        When calling the macro function, we pass the following named arguments:

          - `syntax`:     Our `syntax` argument, as-is.
          - `expander`:   The expander instance.
          - `invocation`: The `target` AST node as-is, for introspection if you
                          need to see not only the destructured `tree` and `args`,
                          but the macro invocation itself, without any processing.

                          Very rarely needed; if you need it, you'll know.

                          **CAUTION**: not a copy, or at most a shallow copy.

        To send additional named arguments from the actual expander to the
        macro function, place them in a dictionary and pass that dictionary
        as `kw`.
        """
        loc = format_location(self.filename, target, sourcecode)  # macro use site

        kw = kw or {}
        kw.update({"syntax": syntax,
                   "expander": self,
                   "invocation": target})

        try:
            # Resolve macro binding.
            macro = self.isbound(macroname)
            if not macro:  # pragma: no cover
                raise MacroApplicationError(f"{loc}\nin {syntax} macro invocation for '{macroname}': the name '{macroname}' is not bound to a macro.")

            # Expand the macro.
            expansion = _apply_macro(macro, tree, kw)

            # Convert possible iterable result to `list`, then typecheck macro output.
            try:
                if expansion is not None and not isinstance(expansion, AST):
                    expansion = list(expansion)

                if isinstance(expansion, AST) or expansion is None:
                    pass  # ok
                elif isinstance(expansion, list):
                    if not all(isinstance(elt, AST) for elt in expansion):
                        raise TypeError("Expected all elements of list returned by macro function to be ASTs")
                else:
                    raise TypeError("Unexpected return type from macro function")
            except Exception:
                reason = f"in {syntax} macro invocation for '{macroname}': expected macro to return AST node, iterable of AST nodes, or None; got {type(expansion)} with value {repr(expansion)} (after iterable to list conversion)"
                msg = f"{loc}\n{reason}"
                err = MacroApplicationError(msg)
                err.__suppress_context__ = True
                raise err

        # If something went wrong, generate a standardized macro use site report.
        except Exception as err:
            msg = f"{loc}\nin {syntax} macro invocation for '{macroname}'"
            if isinstance(err, MacroApplicationError) and err.__cause__:
                # Telescope nested use site reports, by keeping the original
                # traceback and `__cause__`, but combining the messages.
                #
                # When macro invocations are nested, the `expand` call
                # that is processing the innermost macro raises first.
                # So when the next outer one catches the exception,
                # it should add its own message to the beginning,
                # to make the report read in an outside-in order,
                # similarly to a Python traceback.
                oldmsg = err.args[0]
                oldmsg_lines = oldmsg.split("\n")
                hint = "An exception occurred during macro expansion.\n\nMacro use site (most recent macro application last):"
                hint_lines = hint.split("\n")
                hint_length_in_lines = len(hint_lines)
                if oldmsg_lines[0] == hint_lines[0]:
                    oldmsg = "\n".join(oldmsg_lines[hint_length_in_lines:])
                msg = f"{hint}\n{msg}\n{oldmsg}"
                raise MacroApplicationError(msg).with_traceback(err.__traceback__) from err.__cause__
            else:
                # Not nested; tack on a `MacroApplicationError` with
                # use site info to whatever exception we originally got.
                #
                # Use site report telescoping uses the fact that this
                # is the only raise-from for a `MacroApplicationError`.
                # So if it has a `__cause__`, it came from here.
                raise MacroApplicationError(msg) from err

        return self._visit_expansion(expansion, target)

    def _visit_expansion(self, expansion, target):
        """Perform local postprocessing.

        Add in missing source location info and `ctx`.

        Then, if in recursive mode, recurse into (`visit`) the once-expanded
        macro output. That will cause the actual expander to `expand` again
        if it detects any more macro invocations.
        """
        if expansion is not None:
            expansion = fix_locations(expansion, target, mode="reference")
            expansion = fix_ctx(expansion, copy_seen_nodes=False)
            if self.recursive:
                expansion = self.visit(expansion)

        return expansion

    def isbound(self, name, *, global_only=False):
        """Return the macro function the string `name` is bound to, or `False`."""
        bindings = self.bindings if not global_only else global_bindings
        if name in bindings:
            return bindings[name]
        return False

def _apply_macro(macro, tree, kw):
    """Execute `macro` on `tree`, with the dictionary `kw` unpacked into macro's named arguments."""
    return macro(tree, **kw)


# Final postprocessing for the top-level walk can't be done at the end of the
# entrypoints `visit_once` and `visit_recursively`, because it is valid for a
# macro to call those for a subtree.
def global_postprocess(tree):
    """Perform global postprocessing for the top-level expansion.

    Delete any AST markers emitted by the macro expander that it uses to talk
    with itself during expansion.

    Call this after macro expansion is otherwise done, before sending `tree`
    to Python's `compile`.
    """
    tree = delete_markers(tree, cls=MacroExpanderMarker)
    # A name macro, appearing as an assignment target, gets the wrong ctx,
    # because when expanding the name macro, the expander sees only the Name
    # node, and thus puts an `ast.Load` there as the ctx.
    tree = fix_ctx(tree, copy_seen_nodes=True)
    return tree
