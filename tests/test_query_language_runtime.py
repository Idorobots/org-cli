"""Sanity tests for query language runtime execution."""

from __future__ import annotations

import logging
from typing import cast

import orgparse
import pytest
from orgparse.date import OrgDate, OrgDateClock, OrgDateRepeatedTask
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


def test_runtime_unary_minus_behavior() -> None:
    """Unary minus should evaluate as subtraction from zero."""
    negated_stream = _execute(".[] | -.", [1, 2, 3], None)
    precedence = _execute("-2 ** 2", [None], None)
    mixed = _execute("1 - -2", [None], None)

    assert negated_stream == [-1, -2, -3]
    assert precedence == [-4]
    assert mixed == [3]


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


def test_runtime_uuid_function_returns_unique_uuidv4_strings() -> None:
    """uuid should emit one UUIDv4 string per input item."""
    result = _execute(".[] | uuid", [1, 2, 3], None)
    assert len(result) == 3
    assert len(set(result)) == 3
    for value in result:
        assert isinstance(value, str)
        assert len(value) == 36


def test_runtime_debug_function_logs_and_returns_input_unchanged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """debug should log values and pass through stream items unchanged."""
    with caplog.at_level(logging.INFO, logger="org"):
        result = _execute(".[0][] | debug", [[1, "x", None]], None)

    assert result == [1, "x", None]
    assert "1" in caplog.text
    assert "x" in caplog.text
    assert "None" in caplog.text


def test_runtime_cast_functions_convert_supported_values() -> None:
    """str/int/float/bool/ts should convert supported value types."""
    converted = _execute(
        'str(1), int("42"), float("3.5"), bool("true")',
        [None],
        None,
    )
    timestamp_value = _execute('ts("<2026-03-01 Sun 10:00-12:00>")', [None], None)

    assert converted == [
        (
            "1",
            42,
            3.5,
            True,
        )
    ]
    assert len(timestamp_value) == 1
    assert isinstance(timestamp_value[0], OrgDate)
    assert str(timestamp_value[0]) == "<2026-03-01 Sun 10:00--12:00>"


def test_runtime_sha256_function_hashes_supported_values() -> None:
    """sha256 should hash supported string inputs."""
    hashed = _execute('"abc" | sha256', [None], None)

    assert hashed == ["ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"]


def test_runtime_match_function_returns_full_match_and_capture_groups() -> None:
    """match should return full match and capture groups for matching strings."""
    result = _execute('.[] | match("(DONE)-([0-9]+)")', ["DONE-42", "TODO-7"], None)
    assert result == [["DONE-42", "DONE", "42"], None]


def test_runtime_if_expression_evaluates_selected_branch() -> None:
    """if should evaluate then/else branch based on condition truthiness."""
    direct = _execute('2 | if . == 2 then "yes" else "no"', [None], None)
    nodes = _sample_nodes()
    per_item = _execute('.[] | if .todo == "DONE" then .heading else "pending"', nodes, None)

    assert direct == ["yes"]
    assert per_item == ["Parent", "pending", "Zeta child", "pending"]


def test_runtime_if_expression_supports_elif_branches() -> None:
    """if should evaluate the first matching elif branch before else."""
    result = _execute(
        '.[0][] | if . == 1 then "one" elif . == 2 then "two" elif . == 3 then "three" else "other"',
        [[1, 2, 3, 4]],
        None,
    )
    assert result == ["one", "two", "three", "other"]


def test_runtime_let_binding_scopes_variable_to_body_only() -> None:
    """let should bind variables only while evaluating the body expression."""
    context_vars: dict[str, object] = {"x": "outer"}
    result = _execute("let . as $x in str($x)", 2, context_vars)

    assert result == ["2"]
    assert context_vars["x"] == "outer"


def test_runtime_let_binding_without_previous_value_clears_variable_after_body() -> None:
    """let should remove newly introduced variables after body evaluation."""
    compiled = compile_query_text('let "v" as $temp in $temp')
    context = EvalContext({})
    result = compiled(Stream([None]), context)

    assert result == ["v"]
    assert "temp" not in context.variables


def test_runtime_let_binding_evaluates_per_input_item() -> None:
    """let should bind values separately for each stream item."""
    result = _execute(".[] | let . as $x in ($x * 2)", [1, 2, 3], None)
    assert result == [2, 4, 6]


