# AST walkers

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

To bridge the feature gap between [`ast.NodeVisitor`](https://docs.python.org/3/library/ast.html#ast.NodeVisitor)/  [`ast.NodeTransformer`](https://docs.python.org/3/library/ast.html#ast.NodeTransformer) and `macropy`'s `Walker`, we provide `ASTVisitor` and `ASTTransformer` that can context-manage their state for different subtrees, while optionally collecting items across the whole walk. These can be found in the module [`mcpyrate.walkers`](mcpyrate/walkers.py).

The walkers are based on `ast.NodeVisitor` and `ast.NodeTransformer`, respectively. So `ASTVisitor` only looks at the tree, gathering information from it, while `ASTTransformer` may perform edits.

The selling points of both are `withstate`, `state`, `collect`, `collected`, which see below.

For a realistic example, see [`mcpyrate.astfixers`](mcpyrate/astfixers.py), or grep the `mcpyrate` codebase for other uses of `ASTVisitor` and `ASTTransformer` (there are a few).

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [AST walkers](#ast-walkers)
    - [Attributes](#attributes)
    - [Methods](#methods)
    - [Terminating an ongoing visit](#terminating-an-ongoing-visit)

<!-- markdown-toc end -->


## Attributes

Unless otherwise stated, each attribute is present in both `ASTVisitor` and `ASTTransformer`.

 - `state`: [`mcpyrate.bunch.Bunch`](mcpyrate/bunch.py): stores named values as its attributes.

   Mutable. The whole `state` can also be replaced by simply rebinding it
   (`self.state = ...`).

   It's essentially a namespace, implemented as an object that internally stores
   things in a dict. The point of using `Bunch` is convenience in access syntax;
   `self.state.x` instead of `self.state['x']`.

   If you're familiar with `macropy`'s `Walker`, this replaces the `set_ctx`,
   `set_ctx_for` mechanism. Mutating the state directly is equivalent to
   `set_ctx`, and `self.withstate(tree, k0=v0, ...)` is equivalent to `set_ctx_for`.

 - `collected`: a `list` of collected values, in the order collected.


## Methods

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

 - `reset(k0=v0, ...)`: clear the whole state stack and `self.collected`.

   Load the given bindings into the new, otherwise blank initial state. 

   Use this to prepare for walking another unrelated tree, if you want to
   reuse the same `ASTVisitor` or `ASTTransformer` instance.


## Terminating an ongoing visit

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
