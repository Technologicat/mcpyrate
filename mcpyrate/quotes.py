# -*- coding: utf-8; -*-
"""Quasiquotes. Build ASTs in your macros, using syntax that mostly looks like regular code.

The macro operators `q`, `u`, `n`, `a`, `s`, `h` are the primary API.

The functions `capture_value` and `capture_as_macro` are public, so you can get the
benefits of hygienic capture also in old-school macros that build ASTs manually
without using quasiquotes.

The `astify` and `unastify` functions are the low-level quasiquote compiler
and uncompiler, respectively.
"""

__all__ = ["capture_value", "capture_macro", "capture_as_macro",
           "astify", "unastify",
           "q", "u", "n", "a", "s", "t", "h"]

import ast
import pickle

from .core import global_bindings, Done, MacroExpansionError
from .expander import MacroExpander, isnamemacro
from .markers import ASTMarker, check_no_markers_remaining
from .unparser import unparse, unparse_with_fallbacks
from .utils import gensym, scrub_uuid, flatten, extract_bindings, NestingLevelTracker


def _mcpyrate_quotes_attr(attr):
    """Create an AST that, when compiled and run, looks up `mcpyrate.quotes.attr`."""
    mcpyrate_quotes_module = ast.Attribute(value=ast.Name(id="mcpyrate"), attr="quotes")
    return ast.Attribute(value=mcpyrate_quotes_module, attr=attr)


class QuasiquoteMarker(ASTMarker):
    """Base class for AST markers used by quasiquotes. Compiled away by `astify`."""
    pass

class SpliceNodes(QuasiquoteMarker):
    """Splice a `list` of AST nodes into the surrounding context.

    Command sent by `ast_literal` (run-time part of `a`)
    to `splice_ast_literals` (run-time part of the surrounding `q`).
    """
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
    """Interpolate the given iterable of AST nodes as an `ast.List` node. Emitted by `s[]`."""
    pass


class ASTTuple(QuasiquoteMarker):
    """Interpolate the given iterable of AST nodes as an `ast.Tuple` node. Emitted by `t[]`."""
    pass


