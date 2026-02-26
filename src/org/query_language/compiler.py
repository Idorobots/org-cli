"""Compiler entrypoints for query language."""

from __future__ import annotations

from collections.abc import Callable

from org.query_language.ast import Expr
from org.query_language.parser import parse_query
from org.query_language.runtime import EvalContext, Stream, evaluate_expr


type CompiledQuery = Callable[[Stream, EvalContext], Stream]


def compile_expr(expr: Expr) -> CompiledQuery:
    """Compile expression into executable query callable."""

    def _compiled(stream: Stream, context: EvalContext) -> Stream:
        return evaluate_expr(expr, stream, context)

    return _compiled


def compile_query_text(query: str) -> CompiledQuery:
    """Parse and compile query text."""
    expr = parse_query(query)
    return compile_expr(expr)