def test_runtime_cast_and_match_validation_errors() -> None:
    """Cast and match functions should validate argument and input types."""
    with pytest.raises(QueryRuntimeError):
        _execute("int(1.5)", [None], None)
    with pytest.raises(QueryRuntimeError):
        _execute("float(1)", [None], None)
    with pytest.raises(QueryRuntimeError):
        _execute('bool("yes")', [None], None)
    with pytest.raises(QueryRuntimeError):
        _execute("1 | sha256", [None], None)
    with pytest.raises(QueryRuntimeError):
        _execute('sha256("abc")', [None], None)
    with pytest.raises(QueryRuntimeError):
        _execute(".[] | match(1)", ["value"], None)
    with pytest.raises(QueryRuntimeError):
        _execute('.[] | match("x")', [1], None)


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


def test_runtime_iterate_requires_collection() -> None:
    """Iteration should fail when applied to a scalar."""
    with pytest.raises(QueryRuntimeError):
        _execute(".[]", 1, None)


def test_runtime_index_requires_integer_expression_value() -> None:
    """Index expression values must be integers."""
    with pytest.raises(QueryRuntimeError):
        _execute(".[0][1.5]", [[1, 2, 3]], None)


def test_runtime_index_requires_indexable_base() -> None:
    """Indexing should fail for non-indexable values."""
    with pytest.raises(QueryRuntimeError):
        _execute(".[0][0]", [1], None)


def test_runtime_slice_bounds_must_be_int_or_none() -> None:
    """Slice bounds should reject non-integer values."""
    with pytest.raises(QueryRuntimeError):
        _execute(".[0][1.5:2]", [[1, 2, 3]], None)
    with pytest.raises(QueryRuntimeError):
        _execute(".[0][1:2.5]", [[1, 2, 3]], None)


def test_runtime_bracket_key_must_be_string_or_integer() -> None:
    """Bracket access should reject unsupported key types."""
    with pytest.raises(QueryRuntimeError):
        _execute(".[0][none]", [[1, 2, 3]], None)


def test_runtime_bracket_integer_requires_indexable_base() -> None:
    """Integer bracket access requires list/tuple/string base values."""
    with pytest.raises(QueryRuntimeError):
        _execute(".[0][1]", [{"a": 1}], None)


@pytest.mark.parametrize(
    "query,error_message",
    [
        ("1 / 0", "Division by zero"),
        ("1 mod 0", "Modulo by zero"),
        ("1 rem 0", "Remainder by zero"),
        ("1 quot 0", "Quotient by zero"),
    ],
)
def test_runtime_numeric_zero_division_errors(query: str, error_message: str) -> None:
    """Dividing operators should raise specific zero-division runtime errors."""
    with pytest.raises(QueryRuntimeError, match=error_message):
        _execute(query, [None], None)


def test_runtime_in_operator_requires_collection_rhs() -> None:
    """in operator should reject scalar right-hand values."""
    with pytest.raises(QueryRuntimeError):
        _execute('"a" in 1', [None], None)


def test_runtime_in_operator_with_string_rhs_and_non_string_lhs_is_false() -> None:
    """in against strings should return false for non-string probes."""
    result = _execute('1 in "123"', [None], None)
    assert result == [False]


def test_runtime_string_comparison_operators() -> None:
    """String comparisons should use lexical ordering."""
    result = _execute('"b" > "a", "a" <= "a"', [None], None)
    assert result == [(True, True)]


def test_runtime_org_date_comparison_operators_use_start_values() -> None:
    """Date comparisons should work across OrgDate variants using start values."""
    timestamp_value = _execute('timestamp("<2025-01-02 Thu 10:00>")', [None], None)[0]
    clock_same_start = _execute(
        'clock("<2025-01-02 Thu 10:00>", "<2025-01-02 Thu 11:00>")',
        [None],
        None,
    )[0]
    repeated_later = _execute(
        'repeated_task("<2025-01-03 Fri 09:00>", "TODO", "DONE")',
        [None],
        None,
    )[0]

    equal_result = _execute(
        ".[0] == .[1], .[0] != .[1], .[0] >= .[1], .[0] <= .[1]",
        [timestamp_value, clock_same_start],
        None,
    )
    ordered_result = _execute(
        ".[0] < .[1], .[1] > .[0], .[0] != .[1]",
        [timestamp_value, repeated_later],
        None,
    )

    assert equal_result == [(True, False, True, True)]
    assert ordered_result == [(True, True, True)]


