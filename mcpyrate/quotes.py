# -*- coding: utf-8; -*-
"""Quasiquotes. Build ASTs in your macros, using syntax that mostly looks like regular code."""

__all__ = ['lift_sourcecode',
           'capture_value', 'capture_macro',
           'astify', 'unastify',
           'q', 'u', 'n', 'a', 's', 'h',
           'expand1q', 'expandq',
           'expand1', 'expand']

import ast
import pickle

from .core import global_bindings, Done
from .expander import MacroExpander, isnamemacro
from .markers import ASTMarker, get_markers
from .unparser import unparse
from .utils import gensym, flatten, NestingLevelTracker


def _mcpyrate_quotes_attr(attr):
    """Create an AST that, when compiled and run, looks up `mcpyrate.quotes.attr` in `Load` context."""
    mcpyrate_quotes_module = ast.Attribute(value=ast.Name(id="mcpyrate"), attr="quotes")
    return ast.Attribute(value=mcpyrate_quotes_module, attr=attr)


class QuasiquoteMarker(ASTMarker):
    """Base class for AST markers used by quasiquotes. Compiled away by `astify`."""
    pass

# --------------------------------------------------------------------------------
# Unquote commands for `astify`. Each type corresponds to an unquote macro.

class Unquote(QuasiquoteMarker):
    """Interpolate the value of the given subtree into the quoted tree. Emitted by `u[]`."""
    pass


class LiftSourcecode(QuasiquoteMarker):
    """Parse a string as a Python expression, interpolate the resulting AST. Emitted by `n[]`.

    This allows e.g. computing names of lexical variables.
    """
    def __init__(self, body, filename):
        super().__init__(body)
        self.filename = filename
        self._fields += ["filename"]


class ASTLiteral(QuasiquoteMarker):  # similar to `macropy`'s `Literal`, but supports block mode, too.
    """Interpolate the given AST. Emitted by `a`."""
    def __init__(self, body, syntax):
        super().__init__(body)
        self.syntax = syntax
        self._fields += ["syntax"]


class ASTList(QuasiquoteMarker):
    """Interpolate the given `list` of AST nodes as an `ast.List` node. Emitted by `s[]`."""
    pass


class Capture(QuasiquoteMarker):  # like `macropy`'s `Captured`
    """Capture given subtree hygienically. Emitted by `h[]`.

    Details: capture the value or macro name the given subtree evaluates to,
    at the use site of `q`. The value or macro reference is frozen (by pickle)
    so that it can be restored also in another Python process later.
    """
    def __init__(self, body, name):
        super().__init__(body)
        self.name = name
        self._fields += ["name"]

# --------------------------------------------------------------------------------
# Run-time parts of the operators.

# Unquote doesn't have its own function here, because it's a special case of `astify`.

def lift_sourcecode(value, filename="<unknown>"):
    """Parse a string as a Python expression. Run-time part of `n[]`.

    Main use case is to access lexical variables with names computed at your macro definition site::

        lift_sourcecode("kitty") -> Name(id='kitty')

    More complex expressions work, too::

        lift_sourcecode("kitty.tail") -> Attribute(value=Name(id='kitty'),
                                                   attr='tail')
        lift_sourcecode("kitty.tail.color") -> Attribute(value=Attribute(value=Name(id='kitty'),
                                                                         attr='tail'),
                                                         attr='color')
        lift_sourcecode("kitties[3].paws[2].claws")
    """
    if not isinstance(value, str):
        raise TypeError(f"`n[]`: expected an expression that evaluates to str, result was {type(value)} with value {repr(value)}")
    return ast.parse(value, filename=filename, mode="eval").body


