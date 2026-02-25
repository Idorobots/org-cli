"""Sanity tests for query language runtime execution."""

from __future__ import annotations

import orgparse
import pytest
from orgparse.node import OrgRootNode

from org.query_language import EvalContext, QueryRuntimeError, Stream, compile_query_text
from tests.conftest import node_from_org


def _execute(
    query: str,
    nodes: object,
    variables: dict[str, object] | None,
) -> list[object]:
    compiled = compile_query_text(query)
    context_vars = {} if variables is None else variables
    context = EvalContext(context_vars)
    return compiled(Stream([nodes]), context)


def _sample_nodes() -> list[object]:
    org_text = """* DONE Parent
** TODO Alpha child
** DONE Zeta child

* TODO Second
"""
    return [*node_from_org(org_text)]


def _sample_root() -> object:
    org_text = """* DONE Parent
** TODO Alpha child
** DONE Zeta child

* TODO Second
"""
    root = orgparse.loads(org_text)
    assert root is not None
    return root


def test_runtime_select_done_nodes() -> None:
    """select() should filter nodes by todo state."""
    nodes = _sample_nodes()
    result = _execute('.[] | select(.todo == "DONE") | .heading', nodes, None)
    assert result == ["Parent", "Zeta child"]


def test_runtime_select_not_none_todo_filters_missing_values() -> None:
    """Comparing against none should treat missing todo as none."""
    nodes = [*node_from_org("* DONE Keep\n* Plain\n")]
    result = _execute(".[] | select(.todo != none) | .heading", nodes, None)
    assert result == ["Keep"]


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


def test_runtime_root_node_is_iterable_indexable_and_sliceable() -> None:
    """OrgRootNode should behave like a collection in query operators."""
    root = _sample_root()
    result_iterate = _execute(".[0][] | .heading", [root], None)
    result_index = _execute(".[0][0].heading", [root], None)
    result_slice = _execute(".[0][0:2] | .[] | .heading", [root], None)

    assert result_iterate == ["Parent", "Alpha child", "Zeta child", "Second"]
    assert result_index == ["Parent"]
    assert result_slice == ["Parent", "Alpha child"]


def test_runtime_sum_function() -> None:
    """sum() should aggregate numeric collections."""
    result = _execute("sum", [1, 2, 3], None)
    assert result == [6]


def test_runtime_join_function() -> None:
    """join() should join collection values with separator expression."""
    result = _execute('join(",")', ["a", "b", "c"], None)
    assert result == ["a,b,c"]


def test_runtime_join_scalar_raises() -> None:
    """join() should fail on scalar input."""
    with pytest.raises(QueryRuntimeError):
        _execute('join(",")', 1, None)


def test_runtime_map_function() -> None:
    """map() should transform each collection item using subquery."""
    result = _execute("map(. * 2)", [1, 2, 3], None)
    assert result == [[2, 4, 6]]


def test_runtime_numeric_operators_and_slice_expression() -> None:
    """Arithmetic operators and dynamic slice bounds should work."""
    numeric = _execute("2 ** 3, 8 / 2, 7 mod 3, -7 rem 3, -7 quot 3", [None], None)
    sliced = _execute(
        ".[ $offset : $offset + $limit ]", [10, 20, 30, 40], {"offset": 1, "limit": 2}
    )

    assert numeric == [(8, 4.0, 1, -1, -2)]
    assert sliced == [[20, 30]]


def test_runtime_as_binding_visible_in_pipeline() -> None:
    """as-binding should define variables for downstream pipe stages."""
    root = _sample_root()
    typed_root = root if isinstance(root, OrgRootNode) else None
    assert typed_root is not None
    result = _execute(". as $root | $root[], ($root[] | .children | length)", [typed_root], None)

    assert result == [(typed_root, 2)]


def test_runtime_fold_operator() -> None:
    """Fold operator should collect subquery streams into lists."""
    nodes = _sample_nodes()
    folded = _execute('[ .[] | select(.todo == "DONE") | .heading ]', nodes, None)
    tuple_fold = _execute("[1, 2, 3]", [None], None)
    scalar_fold = _execute(".[] | [ .heading ]", nodes, None)
    empty_fold = _execute("[]", [None], None)

    assert folded == [["Parent", "Zeta child"]]
    assert tuple_fold == [[1, 2, 3]]
    assert scalar_fold == [["Parent"], ["Alpha child"], ["Zeta child"], ["Second"]]
    assert empty_fold == [[]]


def test_runtime_returns_stream_type() -> None:
    """Compiled queries should return Stream instances."""
    compiled = compile_query_text(".[] | .heading")
    result = compiled(Stream([_sample_nodes()]), EvalContext({}))
    assert isinstance(result, Stream)
