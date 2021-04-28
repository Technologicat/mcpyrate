**Navigation**

- [Main user manual](main.md)
- [Quasiquotes and `mcpyrate.metatools`](quasiquotes.md)
- [REPL and `macropython`](repl.md)
- [The `mcpyrate` compiler](compiler.md)
- **AST walkers**
- [Dialects](dialects.md)
- [Troubleshooting](troubleshooting.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Introduction](#introduction)
- [Attributes](#attributes)
- [Methods](#methods)
- [Terminating an ongoing visit](#terminating-an-ongoing-visit)
- [`macropy` `@Walker` porting guide](#macropy-walker-porting-guide)

<!-- markdown-toc end -->


# Introduction

```python
def kittify(mytree):
    class Kittifier(ASTTransformer):
        def transform(self, tree):
            if type(tree) is ast.Constant:
                self.collect(tree.value)
                tree.value = "meow!" if self.state.meows % 2 == 0 else "miaow!"
                self.state.meows += 1
            return self.generic_visit(tree)  # recurse
    w = Kittifier(meows=0)    # set the initial state here
    mytree = w.visit(mytree)  # it's basically an ast.NodeTransformer
    print(w.collected)        # collected values, in the order visited
    return mytree

def getmeows(mytree):
    class MeowCollector(ASTVisitor):
        def examine(self, tree):
            if type(tree) is ast.Constant and tree.value in ("meow!", "miaow!"):
                self.collect(tree)
            self.generic_visit(tree)
    w = MeowCollector()
    w.visit(mytree)
    print(w.collected)
    return w.collected
```

To bridge the feature gap between [`ast.NodeVisitor`](https://docs.python.org/3/library/ast.html#ast.NodeVisitor)/  [`ast.NodeTransformer`](https://docs.python.org/3/library/ast.html#ast.NodeTransformer) and `macropy`'s `Walker`, we provide `ASTVisitor` and `ASTTransformer` that can context-manage their state for different subtrees, while optionally collecting items across the whole walk. These can be found in the module [`mcpyrate.walkers`](../mcpyrate/walkers.py).

The walkers are based on `ast.NodeVisitor` and `ast.NodeTransformer`, respectively. So `ASTVisitor` only looks at the tree, gathering information from it, while `ASTTransformer` may perform edits.

The selling points of both are `withstate`, `state`, `collect`, `collected`, which see below.

For a realistic example, see [`mcpyrate.astfixers`](../mcpyrate/astfixers.py), or grep the `mcpyrate` codebase for other uses of `ASTVisitor` and `ASTTransformer` (there are a few).

Also, if you use quasiquotes, read [Treating hygienically captured values in AST walkers](quasiquotes.md#treating-hygienically-captured-values-in-ast-walkers).


# Attributes

Unless otherwise stated, each attribute is present in both `ASTVisitor` and `ASTTransformer`.

 - `state`: [`mcpyrate.bunch.Bunch`](../mcpyrate/bunch.py): stores named values as its attributes.

   Mutable. The whole `state` can also be replaced by simply rebinding it
   (`self.state = ...`).

   It's essentially a namespace, implemented as an object that internally stores
   things in a dict. The point of using `Bunch` is convenience in access syntax;
   `self.state.x` instead of `self.state['x']`.

   If you're familiar with `macropy`'s `Walker`, this replaces the `set_ctx`,
   `set_ctx_for` mechanism. For details, see [the porting guide](#macropy-walker-porting-guide) below.

 - `collected`: a `list` of collected values, in the order collected.


# Methods

Unless otherwise stated, each method is present in both `ASTVisitor` and `ASTTransformer`.

 - `__init__(k0=v0, ...)`: load the given bindings into the walker's initial state.

   The bindings can be accessed as `self.state.k0`, ...

 - `visit(tree)`: start walking the tree. Can also be used to manually recurse selectively.

   **Do not override this method**, override `examine` (`ASTVisitor`) or
   `transform` (`ASTTransformer`) instead.

   This method implements the `withstate` machinery and transparent
   handling of statement suites (i.e. lists of AST nodes).

   Unlike the standard library classes, we **don't** dispatch to different
   methods based on node type; there is only one `visit` method, and only one
   `examine` or `transform` method it delegates to.

   When visiting a single node, `visit` forwards the value returned by `examine` (`ASTVisitor`)
   or `transform` (`ASTTransformer`).

 - `examine(tree)` (`ASTVisitor` only): examine one node. **Abstract method, override this.**

    There is only one `examine` method. To detect node type, use `type(tree)`.

   *This method must recurse explicitly.* Use:

    - `self.generic_visit(tree)` to visit all children of `tree`.
    - `self.visit(tree.something)` to selectively visit only some children.
      Unlike in `ast.NodeVisitor`, it is ok to `visit` a statement suite directly;
      this will loop over the suite, visiting each node in it. (In that case
      there will be no return value.)

    As in `ast.NodeVisitor`:

    - Return value of `examine` is forwarded by `visit`.
    - `generic_visit` always returns `None`.

 - `transform(tree)` (`ASTTransformer` only): transform one node. **Abstract method, override this!**

   There is only one `transform` method. To detect the node type, use `type(tree)`.

   Return value should be as in `ast.NodeTransformer.visit`. Usually it is the
   updated `tree`. It can be a `list` of AST nodes to replace with multiple
   nodes (when syntactically admissible, i.e. in statement suites), or `None`
   to delete this subtree.

   *This method must recurse explicitly.*

   Just like in `ast.NodeTransformer.visit`, you'll only ever get an individual
   AST node passed in as `tree`; statement suites will be sent one node at a time.
   If you need to replace or delete a whole suite, you can do that when transforming
   the statement node the suite belongs to.

   Just like when using `ast.NodeTransformer`, call `self.generic_visit(tree)` to
   recurse into all children of `tree` (including each node in any contained suite).
   If you `generic_visit` at the end of `transform`, then just like in `ast.NodeTransformer`,
   there's the shorthand `return self.generic_visit(tree)` to first `generic_visit(tree)`
   and then `return tree`.

   To recurse selectively, `self.visit` the desired subtrees. Be sure to use `visit`,
   not `transform`, to make `withstate` updates take effect.
   
   Unlike in `ast.NodeTransformer`, it is ok to `visit` a statement suite
   directly; this will loop over the suite, visiting each node in it. When
   visiting a suite this way, the return values for each item in the suite are
   treated properly, so that if a `transform` call returns several nodes, those
   will be spliced in to replace the original node in the suite, and if it
   returns `None`, the corresponding node will be removed from the suite.

 - `generic_visit(tree)`: recurse into all children, including each node in any
   contained suite (i.e. a suite stored in an attribute of `tree`). Inherited
   from the standard library classes.
   
   - `ast.NodeVisitor.generic_visit(tree)` has no return value.
   - `ast.NodeTransformer.generic_visit(tree)` returns `tree`.

 - `collect(value)`: collect a value (any object). For convenience, return `value`.

   The collected values are placed in the list `self.collected`, which is
   retained across the whole walk.

 - `withstate(tree, k0=v0, ...)`: use an updated state while in a given subtree only.

   The current `self.state` is copied. The given bindings are merged into the
   copy, overwriting existing keys.

   When the walker enters the given `tree`, `self.state` becomes
   *temporarily replaced* by the updated state before calling `self.transform`.
   When the walker exits that `tree` (whether by normal exit or exception),
   the previous `self.state` is automatically restored.

   Any mutations to the updated state will then be lost - which is the
   whole point of `withstate`.

   The `tree` is identified by `id(tree)`, at the time when `visit` enters it.

   If you need to store something globally across the walk (and the use case
   is different from collecting items), just write into a regular attribute of
   `self`. Note `self.reset` won't clear any attributes you add, so you might
   then want to override that, too (co-operatively; be sure to call
   `super().reset`).

   For `withstate`, `tree` can be an AST node, or a statement suite (`list` of
   AST nodes). If it is a statement suite, this is exactly equivalent to
   looping `withstate` over each node in the list.

   Nested subtrees can be `withstate`'d. The temporarily stashed previous
   states are kept on a stack.

 - `generic_withstate(tree, k0=v0, ...)`: use an updated state while in the
   **children** of `tree` only.
   
   *Added in v3.2.2.*

   Note the children are iterated over when you call `generic_withstate`;
   the walker behaves just as if `withstate` was called for each of those
   children. It won't notice if you then swap out some children or insert
   new ones.
   
   The point is to save you the trouble of worrying about the names of the
   attributes holding child nodes or lists of child nodes, if you just want
   to set a new state for all children; this iterates over them automatically.

   This implies also that you then have to either `generic_visit(tree)` or
   visit those children explicitly in order for the state update to trigger.
   That is, if you skip a level in the AST by visiting a grandchild directly,
   the state won't update, because the node the state update was registered for
   is then never visited.

   The state instance is shared between the children (just like when calling
   `withstate` for a statement suite).

   This method has a silly name, because it relates to `withstate` as
   the standard `generic_visit` relates to the standard `visit`.

   Generally speaking:

     - `generic_withstate(tree, ...)` should be used if you then intend to
       `generic_visit(tree)`, which recurses into the children of `tree`.

     - `withstate(subtree, ...)` should be used if you then intend to
       `visit(subtree)`, which recurses into that node (or suite) only.

   It is possible to mix and match if you think through what you're doing.

 - `reset(k0=v0, ...)`: clear the whole state stack and `self.collected`.

   Load the given bindings into the new, otherwise blank initial state. 

   Use this to prepare for walking another unrelated tree, if you want to
   reuse the same `ASTVisitor` or `ASTTransformer` instance.


# Terminating an ongoing visit

There are two ways to terminate an ongoing visit:

 - Recursion is explicit; simply don't recurse further. This assumes that the levels further up the call stack will co-operate.
 - Raise an exception. This will immediately exit the whole visit, assuming that the levels further up the call stack won't catch the exception.
 
Pattern for the second strategy:

```python
def getmeows(mytree):
    class DetectionFinished(Exception):
        pass
    class MeowDetector(ASTVisitor):
        def examine(self, tree):
            if type(tree) is ast.Constant and tree.value in ("meow!", "miaow!"):
                raise DetectionFinished
            self.generic_visit(tree)
    w = MeowCollector()
    try:
        w.visit(mytree)
    except DetectionFinished:  # found at least one "meow!" or "miaow!"
        return True
    return False
```


# `macropy` `@Walker` porting guide

If you're a seasoned `macropy` user with lots of AST-walking macro code based on `macropy.core.walkers.Walker` that you'd like to port to use `mcpyrate`, this section may help. These notes arose from my experiences with porting `unpythonic.syntax` [[docs](https://github.com/Technologicat/unpythonic/blob/master/doc/macros.md)] [[source code](https://github.com/Technologicat/unpythonic/tree/master/unpythonic/syntax)], a rather large kitchen-sink language-extension macro package, to use `mcpyrate` as the macro expander.

This section summarizes the important points. For many real-world examples, look at `unpythonic.syntax`, particularly any use sites of `ASTTransformer` and `ASTVisitor`.


- **Starting point**: you have something like this `macropy` code:

  ```python
  from macropy.core.walkers import Walker

  @Walker
  def transform(tree, ..., **kw)
      ...

  tree = transform.recurse(tree)
  ```

  To port this to `mcpyrate`, start with:

  ```python
  from mcpyrate.walkers import ASTTransformer

  class MyTransformer(ASTTransformer):
      def transform(self, tree):
          ...  # paste implementation here and then modify

  tree = MyTransformer().visit(tree)
  ```

  Keep in mind the above documentation on `mcpyrate`'s walkers. This is the exam. ;)

  The abstraction is more explicit than `macropy`'s, along the lines of the standard `ast.NodeTransformer`, but `ASTTransformer` has the extra bells and whistles that allow it to do the same things `macropy`'s `Walker` does.

  You may also want an `ASTVisitor` instead (and implement `examine` instead of `transform`), if you're just collecting stuff from the AST; then there's no danger of accidentally mutating the input.

- When invoking the walker (to start it up, from the outside), there's no `recurse`, `collect`, or `recurse_collect`.

  To **visit and collect** (equivalent to `collect`):

  ```python
  class MyVisitor(ASTVisitor):
      ...
  mv = MyVisitor()
  mv.visit(tree)  # tree is not modified
  collected = mv.collected
  ```

  To **transform and collect** (equivalent to `recurse_and_collect`):

  ```python
  class MyTransformer(ASTTransformer):
      ...
  mt = MyTransformer()
  tree = mt.visit(tree)
  collected = mt.collected 
  ```

  To **just transform** (equivalent to `recurse`):

  ```python
  class MyTransformer(ASTTransformer):
      ...
  tree = MyTransformer().visit(tree)
  ```

- When invoking the walker from the inside, to recurse explicitly, use `self.visit` or `self.generic_visit`, as appropriate. There is no need to manage collected items when doing so; these are retained across the whole walk.
  - This also implies that if you want to use the same walker instance to process another, unrelated tree, `reset()` it first.

- For stateful walkers, initial state is loaded using constructor arguments. For example:

  ```python
  tree = MyTransformer(kittiness=0).visit(tree)
  ```

  This sets `self.state.kittiness = 0` at the start of the visit.

- **There are no kwargs** to the `transform` (or `examine`) method.
  - Particularly, `collect(thing)` becomes `self.collect(thing)`. Once done, the results are in the `collected` attribute of your walker instance.

  - **There is no `stop()`**, because there is no automatic recursion. Instead, `mcpyrate` expects you to explicitly tell it where to recurse.
    
    **This is the part where you may have to stop and think**, because this may require inverting some logic or arranging things differently.

    - Each code path in your `macropy` implementation that calls `stop()`, in `mcpyrate` should end with `return tree` or something similar. This means recursion on all children is **not** desired on that code path.
      - Usually before that code path returns, it will also want to `self.visit` some particular subtrees to recurse selectively, for example `tree.body = self.visit(tree.body)`.
    - Each code path in your `macropy` implementation that **doesn't** call `stop()`, in `mcpyrate` should end with `return self.generic_visit(tree)` or something similar. This explicitly recurses on all children of `tree`.
      - Especially, this includes the default do-nothing path that triggers when `tree` does not match what you want to modify or look at. That is, the default case should usually be `return self.generic_visit(tree)`.

- **Management of the walker state** is the other part where you may have to stop and think.
  - State is passed to the walker function differently.
    - In `macropy`, the walker state is automatically copied into local variables, simply by virtue of that state being passed in to the walker function as arguments.
    - In `mcpyrate`, `self.state` is global across the whole walk (unless overridden), so if you mutate it, the mutations will persist over the walk. Often this is not what you want.
    - To obtain `macropy`-like behavior in `mcpyrate`, you can explicitly copy from attributes of `self.state` into local variables at the start of your `transform` (or `examine`) function, for example `kittiness = self.state.kittiness`.

  - The API to process a subtree with temporarily updated state is different.
    - `set_ctx(k0=v0)` often becomes `self.generic_withstate(tree, k0=v0)`. There is no concept of *current tree*, so you are expected to pass `tree` explicitly.
      - You can also use `self.withstate(somesubtree, k0=v0)` if you only need the new state for some particular subtree, not for all children of `tree`.
      - If you need to set several state variables (in the example, not just `k0` but also `k1`, `k2`, ...), they must be passed as kwargs **in the same call**. Each call to `withstate` or `generic_withstate`, that registers a new state for the same AST nodes, will **completely override** the previously registered state. This is different from `macropy` where you would send one binding per call to `set_ctx`.
      - Make note of the difference between `withstate` and `generic_withstate`, and think through which to use where. In short, `generic_withstate` relates to `withstate` as `generic_visit` relates to `visit`.

    - `set_ctx_for(subtree, k0=v0)` becomes `self.withstate(subtree, k0=v0)`.

    - In `macropy`, when you use `stop()`, you'll often explicitly recurse selectively, and while doing so, pass updated state variables directly to `recurse`, `collect` or `recurse_collect`, for example:

      ```python
      stop()

      tree.body = transform.recurse(tree.body, k0=v0, k1=v1)
  
      return tree  # does not recurse, because `stop()` has been called
      ```

      In `mcpyrate` this becomes:

      ```python
      # `mcpyrate` does not use stop()
  
      self.withstate(tree.body, k0=v0, k1=v1)
      tree.body = self.visit(tree.body)
  
      return tree  # does not recurse, because no explicit recursion call!
      ```

    - Note that you can `visit` a statement suite directly (no need to iterate over nodes in it), since `ASTTransformer` handles this detail.