def test_runtime_comparison_rejects_mixed_org_date_and_non_date() -> None:
    """Date comparisons should still reject mixed date/non-date operands."""
    with pytest.raises(QueryRuntimeError):
        _execute('timestamp("<2025-01-02 Thu>") > 1', [None], None)


def test_runtime_org_date_ordering_against_none_returns_false() -> None:
    """Date ordering operators should return false when one side is none."""
    left_none = _execute(
        'timestamp("<2025-01-02 Thu>") > none, '
        'timestamp("<2025-01-02 Thu>") < none, '
        'timestamp("<2025-01-02 Thu>") >= none, '
        'timestamp("<2025-01-02 Thu>") <= none',
        [None],
        None,
    )
    right_none = _execute(
        'none > timestamp("<2025-01-02 Thu>"), '
        'none < timestamp("<2025-01-02 Thu>"), '
        'none >= timestamp("<2025-01-02 Thu>"), '
        'none <= timestamp("<2025-01-02 Thu>")',
        [None],
        None,
    )

    assert left_none == [(False, False, False, False)]
    assert right_none == [(False, False, False, False)]


def test_runtime_org_date_equality_with_none() -> None:
    """Date equality operators should work when compared against none."""
    result = _execute(
        'timestamp("<2025-01-02 Thu>") == none, timestamp("<2025-01-02 Thu>") != none',
        [None],
        None,
    )
    assert result == [(False, True)]


def test_runtime_comparison_operators_with_none_for_any_type() -> None:
    """Ordering comparisons with none should follow language-wide none semantics."""
    result = _execute(
        "1 > none, 1 < none, 1 >= none, 1 <= none, "
        "none > 1, none < 1, none >= 1, none <= 1, "
        "none > none, none < none, none >= none, none <= none, "
        '"x" > none, "x" <= none',
        [None],
        None,
    )

    assert result == [
        (
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            False,
            False,
        )
    ]


def test_runtime_function_arity_validation_for_no_arg_functions() -> None:
    """No-argument functions should reject unexpected argument expressions."""
    with pytest.raises(QueryRuntimeError):
        _execute("reverse(1)", [None], None)


@pytest.mark.parametrize("function_name", ["select", "sort_by", "join", "map", "not"])
def test_runtime_function_arity_validation_for_arg_functions(function_name: str) -> None:
    """Argument-requiring functions should reject missing arguments."""
    with pytest.raises(QueryRuntimeError):
        _execute(function_name, [None], None)


def test_runtime_join_separator_must_be_string() -> None:
    """join should validate separator type."""
    with pytest.raises(QueryRuntimeError):
        _execute("join(1)", ["a", "b"], None)


def test_runtime_sum_requires_numeric_collections() -> None:
    """sum should reject scalar and mixed-type collections."""
    with pytest.raises(QueryRuntimeError):
        _execute("sum", 1, None)
    with pytest.raises(QueryRuntimeError):
        _execute("sum", [1, "x"], None)


def test_runtime_map_requires_collection_input() -> None:
    """map should reject scalar inputs."""
    with pytest.raises(QueryRuntimeError):
        _execute("map(.)", 1, None)


def test_runtime_sort_by_requires_uniform_key_type() -> None:
    """sort_by should fail when key categories are mixed."""
    with pytest.raises(QueryRuntimeError):
        _execute(".[0] | .[] | sort_by(.)", [[1, "a"]], None)


def test_runtime_binary_broadcast_requires_compatible_stream_lengths() -> None:
    """Binary operators should reject incompatible stream lengths."""
    compiled = compile_query_text(".[] + .")
    with pytest.raises(QueryRuntimeError):
        compiled(Stream([[1, 2], [3]]), EvalContext({}))


def test_runtime_tuple_expr_skips_items_when_part_yields_empty_stream() -> None:
    """Tuple combinations should be omitted if any part is empty."""
    result = _execute(".[] | (select(none), .)", [1, 2, 3], None)
    assert result == []


def test_runtime_unique_length_and_reverse_variants() -> None:
    """Utility functions should handle mixed stream and collection inputs."""
    unique_result = _execute(".[0][] | unique", [[1, 1, 2, 2, 3]], None)
    reverse_collection = _execute(".[0] | reverse", [[1, 2, 3]], None)
    reverse_stream = compile_query_text("reverse")(Stream([1, 2, 3]), EvalContext({}))
    length_result = _execute(".[] | length", [[1], {"a": 1}, {1, 2}, "xy", 10], None)

    assert unique_result == [1, 2, 3]
    assert reverse_collection == [[3, 2, 1]]
    assert reverse_stream == [3, 2, 1]
    assert length_result == [1, 1, 2, 2, None]