_splice_ast_literal_block_marker = object()  # nonce value, only used at run time inside the same process.
def ast_literal(tree, syntax):
    """Perform run-time typecheck on AST literal `tree`. Run-time part of `a`.

    If `syntax="block", also flatten locally, and inject a run-time marker
    for `splice_ast_literal_blocks`, to indicate where splicing into the
    surrounding context is needed.
    """
    if syntax not in ("expr", "block"):
        raise TypeError(f"expected `syntax` either 'expr' or 'block', got {type(syntax)} with value {repr(syntax)}")

    if syntax == "expr":
        body = tree.body if isinstance(tree, ASTMarker) else tree
        if not isinstance(body, ast.expr):
            raise TypeError(f"`a` (expr mode): expected an expression node, got {type(body)} with value {repr(body)}")
        return tree

    assert syntax == "block"
    # Block mode `a` always produces a `list` of the items in its body.
    # Each item may refer, at run time, to a statement AST node or to a `list`
    # of statement AST nodes.
    #
    # We flatten locally here to get rid of the sublists, so that all statement
    # nodes injected by this invocation of block mode `a` become gathered into
    # a single flat "master list".
    #
    # However, there's a piece of postprocessing we cannot do here: the splice
    # of the master list into the surrounding context. For that, we mark the
    # place for `splice_ast_literal_blocks`, which is the run-time part of the
    # surrounding block mode `q` (which allows it to operate on the whole
    # quoted tree).
    assert isinstance(tree, list)
    tree = flatten(tree)
    for stmt in tree:
        body = stmt.body if isinstance(stmt, ASTMarker) else stmt
        if not isinstance(body, ast.stmt):
            raise TypeError(f"`a` (block mode): expected statement nodes only, got {type(body)} with value {repr(body)}")
    return [_splice_ast_literal_block_marker] + tree

def splice_ast_literal_blocks(tree):
    """Splice block mode `a` AST literals into the surrounding context. Run-time part of block mode `q`."""
    assert isinstance(tree, list)  # block mode of `q` always produces a list of nodes

    # We do this recursively to splice also at any inner levels of the quoted
    # AST (e.g. `with a` inside an `if`). We have to be careful to splice only
    # output from block mode of `a`, because lists occur in many places in a
    # Python AST beside statement suites (e.g. `Assign` targets, the parameter
    # list in a function definition, ...).
    def doit(thing):
        if isinstance(thing, list):
            newthing = []
            for item in thing:
                if isinstance(item, list) and item and item[0] == _splice_ast_literal_block_marker:
                    elts = item[1:]
                    doit(elts)
                    newthing.extend(elts)
                else:
                    doit(item)
                    newthing.append(item)
            thing[:] = newthing
        elif isinstance(thing, ast.AST):
            for fieldname, value in ast.iter_fields(thing):
                if isinstance(value, list):
                    doit(value)
        else:
            raise TypeError(f"Expected `list` or AST node, got {type(thing)} with value {repr(thing)}")
    doit(tree)

    return tree


def ast_list(nodes):
    """Interpolate a `list` of AST nodes as an `ast.List` node. Run-time part of `s[]`."""
    if not isinstance(nodes, list):
        raise TypeError(f"`s[]`: expected an expression that evaluates to list, result was {type(nodes)} with value {repr(nodes)}")
    if not all(isinstance(tree, ast.AST) for tree in nodes):
        raise ValueError(f"`s[]`: expected a list of AST nodes, got {repr(nodes)}")
    return ast.List(elts=nodes)


