# Deferred Issues

- **D1: Expand unit tests**: The test suite is thin relative to the codebase. Needs thought on how to test meaningfully given tight coupling between parts (expander, quotes, compiler). Automated integration tests would also be valuable.

- **D2: Fix TODO list**: `todo.md` (lowercase) has old notes that need review — update, reorganize, or replace.

## expand1sq / expandsq block mode possibly broken

`expand1sq` and `expandsq` in block mode (metatools.py lines 188–190, 216–218) fail with `TypeError` from `unastify` — the `splice_ast_literals` wrapping produced by block-mode `q` isn't unastifiable. These code paths have never been exercised (no tests, no uses in the codebase or docs). Read the docs and figure out what they should do, then either fix or remove the block mode claim. (Coverage lines 189, 217 in metatools.py.)
