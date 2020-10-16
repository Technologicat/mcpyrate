# AST walker

```python
    def kittify(mytree):
        class Kittifier(Walker):
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
```

To bridge the feature gap between
[`ast.NodeTransformer`](https://docs.python.org/3/library/ast.html#ast.NodeTransformer)
and MacroPy's `Walker`, we provide `mcpyrate.walker.Walker`, a zen-minimalistic
AST walker base class based on `ast.NodeTransformer`, that can context-manage
its state for different subtrees, while optionally collecting items across the
whole walk.

The selling points are `withstate`, `state`, `collect`, `collected`, which see below.

For a realistic example, see [`mcpyrate.astfixers`](mcpyrate/astfixers.py).

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [AST walker](#ast-walker)
    - [Attributes](#attributes)
    - [Methods](#methods)

<!-- markdown-toc end -->


## Attributes

 - `state`: [`mcpyrate.bunch.Bunch`](mcpyrate/bunch.py): stores named values as its attributes.

   Mutable. The whole `state` can also be replaced by simply rebinding it
   (`self.state = ...`).

   It's essentially a namespace, implemented as an object that internally stores
   things in a dict. The point of using `Bunch` is convenience in access syntax;
   `self.state.x` instead of `self.state['x']`.

   If you're familiar with MacroPy's `Walker`, this replaces the `set_ctx`,
   `set_ctx_for` mechanism. Mutating the state directly is equivalent to
   `set_ctx`, and `withstate(tree, k0=v0, ...)` is equivalent to `set_ctx_for`.

 - `collected`: a `list` of collected values, in the order collected.


## Methods

 - `__init__(k0=v0, ...)`: load the given bindings into the walker's initial state.

   The bindings can be accessed as `self.state.k0`, ...

 - `visit(tree)`: start walking. Can also be used to manually recurse selectively.

   **Do not override this method**, override `transform` instead.

   This method implements the `withstate` machinery and transparent
   handling of statement suites (i.e. lists of AST nodes).

   Unlike the default `ast.NodeTransformer.visit`, we **don't** dispatch
   to different methods based on node type; there is only one `visit`
   method, and only one `transform` method it delegates to.

 - `transform(tree)`: examine and/or transform one node. **Abstract method, override this!**

   There is only one `transform` method. To detect the node type, use `type(tree)`.

   If you only want to examine `tree`, not modify it, that's fine;
   just be sure to `return tree` when done.

   Return value should be as in `ast.NodeTransformer.visit`. Usually it is the
   updated `tree`. It can be a `list` of AST nodes to replace with multiple
   nodes (when syntactically admissible, i.e. in statement suites), or `None`
   to delete this subtree.

   *This method must recurse explicitly.*

   Just like in `ast.NodeTransformer.visit`, you'll only ever get an individual
   AST node passed in as `tree`; statement suites will be sent one node at a time.
   If you need to replace or delete a whole suite, you can do that when transforming
   the statement node the suite belongs to.

   Like in any `ast.NodeTransformer`, call `self.generic_visit(tree)` to
   recurse into all children of `tree` (including each node in any contained suite).

   To recurse selectively, `self.visit` the desired subtrees. Be sure to use `visit`,
   not `transform`, to make `withstate` updates take effect.
   
   Unlike in `ast.NodeTransformer`, it is ok to `visit` a statement suite directly;
   this will loop over the suite, visiting each node in it. When visiting a suite
   this way, the return values are treated properly so that if a `transform` call
   returns several nodes, those will be spliced in to replace the original node in
   the suite, and if it returns `None`, the corresponding node will be removed
   from the suite.

 - `generic_visit(tree)`: recurse into all children, including each node in any
   contained suite. Inherited from `ast.NodeTransformer`.

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
   reuse the same `Walker` instance.
