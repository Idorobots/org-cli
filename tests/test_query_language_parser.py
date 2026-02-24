"""Sanity tests for query language parser."""

from __future__ import annotations

import pytest

from org.query_language import parse_query
from org.query_language.ast import BinaryOp, FieldAccess, FunctionCall, Pipe, Slice
from org.query_language.errors import QueryParseError


@pytest.mark.parametrize(
    "query",
    [
        ".todo",
        '.todo == "DONE"',
        '.properties["foo"]',
        ".[0]",
        ".[0:10]",
        ".children[1:2].heading",
        ".[]",
        ".[] | reverse",
        'select(.properties["gamify_exp"] > X)',
        "sort_by(.latest_timestamp) | reverse",
        "select(.heading == ID, .properties[$id] == ID) | .children",
        ".children[] | sort_by(.level) | reverse | .[0:10]",
        "select((.depndencies[] | length) == 0)",
    ],
)
def test_parse_query_examples(query: str) -> None:
    """Parser should accept representative query examples."""
    expr = parse_query(query)
    assert expr is not None


def test_parse_field_comparison_shape() -> None:
    """Parser should build expected nodes for comparison queries."""
    expr = parse_query('.todo == "DONE"')
    assert isinstance(expr, BinaryOp)
    assert expr.operator == "=="
    assert isinstance(expr.left, FieldAccess)


def test_parse_slice_query_shape() -> None:
    """Parser should build slice node for slicing queries."""
    expr = parse_query(".[0:10]")
    assert isinstance(expr, Slice)


def test_parse_pipe_with_function_shape() -> None:
    """Parser should parse function call in pipe stage."""
    expr = parse_query(".[] | reverse")
    assert isinstance(expr, Pipe)
    assert isinstance(expr.right, FunctionCall)
    assert expr.right.name == "reverse"


@pytest.mark.parametrize("query", [".[", "select(.todo ==", ".[] | | .todo"])
def test_parse_invalid_queries(query: str) -> None:
    """Parser should reject malformed query text."""
    with pytest.raises(QueryParseError):
        parse_query(query)
