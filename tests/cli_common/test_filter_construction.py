"""Tests for CLI query construction helpers."""

import logging
from dataclasses import dataclass
from pathlib import Path

import click
import pytest


@dataclass
class FilterArgsStub:
    """Stub arguments for query construction tests."""

    filter_priority: str | None = None
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
    files: list[str] | None = None
    order_by_level: bool = False
    order_by_file_order: bool = False
    order_by_file_order_reversed: bool = False
    order_by_priority: bool = False
    order_by_timestamp_asc: bool = False
    order_by_timestamp_desc: bool = False
    offset: int = 0
    max_results: int = 10
    todo_keys: str = "TODO"
    done_keys: str = "DONE"
    with_gamify_category: bool = False
    with_numeric_gamify_exp: bool = False
    with_tags_as_category: bool = False
    category_property: str = "CATEGORY"


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
        "--filter-priority",
        "A",
        "--filter-tag",
        "work$",
        "file.org",
    ]

    result = parse_filter_order_from_argv(argv)

    assert result == ["--filter-priority", "--filter-tag"]


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


def test_build_query_text_with_priority_ordering() -> None:
    """priority ordering should sort by node priority value."""
    from org.cli_common import build_query_text

    args = make_args(order_by_priority=True)
    argv = ["org", "tasks", "list", "--order-by-priority", "file.org"]

    query = build_query_text(args, argv, include_ordering=True, include_slice=False)

    assert query == "[ .[] | sort_by(.priority) ]"


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


def test_build_query_text_with_custom_filter_and_optional_arg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Custom filter switches should bind $arg and support omitted values."""
    from org import config
    from org.cli_common import build_query_text

    monkeypatch.setattr(
        config,
        "CONFIG_CUSTOM_FILTERS",
        {
            "todo-state": "select(.todo == $arg)",
            "has-todo": "select(.todo != none)",
        },
    )
    monkeypatch.setattr(config, "CONFIG_CUSTOM_ORDER_BY", {})
    monkeypatch.setattr(config, "CONFIG_CUSTOM_WITH", {})

    args = make_args(files=["file.org"])
    argv = [
        "org",
        "tasks",
        "list",
        "--filter-todo-state",
        "3",
        "--filter-has-todo",
        "file.org",
    ]

    query = build_query_text(args, argv, include_ordering=False, include_slice=False)

    assert query == (
        "[ .[] | let 3 as $arg in (select(.todo == $arg))"
        " | let none as $arg in (select(.todo != none)) ]"
    )


def test_collect_custom_context_vars_returns_empty_for_custom_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Custom arguments are embedded in query text and not added to context vars."""
    from org import config
    from org.cli_common import collect_custom_context_vars

    monkeypatch.setattr(config, "CONFIG_CUSTOM_FILTERS", {"value": "select(.v == $arg)"})
    monkeypatch.setattr(config, "CONFIG_CUSTOM_ORDER_BY", {"weight": "sort_by(.priority)"})
    monkeypatch.setattr(config, "CONFIG_CUSTOM_WITH", {"mark": '. + {"x": $arg}'})

    args = make_args(files=["file.org"])
    argv = [
        "org",
        "tasks",
        "list",
        "--with-mark",
        "none",
        "--with-mark",
        "true",
        "--filter-value",
        "12",
        "--order-by-weight",
        "12.5",
        "--order-by-weight",
        "alpha",
        "file.org",
    ]

    context_vars = collect_custom_context_vars(argv, args.files, include_builtin_ordering=True)

    assert context_vars == {}


def test_build_query_text_custom_with_before_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Custom enrichment stages should be applied before filters."""
    from org import config
    from org.cli_common import build_query_text

    monkeypatch.setattr(config, "CONFIG_CUSTOM_FILTERS", {"tagged": "select(.tag != none)"})
    monkeypatch.setattr(config, "CONFIG_CUSTOM_ORDER_BY", {})
    monkeypatch.setattr(config, "CONFIG_CUSTOM_WITH", {"mark": '. + {"x": $arg}'})

    args = make_args(filter_completed=True, files=["file.org"])
    argv = [
        "org",
        "tasks",
        "list",
        "--with-mark",
        "one",
        "--filter-tagged",
        "--filter-completed",
        "file.org",
    ]

    query = build_query_text(args, argv, include_ordering=False, include_slice=False)

    assert query.startswith('[ .[] | let "one" as $arg in (. + {"x": $arg}) | ')
    assert "| let none as $arg in (select(.tag != none)) |" in query


def test_build_query_text_custom_ordering_for_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    """Custom order-by switches should work even when built-in ordering is disabled."""
    from org import config
    from org.cli_common import build_query_text

    monkeypatch.setattr(config, "CONFIG_CUSTOM_FILTERS", {})
    monkeypatch.setattr(config, "CONFIG_CUSTOM_WITH", {})
    monkeypatch.setattr(config, "CONFIG_CUSTOM_ORDER_BY", {"weight": "sort_by(.priority)"})

    args = make_args(files=["file.org"])
    argv = ["org", "stats", "summary", "--order-by-weight", "file.org"]

    query = build_query_text(args, argv, include_ordering=False, include_slice=False)

    assert query == "[ .[] | let none as $arg in (sort_by(.priority)) ]"


def test_load_and_process_data_logs_query_context(caplog: pytest.LogCaptureFixture) -> None:
    """Data loading should log the query execution context."""
    from org.cli_common import load_and_process_data

    fixture_path = str((Path(__file__).resolve().parents[1] / "fixtures" / "simple.org").resolve())
    args = make_args(files=[fixture_path], offset=0, max_results=1)

    with caplog.at_level(logging.INFO, logger="org"):
        load_and_process_data(args)

    assert "Query context:" in caplog.text
    assert "'todo_keys': ['TODO']" in caplog.text


def test_build_query_text_preserves_mixed_ordering_cli_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Built-in and custom ordering switches should follow CLI specification order."""
    from org import config
    from org.cli_common import build_query_text

    monkeypatch.setattr(config, "CONFIG_CUSTOM_FILTERS", {})
    monkeypatch.setattr(config, "CONFIG_CUSTOM_WITH", {})
    monkeypatch.setattr(config, "CONFIG_CUSTOM_ORDER_BY", {"weight": "sort_by(.priority)"})

    args = make_args(order_by_timestamp_desc=True, files=["file.org"])
    argv = [
        "org",
        "tasks",
        "list",
        "--order-by-weight",
        "--order-by-timestamp-desc",
        "file.org",
    ]

    query = build_query_text(args, argv, include_ordering=True, include_slice=False)

    assert query == (
        "[ .[] | let none as $arg in (sort_by(.priority))"
        " | sort_by(.repeated_tasks + .deadline + .closed + .scheduled | max) ]"
    )


def test_build_query_text_rejects_unknown_custom_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown prefixed custom switches should fail validation."""
    from org import config
    from org.cli_common import build_query_text

    monkeypatch.setattr(config, "CONFIG_CUSTOM_FILTERS", {})
    monkeypatch.setattr(config, "CONFIG_CUSTOM_ORDER_BY", {})
    monkeypatch.setattr(config, "CONFIG_CUSTOM_WITH", {})

    args = make_args(files=["file.org"])
    argv = ["org", "tasks", "list", "--filter-unknown", "file.org"]

    with pytest.raises(click.NoSuchOption, match="No such option"):
        build_query_text(args, argv, include_ordering=False, include_slice=False)


def test_get_top_day_info_none() -> None:
    """get_top_day_info returns none with missing timeline."""
    from org.cli_common import get_top_day_info

    result = get_top_day_info(None)

    assert result is None
