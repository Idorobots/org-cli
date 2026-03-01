"""Tests for CLI query construction helpers."""

import logging
from dataclasses import dataclass

import pytest


@dataclass
class FilterArgsStub:
    """Stub arguments for query construction tests."""

    filter_gamify_exp_above: int | None = None
    filter_gamify_exp_below: int | None = None
    filter_level: int | None = None
    filter_repeats_above: int | None = None
    filter_repeats_below: int | None = None
    filter_date_from: str | None = None
    filter_date_until: str | None = None
    filter_properties: list[str] | None = None
    filter_tags: list[str] | None = None
    filter_headings: list[str] | None = None
    filter_bodies: list[str] | None = None
    filter_completed: bool = False
    filter_not_completed: bool = False
    order_by_level: bool = False
    order_by_file_order: bool = False
    order_by_file_order_reversed: bool = False
    order_by_timestamp_asc: bool = False
    order_by_timestamp_desc: bool = False
    order_by_gamify_exp_asc: bool = False
    order_by_gamify_exp_desc: bool = False
    offset: int = 0
    max_results: int = 10


def make_args(**overrides: object) -> FilterArgsStub:
    """Build a FilterArgsStub with overrides."""
    args = FilterArgsStub()
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_parse_filter_order_from_argv() -> None:
    """Filter order should follow argv position."""
    from org.cli_common import parse_filter_order_from_argv

    argv = [
        "org",
        "tasks",
        "list",
        "--filter-gamify-exp-above",
        "10",
        "--filter-tag",
        "work$",
        "file.org",
    ]

    result = parse_filter_order_from_argv(argv)

    assert result == ["--filter-gamify-exp-above", "--filter-tag"]


def test_parse_filter_order_from_argv_supports_equals_form() -> None:
    """Filter order parsing should support --opt=value form."""
    from org.cli_common import parse_filter_order_from_argv

    argv = ["org", "tasks", "list", "--filter-level=2", "--filter-tag=work", "file.org"]

    result = parse_filter_order_from_argv(argv)

    assert result == ["--filter-level", "--filter-tag"]


def test_parse_order_values_from_argv() -> None:
    """Ordering switches should preserve command-line occurrence order."""
    from org.cli_common import parse_order_values_from_argv

    argv = [
        "org",
        "tasks",
        "list",
        "--order-by-level",
        "--order-by-timestamp-asc",
        "--order-by-level",
        "file.org",
    ]

    result = parse_order_values_from_argv(argv)

    assert result == ["level", "timestamp-asc", "level"]


def test_build_query_text_filters_only() -> None:
    """Query text should include filters in command order."""
    from org.cli_common import build_query_text

    args = make_args(filter_tags=["simple"])
    argv = ["org", "stats", "summary", "--filter-tag", "simple", "file.org"]

    query = build_query_text(args, argv, include_ordering=False, include_slice=False)

    assert query == '[ .[] | select(.tags[] matches "simple") ]'


def test_build_query_text_with_ordering_and_slice() -> None:
    """Query text should append order stages then slice."""
    from org.cli_common import build_query_text

    args = make_args(filter_tags=["work"], order_by_timestamp_desc=True, offset=5, max_results=10)
    argv = [
        "org",
        "tasks",
        "list",
        "--filter-tag",
        "work",
        "--order-by-timestamp-desc",
        "file.org",
    ]

    query = build_query_text(args, argv, include_ordering=True, include_slice=True)

    assert query == (
        '[ .[] | select(.tags[] matches "work") '
        "| sort_by(.repeated_tasks + .deadline + .closed + .scheduled | max) ]"
        "[$offset:($offset + $limit)]"
    )


def test_build_query_text_with_timestamp_asc_keeps_none_last() -> None:
    """timestamp-asc should keep items with no timestamp at the end."""
    from org.cli_common import build_query_text

    args = make_args(order_by_timestamp_asc=True)
    argv = ["org", "tasks", "list", "--order-by-timestamp-asc", "file.org"]

    query = build_query_text(args, argv, include_ordering=True, include_slice=False)

    assert query == (
        "[ .[] | sort_by(.repeated_tasks + .deadline + .closed + .scheduled | max) "
        "| reverse "
        "| sort_by((.repeated_tasks + .deadline + .closed + .scheduled | max) != none) ]"
    )


def test_build_query_text_with_gamify_exp_asc_keeps_none_last() -> None:
    """gamify-exp-asc should keep items with missing value at the end."""
    from org.cli_common import build_query_text

    args = make_args(order_by_gamify_exp_asc=True)
    argv = ["org", "tasks", "list", "--order-by-gamify-exp-asc", "file.org"]

    query = build_query_text(args, argv, include_ordering=True, include_slice=False)

    assert query == (
        '[ .[] | sort_by(.properties["gamify_exp"]) | reverse '
        '| sort_by((.properties["gamify_exp"]) != none) ]'
    )


def test_build_query_text_with_property_filter() -> None:
    """Property filters should quote keys and values."""
    from org.cli_common import build_query_text

    args = make_args(filter_properties=["priority=A"])
    argv = ["org", "stats", "summary", "--filter-property", "priority=A", "file.org"]

    query = build_query_text(args, argv, include_ordering=False, include_slice=False)

    assert query == '[ .[] | select(.properties["priority"] == "A") ]'


def test_build_query_text_with_filter_completed() -> None:
    """Completed filter should include repeated task completion states."""
    from org.cli_common import build_query_text

    args = make_args(filter_completed=True)
    argv = ["org", "tasks", "list", "--filter-completed", "file.org"]

    query = build_query_text(args, argv, include_ordering=False, include_slice=False)

    assert query == ("[ .[] | select(((.repeated_tasks | map(.after)) + .todo)[] in $done_keys) ]")


def test_build_query_text_with_filter_not_completed() -> None:
    """Not-completed filter should include tasks with no done state."""
    from org.cli_common import build_query_text

    args = make_args(filter_not_completed=True)
    argv = ["org", "tasks", "list", "--filter-not-completed", "file.org"]

    query = build_query_text(args, argv, include_ordering=False, include_slice=False)

    assert query == (
        "[ .[] | select(not(((.repeated_tasks | map(.after)) + .todo)[] in $done_keys)) ]"
    )


def test_build_query_logs_query_before_compile(caplog: pytest.LogCaptureFixture) -> None:
    """build_query should log the query text before compilation."""
    from org.cli_common import build_query

    args = make_args(filter_tags=["simple"])
    argv = ["org", "stats", "summary", "--filter-tag", "simple", "file.org"]

    with caplog.at_level(logging.INFO, logger="org"):
        build_query(args, argv, include_ordering=False, include_slice=False)

    assert 'Query: [ .[] | select(.tags[] matches "simple") ]' in caplog.text


def test_get_top_day_info_none() -> None:
    """get_top_day_info returns none with missing timeline."""
    from org.cli_common import get_top_day_info

    result = get_top_day_info(None)

    assert result is None
