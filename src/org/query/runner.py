"""Query text assembly, compilation, and execution helpers."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from typing import cast

from org.query.engine.compiler import CompiledQuery, compile_query_text
from org.query.engine.errors import QueryParseError, QueryRuntimeError
from org.query.engine.interpreter import EvalContext, Stream


logger = logging.getLogger("org")

ErrorBuilder = Callable[[str], Exception]


def build_custom_stage(query: str, arg_value: object) -> str:
    """Build one custom query stage preserving input item stream values."""
    return f"let {_query_literal(arg_value)} as $arg in ({query})"


def _query_literal(value: object) -> str:
    """Render a Python value as a query-language literal."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return json.dumps(value)


def build_query_text_from_stages(stages: Sequence[str], include_slice: bool) -> str:
    """Build query text from an ordered list of pipeline stages."""
    pipeline_body = " | ".join(stages)
    base_query = f"[ .[] | {pipeline_body} ]" if pipeline_body else "[ .[] ]"
    return f"{base_query}[$offset:($offset + $limit)]" if include_slice else base_query


def build_query_from_stages(stages: Sequence[str], include_slice: bool) -> CompiledQuery:
    """Compile query from an ordered list of pipeline stages."""
    query_text = build_query_text_from_stages(stages, include_slice)
    logger.info("Query: %s", query_text)
    return compile_query_text(query_text)


def compile_query_or_raise(query_text: str, error_builder: ErrorBuilder) -> CompiledQuery:
    """Compile query text and convert parse failures to caller-specific errors."""
    try:
        return compile_query_text(query_text)
    except QueryParseError as exc:
        raise error_builder(str(exc)) from exc


def compile_filter_order_query(filter_query: str, order_by: str | None) -> CompiledQuery:
    """Compile a `select(...)` query with optional sort stage."""
    base_query = f"select({filter_query})"
    if order_by is None:
        return compile_query_text(base_query)
    return compile_query_text(f"{base_query} | sort_by({order_by})")


def execute_query(
    compiled_query: CompiledQuery,
    stream_values: Sequence[object],
    context_vars: dict[str, object],
) -> list[object]:
    """Execute a compiled query over stream input values."""
    return list(compiled_query(Stream(stream_values), EvalContext(context_vars)))


def execute_query_or_raise(
    compiled_query: CompiledQuery,
    stream_values: Sequence[object],
    context_vars: dict[str, object],
    error_builder: ErrorBuilder,
) -> list[object]:
    """Execute query and convert runtime failures to caller-specific errors."""
    try:
        return execute_query(compiled_query, stream_values, context_vars)
    except QueryRuntimeError as exc:
        raise error_builder(str(exc)) from exc


def run_query_text_or_raise(
    query_text: str,
    stream_values: Sequence[object],
    context_vars: dict[str, object],
    error_builder: ErrorBuilder,
) -> list[object]:
    """Compile and execute query text with caller-specific error conversion."""
    return execute_query_or_raise(
        compile_query_or_raise(query_text, error_builder),
        stream_values,
        context_vars,
        error_builder,
    )


def flatten_query_results(results: list[object]) -> list[object]:
    """Flatten common single-list query result shape."""
    if len(results) == 1 and isinstance(results[0], list):
        return cast("list[object]", results[0])
    return list(results)
