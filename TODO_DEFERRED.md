# Deferred Issues

- **D1: Expand unit tests**: Overall coverage is 96% (7335 stmts, 308 miss). Remaining gaps are mostly Python version branches (unparser.py, astcompat.py), deep edge cases in the expander (macro returns `None`, self-macro-import without location info), test file catch-blocks, and the `ansi.py` fallback module. Diminishing returns from here.

- **D2: Fix TODO list**: `todo.md` (lowercase) has old notes that need review — update, reorganize, or replace.

