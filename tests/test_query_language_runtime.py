"""Sanity tests for query language runtime execution."""

from __future__ import annotations

from typing import cast

import orgparse
import pytest
from orgparse.date import OrgDateClock, OrgDateRepeatedTask
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


def test_runtime_sort_by_dates_orders_latest_first_with_none_last() -> None:
    """sort_by should sort date keys by timestamp and place none keys last."""
    nodes = [
        *node_from_org(
            """* TODO Older
SCHEDULED: <2024-01-10 Wed>
* TODO Newer
SCHEDULED: <2024-01-12 Fri>
* TODO Missing
"""
        )
    ]
    query = (
        ".[] | sort_by(.repeated_tasks + .deadline + .closed + .scheduled"
        " | [ .[] | select(.) ] | max) | .heading"
    )

    result = _execute(query, nodes, None)
    assert result == ["Newer", "Older", "Missing"]


def test_runtime_sort_by_places_none_keys_last() -> None:
    """sort_by should place values with none keys at the end."""
    result = _execute(".[0][] | sort_by(.)", [[3, None, 1, None, 2]], None)
    assert result[:3] == [3, 2, 1]
    assert result[3:] == [None, None]


def test_runtime_empty_org_date_fields_are_none() -> None:
    """Unset org date fields should resolve to none values."""
    nodes = [*node_from_org("* TODO Plain\n")]
    result = _execute(".[] | .scheduled", nodes, None)
    assert result == [None]


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


def test_runtime_max_and_min_functions() -> None:
    """max/min should return extrema for comparable collections."""
    numeric_max = _execute("max", [1, 9, 3], None)
    numeric_min = _execute("min", [1, 9, 3], None)
    string_max = _execute("max", ["alpha", "zulu", "beta"], None)
    string_min = _execute("min", ["alpha", "zulu", "beta"], None)

    assert numeric_max == [9]
    assert numeric_min == [1]
    assert string_max == ["zulu"]
    assert string_min == ["alpha"]


def test_runtime_max_and_min_for_org_dates_compare_by_start() -> None:
    """max/min should compare OrgDate values by start value."""
    dates = [
        _execute('timestamp("<2025-01-02 Thu 10:00>")', [None], None)[0],
        _execute('timestamp("<2025-01-02 Thu 09:00>")', [None], None)[0],
    ]
    result_max = _execute("max", dates, None)
    result_min = _execute("min", dates, None)

    assert [str(value) for value in result_max] == ["<2025-01-02 Thu 10:00>"]
    assert [str(value) for value in result_min] == ["<2025-01-02 Thu 09:00>"]


def test_runtime_max_and_min_empty_collection_returns_none() -> None:
    """max/min should return none for empty collections."""
    assert _execute("max", [], None) == [None]
    assert _execute("min", [], None) == [None]


def test_runtime_max_and_min_ignore_none_values() -> None:
    """max/min should ignore none values in collections."""
    assert _execute("max", [1, None, 9, 3], None) == [9]
    assert _execute("min", [1, None, 9, 3], None) == [1]


def test_runtime_max_and_min_all_none_returns_none() -> None:
    """max/min should return none when all values are none."""
    assert _execute("max", [None, None], None) == [None]
    assert _execute("min", [None, None], None) == [None]


def test_runtime_max_and_min_raise_for_mixed_non_comparable_values() -> None:
    """max/min should fail for mixed-type values that are not comparable."""
    with pytest.raises(QueryRuntimeError):
        _execute("max", [1, "x"], None)
    with pytest.raises(QueryRuntimeError):
        _execute("min", ["x", 1], None)


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


def test_runtime_or_and_operator_semantics() -> None:
    """or/and should follow query truthiness semantics."""
    result = _execute('"foo" or "x", none or "x", "x" and none, "x" and 1', [None], None)
    assert result == [("foo", "x", False, True)]


def test_runtime_type_function() -> None:
    """type should return the type name for each stream value."""
    node = next(iter(node_from_org("* TODO Task\n")))
    repeated = _execute('timestamp("<2025-01-02 Thu>")', [None], None)[0]
    result = _execute(".[] | type", [None, 1, "x", node, repeated], None)
    assert result == ["none", "int", "str", "OrgNode", "OrgDate"]


def test_runtime_not_function() -> None:
    """not should invert subquery truthiness."""
    nodes = _sample_nodes()
    result = _execute(".[] | not(.todo in $done_keys)", nodes, {"done_keys": ["DONE"]})
    assert result == [False, True, False, True]


