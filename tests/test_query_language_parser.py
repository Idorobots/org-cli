"""Sanity tests for query language parser."""

from __future__ import annotations

import pytest

from org.query_language import parse_query
from org.query_language.ast import (
    AsBinding,
    BinaryOp,
    FieldAccess,
    Fold,
    FunctionCall,
    NoneLiteral,
    Pipe,
    Slice,
)
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
        ".[1:1 + $limit]",
        "sum",
        'join(",")',
        "map(. * 2)",
        ". as $root | $root[]",
        '[ .[] | select(.todo == "DONE") ] | .[10:20]',
        "[]",
        "[1, 2, 3]",
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


def test_parse_as_binding_shape() -> None:
    """Parser should parse as-binding nodes."""
    expr = parse_query(". as $root | $root[]")
    assert isinstance(expr, Pipe)
    assert isinstance(expr.left, AsBinding)
    assert expr.left.name == "root"


def test_parse_fold_shape() -> None:
    """Parser should parse fold expressions."""
    expr = parse_query("[ .[] | .heading ]")
    assert isinstance(expr, Fold)


def test_parse_none_literal_is_not_identifier_string() -> None:
    """none should parse as NoneLiteral in comparisons."""
    expr = parse_query(".todo != none")
    assert isinstance(expr, BinaryOp)
    assert isinstance(expr.right, NoneLiteral)


@pytest.mark.parametrize(
    "query",
    [
        ".[",
        "select(.todo ==",
        ".[] | | .todo",
        "a +",
        ". as root",
    ],
)
def test_parse_invalid_queries(query: str) -> None:
    """Parser should reject malformed query text."""
    with pytest.raises(QueryParseError):
        parse_query(query)


def test_parse_error_does_not_include_keyword_boundary_regex() -> None:
    """Syntax errors should not expose keyword-boundary regex internals."""
    with pytest.raises(QueryParseError) as exc_info:
        parse_query("select(.todo ==")
    assert "(?![A-Za-z0-9_])" not in str(exc_info.value)