def test_runtime_constructor_functions_validate_supported_arities() -> None:
    """Constructor functions should reject unsupported argument counts."""
    with pytest.raises(QueryRuntimeError):
        _execute("timestamp(1, 2, 3, 4)", [None], None)
    with pytest.raises(QueryRuntimeError):
        _execute('clock("<2025-01-02 Thu>", "<2025-01-03 Fri>", true, false)', [None], None)
    with pytest.raises(QueryRuntimeError):
        _execute(
            'repeated_task("<2025-01-02 Thu>", "TODO", "DONE", true, false)',
            [None],
            None,
        )


def test_runtime_bracket_field_access_variants() -> None:
    """Bracket field access should work for dicts, nodes, and none bases."""
    dict_value = _execute('.[0]["key"]', [{"key": 7}], None)
    node_value = _execute('.[0]["heading"]', _sample_nodes(), None)
    none_value = _execute('.[0]["missing"]', [None], None)

    assert dict_value == [7]
    assert node_value == ["Parent"]
    assert none_value == [None]


def test_runtime_dict_assignment_sets_and_overwrites_values() -> None:
    """Dictionary assignment should set and overwrite dictionary keys."""
    values = [{"x": 1}, {}]
    result = _execute('.[] | .["x"] = 2', values, None)

    assert result == [{"x": 2}, {"x": 2}]
    assert values == [{"x": 2}, {"x": 2}]


def test_runtime_dict_assignment_with_dot_target() -> None:
    """Dictionary assignment should work with dot field targets."""
    values = [{"meta": {}}, {"meta": {"done": False}}]
    result = _execute(".[] | .meta.done = true", values, None)

    assert result == [{"done": True}, {"done": True}]
    assert values == [{"meta": {"done": True}}, {"meta": {"done": True}}]


def test_runtime_dict_assignment_with_dynamic_key_expression() -> None:
    """Dictionary assignment should support computed bracket keys."""
    values = [{"k": "done", "meta": {}}, {"k": "state", "meta": {}}]
    result = _execute('.[] | .meta[.["k"]] = true; .meta', values, None)

    assert result == [{"done": True}, {"state": True}]
    assert values == [
        {"k": "done", "meta": {"done": True}},
        {"k": "state", "meta": {"state": True}},
    ]


def test_runtime_sequence_evaluates_side_effects_before_returning_right_value() -> None:
    """Sequence should run left side effects and return right expression values."""
    values = [{"x": 1}, {"x": 10}]
    result = _execute('.[] | .["x"] = .["x"] + 1; .["x"]', values, None)

    assert result == [2, 11]
    assert values == [{"x": 2}, {"x": 11}]


def test_runtime_dict_assignment_requires_dictionary_target() -> None:
    """Dictionary assignment should fail for non-dictionary target values."""
    with pytest.raises(QueryRuntimeError):
        _execute('.[] | .["x"] = 1', [1], None)


def test_runtime_dict_assignment_requires_string_key() -> None:
    """Dictionary assignment should reject non-string key values."""
    with pytest.raises(QueryRuntimeError):
        _execute(".[] | .[$k] = 1", [{}], {"k": 1})


def test_runtime_iterate_skips_none_values() -> None:
    """Iteration should ignore none values in collection streams."""
    result = _execute(".[] | .[]", [None, [1, 2]], None)
    assert result == [1, 2]


def test_runtime_index_and_slice_on_org_root_variants() -> None:
    """Root indexing/slicing should support out-of-bounds and full slices."""
    root = _sample_root()
    root_index = _execute(".[0][99]", [root], None)
    root_slice = _execute(".[0][:] | length", [root], None)

    assert root_index == [None]
    assert root_slice == [4]


def test_runtime_slice_requires_sliceable_base() -> None:
    """Slicing should reject non-sliceable scalar values."""
    with pytest.raises(QueryRuntimeError):
        _execute(".[0][1:2]", [1], None)


def test_runtime_matches_requires_string_operands() -> None:
    """matches should reject non-string operands."""
    with pytest.raises(QueryRuntimeError):
        _execute('1 matches "1"', [None], None)


def test_runtime_extended_string_multiplier_requires_integer_rhs() -> None:
    """String multiplication should validate integer multiplier."""
    with pytest.raises(QueryRuntimeError):
        _execute('"foo" * 1.5', [None], None)


