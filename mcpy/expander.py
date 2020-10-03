# -*- coding: utf-8; -*-
'''Find and expand macros.

This layer provides the actual macro expander, defining:

 - Macro invocation types:
   - expr: `macroname[...]`,
   - block: `with macroname:`,
   - decorator: `@macroname`,
   - name: `macroname`.
 - Syntax for establishing macro bindings:
   - `from module import macros, ...`.
'''

__all__ = ['namemacro', 'isnamemacro',
           'parametricmacro', 'isparametricmacro',
           'MacroExpander', 'MacroCollector',
           'expand_macros', 'find_macros']

import importlib
import importlib.util  # in PyPy3, this must be imported explicitly
from inspect import signature
from ast import (Name, Call, Import, ImportFrom, alias, AST, Expr, Constant,
                 copy_location, iter_fields, NodeVisitor)
from .core import BaseMacroExpander, MacroExpansionError, global_postprocess, Done
from .importer import resolve_package
from .unparser import unparse_with_fallbacks
from .utilities import NodeVisitorListMixin

def namemacro(function):
    '''Decorator. Declare a macro function as an identifier macro.

    Since identifier macros are a rarely needed feature, only macros that are
    declared as such will be called as identifier macros.

    This must be the outermost decorator.
    '''
    function._isnamemacro = True
    return function

def isnamemacro(function):
    '''Return whether the macro function `function` has been declared as an identifier macro.'''
    return hasattr(function, '_isnamemacro')

def parametricmacro(signature_from):
    '''Decorator. Declare that a macro takes arguments, and specify its call signature.

    `signature_from` is a callable whose call signature (parameter list)
    will be used as the call signature of the macro.

    The user-supplied values for the arguments will be AST nodes, so if you
    define any default values, those should be AST nodes, too::

        from mcpy.quotes import macros, q

        @parametricmacro(signature_from=(lambda a=q[42], *, k=q["v"]: None))
        def mymacro(tree, args, syntax, **kw):
            ...

    The pattern is to use a `lambda` to create a callable inline; it'll never
    be actually called, so its return value doesn't matter (`None` is good).

    The arguments given to the macro invocation will be destructured, using the
    reference call signature to establish bindings between parameter names and
    the supplied arguments. The established bindings are sent as the `args`
    named parameter to the macro function. It is a dictionary, where the keys
    are the parameter names (as defined in `signature_from`), and the values
    are the AST nodes that were supplied as arguments.

    The macro does not need to care whether it receives arguments by position
    or by name; the established bindings are all that matters.

    Since it is rare for macros to need to have parameters, only macros that
    are declared as such will accept invocations with arguments. Trying to give
    arguments to a macro that is not declared as accepting arguments raises an
    error at macro expansion time.

    In most cases, instead of taking arguments, you can just require `tree`
    to have a specific layout. For example, `let(a << 1, b << 2)[...]` could
    instead be designed to be invoked as `let[(a << 1, b << 2) in ...]`. But
    if `let` should also work as a decorator, then it'll need to take arguments.

    This must be the outermost decorator.
    '''
    sig = signature(signature_from)
    def set_macrocallsignature(function):
        function._macrocallsignature = sig
    return set_macrocallsignature

def isparametricmacro(function):
    '''Return whether the macro function `function` has been declared as parametric.'''
    return hasattr(function, '_macrocallsignature')

# --------------------------------------------------------------------------------

def destructure(candidate):
    '''Destructure a macro invocation candidate into `(macroname, args, keywords)`.

    This unifies the handling of `Name` and `Call` nodes in macro invocations.
    '''
    if type(candidate) is Name:
        return candidate.id, None, None
    elif type(candidate) is Call and type(candidate.func) is Name:
        return candidate.func.id, candidate.args, candidate.keywords
    return None, None, None  # not a macro invocation


