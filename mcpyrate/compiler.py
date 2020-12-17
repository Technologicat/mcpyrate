# -*- coding: utf-8; -*-
"""Compile macro-enabled code.

This is used by the import hooks in `mcpyrate.importer`.

Functions specific to multi-phase compilation live in `mcpyrate.multiphase`.
This module orchestrates all other transformations `mcpyrate` performs when
a module is imported. You can also call the `compile` function manually if
you want to compile macro-enabled code at run time.
"""

__all__ = ["expand", "compile",
           "singlephase_expand",
           "run", "create_module"]

import ast
import builtins
import importlib.util
import sys
from types import ModuleType, CodeType

from .astfixers import fix_locations
from .dialects import DialectExpander
from .expander import find_macros, expand_macros
from .markers import check_no_markers_remaining
from .multiphase import ismultiphase, multiphase_expand
from .utils import gensym, getdocstring


def expand(source, filename, optimize=-1, self_module=None):
    """Expand macros and dialects, accounting for multi-phase compilation if needed.

    This is the top-level entry point that orchestrates all the transformations
    `mcpyrate` performs when a module is imported.

    `source`:       `str` or `bytes` containing Python source code, an `ast.Module`,
                    or a `list` of statement AST nodes. A list behaves as if it
                    was the top level of a module.

                    We always support macros, dialect AST transforms, dialect AST
                    postprocessors, and multi-phase compilation.

                    Obviously, we support dialect source transforms only when
                    `source` is an `str` or a `bytes`.

    `filename`:     Full path to the `.py` file being compiled.

    `optimize`:     Passed to Python's built-in `compile` function, as well as to
                    the multi-phase compiler. The multi-phase compiler uses the
                    `optimize` setting for the temporary higher-phase modules.

    `self_module`:  Absolute dotted module name of the module being compiled.
                    Needed for modules that request multi-phase compilation.
                    Ignored in single-phase compilation.

                    In multi-phase compilation, used for temporarily injecting
                    the temporary, higher-phase modules into `sys.modules`,
                    as well as resolving `__self__` in self-macro-imports
                    (`from __self__ import macros, ...`).

    Return value is the final expanded AST, ready for Python's built-in `compile`.

    If you don't care about the expanded AST, and just want the final bytecode,
    see `mcpyrate.compiler.compile`, which performs both steps. It takes the
    same parameters as `expand`.
    """
    if not isinstance(source, (str, bytes, ast.Module, list)):
        raise TypeError(f"`source` must be Python source code (as `str` or `bytes`), an `ast.Module`, or a `list` of statement AST nodes; got {type(source)} with value {repr(source)}")

    dexpander = DialectExpander(filename=filename)

    if isinstance(source, (str, bytes)):
        if isinstance(source, bytes):
            text = importlib.util.decode_source(source)  # uses the "coding" prop line like Python itself does
        else:
            text = source

        # dialect source transforms (transpilers, surface syntax extensions, etc.)
        text = dexpander.transform_source(text)

        # produce initial AST
        try:
            tree = ast.parse(text, filename=filename, mode="exec")
        except Exception as err:
            raise ImportError(f"Failed to parse {filename} as Python after applying all dialect source transformers.") from err

    else:  # `ast.Module` or a `list` of statement AST nodes
        if isinstance(source, list):  # convenience, not provided by built-in `compile`.
            tree = ast.Module(body=source, type_ignores=[])
        else:
            tree = source

        if not all(isinstance(x, ast.stmt) for x in tree.body):
            invalid_inputs = [x for x in tree.body if not isinstance(x, ast.stmt)]
            invalid_inputs_msg = ", ".join(repr(x) for x in invalid_inputs)
            raise TypeError(f"module body has one or more elements that are not statement AST nodes: {invalid_inputs_msg}")

    # AST transforms: dialects, macros
    if not ismultiphase(tree):
        expansion = singlephase_expand(tree, filename=filename, self_module=self_module, dexpander=dexpander)
    else:
        if not self_module:
            raise ValueError("`self_module` must be specified when multi-phase compiling.")
        expansion = multiphase_expand(tree, filename=filename, self_module=self_module, dexpander=dexpander,
                                      _optimize=optimize)

    return expansion