def capture_value(value, name):
    """Hygienically capture a run-time value. Used by `h[]`.

    `value`: A run-time value. Must be picklable.
    `name`:  For human-readability.

    The return value is an AST that, when compiled and run, returns the
    captured value (even in another Python process later).
    """
    # If we didn't need to consider bytecode caching, we could just store the
    # value in a dictionary (that lives at the top level of `mcpyrate.quotes`)
    # that is populated at macro expansion time. Each unique value (by `id`)
    # could be stored only once.
    #
    # But we want to support bytecode caching. To avoid introducing hard-to-find
    # bugs into user code, we must provide consistent semantics, regardless of
    # whether updating of the bytecode cache is actually enabled or not (see
    # `sys.dont_write_bytecode`). So we must do the same thing regardless of
    # whether the captured value is used in the current process, or in another
    # Python process later.
    #
    # If the macro expansion result is to remain available for re-use from a
    # `.pyc`, we must serialize and store the captured value to disk, so that
    # values from "macro expansion time last week" are still available when the
    # `.pyc` is loaded in another Python process later.
    #
    # Modules are macro-expanded independently (no global finalization for the
    # whole codebase), and a `.pyc` may indeed later get loaded into some other
    # codebase that imports the same module, so we can't make a centralized
    # registry, like we could without bytecode caching.
    #
    # So really pretty much the only thing we can do reliably and simply is to
    # store a fresh serialized copy of the value at the capture location in the
    # source code, independently at each capture location.
    #
    # Putting these considerations together, we pickle the value, causing a copy
    # and serialization.
    #
    frozen_value = pickle.dumps(value)
    return ast.Call(_mcpyrate_quotes_attr("lookup_value"),
                    [ast.Tuple(elts=[ast.Constant(value=name),
                                     ast.Constant(value=frozen_value)])],
                    [])


_lookup_cache = {}
def lookup_value(key):
    """Look up a hygienically captured run-time value. Used by `h[]`.

    Usually there's no need to call this function manually; `capture_value`
    (and thus also `h[]`) will generate an AST that calls this automatically.
    """
    name, frozen_value = key
    cachekey = (name, id(frozen_value))  # id() so each capture instance behaves independently
    if cachekey not in _lookup_cache:
        _lookup_cache[cachekey] = pickle.loads(frozen_value)
    return _lookup_cache[cachekey]


def capture_macro(macro, name):
    """Hygienically capture a macro. Used by `h[]`.

    `macro`: A macro function. Must be picklable.
    `name`:  For human-readability. The recommended value is the name of
             the macro, as it appeared in the bindings of the expander
             it was captured from.

    The name of the captured macro is automatically uniqified using
    `gensym(name)`.

    The return value is an AST that, when compiled and run, injects the macro
    into the expander's global macro bindings table (even in another Python
    process later), and then evaluates to the uniqified macro name as an
    `ast.Name`, so that macro-expanding that AST will invoke the macro.
    """
    frozen_macro = pickle.dumps(macro)
    unique_name = gensym(name)
    return ast.Call(_mcpyrate_quotes_attr("lookup_macro"),
                    [ast.Tuple(elts=[ast.Constant(value=unique_name),
                                     ast.Constant(value=frozen_macro)])],
                    [])


def lookup_macro(key):
    """Look up a hygienically captured macro. Used by `h[]`.

    This injects the macro to the expander's global macro bindings table,
    and then returns the macro name, as an `ast.Name`.

    Usually there's no need to call this function manually; `capture_macro`
    (and thus also `h[]`) will generate an AST that calls this automatically.
    """
    unique_name, frozen_macro = key
    if unique_name not in global_bindings:
        global_bindings[unique_name] = pickle.loads(frozen_macro)
    return ast.Name(id=unique_name)

# --------------------------------------------------------------------------------
# The quasiquote compiler and uncompiler.