class MacroExpander(BaseMacroExpander):
    '''The actual macro expander.'''

    def _bind_macro_arguments(self, target, macroname, args, keywords):
        '''Bind arguments from a parametric macro `Call` to the macro's parameters.

        `target`: the macro invocation node being expanded, for error reporting.
        `macroname`: the name of the macro in `self.bindings`.
        `args`: list of AST nodes, as in a `Call` node.
        `keywords`: list of `keyword` AST nodes, as in a `Call` node.

        Return value is `{'args': ...}`, where `...` is a `dict` where the keys are
        raw strings of parameter names from the macro function's macro call signature
        (see `@parametricmacro`), and the values are the argument AST nodes from the
        macro invocation `Call` node.

        As a convenience, can be invoked for a `Name` node to no-op, by setting both
        `args` and `keywords` to `None`. In that case, return the empty dictionary.

        This format can be easily injected to `kw` for `BaseMacroExpander.expand`,
        by `kw.update(...)`, so it'll create at most an `args` entry.
        '''
        if args is None and keywords is None:  # no `Call`, just `Name`
            return {}
        function = self.bindings[macroname]
        if not isparametricmacro(function):
            approx_sourcecode_before_expansion = unparse_with_fallbacks(target)
            def usesite_location():
                lineno = target.lineno if hasattr(target, 'lineno') else None
                sep = " " if "\n" not in approx_sourcecode_before_expansion else "\n"
                return f'at {self.filename}:{lineno}:{sep}{approx_sourcecode_before_expansion}'
            msg = usesite_location()
            reason = f"{macroname} does not take arguments"
            msg = f"{msg}\n{reason}"
            raise MacroExpansionError(msg)
        args = args or []
        keywords = keywords or []
        # TODO: handle Starred nodes (after we figure out what those should mean here)
        kwargs = {kw.arg: kw.value for kw in keywords}
        bound = function._macrocallsignature.bind(*args, **kwargs)
        bound.apply_defaults()
        return {'args': dict(bound.arguments)}

    def visit_Subscript(self, subscript):
        '''Detect an expression (expr) macro invocation.

        Detected syntax::

            macroname[...]
            macroname(arg0, ..., kw0=v0, ...)[...]

        Replace the `SubScript` node with the result of the macro.

        Positional arguments are sent to the macro as `args`, named arguments
        as `keywords`. Content as in a `Call` node.
            https://greentreesnakes.readthedocs.io/en/latest/nodes.html#Call

        Any macro invocations in the macro arguments are expanded after this
        macro invocation itself.
        '''
        candidate = subscript.value
        macroname, args, keywords = destructure(candidate)
        if macroname and self.isbound(macroname):
            kw = self._bind_macro_arguments(subscript, macroname, args, keywords)
            tree = subscript.slice.value
            new_tree = self.expand('expr', subscript, macroname, tree, fill_root_location=True, kw=kw)
        else:
            new_tree = self.generic_visit(subscript)

        return new_tree

    def visit_With(self, withstmt):
        '''Detect a block macro invocation.

        Detected syntax::

            with macroname:
                ...
            with macroname as result:
                ...
            with macroname(arg0, ..., kw0=v0, ...):
                ...
            with macroname(arg0, ..., kw0=v0, ...) as result:
                ...

        Replace the `With` node with the result of the macro.

        Positional arguments are sent to the macro as `args`, named arguments
        as `keywords`. Content as in a `Call` node.
            https://greentreesnakes.readthedocs.io/en/latest/nodes.html#Call

        Any macro invocations in the macro arguments are expanded after this
        macro invocation itself.

        The `result` part is sent to the macro as `optional_vars`; it's a
        `Name`, `Tuple` or `List` node.
            https://greentreesnakes.readthedocs.io/en/latest/nodes.html#withitem
        '''
        with_item = withstmt.items[0]
        candidate = with_item.context_expr
        macroname, args, keywords = destructure(candidate)
        if macroname and self.isbound(macroname):
            kw = {'optional_vars': with_item.optional_vars}
            kw.update(self._bind_macro_arguments(withstmt, macroname, args, keywords))
            tree = withstmt.body
            new_tree = self.expand('block', withstmt, macroname, tree, fill_root_location=False, kw=kw)
            new_tree = _add_coverage_dummy_node(new_tree, withstmt, macroname)
        else:
            new_tree = self.generic_visit(withstmt)

        return new_tree

    def visit_ClassDef(self, classdef):
        return self._visit_Decorated(classdef)

    def visit_FunctionDef(self, functiondef):
        return self._visit_Decorated(functiondef)

    def _visit_Decorated(self, decorated):
        '''Detect a decorator macro invocation.

        Detected syntax::

            @macroname
            def f():
                ...

            @macroname(arg0, ..., kw0=v0, ...)
            def f():
                ...

        Or::

            @macroname
            class C():
                ...

            @macroname(arg0, ..., kw0=v0, ...)
            class C:
                ...

        Replace the whole decorated node with the result of the macro.

        Positional arguments are sent to the macro as `args`, named arguments
        as `keywords`. Content as in a `Call` node.
            https://greentreesnakes.readthedocs.io/en/latest/nodes.html#Call

        Any macro invocations in the macro arguments are expanded after this
        macro invocation itself.

        The body is expanded after the whole decorator list has been processed.
        '''
        macros, others = self._detect_decorator_macros(decorated.decorator_list)
        if not macros:
            return self.generic_visit(decorated)
        innermost_macro = macros[-1]
        macroname, args, keywords = destructure(innermost_macro)
        decorated.decorator_list.remove(innermost_macro)
        with self._recursive_mode(False):  # don't trigger other decorator macros yet
            kw = self._bind_macro_arguments(decorated, macroname, args, keywords)
            new_tree = self.expand('decorator', decorated, macroname, decorated, fill_root_location=True, kw=kw)
        new_tree = _add_coverage_dummy_node(new_tree, innermost_macro, macroname)
        return self.visit(new_tree)

    def _detect_decorator_macros(self, decorator_list):
        '''Identify macros in a `decorator_list`.

        Return a pair `(macros, others)`, where `macros` is a `list` of macro
        decorator AST nodes, and `others` is a `list` of the decorator AST
        nodes not identified as macros. Ordering is preserved within each
        of the two subsets.
        '''
        macros, others = [], []
        for decorator in decorator_list:
            macroname, args, keywords = destructure(decorator)
            if macroname and self.isbound(macroname):
                macros.append(decorator)
            else:
                others.append(decorator)

        return macros, others

    def visit_Name(self, name):
        '''Detect an identifier (name) macro invocation.

        Detected syntax::

            macroname

        Note no `...` in the example; the `Name` node itself is the input tree
        for the macro.

        Replace the `Name` node with the result of the macro.

        Identifier macros do not support arguments.

        Macro functions that want to get called as an identifier macro must
        be declared. Use the `@mcpy.namemacro` decorator, place it outermost.

        The main use case of identifier macros is to define magic variables
        that are valid only inside the invocation of some other macro.
        An classic example is the anaphoric if's `it`.

        Another use case is where you just need to paste some boilerplate
        code without any parameters.
        '''
        if self.isbound(name.id) and isnamemacro(self.bindings[name.id]):
            macroname = name.id
            def ismodified(tree):
                return not (type(tree) is Name and tree.id == macroname)
            # For identifier macros, no part of the tree is guaranteed to be compiled away.
            # So prevent an infinite loop if the macro no-ops, returning `tree` as-is.
            # (That's the public API for "I did what I needed to, now go ahead and use this
            #  as a regular run-time identifier").
            with self._recursive_mode(False):
                new_tree = self.expand('name', name, macroname, name, fill_root_location=True)
            if self.recursive and new_tree is not None:
                if ismodified(new_tree):
                    new_tree = self.visit(new_tree)
                else:
                    # When a magic variable expands in a valid surrounding context and does
                    # `return tree`, the expander needs to know it has applied its context check,
                    # so it shouldn't be expanded again (when expanding remaining macros in the result).
                    new_tree = Done(new_tree)
        else:
            new_tree = name

        return new_tree


