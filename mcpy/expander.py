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
           'MacroExpander', 'MacroCollector',
           'expand_macros', 'find_macros']

import importlib
from ast import (Name, Call, Import, ImportFrom, alias, AST, Expr, Constant,
                 copy_location, iter_fields, NodeVisitor)
from .core import BaseMacroExpander, global_postprocess, Done
from .importer import resolve_package
from .unparser import unparse_with_fallbacks

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

    def visit_Subscript(self, subscript):
        '''Detect an expression (expr) macro invocation.

        Detected syntax::

            macroname[...]
            macroname(arg0, ..., kw0=v0, ...)[...]

        Replace the `SubScript` node with the result of the macro.

        Positional arguments are sent to the macro as `args`, named arguments
        as `keywords`. Content as in a `Call` node.
            https://greentreesnakes.readthedocs.io/en/latest/nodes.html#Call
        '''
        candidate = subscript.value
        macroname, args, keywords = destructure(candidate)
        if macroname and self.isbound(macroname):
            kw = {'args': args, 'keywords': keywords}
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

        The `result` part is sent to the macro as `optional_vars`; it's a
        `Name`, `Tuple` or `List` node.
            https://greentreesnakes.readthedocs.io/en/latest/nodes.html#withitem
        '''
        with_item = withstmt.items[0]
        candidate = with_item.context_expr
        macroname, args, keywords = destructure(candidate)
        if macroname and self.isbound(macroname):
            tree = withstmt.body
            kw = {'optional_vars': with_item.optional_vars, 'args': args, 'keywords': keywords}
            new_tree = self.expand('block', withstmt, macroname, tree, fill_root_location=False, kw=kw)
            new_tree = _add_coverage_dummy_node(new_tree, withstmt)
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
        '''
        # TODO: let inner decorator macros see outer decorator macro invocations
        macros, others = self._detect_decorator_macros(decorated.decorator_list)
        decorated.decorator_list = others
        if macros:
            macros_executed = []
            for macro in reversed(macros):
                macroname, args, keywords = destructure(macro)
                kw = {'args': args, 'keywords': keywords}
                new_tree = self.expand('decorator', decorated, macroname, decorated, fill_root_location=False, kw=kw)
                macros_executed.append(macro)
                if new_tree is None:
                    break
            for macro in macros_executed:
                new_tree = _add_coverage_dummy_node(new_tree, macro)
        else:
            new_tree = self.generic_visit(decorated)

        return new_tree

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
            new_tree = self.generic_visit(name)

        return new_tree


class MacroCollector(NodeVisitor):
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
        if isinstance(candidate, Name) and self.isbound(candidate.id):
            self.collected.add((candidate.id, 'expr'))
        # We can't just `self.generic_visit(subscript)`, because that'll incorrectly detect
        # the name part of the invocation as an identifier macro. So recurse only where safe.
        self.visit(subscript.slice.value)

    def visit_With(self, withstmt):
        with_item = withstmt.items[0]
        candidate = with_item.context_expr
        if isinstance(candidate, Name) and self.isbound(candidate.id):
            self.collected.add((candidate.id, 'block'))
        self.visit(withstmt.body)

    def visit_ClassDef(self, classdef):
        self._visit_Decorated(classdef)

    def visit_FunctionDef(self, functiondef):
        self._visit_Decorated(functiondef)

    def _visit_Decorated(self, decorated):
        macros, decorators = self.expander._detect_decorator_macros(decorated.decorator_list)
        for macro in macros:
            self.collected.add((macro.id, 'decorator'))
        for decorator in decorators:
            self.visit(decorator)
        for field, value in iter_fields(decorated):
            if field == "decorator_list":
                continue
            if isinstance(value, list):
                for node in value:
                    self.visit(node)
            elif isinstance(value, AST):
                self.visit(value)

    def visit_Name(self, name):
        if self.isbound(name.id) and isnamemacro(self.expander.bindings[name.id]):
            self.collected.add((name.id, 'name'))
        self.generic_visit(name)


def _add_coverage_dummy_node(tree, target):
    '''Force `target` node to be reported as covered by coverage tools.

    Fixes coverage reporting for block and decorator macro invocations.

    `tree` must appear in a position where `ast.NodeTransformer.visit` is
    allowed to return a list of nodes. The return value is a `list` of nodes.
    '''
    # `target` itself might be macro-generated. In that case don't bother.
    if not hasattr(target, 'lineno') and not hasattr(target, 'col_offset'):
        return tree
    if tree is None:
        tree = []
    elif isinstance(tree, AST):
        tree = [tree]
    # The dummy node must actually run to get coverage, an `ast.Pass` won't do.
    # We must set location info manually, because we run after `expand`.
    non = copy_location(Constant(value=None), target)
    dummy = copy_location(Expr(value=non), target)
    tree.insert(0, Done(dummy))  # mark as Done so any expansions further out won't mess this up.
    return tree


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
        # fallbacks may trigger if the macro-import statement itself is macro-generated.
        approx_sourcecode = unparse_with_fallbacks(macroimport)
        sep = " " if "\n" not in approx_sourcecode else "\n"
        raise ImportError(f"while resolving relative macro-import at {filename}:{lineno}:{sep}{approx_sourcecode}") from err

    module_absname = importlib.util.resolve_name('.' * macroimport.level + macroimport.module, package_absname)
    module = importlib.import_module(module_absname)
    if reload:
        module = importlib.reload(module)

    return module_absname, {name.asname or name.name: getattr(module, name.name)
                            for name in macroimport.names[1:]}