class Capture(QuasiquoteMarker):  # like `macropy`'s `Captured`
    """Capture given subtree hygienically. Emitted by `h[]`.

    Details: capture the value or macro name the given subtree evaluates to,
    at the use site of `q`. The value or macro reference is frozen (by pickle)
    so that it can be restored also in another Python process later.

    (It is important hygienic captures can be restored across process boundaries,
    to support bytecode caching for source files that invoke a macro that uses
    `h[]` in its output.)
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


def _typecheck(node, cls, macroname):
    body = node.body if isinstance(node, ASTMarker) else node
    if not isinstance(body, cls):
        raise TypeError(f"{macroname}: expected an expression node, got {type(body)} with value {repr(body)}")

def _flatten_and_typecheck_iterable(nodes, cls, macroname):
    try:
        lst = list(nodes)
    except TypeError:
        raise TypeError(f"{macroname}: expected an iterable of AST nodes, got {type(nodes)} with value {repr(nodes)}")
    lst = flatten(lst)
    for node in lst:
        _typecheck(node, cls, macroname)
    return lst

def ast_literal(tree, syntax):
    """Perform run-time typecheck on AST literal `tree`. Run-time part of `a`.

    If `tree` is a run-time iterable, convert it to a `list`, flatten that `list`
    locally, and inject a run-time marker for `splice_ast_literals`, to indicate
    where splicing into the surrounding context is needed.
    """
    if syntax not in ("expr", "block"):
        raise TypeError(f"expected `syntax` either 'expr' or 'block', got {type(syntax)} with value {repr(syntax)}")

    if syntax == "expr":
        if isinstance(tree, ast.AST):
            _typecheck(tree, ast.expr, "`a` (expr mode)")
            return tree
        else:
            lst = _flatten_and_typecheck_iterable(tree, ast.expr, "`a` (expr mode)")
            return SpliceNodes(lst)

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
    # place for `splice_ast_literals`, which is the run-time part of the
    # surrounding block mode `q` (which allows it to operate on the whole
    # quoted tree).
    #
    # The splicer must splice only places marked by us, because lists occur
    # in many places in a Python AST beside statement suites (e.g. `Assign`
    # targets, the parameter list in a function definition, ...).
    lst = _flatten_and_typecheck_iterable(tree, ast.stmt, "`a` (block mode)")
    return SpliceNodes(lst)


def splice_ast_literals(tree, filename):
    """Splice list-valued `a` AST literals into the surrounding context. Run-time part of `q`."""
    # We do this recursively to splice also at any inner levels of the quoted
    # AST (e.g. `with a` inside an `if`).
    def doit(thing):
        if isinstance(thing, list):
            newthing = []
            for item in thing:
                if isinstance(item, SpliceNodes):
                    doit(item.body)
                    # Discard the `SpliceNodes` marker and splice the `list` that was contained in it.
                    newthing.extend(item.body)
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

    try:
        check_no_markers_remaining(tree, filename=filename, cls=SpliceNodes)
    except MacroExpansionError:
        err = RuntimeError("`q`: `SpliceNodes` markers remaining after expansion, likely a misplaced `a` unquote; did you mean `s[]` or `t[]`?")
        # The list of remaining markers is not very useful, suppress it
        # (but leave it available for introspection in the `__context__` attribute).
        err.__suppress_context__ = True
        raise err

    return tree


def ast_list(nodes):
    """Interpolate an iterable of expression AST nodes as an `ast.List` node. Run-time part of `s[]`."""
    lst = _flatten_and_typecheck_iterable(nodes, ast.expr, "`s[]`")
    return ast.List(elts=lst)


def ast_tuple(nodes):
    """Interpolate an iterable of expression AST nodes as an `ast.Tuple` node. Run-time part of `t[]`."""
    lst = _flatten_and_typecheck_iterable(nodes, ast.expr, "`t[]`")
    return ast.Tuple(elts=lst)


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
    `ast.Name`.
    """
    if not callable(macro):
        raise TypeError(f"`macro` must be callable (a macro function), got {type(macro)} with value {repr(macro)}")
    # Scrub any previous UUID suffix from the macro name. We'll get those when
    # `unastify` uncompiles a hygienic macro capture, and then `astify`
    # compiles the result again.
    frozen_macro = pickle.dumps(macro)
    name = scrub_uuid(name)
    return ast.Call(_mcpyrate_quotes_attr("lookup_macro"),
                    [ast.Tuple(elts=[ast.Constant(value=name),
                                     ast.Constant(value=gensym(name)),
                                     ast.Constant(value=frozen_macro)])],
                    [])


def capture_as_macro(macro):
    """Hygienically capture a macro function as a macro, manually.

    Like `capture_macro`, but with one less level of delay. This injects the
    macro into the expander's global bindings table immediately, and returns
    the uniqified `ast.Name` that can be used to refer to it.

    The name is taken automatically from the name of the macro function.
    """
    if not callable(macro):
        raise TypeError(f"`macro` must be callable (a macro function), got {type(macro)} with value {repr(macro)}")
    frozen_macro = pickle.dumps(macro)
    name = macro.__name__
    return lookup_macro((name, gensym(name), frozen_macro))