class MacroCollector(NodeVisitorListMixin, NodeVisitor):
    '''Scan `tree` for macro invocations, with respect to given `expander`.

    Collect a set of `(macroname, syntax)`. Constructor parameters:

        - `expander`: a `MacroExpander` instance to query macro bindings from.

    Usage::

        mc = MacroCollector(expander)
        mc.visit(tree)
        print(mc.collected)
        # ...do something to tree...
        mc.clear()
        mc.visit(tree)
        print(mc.collected)

    This is a sister class of the actual `MacroExpander`, mirroring its macro
    invocation syntax detection.
    '''
    def __init__(self, expander):
        self.expander = expander
        self.clear()

    def clear(self):
        self.collected = set()

    def isbound(self, name):
        return self.expander.isbound(name)

    def visit_Subscript(self, subscript):
        candidate = subscript.value
        macroname, args, keywords = destructure(candidate)
        if macroname and self.isbound(macroname):
            self.collected.add((macroname, 'expr'))
            self.visit(args)
            self.visit(keywords)
            # We can't just `self.generic_visit(tree)`, because that'll incorrectly detect
            # the name part of the invocation as an identifier macro. So recurse only where safe.
            self.visit(subscript.slice.value)
        else:
            self.generic_visit(subscript)

    def visit_With(self, withstmt):
        with_item = withstmt.items[0]
        candidate = with_item.context_expr
        macroname, args, keywords = destructure(candidate)
        if macroname and self.isbound(macroname):
            self.collected.add((macroname, 'block'))
            self.visit(args)
            self.visit(keywords)
            self.visit(withstmt.body)
        else:
            self.generic_visit(withstmt)

    def visit_ClassDef(self, classdef):
        self._visit_Decorated(classdef)

    def visit_FunctionDef(self, functiondef):
        self._visit_Decorated(functiondef)

    def _visit_Decorated(self, decorated):
        macros, decorators = self.expander._detect_decorator_macros(decorated.decorator_list)
        if macros:
            for macro in macros:
                macroname, args, keywords = destructure(macro)
                self.collected.add((macroname, 'decorator'))
                self.visit(args)
                self.visit(keywords)
            for decorator in decorators:
                self.visit(decorator)
            for k, v in iter_fields(decorated):
                if k == "decorator_list":
                    continue
                self.visit(v)
        else:
            self.generic_visit(decorated)

    def visit_Name(self, name):
        macroname = name.id
        if self.isbound(macroname) and isnamemacro(self.expander.bindings[macroname]):
            self.collected.add((macroname, 'name'))


