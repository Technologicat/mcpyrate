# Deferred Issues

- **unparser `_Expression` broken for `mode="eval"`**: `toplevelnode()` (line ~294 in `unparser.py`) iterates `t.body` as a list, but `Expression.body` is a single node. `unparse(ast.parse("42", mode="eval"))` raises `TypeError`. Has always been this way — never triggered because nothing uses `mode="eval"` with this unparser. Fix: `_Expression` should dispatch `t.body` directly instead of delegating to `toplevelnode`.