def astify(x, expander=None):  # like `macropy`'s `ast_repr`
    """Quasiquote compiler. Lift a value into its AST representation, if possible.

    When the AST is compiled and run, it will evaluate to `x`.

    Note the above implies that if `x` itself is an AST, then this produces
    an AST that, when compiled and run, will generate the AST `x`. This is
    the mechanism that `q` uses to produce the quoted AST.

    If the input is a `list` of ASTs (e.g. a statement suite), the return value
    is a single `ast.List` node, with its `elts` taken from the input list.
    However, most of the time it's not used this way, because `BaseMacroExpander`
    already translates a `visit` to a statement suite into visits to individual
    nodes, because `ast.NodeTransformer` requires that. The only exception is
    `q` in block mode; it'll produce a `List` this way.

    `expander` is a `BaseMacroExpander` instance, used for detecting macros
    inside `Capture` markers. Macros can be hygienically captured only if
    an `expander` is provided.

    Raises `TypeError` if the lifting fails.
    """
    def recurse(x):  # second layer just to auto-pass `expander` by closure.
        T = type(x)

        # Compile the unquote commands.
        #
        # Minimally, `astify` must support `ASTLiteral`; the others could be
        # implemented inside the unquote operators, as `ASTLiteral(ast.Call(...), "expr")`.
        # But maybe this approach is cleaner.
        if T is Unquote:  # `u[]`
            # We want to generate an AST that compiles to the *value* of `x.body`,
            # evaluated at the use site of `q`. But when the `q` expands, it is
            # too early. We must `astify` *at the use site* of `q`. So use an
            # `ast.Call` to delay until run-time, and pass in `x.body` as-is.
            return ast.Call(_mcpyrate_quotes_attr("astify"), [x.body], [])

        elif T is LiftSourcecode:  # `n[]`
            # Delay the identifier lifting, so it runs at the use site of `q`,
            # where the actual value of `x.body` becomes available.
            return ast.Call(_mcpyrate_quotes_attr('lift_sourcecode'),
                            [x.body,
                             ast.Constant(value=x.filename)],
                            [])

        elif T is ASTLiteral:  # `a`
            # Pass through this subtree as-is, but apply a run-time typecheck,
            # as well as some special run-time handling for block mode `a`.
            return ast.Call(_mcpyrate_quotes_attr('ast_literal'),
                            [x.body,
                             ast.Constant(value=x.syntax)],
                            [])

        elif T is ASTList:  # `s[]`
            return ast.Call(_mcpyrate_quotes_attr('ast_list'), [x.body], [])

        elif T is Capture:  # `h[]`
            if expander and type(x.body) is ast.Name:
                function = expander.isbound(x.body.id)
                if function:
                    # Hygienically capture a macro. We do this immediately,
                    # during the expansion of `q`, because the value we want to
                    # store, i.e. the macro function, is available only at
                    # macro-expansion time.
                    #
                    # This allows macros in scope at the use site of `q` to be
                    # hygienically propagated out to the use site of the macro
                    # that used `q`. So you can write macros that `q[h[macroname][...]]`,
                    # and `macroname` doesn't have to be macro-imported wherever
                    # that code gets spliced in.
                    return capture_macro(function, x.body.id)
            # Hygienically capture a garden variety run-time value.
            # At the use site of q[], this captures the value, and rewrites itself
            # into an AST that represents a lookup. At the use site of the macro
            # that used q[], that code runs, and looks up the captured value.
            return ast.Call(_mcpyrate_quotes_attr('capture_value'),
                            [x.body,
                             ast.Constant(value=x.name)],
                            [])

        # Builtin types. Mainly support for `u[]`, but also used by the
        # general case for AST node fields that contain bare values.
        elif T in (int, float, str, bytes, bool, type(None)):
            return ast.Constant(value=x)

        elif T is list:
            return ast.List(elts=list(recurse(elt) for elt in x))
        elif T is tuple:
            return ast.Tuple(elts=list(recurse(elt) for elt in x))
        elif T is dict:
            return ast.Dict(keys=list(recurse(k) for k in x.keys()),
                            values=list(recurse(v) for v in x.values()))
        elif T is set:
            return ast.Set(elts=list(recurse(elt) for elt in x))

        # We must support at least the `Done` AST marker, so that things like
        # coverage dummy nodes and expanded name macros can be astified.
        elif isinstance(x, Done):
            fields = [ast.keyword(a, recurse(b)) for a, b in ast.iter_fields(x)]
            node = ast.Call(_mcpyrate_quotes_attr('Done'),
                            [],
                            fields)
            return node

        # General case.
        elif isinstance(x, ast.AST):
            # TODO: Add support for astifying general ASTMarkers?
            # Otherwise the same as regular AST node, but need to refer to the
            # module it is defined in, and we don't have everything in scope here.
            if isinstance(x, ASTMarker):
                raise TypeError(f"Cannot astify internal AST markers, got {unparse(x)}")

            # The magic is in the Call. Take apart the input AST, and construct a
            # new AST, that (when compiled and run) will re-generate the input AST.
            #
            # We refer to the stdlib `ast` module as `mcpyrate.quotes.ast` to avoid
            # name conflicts at the use site of `q[]`.
            fields = [ast.keyword(a, recurse(b)) for a, b in ast.iter_fields(x)]
            node = ast.Call(ast.Attribute(value=_mcpyrate_quotes_attr('ast'),
                                          attr=x.__class__.__name__),
                            [],
                            fields)
            # Copy source location info for correct coverage reporting of a quoted block.
            #
            # The location info we fill in here is for the use site of `q`, which is
            # typically inside a macro definition. Coverage for a quoted line of code
            # means that the expansion of the quote contains input from that line.
            # It says nothing about the run-time behavior of that code.
            #
            # Running the AST produced by the quote re-produces the input AST, which is
            # indeed the whole point of quoting stuff. The AST is re-produced **without
            # any source location info**. The fact that *this* location info is missing,
            # on purpose, is the magic that allows the missing location fixer to fill
            # the correct location info at the final use site, i.e. the use site of the
            # macro that used `q`.
            node = ast.copy_location(node, x)
            return node

        raise TypeError(f"Don't know how to astify {repr(x)}")
    return recurse(x)