def _add_coverage_dummy_node(tree, macronode, macroname):
    '''Force `macronode` to be reported as covered by coverage tools.

    `tree` is the original output of the macro. `tree` must appear in a
    position where `ast.NodeTransformer.visit` is allowed to return a
    list of nodes.

    `macronode` is the macro invocation node to copy source location info from.

    `macroname` is included in the coverage dummy node, to ease debugging.
    '''
    # `macronode` itself might be macro-generated. In that case don't bother.
    if not hasattr(macronode, 'lineno') and not hasattr(macronode, 'col_offset'):
        return tree
    if tree is None:
        tree = []
    elif isinstance(tree, AST):
        tree = [tree]
    # The dummy node must actually run to get coverage, an `ast.Pass` won't do.
    # We must set location info manually, because we run after `expand`.
    x = copy_location(Constant(value=f"mcpy coverage: source line {macronode.lineno} invoked macro {macroname}"),
                      macronode)
    dummy = copy_location(Expr(value=x), macronode)
    tree.insert(0, Done(dummy))  # mark as Done so any expansions further out won't mess this up.
    return tree

# --------------------------------------------------------------------------------

def expand_macros(tree, bindings, *, filename):
    '''Expand `tree` with macro bindings `bindings`. Top-level entrypoint.

    This is primarily meant to be called with `tree` the AST of a module that
    uses macros, but can be called with any `tree` (even inside a macro, if you
    need an independent second instance of the expander with different bindings).

    `bindings`: dict of macro name/function pairs.

    `filename`: str, full path to the `.py` being macroexpanded, for error reporting.
                In interactive use, it can be an arbitrary label.
    '''
    expansion = MacroExpander(bindings, filename).visit(tree)
    expansion = global_postprocess(expansion)
    return expansion