# TODO: Think about how to support `mode="single"`, needed to use the same machinery for the REPL.
# TODO: Pass through also `flags` and `dont_inherit`? (Need to thread them to the multi-phase compiler, too.
# TODO:                This starts to look like a job for `unpythonic.dyn`; should we move it to `mcpyrate`?)
def compile(source, filename, optimize=-1, self_module=None):
    """[mcpyrate] Compile macro-enabled code.

    Like the built-in `compile` function, but for macro-enabled code. Supports
    macros, dialects, and multi-phase compilation.

    Parameters are the same as for `expand`. This function is in fact a thin wrapper
    that calls `expand`, and then passes the result to Python's built-in `compile`.
    The main reason for its existence is to provide a near drop-in replacement for
    the built-in `compile` for macro-enabled input.

    Currently the API differs from the built-in `compile` in that:

     - `mode` is always `"exec"`,
     - `dont_inherit` is always `True`, and
     - flags are not supported.

    Return value is a code object, ready for `exec`.
    """
    code, _ignored_docstring = _compile(source, filename, optimize, self_module)
    return code

def _compile(source, filename, optimize, self_module):
    expansion = expand(source, filename=filename, self_module=self_module, optimize=optimize)
    docstring = getdocstring(expansion.body)
    _fill_dummy_location_info(expansion)  # convenience, not sure if this step should be optional?
    code = builtins.compile(expansion, filename, mode="exec", dont_inherit=True, optimize=optimize)
    return code, docstring


def singlephase_expand(tree, *, filename, self_module, dexpander):
    """Expand dialects and macros in `tree`. Single phase only.

    This is a low-level function; you likely want `expand` instead. If you
    really do need something like this, but have a multi-phase `tree`, use
    `mcpyrate.multiphase.multiphase_expand` instead.

    Primarily meant to be called with `tree` the AST of a module that
    uses macros, but works with any `tree` that has a `body` attribute,
    where that `body` is a `list` of statement AST nodes.

    `filename`:     Full path to the `.py` file being compiled.

    `self_module`:  Passed in by the multi-phase compiler when it compiles an individual phase
                    using this function. Used for resolving `__self__` in self-macro-imports
                    (`from __self__ import macros, ...`).

                    Ignored in single-phase compilation.

    `dexpander`:    The `DialectExpander` instance to use for dialect AST transforms.
                    If not provided, dialect processing is skipped.

    Return value is the expanded `tree`.
    """
    if dexpander:
        tree, dialect_instances = dexpander.transform_ast(tree)
    module_macro_bindings = find_macros(tree, filename=filename, self_module=self_module)
    expansion = expand_macros(tree, bindings=module_macro_bindings, filename=filename)
    if dexpander:
        expansion = dexpander.postprocess_ast(expansion, dialect_instances)
    check_no_markers_remaining(expansion, filename=filename)
    return expansion

# --------------------------------------------------------------------------------
# Convenience functions for compiling and running macro-enabled code snippets at run time.

# Curiously, Python does not have a similar built-in for regular Python code,
# though it comes with all the parts to implement one.

def run(source, module=None, optimize=-1):
    """Compile and run macro-enabled code at run time.

    This behaves, for macro-enabled code, somewhat like the built-in `exec` for
    regular code, but instead of a dictionary, we take in an optional module.

    `source` supports the same formats as in `expand`, plus passthrough
    for an already compiled code object that represents a module
    (i.e. the output of our `compile`).

    The `module` parameter allows to run more code in the context of an
    existing module. It can be a dotted name (looked up in `sys.modules`)
    or a `types.ModuleType` object (such as returned by this function).

    If `module is None`, a new module is created with autogenerated unique
    values for `__file__` and `__name__`.

    If you need to create a new module, but with a specific filename and/or
    dotted name in `sys.modules`, call `create_module` first, and then pass in
    the result here as `module`.

    If `source` is not yet compiled, and the first statement in it is a static
    string (no f-strings or string arithmetic), it is used as the module's
    docstring. Otherwise the module's docstring is set to `None`.

    When a new module is created, it is inserted into `sys.modules` **before**
    the code runs. If you need to remove it from there later, the key is
    `module.__name__`, as usual.

    Return value is the module, after the code has been `exec`'d in its
    `__dict__`.

    Examples::

        from mcpyrate.quotes import macros, q
        from mcpyrate.compiler import run, create_module

        with q as quoted:
            '''This quoted snippet is effectively a module.

            You can put a module docstring here if you want.

            This code can use macros and multi-phase compilation.
            To do that, you have to import the macros (and/or enable
            the multi-phase compiler) at the top level of the quoted
            snippet.
            '''
            x = 21

        module = run(quoted)  # run in a new module, don't care about name
        assert module.x == 21
        assert module.__doc__.startswith("You")

        with q as quoted:
            x = 2 * x
        run(quoted, module)  # run in the namespace of an existing module
        assert module.x == 42

        # run in a module with a custom filename and dotted name
        mymodule = create_module(dotted_name="mymod",
                                 filename="some descriptive string")
        with q as quoted:
            x = 17
        run(quoted, mymodule)
        assert mymodule.x == 17
    """
    if module is not None and not isinstance(module, (ModuleType, str)):
        raise TypeError(f"`module` must be a `types.ModuleType`, a dotted name as `str`, or `None`; got {type(module)} with value {repr(module)}")

    if module is None:
        module = create_module()
    elif isinstance(module, str):
        dotted_name = module
        try:
            module = sys.modules[dotted_name]
        except KeyError:
            err = ModuleNotFoundError(f"Module '{dotted_name}' not found in `sys.modules`")
            err.__suppress_context__ = True
            raise err
    filename = module.__file__
    self_module = module.__name__

    if isinstance(source, CodeType):  # already compiled?
        code = source
        module.__doc__ = None
    else:
        code, docstring = _compile(source, filename=filename, self_module=self_module, optimize=optimize)
        module.__doc__ = docstring

    exec(code, module.__dict__)
    return module