def unastify(tree):
    """Quasiquote uncompiler. Inverse of `astify`.

    `tree` must have been produced by `astify`. Otherwise raises `TypeError`.

    Essentially, this turns an AST representing quoted code back into an AST
    that represents that code directly, not quoted. So in a sense, `unastify`
    is a top-level unquote operator.

    Note subtle difference in meaning to `u[]`. The `u[]` operator interpolates
    a value from outside the quote context into the quoted representation - so
    that the value actually becomes quoted! - whereas `unastify` inverts the
    quote operation.

    Note also that `astify` compiles unquote commands into ASTs for calls to
    the run-time parts of the unquote operators. That's what `unastify` sees.
    We *could* detect those calls and uncompile them into AST markers, but we
    currently don't.

    The use case of `unastify` is higher-order macros, to transform a quoted
    AST at macro expansion time when the extra AST layer added by `astify` is
    still present. The recipe is `unastify`, process just like any AST, then
    quote again. (`expand` and `expand1` are examples of this.)

    If you just want to macro-expand a quoted AST, see `expand` and `expand1`.
    """
    # CAUTION: in `unastify`, we implement only what we minimally need.
    our_module_globals = globals()
    def lookup_thing(dotted_name):
        if not dotted_name.startswith("mcpyrate.quotes"):
            raise NotImplementedError
        path = dotted_name.split(".")
        if not all(component.isidentifier() for component in path):
            raise NotImplementedError
        if len(path) < 3:
            raise NotImplementedError
        name_of_thing = path[2]
        thing = our_module_globals[name_of_thing]
        if len(path) > 3:
            for attrname in path[3:]:
                thing = getattr(thing, attrname)
        return thing

    T = type(tree)

    if T is ast.Constant:
        return tree.value

    # Support machinery for `Call` AST node. This serendipitously supports also
    # *args and **kwargs, because as of Python 3.6 those appear in `args` and
    # `keywords`, and `Starred` needs no special support here.
    elif T is list:
        return [unastify(elt) for elt in tree]
    elif T is ast.keyword:
        return tree.arg, unastify(tree.value)

    elif T is ast.List:
        return [unastify(elt) for elt in tree.elts]
    elif T is ast.Tuple:
        return tuple(unastify(elt) for elt in tree.elts)
    elif T is ast.Dict:
        return {unastify(k): unastify(v) for k, v in zip(tree.keys, tree.values)}
    elif T is ast.Set:
        return {unastify(elt) for elt in tree.elts}

    elif T is ast.Call:
        dotted_name = unparse(tree.func)
        callee = lookup_thing(dotted_name)
        args = unastify(tree.args)
        kwargs = {k: v for k, v in unastify(tree.keywords)}
        node = callee(*args, **kwargs)
        node = ast.copy_location(node, tree)
        return node

    raise TypeError(f"Don't know how to unastify {unparse(tree)}")