def find_macros(tree, *, filename, reload=False):
    '''Establish macro bindings from `tree`. Top-level entrypoint.

    Look at each macro-import statement (`from ... import macros, ...`)
    at the top level of `tree.body`. Collect its macro bindings.

    Transform the macro-import into `import ...`, where `...` is the absolute
    module name the macros are being imported from.

    This is primarily meant to be called with `tree` the AST of a module that
    uses macros, but can be called with any `tree` that has a `body` attribute.

    `filename`: str, full path to the `.py` being macroexpanded, for resolving
                relative macro-imports and for error reporting. In interactive
                use, it can be an arbitrary label.

    `reload`:   bool, can be used to force a module reload for the macro definition
                modules `tree` uses. Useful for implementing macro support in a REPL,
                to make the REPL session refresh the macros when you import them again.

                Otherwise, avoid reloading here, to make sure all uses of the same
                macros (across different use site modules) point to the same function
                object.

    Return value is a dict `{macroname: function, ...}` with all collected bindings.
    '''
    bindings = {}
    for index, statement in enumerate(tree.body):
        if _is_macro_import(statement):
            module_absname, more_bindings = _get_macros(statement, filename=filename, reload=reload)
            bindings.update(more_bindings)
            # Remove all names to prevent the macros being accidentally used as regular run-time objects.
            # Always convert to an absolute import so that the unhygienic expose API guarantee works.
            tree.body[index] = copy_location(Import(names=[alias(name=module_absname, asname=None)]),
                                             statement)

    return bindings

def _is_macro_import(statement):
    '''
    A "macro import" is a statement of the form::

        from ... import macros, ...
    '''
    is_macro_import = False
    if isinstance(statement, ImportFrom):
        firstimport = statement.names[0]
        if firstimport.name == 'macros' and firstimport.asname is None:
            is_macro_import = True

    return is_macro_import

def _get_macros(macroimport, *, filename, reload=False):
    '''Get absolute module name, macro names and macro functions from a macro-import.

    As a side effect, import the macro definition module.

    `filename`: str, full path to the `.py` being macroexpanded, for resolving
                relative macro-imports and for error reporting. In interactive
                use, it can be an arbitrary label.

    `reload`:   bool, can be used to force a module reload for the macro definition
                module. Useful for implementing macro support in a REPL, to make
                the REPL session refresh the macros when you import them again.

                Otherwise, avoid reloading here, to make sure all uses of the same
                macros (across different use site modules) point to the same function
                object.

    Return value is `(module_absname, {macroname: function, ...})`.

    If a relative macro-import is attempted outside any package, raises `ImportError`.
    '''
    lineno = macroimport.lineno if hasattr(macroimport, "lineno") else None
    if macroimport.module is None:
        raise SyntaxError(f"{filename}:{lineno}: missing module name in macro-import")

    try:  # resolve relative macro-import, if we're actually reading a .py file
        package_absname = None
        if macroimport.level and filename.endswith(".py"):
            package_absname = resolve_package(filename)
    except (ValueError, ImportError) as err:
        # fallbacks may trigger if the macro-import statement itself is programmatically generated.
        approx_sourcecode = unparse_with_fallbacks(macroimport)
        sep = " " if "\n" not in approx_sourcecode else "\n"
        raise ImportError(f"while resolving relative macro-import at {filename}:{lineno}:{sep}{approx_sourcecode}") from err

    module_absname = importlib.util.resolve_name('.' * macroimport.level + macroimport.module, package_absname)
    module = importlib.import_module(module_absname)
    if reload:
        module = importlib.reload(module)

    return module_absname, {name.asname or name.name: getattr(module, name.name)
                            for name in macroimport.names[1:]}