def lookup_macro(key):
    """Look up a hygienically captured macro. Used by `h[]`.

    This injects the macro to the expander's global macro bindings table,
    and then returns the macro name, as an `ast.Name`.

    Usually there's no need to call this function manually; `capture_macro`
    (and thus also `h[]`) will generate an AST that calls this automatically.
    """
    name, unique_name, frozen_macro = key
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

    If the input is a `list` of ASTs (e.g. body of block mode `q`), the return value
    is a single `ast.List` node, with its `elts` taken from the input list
    (after recursing into each element).

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
            return ast.Call(_mcpyrate_quotes_attr("lift_sourcecode"),
                            [x.body,
                             ast.Constant(value=x.filename)],
                            [])

        elif T is ASTLiteral:  # `a`
            # Pass through this subtree as-is, but apply a run-time typecheck,
            # as well as some special run-time handling for `list`s of AST nodes.
            return ast.Call(_mcpyrate_quotes_attr("ast_literal"),
                            [x.body,
                             ast.Constant(value=x.syntax)],
                            [])

        elif T is ASTList:  # `s[]`
            return ast.Call(_mcpyrate_quotes_attr("ast_list"), [x.body], [])

        elif T is ASTTuple:  # `t[]`
            return ast.Call(_mcpyrate_quotes_attr("ast_tuple"), [x.body], [])

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
            return ast.Call(_mcpyrate_quotes_attr("capture_value"),
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
            node = ast.Call(_mcpyrate_quotes_attr("Done"),
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
            node = ast.Call(ast.Attribute(value=_mcpyrate_quotes_attr("ast"),
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
    """Quasiquote uncompiler. Approximate inverse of `astify`.

    `tree` must have been produced by `astify`. Otherwise raises `TypeError`.

    This turns an "astified" AST, that represents code to construct a run-time
    AST value, back into a direct AST. So in a sense, `unastify` is a top-level
    unquote operator.

    Note subtle difference in meaning to `u[]`. The `u[]` operator interpolates
    a value from outside the quote context into the quoted representation - so
    that the value actually becomes quoted! - whereas `unastify` inverts the
    quote operation.

    Note also that `astify` compiles unquote AST markers into ASTs for calls to
    the run-time parts of the unquote operators. `unastify` uncompiles those
    calls back into the corresponding AST markers. That's the best we can do;
    the only context that has the user-provided names (where the unquoted data
    comes from) in scope is each particular use site of `q`, at its run time.

    The use case of `unastify` is to transform a quoted AST at macro expansion
    time when the extra AST layer added by `astify` is still present. The
    recipe is `unastify`, process just like any AST, then quote again.
    (`expands` and `expand1s` in `mcpyrate.metatools` are examples of this.)

    If you just want to macro-expand a quoted AST in the REPL, see the `expand`
    family of macros. Prefer the `r` variants; they expand at run time, so
    you'll get the final AST with the actual unquoted values spliced in.
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

        # Even though the unquote operators compile into calls, `unastify`
        # must not apply their run-time parts, because it's running in the
        # wrong context. Those only work properly at run time, and they
        # must run at the use site of `q`, where the user-provided names
        # (where the unquoted data comes from) will be in scope.
        #
        # So we undo what `astify` did, converting the unquote calls back into
        # the corresponding AST markers.
        if dotted_name == "mcpyrate.quotes.astify":  # `u[]`
            body = tree.args[0]
            return Unquote(body)
        elif dotted_name == "mcpyrate.quotes.lift_sourcecode":  # `n[]`
            body, filename = tree.args[0], tree.args[1].value
            return LiftSourcecode(body, filename)
        elif dotted_name == "mcpyrate.quotes.ast_literal":  # `a[]`
            body, syntax = tree.args[0], tree.args[1].value
            return ASTLiteral(body, syntax)
        elif dotted_name == "mcpyrate.quotes.ast_list":  # `s[]`
            body = tree.args[0]
            return ASTList(body)
        elif dotted_name == "mcpyrate.quotes.ast_tuple":  # `t[]`
            body = tree.args[0]
            return ASTTuple(body)
        elif dotted_name == "mcpyrate.quotes.capture_value":  # `h[]` (run-time value)
            body, name = tree.args[0], tree.args[1].value
            return Capture(body, name)
        elif dotted_name == "mcpyrate.quotes.lookup_macro":  # `h[]` (macro)
            # `capture_macro` is gone and done by the time we get here.
            # `astify` has generated an `ast.Call` to `lookup_macro`.
            #
            # To make the this work properly even across process boundaries,
            # we cannot simply run the `lookup_macro`. It injects the binding
            # once, and then becomes an inert lexical name (pointing to that
            # binding) - so that strategy only works inside the same process.
            #
            # We can't just leave the `lookup_macro` call in the AST, either,
            # since that doesn't make any sense when the tree is later sent
            # to `astify` to compile it again (we don't want another `ast.Call`
            # layer around it).
            #
            # So we need something that triggers `capture_macro` when the
            # result is astified again.
            #
            # Hence, we uncompile the `lookup_macro` into a `Capture` marker.
            #
            # But if the astified tree comes from an earlier run (in another
            # Python process), the original macro name might not be in the
            # expander's bindings any more.
            #
            # So we inject the captured macro into the expander's global
            # bindings table now (by calling `lookup_macro`), and make the
            # uncompiled capture command capture that macro.
            #
            # This does make the rather mild assumption that our input tree
            # will be astified again in the same Python process, in order for
            # the uncompiled capture to succeed when `astify` compiles it.
            key = tree.args[0]
            assert type(key) is ast.Tuple
            assert all(type(elt) is ast.Constant for elt in key.elts)
            name, unique_name, frozen_macro = [elt.value for elt in key.elts]
            uniquename_node = lookup_macro((name, unique_name, frozen_macro))
            return Capture(uniquename_node, name)

        else:
            # General case: an astified AST node.
            callee = lookup_thing(dotted_name)
            args = unastify(tree.args)
            kwargs = {k: v for k, v in unastify(tree.keywords)}
            node = callee(*args, **kwargs)
            node = ast.copy_location(node, tree)
            return node

    raise TypeError(f"Don't know how to unastify {unparse_with_fallbacks(tree, debug=True, color=True)}")

# --------------------------------------------------------------------------------
# Quasiquote macros
#
# These operators are named after Qu'nasth, the goddess of quasiquotes in high-tech-elven mythology.

_quotelevel = NestingLevelTracker()

def _expand_quasiquotes(tree, expander):
    """Expand quasiquote macros only."""
    # Use a second expander instance, with different bindings. Copy only the
    # bindings of the quasiquote macros from the main `expander`, accounting
    # for possible as-imports. This second expander won't even see other macros,
    # thus leaving them alone.
    bindings = extract_bindings(expander.bindings, q, u, n, a, s, t, h)
    return MacroExpander(bindings, expander.filename).visit(tree)


def q(tree, *, syntax, expander, **kw):
    """[syntax, expr/block] quasiquote. Lift code into its AST representation."""
    if syntax not in ("expr", "block"):
        raise SyntaxError("`q` is an expr and block macro only")
    with _quotelevel.changed_by(+1):
        tree = _expand_quasiquotes(tree, expander)  # expand any inner quotes and unquotes first
        tree = astify(tree, expander)  # Magic part of `q`. Supply `expander` for `h[macro]` detection.
        # `astify` should compile the unquote commands away, and `SpliceNodes`
        # markers only spring into existence when the run-time part of `a` runs
        # (for communication with the run-time part of the surrounding `q`).
        # So at this point, there should be no quasiquote markers in `tree`.
        try:
            check_no_markers_remaining(tree, filename=expander.filename, cls=QuasiquoteMarker)
        except MacroExpansionError as err:
            raise RuntimeError("`q`: internal error in quasiquote system") from err

        # `a` introduces the need to splice any interpolated `list`s of ASTs at
        # run time into the surrounding context (which is only available to the
        # surrounding `q`). Inject a handler for that.
        #
        # Block mode `a` always produces a `list` of statement AST nodes.
        #
        # For expression mode `a`, a `list` of expression AST nodes is valid
        # e.g. in a function call argument position, to splice the list into
        # positional arguments of the `Call`.
        tree = ast.Call(_mcpyrate_quotes_attr("splice_ast_literals"),
                        [tree,
                         ast.Constant(value=expander.filename)],
                        [])

        if syntax == "block":
            # Generate AST to perform the assignment for `with q as quoted`.
            target = kw["optional_vars"]  # List, Tuple, Name
            if target is None:
                raise SyntaxError("`q` (block mode) requires an asname to receive the quoted code")
            if type(target) is not ast.Name:
                raise SyntaxError(f"`q` (block mode) expected a single asname, got {unparse(target)}")
            # This `Assign` runs at the use site of `q`, it's not part of the
            # quoted code block. The statement nodes are packed into a `List` node,
            # because the original `tree` was a `list` of AST nodes (because block mode),
            # and we ran it through `astify`.
            tree = ast.Assign([target], tree)
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
    """[syntax, expr/block] ast-unquote. Splice an AST into a quasiquote.

    **Expression mode**::

        a[expr]

    The expression `expr` must evaluate, at run time at the use site of the
    surrounding `q`, to an *expression* AST node, an AST marker containing
    an *expression* AST node in its `body` attribute, or in certain contexts
    where that is valid in the AST, a `list` of such values.

    Typically, `expr` is the name of a variable that holds such data, but
    it doesn't have to be; any expression that evaluates to acceptable data
    is fine.

    An example of a context that accepts a `list` of expression nodes is the
    positional arguments of a function call. `q[myfunc(a[args])]` will splice
    the `list` `args` into the positional arguments of the `Call`. Of course,
    ast-unquoting single positional arguments such as `q[myfunc(a[arg1], a[arg2])]`
    is also fine.

    **Block mode**::

        with a:
            stmts
            ...

    Each `stmts` must evaluate, at run time at the use site of the surrounding `q`,
    to a *statement* AST node, an AST marker containing a *statement* AST node in
    its `body` attribute, or a `list` of such values.

    Typically, `stmts`t is the name of a variable that holds such data, but
    it doesn't have to be; any expression that evaluates to acceptable data
    is fine.

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
        # containing expressions. Typically each expression is just a `Name`
        # node, or in general, any expression that at run time evaluates to
        # a statement AST node, or to an iterable of statement AST nodes.
        #
        # We want to return, as an AST, a list of those expressions for processing
        # later.
        #
        # The value of the expressions become available when the use site of
        # `q` reaches run time. Because each expression may refer to a list of
        # AST nodes, `q` injects a call to a postprocessor that, at run time
        # (once the values are available), will flatten the quoted AST structure.
        out = []
        for stmt in tree:
            if type(stmt) is not ast.Expr:
                raise SyntaxError("`a` (block mode): each item in the body must be an expression (that at run time evaluates to a statement node or iterable of statement nodes)")
            out.append(stmt.value)
        return ASTLiteral(ast.List(elts=out), syntax)


def s(tree, *, syntax, expander, **kw):
    """[syntax, expr] ast-list-unquote. Splice an iterable of ASTs, as an `ast.List`, into a quasiquote."""
    if syntax != "expr":
        raise SyntaxError("`s` is an expr macro only")
    if _quotelevel.value < 1:
        raise SyntaxError("`s` encountered while quotelevel < 1")
    with _quotelevel.changed_by(-1):
        tree = expander.visit_recursively(tree)
        return ASTList(tree)


def t(tree, *, syntax, expander, **kw):
    """[syntax, expr] ast-tuple-unquote. Splice an iterable of ASTs, as an `ast.Tuple`, into a quasiquote."""
    if syntax != "expr":
        raise SyntaxError("`t` is an expr macro only")
    if _quotelevel.value < 1:
        raise SyntaxError("`t` encountered while quotelevel < 1")
    with _quotelevel.changed_by(-1):
        tree = expander.visit_recursively(tree)
        return ASTTuple(tree)


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