# --------------------------------------------------------------------------------
# Quasiquote macros
#
# These operators are named after Qu'nash, the goddess of quasiquotes in high-tech-elven mythology.

_quotelevel = NestingLevelTracker()

def _expand_quasiquotes(tree, expander):
    """Expand quasiquote macros only."""
    # Use a second expander instance, with different bindings. Copy only the
    # bindings of the quasiquote macros from the main `expander`, accounting
    # for possible as-imports. This second expander won't even see other macros,
    # thus leaving them alone.
    bindings = {k: v for k, v in expander.bindings.items() if v in (q, u, n, a, s, h)}
    return MacroExpander(bindings, expander.filename).visit(tree)


def q(tree, *, syntax, expander, **kw):
    """[syntax, expr/block] quasiquote. Lift code into its AST representation."""
    if syntax not in ("expr", "block"):
        raise SyntaxError("`q` is an expr and block macro only")
    with _quotelevel.changed_by(+1):
        tree = _expand_quasiquotes(tree, expander)  # expand any inner quotes and unquotes first
        tree = astify(tree, expander)  # Magic part of `q`. Supply `expander` for `h[macro]` detection.

        ps = get_markers(tree, QuasiquoteMarker)  # postcondition: no remaining QuasiquoteMarkers
        if ps:
            assert False, f"QuasiquoteMarker instances remaining in output: {ps}"

        if syntax == 'block':
            # Generate AST to perform the assignment for `with q as quoted`.
            target = kw['optional_vars']  # List, Tuple, Name
            if target is None:
                raise SyntaxError("`q` (block mode) requires an asname to receive the quoted code")
            if type(target) is not ast.Name:
                raise SyntaxError(f"`q` (block mode) expected a single asname, got {unparse(target)}")
            # This `Assign` runs at the use site of `q`, it's not part of the
            # quoted code block. Here `tree` is a `List`, because the original
            # input was a `list` of AST nodes, and we ran it through `astify`.
            #
            # Because block mode `a` introduces the need to splice the interpolated
            # ASTs at run time into the surrounding context (which is only available
            # to the surrounding `q`), we inject a handler for that on the RHS here.
            tree = ast.Assign([target], ast.Call(_mcpyrate_quotes_attr('splice_ast_literal_blocks'),
                                                 [tree],
                                                 []))
        return tree


def u(tree, *, syntax, expander, **kw):
    """[syntax, expr] unquote. Splice a simple value into a quasiquote.

    The value is lifted into an AST that re-constructs that value.
    """
    if syntax != "expr":
        raise SyntaxError("`u` is an expr macro only")
    if _quotelevel.value < 1:
        raise SyntaxError("`u` encountered while quotelevel < 1")
    with _quotelevel.changed_by(-1):
        tree = expander.visit_recursively(tree)
        return Unquote(tree)


def n(tree, *, syntax, expander, **kw):
    """[syntax, expr] name-unquote. Parse a string, as Python source code, into an AST.

    With `n[]`, you can e.g. compute a name (e.g. by `mcpyrate.gensym`) for a
    variable and then use that variable in quasiquoted code - also as an assignment
    target. Things like `n[f"self.{x}"]` and `n[f"kitties[{j}].paws[{k}].claws"]`
    are also valid.

    The use case this operator was designed for is variable access (identifiers,
    attributes, subscripts, in any syntactically allowed nested combination) with
    computed names, but who knows what else can be done with it?

    The correct `ctx` is filled in automatically by the macro expander later.

    See also `n[]`'s sister, `a`.

    Generalized from `macropy`'s `n`, which converts a string into a variable access.
    """
    if syntax != "expr":
        raise SyntaxError("`n` is an expr macro only")
    if _quotelevel.value < 1:
        raise SyntaxError("`n` encountered while quotelevel < 1")
    with _quotelevel.changed_by(-1):
        tree = expander.visit_recursively(tree)
        return LiftSourcecode(tree, expander.filename)