def test_runtime_timestamp_function_with_supported_arities() -> None:
    """timestamp should create OrgDate values for one, two, and three arguments."""
    one = _execute('timestamp("<2025-01-02 Thu>")', [None], None)[0]
    two = _execute('timestamp("<2025-01-02 Thu>", "<2025-01-03 Fri>")', [None], None)[0]
    three = _execute('timestamp("<2025-01-02 Thu>", none, false)', [None], None)[0]

    assert str(one) == "<2025-01-02 Thu>"
    assert str(two) == "<2025-01-02 Thu>--<2025-01-03 Fri>"
    assert str(three) == "[2025-01-02 Thu]"


def test_runtime_clock_function_with_supported_arities() -> None:
    """clock should create OrgDateClock values with computed durations."""
    two = _execute('clock("<2025-01-02 Thu 10:00>", "<2025-01-02 Thu 11:30>")', [None], None)[0]
    three = _execute(
        'clock("<2025-01-02 Thu 10:00>", "<2025-01-02 Thu 11:30>", true)', [None], None
    )[0]

    assert isinstance(two, OrgDateClock)
    assert two.duration.total_seconds() == 5400
    assert str(two) == "[2025-01-02 Thu 10:00]--[2025-01-02 Thu 11:30]"
    assert str(three) == "<2025-01-02 Thu 10:00>--<2025-01-02 Thu 11:30>"


def test_runtime_repeated_task_function_with_supported_arities() -> None:
    """repeated_task should create OrgDateRepeatedTask values."""
    three = _execute('repeated_task("<2025-01-02 Thu>", "TODO", none)', [None], None)[0]
    four = _execute(
        'repeated_task("<2025-01-02 Thu>", none, "DONE", true)',
        [None],
        None,
    )[0]

    assert isinstance(three, OrgDateRepeatedTask)
    assert three.before is not None and three.before == "TODO"
    assert cast(object, three.after) is None
    assert str(three) == "[2025-01-02 Thu]"
    assert isinstance(four, OrgDateRepeatedTask)
    assert cast(object, four.before) is None
    assert four.after is not None and four.after == "DONE"
    assert str(four) == "<2025-01-02 Thu>"


def test_runtime_string_and_collection_operator_extensions() -> None:
    """String and collection operator extensions should be supported."""
    multiplied = _execute('"foo" * 2', [None], None)
    concatenated = _execute('"foo" + "bar"', [None], None)
    appended = _execute(".[0] + 4", [[1, 2, 3]], None)
    concatenated_collections = _execute(".[0] + .[1]", [[1, 2, 3], [4]], None)
    removed_scalar = _execute(".[0] - 3", [[1, 2, 3]], None)
    removed_all_matches = _execute(".[0] - 2", [[1, 2, 2, 3]], None)
    diff = _execute(".[0] - .[1]", [[1, 2, 3], [2, 3]], None)

    assert multiplied == ["foofoo"]
    assert concatenated == ["foobar"]
    assert appended == [[1, 2, 3, 4]]
    assert concatenated_collections == [[1, 2, 3, 4]]
    assert removed_scalar == [[1, 2]]
    assert removed_all_matches == [[1, 3]]
    assert diff == [[1]]


def test_runtime_extended_operators_reject_invalid_operands() -> None:
    """Extended operators should still reject unsupported operand shapes."""
    with pytest.raises(QueryRuntimeError):
        _execute('2 * "foo"', [None], None)
    with pytest.raises(QueryRuntimeError):
        _execute('"foo" + 2', [None], None)


def test_runtime_collection_concatenation_preserves_lhs_type() -> None:
    """Collection concatenation should keep the left-hand collection type."""
    tuple_result = _execute(".[0] + .[1]", [(1, 2), [3]], None)
    set_result = _execute(".[0] + .[1]", [{1, 2}, {2, 3}], None)

    assert tuple_result == [(1, 2, 3)]
    assert set_result == [{1, 2, 3}]


def test_runtime_constructor_function_validation_errors() -> None:
    """Constructor functions should validate argument values and arity."""
    with pytest.raises(QueryRuntimeError):
        _execute('timestamp("not a timestamp")', [None], None)
    with pytest.raises(QueryRuntimeError):
        _execute('timestamp("<2025-01-02 Thu>", none, "yes")', [None], None)
    with pytest.raises(QueryRuntimeError):
        _execute('clock("<2025-01-02 Thu 10:00>", none)', [None], None)
    with pytest.raises(QueryRuntimeError):
        _execute('repeated_task("<2025-01-02 Thu>", 1, "DONE")', [None], None)


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
