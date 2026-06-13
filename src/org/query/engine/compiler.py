"""Compiler entrypoints for query language."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from org.query.engine.interpreter import EvalContext, Stream, evaluate_expr
from org.query.engine.parser import parse_query


if TYPE_CHECKING:
    from org.query.engine.ast import Expr


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