def a(tree, *, syntax, expander, **kw):
    """[syntax, expr/block] AST-unquote. Splice an AST into a quasiquote.

    **Expression mode**::

        a[expr]

    `expr` must evaluate, at the use site of `q`, to an *expression* AST node.
    Typically, it is the name of a variable that holds such a node, but any
    kind of expression is fine.

    **Block mode**::

        with a:
            stmts
            ...

    Each `stmts` must evaluate to either a single *statement* AST node,
    or a `list` of *statement* AST nodes. Typically, it is the name of
    a variable that holds such data.

    This expands as if all those statements appeared in the `with` body,
    in the order listed.

    The `with` body must not contain anything else.

    See also `a`'s sister, `n[]`.
    """
    if syntax not in ("expr", "block"):
        raise SyntaxError("`a` is an expr and block macro only")
    if _quotelevel.value < 1:
        raise SyntaxError("`a` encountered while quotelevel < 1")
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("`a` (block mode) does not take an asname")

    with _quotelevel.changed_by(-1):
        tree = expander.visit_recursively(tree)

        if syntax == "expr":
            return ASTLiteral(tree, syntax)

        assert syntax == "block"
        # Block mode: strip `Expr` wrappers.
        #
        # When `a` expands, the elements of the list `tree` are `Expr` nodes
        # containing expressions. Typically each is just a `Name` node, or in
        # general, any expression that at run time evaluates to a statement AST
        # node, or to a list of statement AST nodes.
        #
        # We want to return, as an AST, a list of those expressions for processing
        # later.
        #
        # The value of the expressions become available when the use site of
        # `q` reaches run time. Because each expression may refer to a list of
        # AST nodes, the block mode of `q` injects a call to a postprocessor
        # that, at run time (once the values are available), will flatten the
        # quoted AST structure.
        out = []
        for stmt in tree:
            if type(stmt) is not ast.Expr:
                raise SyntaxError("`a` (block mode): each item in the body must be an expression (that at run time evaluates to a statement node or list of statement nodes)")
            out.append(stmt.value)
        return ASTLiteral(ast.List(elts=out), syntax)


def s(tree, *, syntax, expander, **kw):
    """[syntax, expr] list-unquote. Splice a `list` of ASTs, as an `ast.List`, into a quasiquote."""
    if syntax != "expr":
        raise SyntaxError("`s` is an expr macro only")
    if _quotelevel.value < 1:
        raise SyntaxError("`s` encountered while quotelevel < 1")
    with _quotelevel.changed_by(-1):
        tree = expander.visit_recursively(tree)
        return ASTList(tree)


def h(tree, *, syntax, expander, **kw):
    """[syntax, expr] hygienic-unquote. Splice any value, from the macro definition site, into a quasiquote.

    Supports also values that have no meaningful `repr`. The value is captured
    at the use site of the surrounding `q`.

    The value is frozen into the expanded source code as a pickled blob,
    separately at each use site of `h[]`. Thus the value must be picklable,
    and each capture will pickle it again.

    This is done to ensure the value will remain available, when the
    already-expanded code (due to `.pyc` caching) runs again in another
    Python process. (In other words, values from "macro expansion time
    last week" would not otherwise be available.)

    Supports also macros. To hygienically splice a macro invocation,
    `h[]` only the macro name.
    """
    if syntax != "expr":
        raise SyntaxError("`h` is an expr macro only")
    if _quotelevel.value < 1:
        raise SyntaxError("`h` encountered while quotelevel < 1")

    with _quotelevel.changed_by(-1):
        name = unparse(tree)

        # Expand macros in the unquoted expression. The only case we need to
        # look out for is a `@namemacro` if we have a `h[macroname]`. We're
        # only capturing it, so don't expand it just yet.
        expand = True
        if type(tree) is ast.Name:
            function = expander.isbound(tree.id)
            if function and isnamemacro(function):
                expand = False
        if expand:
            tree = expander.visit_recursively(tree)

        return Capture(tree, name)

# --------------------------------------------------------------------------------

