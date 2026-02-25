"""Sanity tests for query language runtime execution."""

from __future__ import annotations

import pytest

from org.query_language import EvalContext, QueryRuntimeError, compile_query_text
from tests.conftest import node_from_org


def _execute(
    query: str,
    nodes: list[object],
    variables: dict[str, object] | None,
) -> list[object]:
    compiled = compile_query_text(query)
    context_vars = {} if variables is None else variables
    context = EvalContext(context_vars)
    return compiled([nodes], context)


def _sample_nodes() -> list[object]:
    org_text = """* DONE Parent
** TODO Alpha child
** DONE Zeta child

* TODO Second
"""
    return [*node_from_org(org_text)]


def test_runtime_select_done_nodes() -> None:
    """select() should filter nodes by todo state."""
    nodes = _sample_nodes()
    result = _execute('.[] | select(.todo == "DONE") | .heading', nodes, None)
    assert result == ["Parent", "Zeta child"]


def test_runtime_reverse_and_index() -> None:
    """reverse and index should return the last child heading."""
    nodes = _sample_nodes()
    result = _execute(".[0].children | reverse | .[0].heading", nodes, None)
    assert result == ["Zeta child"]


def test_runtime_sort_by_heading_descending() -> None:
    """sort_by should order by heading descending."""
    nodes = _sample_nodes()
    result = _execute(".[0].children | .[] | sort_by(.heading) | .heading", nodes, None)
    assert result == ["Zeta child", "Alpha child"]


def test_runtime_missing_field_returns_none() -> None:
    """Missing field access should return none values."""
    nodes = _sample_nodes()
    result = _execute(".[] | .missing_field", nodes, None)
    assert result == [None, None, None, None]


def test_runtime_index_out_of_bounds_returns_none() -> None:
    """Out-of-bounds index should return none."""
    nodes = _sample_nodes()
    result = _execute(".[0].children[99]", nodes, None)
    assert result == [None]


def test_runtime_slice_out_of_bounds_returns_empty_collection() -> None:
    """Out-of-bounds slice should return empty collection."""
    nodes = _sample_nodes()
    result = _execute(".[0].children[99:120]", nodes, None)
    assert result == [[]]


def test_runtime_matches_and_membership() -> None:
    """matches and in should work in select conditions."""
    nodes = _sample_nodes()
    matches_result = _execute('.[] | select(.heading matches "^P") | .heading', nodes, None)
    in_result = _execute(
        ".[] | select(.todo in $done_keys) | .todo",
        nodes,
        {"done_keys": ["DONE"]},
    )
    assert matches_result == ["Parent"]
    assert in_result == ["DONE", "DONE"]


def test_runtime_comma_builds_tuples() -> None:
    """Comma expressions should produce tuple values."""
    nodes = _sample_nodes()
    result = _execute(".[] | .todo, .heading", nodes, None)
    assert result[0] == ("DONE", "Parent")


def test_runtime_type_mismatch_raises_exception() -> None:
    """Type mismatch in operator should raise query runtime error."""
    nodes = _sample_nodes()
    with pytest.raises(QueryRuntimeError):
        _execute(".[] | select(.heading > 1)", nodes, None)
