"""Query text assembly and execution helpers."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from org.query.engine.compiler import compile_query_text
from org.query.engine.interpreter import EvalContext, Stream


if TYPE_CHECKING:
    from collections.abc import Sequence

    from org_parser import Document
    from org_parser.document import Heading


logger = logging.getLogger("org")


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


def build_query_text_from_stages(stages: Sequence[str]) -> str:
    """Build query text from an ordered list of pipeline stages."""
    return " | ".join(stages) if stages else "."


def build_filter_order_query_text(filter_query: str, order_by: str | None) -> str:
    """Build a `select(...)` query with optional sort stage."""
    base_query = f"select({filter_query})"
    if order_by is None:
        return base_query
    return f"{base_query} | sort_by({order_by})"


def run_query(
    inputs: Sequence[Document | Heading],
    stages: Sequence[str],
    context_vars: dict[str, object],
) -> list[object]:
    """Compile and execute query stages over the provided input stream."""
    query_text = build_query_text_from_stages(stages)
    logger.info("Query: %s", query_text)
    compiled_query = compile_query_text(query_text)
    return list(compiled_query(Stream(inputs), EvalContext(context_vars)))