def expand1q(tree, *, syntax, **kw):
    '''[syntax, expr/block] quote-then-expand-once.

    Quasiquote `tree`, then expand one layer of macros in it. Return the result
    quasiquoted.

    If your tree is already quasiquoted, use `expand1` instead.
    '''
    if syntax not in ("expr", "block"):
        raise SyntaxError("`expand1q` is an expr and block macro only")
    tree = q(tree, syntax=syntax, **kw)
    return expand1(tree, syntax=syntax, **kw)


def expandq(tree, *, syntax, **kw):
    '''[syntax, expr/block] quote-then-expand.

    Quasiquote `tree`, then expand it until no macros remain. Return the result
    quasiquoted. This operator is equivalent to `macropy`'s `q`.

    If your tree is already quasiquoted, use `expand` instead.
    '''
    if syntax not in ("expr", "block"):
        raise SyntaxError("`expandq` is an expr and block macro only")
    tree = q(tree, syntax=syntax, **kw)
    return expand(tree, syntax=syntax, **kw)

# --------------------------------------------------------------------------------

def expand1(tree, *, syntax, expander, **kw):
    '''[syntax, expr/block] expand one layer of macros in quasiquoted `tree`.

    The result remains in quasiquoted form.

    Like calling `expander.visit_once(tree)`, but for quasiquoted `tree`,
    and already at macro expansion time. Convenient for interactively expanding
    macros in quoted trees in the REPL.

    `tree` must be a quasiquoted AST; i.e. output from, or an invocation of,
    `q`, `expand1q`, `expandq`, `expand1`, or `expand`. Passing any other AST
    as `tree` raises `TypeError`.

    If your `tree` is not quasiquoted, `expand1q[...]` is a shorthand for
    `expand1[q[...]]`.
    '''
    if syntax not in ("expr", "block"):
        raise SyntaxError("`expand1` is an expr and block macro only")
    # We first invert the quasiquote operation, then use the garden variety
    # `expander` on the result, and then re-quote the expanded AST.
    #
    # The first `visit_once` makes any quote invocations inside this macro invocation expand first.
    # If the input `tree` is an already expanded `q`, it will do nothing, because any macro invocations
    # are then in a quoted form, which don't look like macro invocations to the expander.
    # If the input `tree` is a `Done`, it will likewise do nothing.
    tree = expander.visit_once(tree)  # -> Done(body=...)
    tree = expander.visit_once(unastify(tree.body))  # On wrong kind of input, `unastify` will `TypeError` for us.
    # The final piece of the magic, why this works in the expander's recursive mode,
    # without wrapping the result with `Done`, is that after `q` has finished, the output
    # will be a **quoted** AST, so macro invocations in it don't look like macro invocations.
    # Hence upon looping on the output, the expander finds no more macros.
    return q(tree.body, syntax=syntax, expander=expander, **kw)


def expand(tree, *, syntax, expander, **kw):
    '''[syntax, expr/block] expand quasiquoted `tree` until no macros remain.

    The result remains in quasiquoted form.

    Like calling `expander.visit_recursively(tree)`, but for quasiquoted `tree`,
    and already at macro expansion time. Convenient for interactively expanding
    macros in quoted trees in the REPL.

    `tree` must be a quasiquoted AST; i.e. output from, or an invocation of,
    `q`, `expand1q`, `expandq`, `expand1`, or `expand`. Passing any other AST
    as `tree` raises `TypeError`.

    If your `tree` is not quasiquoted, `expandq[...]` is a shorthand for
    `expand[q[...]]`.
    '''
    if syntax not in ("expr", "block"):
        raise SyntaxError("`expand` is an expr and block macro only")
    tree = expander.visit_once(tree)  # make the quotes inside this invocation expand first; -> Done(body=...)
    # Always use recursive mode, because `expand[...]` may appear inside
    # another macro invocation that uses `visit_once` (which sets the expander
    # mode to non-recursive for the dynamic extent of the `visit_once`).
    tree = expander.visit_recursively(unastify(tree.body))  # On wrong kind of input, `unastify` will `TypeError` for us.
    return q(tree, syntax=syntax, expander=expander, **kw)