def test_runtime_collection_subtraction_preserves_rhs_behavior_for_tuple_and_set() -> None:
    """Collection subtraction should preserve tuple and set output types."""
    tuple_result = _execute(".[0] - .[1]", [(1, 2, 3), (2,)], None)
    set_result = _execute(".[0] - .[1]", [{1, 2, 3}, {2}], None)

    assert tuple_result == [(1, 3)]
    assert set_result == [{1, 3}]


def test_runtime_numeric_and_string_comparison_variants() -> None:
    """Comparison operators should handle all numeric/string directions."""
    numeric = _execute("2 > 1, 2 >= 2, 1 < 2, 1 <= 1", [None], None)
    string = _execute('"b" > "a", "b" >= "b", "a" < "b", "a" <= "a"', [None], None)

    assert numeric == [(True, True, True, True)]
    assert string == [(True, True, True, True)]


def test_runtime_length_supports_org_root() -> None:
    """length should count top-level nodes on org roots."""
    root = _sample_root()
    result = _execute(".[0] | length", [root], None)
    assert result == [4]


def test_runtime_join_supports_org_root_collection_extraction() -> None:
    """join should accept org roots as collection values."""
    root = _sample_root()
    result = _execute('.[0] | map(.heading) | join(",")', [root], None)
    assert result == ["Parent,Alpha child,Zeta child,Second"]


def test_runtime_iter_function_arguments_skip_empty_parts() -> None:
    """Function argument expansion should skip combinations with empty parts."""
    result = _execute('timestamp(select(none), "<2025-01-02 Thu>")', [None], None)
    assert result == []


def test_runtime_parse_org_date_accepts_orgdate_values() -> None:
    """timestamp should accept already-parsed OrgDate values."""
    result = _execute('timestamp(timestamp("<2025-01-02 Thu>"))', [None], None)
    assert [str(value) for value in result] == ["<2025-01-02 Thu>"]


def test_runtime_parse_org_date_rejects_non_string_non_orgdate() -> None:
    """timestamp should reject non-string and non-OrgDate values."""
    with pytest.raises(QueryRuntimeError):
        _execute("timestamp(1)", [None], None)


def test_runtime_parse_org_date_rejects_unparseable_strings() -> None:
    """timestamp should fail for values that cannot be parsed as OrgDate."""
    with pytest.raises(QueryRuntimeError):
        _execute('timestamp("xyz")', [None], None)


def test_runtime_constructor_functions_accept_none_for_optional_active_flag() -> None:
    """Constructor active flags should accept none where supported."""
    result = _execute(
        'clock("<2025-01-02 Thu 10:00>", "<2025-01-02 Thu 10:30>", none)',
        [None],
        None,
    )
    assert len(result) == 1


def test_runtime_unique_skips_duplicate_stream_values() -> None:
    """unique should remove duplicate values from stream output."""
    result = _execute(".[] | unique", [1, 1, 2, 2], None)
    assert result == [1, 2]


def test_runtime_sort_by_all_none_keys_preserves_input_order() -> None:
    """sort_by should keep original order when all keys are none."""
    result = _execute(".[0] | .[] | sort_by(.)", [[None, None]], None)
    assert result == [None, None]


def test_runtime_unsupported_expression_type_raises_runtime_error() -> None:
    """Evaluating unknown AST nodes should raise runtime error."""
    from org.query_language.ast import Expr
    from org.query_language.compiler import compile_expr

    compiled = compile_expr(Expr())
    with pytest.raises(QueryRuntimeError):
        compiled(Stream([None]), EvalContext({}))


def test_runtime_unsupported_function_name_raises_runtime_error() -> None:
    """Unknown function names in AST should raise runtime error."""
    from org.query_language.ast import FunctionCall
    from org.query_language.compiler import compile_expr

    compiled = compile_expr(FunctionCall("unknown", None))
    with pytest.raises(QueryRuntimeError):
        compiled(Stream([None]), EvalContext({}))


def test_runtime_broadcast_with_singleton_side_variants() -> None:
    """Binary operations should broadcast when one side has length one."""
    left_singleton = compile_query_text("1 + .")
    right_singleton = compile_query_text(". + 1")

    assert left_singleton(Stream([2, 3]), EvalContext({})) == [3, 4]
    assert right_singleton(Stream([2, 3]), EvalContext({})) == [3, 4]
