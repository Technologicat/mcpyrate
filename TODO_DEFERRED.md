# Deferred Issues

- **D1: Expand unit tests**: The test suite is thin relative to the codebase. Needs thought on how to test meaningfully given tight coupling between parts (expander, quotes, compiler). Automated integration tests would also be valuable.

- **D2: Fix TODO list**: `todo.md` (lowercase) has old notes that need review — update, reorganize, or replace.

- **D3: splice_dialect docstring concatenation wraps in bare ast.Constant**: In `splicing.py` line ~269, when both body and template have docstrings, the combined docstring is `ast.Constant(...)` but should be `ast.Expr(ast.Constant(...))` to be valid as a statement in a module body. Found during coverage testing.
