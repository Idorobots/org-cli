"""Tests for query language compiler entrypoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import org.query.engine.parser as parser_module
from org.query.engine.ast import NumberLiteral
from org.query.engine.compiler import compile_expr, compile_query_text
from org.query.engine.interpreter import EvalContext, Stream


if TYPE_CHECKING:
    import pytest


def test_compile_expr_returns_executable_callable() -> None:
    """compile_expr should execute the provided AST expression."""
    compiled = compile_expr(NumberLiteral(42))
    result = compiled(Stream([None]), EvalContext({}))
    assert result == [42]


def test_compile_query_text_parses_and_executes_expression() -> None:
    """compile_query_text should parse query text and run the result."""
    compiled = compile_query_text(".[] | .title_text")
    result = compiled(Stream([[{"title_text": "Task"}]]), EvalContext({}))
    assert result == ["Task"]


def test_parse_query_memoizes_repeated_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    """parse_query should only parse identical query text once per process."""
    parser_module.parse_query.cache_clear()
    calls = 0
    original_parse = parser_module.QUERY_PARSER.parse

    def counted_parse(query: str) -> object:
        nonlocal calls
        calls += 1
        return original_parse(query)

    monkeypatch.setattr(parser_module.QUERY_PARSER, "parse", counted_parse)

    compile_query_text(".[] | .title_text")
    compile_query_text(".[] | .title_text")

    assert calls == 1