def _fill_dummy_location_info(tree):
    """Populate missing location info with dummy values, so that Python can compile `tree`.

    It's better to use sensible values for location info when available. This
    function only exists because quoted code snippets carry no location info
    (which is appropriate for their usual use case, in macro output).
    """
    fake_lineno = 9999
    fake_col_offset = 9999
    reference_node = ast.Constant(value=None, lineno=fake_lineno, col_offset=fake_col_offset)
    fix_locations(tree, reference_node, mode="reference")


def create_module(dotted_name=None, filename=None):
    """Create a module at run time, insert it into `sys.modules`, and return it.

    This is a utility function that fills in some attributes of the module
    (usually populated by the importer), and inserts the new module into
    `sys.modules`. Used by `run` when no module is given.

    This does not care whether a module by the given dotted name is already in
    `sys.modules`; if so, its entry will get overwritten.

    `dotted_name`:  Fully qualified name of the module, for `sys.modules`. Optional.

                    Used as the `__name__` attribute of the module. If not provided,
                    a unique placeholder name will be auto-generated.

    `filename`:     Full path to the `.py` file the module represents, if applicable.
                    Otherwise some descriptive string is recommended. Optional.

                    Used as the `__file__` attribute of the module. If not provided,
                    a description will be auto-generated (based on `dotted_name`).

    When `dotted_name` has dots in it, the parent package for the new module
    must exist in `sys.modules`. The new module is added to its parent's
    namespace (like Python's importer would do), and the new module's
    `__package__` attribute will be set to the dotted name of the parent package.

    Otherwise the new module's `__package__` attribute will be the empty string.
    """
    if dotted_name:
        if not isinstance(dotted_name, str):
            raise TypeError(f"`dotted_name` must be an `str`, got {type(dotted_name)} with value {repr(dotted_name)}")
        path = dotted_name.split(".")
        if not all(component.isidentifier() for component in path):
            raise TypeError(f"each component of `dotted_name` must be a valid identifier`, got {repr(dotted_name)}")
    if filename and not isinstance(filename, str):
        raise TypeError(f"`filename` must be an `str`, got {type(filename)} with value {repr(filename)}")

    uuid = gensym("")
    if not filename:
        if dotted_name:
            filename = f"<dynamically created module '{dotted_name}'>"
        else:
            filename = f"<dynamically created module {uuid}>"
    dotted_name = dotted_name or f"dynamically_created_module_{uuid}"

    # Look at the definition of `types.ModuleType` for available attributes.
    #
    # We always populate `__name__` and `__file__`, and when applicable, `__package__`.
    #
    # `__loader__` and `__spec__` are left to the default value `None`, because
    # those don't make sense for a dynamically created module.
    #
    # `__doc__` can be filled later (by `run`, if that is used); we don't have the AST yet.
    #
    # `__dict__` is left at the default value, empty dictionary. It is filled later,
    # when some code is executed in this module.
    #
    module = ModuleType(dotted_name)
    module.__name__ = dotted_name
    module.__file__ = filename

    # Manage the package abstraction, like the importer does - with the difference that we
    # shouldn't import parent packages here. To keep things simple, we only allow creating
    # a module with dots in the name if its parent package already exists in `sys.modules`.
    if dotted_name.find(".") != -1:
        packagename, finalcomponent = dotted_name.rsplit(".", maxsplit=1)
        package = sys.modules.get(packagename, None)

        if not package:
            raise ModuleNotFoundError(f"while dynamically creating module '{dotted_name}': its parent package '{packagename}' not found in `sys.modules`")

        module.__package__ = packagename

        # The standard importer adds submodules to the package namespace, so we should too.
        # http://python-notes.curiousefficiency.org/en/latest/python_concepts/import_traps.html
        setattr(package, finalcomponent, module)

    sys.modules[dotted_name] = module
    return module
