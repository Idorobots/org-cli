"""Tests for query language compiler entrypoints."""

from __future__ import annotations

from org.query_language import EvalContext, Stream, compile_query_text
from org.query_language.ast import NumberLiteral
from org.query_language.compiler import compile_expr


def test_compile_expr_returns_executable_callable() -> None:
    """compile_expr should execute the provided AST expression."""
    compiled = compile_expr(NumberLiteral(42))
    result = compiled(Stream([None]), EvalContext({}))
    assert result == [42]


def test_compile_query_text_parses_and_executes_expression() -> None:
    """compile_query_text should parse query text and run the result."""
    compiled = compile_query_text(".[] | .heading")
    result = compiled(Stream([[{"heading": "Task"}]]), EvalContext({}))
    assert result == ["Task"]
