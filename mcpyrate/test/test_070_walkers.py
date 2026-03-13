# -*- coding: utf-8 -*-
"""Tests for AST walkers (walkers.py)."""

import ast

from ..walkers import ASTVisitor, ASTTransformer


def runtests():
    # -- ASTVisitor basics --

    def test_visitor_collect():
        class ConstCollector(ASTVisitor):
            def examine(self, tree):
                if isinstance(tree, ast.Constant):
                    self.collect(tree.value)
                self.generic_visit(tree)
        w = ConstCollector()
        tree = ast.parse("x = 1\ny = 'hello'")
        w.visit(tree)
        assert 1 in w.collected
        assert "hello" in w.collected
    test_visitor_collect()

    def test_visitor_state():
        class StatefulVisitor(ASTVisitor):
            def examine(self, tree):
                if isinstance(tree, ast.Constant):
                    self.collect(self.state.depth)
                self.generic_visit(tree)
        w = StatefulVisitor(depth=0)
        tree = ast.parse("x = 1")
        w.visit(tree)
        assert 0 in w.collected
    test_visitor_state()

    def test_visitor_list():
        """Visiting a list of statements."""
        class Counter(ASTVisitor):
            def examine(self, tree):
                if isinstance(tree, ast.Assign):
                    self.collect(tree)
                self.generic_visit(tree)
        w = Counter()
        stmts = ast.parse("x = 1\ny = 2").body
        w.visit(stmts)
        assert len(w.collected) == 2
    test_visitor_list()

    def test_visitor_withstate():
        """withstate pushes state for a subtree visit."""
        class StateTracker(ASTVisitor):
            def examine(self, tree):
                if isinstance(tree, ast.FunctionDef):
                    self.withstate(tree.body, inside_func=True)
                if isinstance(tree, ast.Constant):
                    self.collect(self.state.get("inside_func", False))
                self.generic_visit(tree)
        w = StateTracker()
        tree = ast.parse("x = 1\ndef f():\n  y = 2\nz = 3")
        w.visit(tree)
        # x=1 → False, y=2 → True, z=3 → False
        assert w.collected == [False, True, False]
    test_visitor_withstate()

    def test_visitor_withstate_pops():
        """withstate pops state correctly when subtree visit completes."""
        states = []
        class StatePeeker(ASTVisitor):
            def examine(self, tree):
                if isinstance(tree, ast.Assign):
                    states.append(dict(self.state))
                self.generic_visit(tree)
        w = StatePeeker(x=1)
        body = ast.parse("a = 1\nb = 2").body
        # Set state override for the first statement only
        w.withstate(body[0], x=42)
        for stmt in body:
            w.visit(stmt)
        assert states[0]["x"] == 42
        assert states[1]["x"] == 1
    test_visitor_withstate_pops()

    def test_visitor_generic_withstate():
        """generic_withstate sets state for all children."""
        class ChildStateTracker(ASTVisitor):
            def examine(self, tree):
                if isinstance(tree, ast.Constant):
                    self.collect(self.state.get("level", 0))
                self.generic_visit(tree)
        w = ChildStateTracker()
        tree = ast.parse("x = 1 + 2")
        # Set state for all children of module
        w.generic_withstate(tree, level=1)
        w.visit(tree)
        # All constants should see level=1
        assert all(v == 1 for v in w.collected)
    test_visitor_generic_withstate()

    # -- ASTVisitor state property --

    def test_visitor_state_rebind():
        """state property setter replaces current state."""
        from ..bunch import Bunch
        class RebindingVisitor(ASTVisitor):
            def examine(self, tree):
                self.generic_visit(tree)
        w = RebindingVisitor(x=1)
        assert w.state.x == 1
        w.state = Bunch(x=42)
        assert w.state.x == 42
    test_visitor_state_rebind()

    def test_visitor_reset():
        """reset clears collected and state."""
        class Collector(ASTVisitor):
            def examine(self, tree):
                self.collect(tree)
                self.generic_visit(tree)
        w = Collector(x=1)
        w.visit(ast.parse("a = 1"))
        assert len(w.collected) > 0
        w.reset(x=2)
        assert w.collected == []
        assert w.state.x == 2
    test_visitor_reset()

    # -- ASTTransformer basics --

    def test_transformer_identity():
        class IdentityTransformer(ASTTransformer):
            def transform(self, tree):
                return self.generic_visit(tree)
        w = IdentityTransformer()
        tree = ast.parse("x = 1")
        result = w.visit(tree)
        assert ast.dump(result) == ast.dump(tree)
    test_transformer_identity()

    def test_transformer_edit():
        class ConstReplacer(ASTTransformer):
            def transform(self, tree):
                if isinstance(tree, ast.Constant) and tree.value == 1:
                    tree.value = 42
                    return tree
                return self.generic_visit(tree)
        w = ConstReplacer()
        tree = ast.parse("x = 1")
        result = w.visit(tree)
        code = ast.unparse(result)
        assert "42" in code
    test_transformer_edit()

    def test_transformer_remove_node():
        """Returning None removes a statement."""
        class StmtRemover(ASTTransformer):
            def transform(self, tree):
                if isinstance(tree, ast.Assign):
                    return None
                return self.generic_visit(tree)
        w = StmtRemover()
        tree = ast.parse("x = 1\ny = 2")
        result = w.visit(tree)
        assert len(result.body) == 0
    test_transformer_remove_node()

    def test_transformer_list():
        """Transformer visiting a statement suite directly."""
        class PassThrough(ASTTransformer):
            def transform(self, tree):
                self.collect(type(tree).__name__)
                return self.generic_visit(tree)
        w = PassThrough()
        stmts = ast.parse("x = 1\ny = 2").body
        result = w.visit(stmts)
        assert isinstance(result, list)
        assert len(result) == 2
    test_transformer_list()

    def test_transformer_list_empty():
        """Transformer producing empty list preserves list type."""
        class Eater(ASTTransformer):
            def transform(self, tree):
                return None
        w = Eater()
        stmts = ast.parse("x = 1").body
        result = w.visit(stmts)
        assert isinstance(result, list)
        assert len(result) == 0
    test_transformer_list_empty()

    def test_transformer_withstate():
        """Transformer uses withstate for subtree state."""
        class StateTransformer(ASTTransformer):
            def transform(self, tree):
                if isinstance(tree, ast.FunctionDef):
                    self.withstate(tree.body, inside_func=True)
                if isinstance(tree, ast.Constant):
                    if self.state.get("inside_func", False):
                        tree.value = 99
                return self.generic_visit(tree)
        w = StateTransformer()
        tree = ast.parse("x = 1\ndef f():\n  y = 2\nz = 3")
        result = w.visit(tree)
        code = ast.unparse(result)
        assert "x = 1" in code
        assert "y = 99" in code
        assert "z = 3" in code
    test_transformer_withstate()


if __name__ == '__main__':
    runtests()
