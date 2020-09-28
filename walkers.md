# AST walker

```python
    def kittify(mytree):
        class Kittifier(Walker):
            def transform(self, tree):
                if type(tree) is ast.Constant:
                    self.collect(tree.value)
                    tree.value = "meow!" if self.state.meows % 2 == 0 else "miaow!"
                    self.state.meows += 1
                self.generic_visit(tree)  # recurse
                return tree
        k = Kittifier(meows=0)    # set the initial state here
        mytree = k.visit(mytree)  # it's basically an ast.NodeTransformer
        print(k.collected)        # collected values, in the order visited
        return mytree
```

To bridge the feature gap between
[`ast.NodeTransformer`](https://docs.python.org/3/library/ast.html#ast.NodeTransformer)
and MacroPy's `Walker`, we provide `mcpy.walker.Walker`, a zen-minimalistic AST
walker base class based on `ast.NodeTransformer`, with a state stack and a node collector.

The selling points are `withstate`, `state`, `collect`, `collected`, which see below.

For a realistic example, see [`mcpy.ctxfixer`](mcpy/ctxfixer.py).


## Attributes

 - `state: mcpy.utilities.Bunch`: stores named values as its attributes.

   Mutable. The whole `state` can also be replaced by simply rebinding it
   (`self.state = ...`).

   It's essentially a namespace, implemented as an object that internally stores
   things in a dict. The point of using `Bunch` here is more convenient access
   syntax; `self.state.x` instead of `self.state['x']`.

   If you're familiar with MacroPy's `Walker`, this replaces the `set_ctx`,
   `set_ctx_for` mechanism. Mutating the state is equivalent to `set_ctx`,
   and `withstate` is equivalent to `set_ctx_for`.

 - `collected: list`: list of collected values.


## Methods

 - `__init__`: load the given bindings into the walker's initial state.

 - `visit`: start walking. Can also be used to manually recurse selectively.

   **Do not override this method**, override `transform` instead.

   This method implements the `withstate` machinery and transparent
   handling of statement suites (i.e. lists of AST nodes).

   Unlike the default `ast.NodeTransformer.visit`, we **don't** dispatch
   to different methods based on node type; there is only one `visit`
   method, and only one `transform` method it delegates to.

 - `transform`: examine and/or transform one node. **Abstract method, override this!**

   There is only one `transform` method. To detect the node type, use `type(tree)`.

   If you only want to examine `tree`, not modify it, that's fine;
   just be sure to `return tree` when done.

   Return value should be as in `ast.NodeTransformer.visit`. Usually it is the
   updated `tree`. It can be a `list` of AST nodes to replace with multiple
   nodes (when syntactically admissible, i.e. in statement suites), or `None`
   to delete this subtree.

   *This method must recurse explicitly.*

   Like in any `ast.NodeTransformer`, call `self.generic_visit(tree)` to
   recurse into all children of `tree`.

   To recurse selectively, `self.visit` the desired subtrees (statement suites
   are also ok). Be sure to use `visit`, not `transform`, to make `withstate`
   updates take effect.

 - `generic_visit`: recurse into all children. Inherited from `ast.NodeTransformer`.

 - `collect`: collect a value (any object). For convenience, return `value`.

   The collected values are placed in the list `self.collected`, which is
   retained across the whole walk.

 - `withstate`: use an updated state while in a given subtree only.

   The current `self.state` is copied. Given `bindings` are merged into the
   copy, overwriting existing keys.

   When the walker enters the given `tree`, `self.state` becomes
   *temporarily replaced* by the updated state before calling `self.transform`.
   When the walker exits that `tree` (whether by normal exit or exception),
   the previous `self.state` is automatically restored.

   Any mutations to the updated state will then be lost - which is the
   whole point of `withstate`.

   If you need to store something globally across the walk, just write
   into a regular attribute of `self`. Note `self.reset` won't clear any
   attributes you add, so you might then want to override that, too
   (co-operatively; be sure to call `super().reset`).

   `tree` can be an AST node, or a statement suite (`list` of AST nodes).
   It is identified by `id(tree)` at enter time.

   Nested subtrees can be `withstate`'d. The temporarily stashed previous
   states are kept on a stack.

 - `reset`: clear the state and the list of collected objects.

    Use this to prepare for walking another unrelated tree, if you want to
    reuse the same `Walker` instance.

    `bindings` are loaded into the new, otherwise blank initial state.
