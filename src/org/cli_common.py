"""Shared CLI helpers and data processing utilities."""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, cast

import click
import orgparse
import typer

from org import config as config_module
from org.analyze import TimeRange, normalize
from org.filters import (
    preprocess_gamify_categories,
    preprocess_numeric_gamify_exp,
    preprocess_tags_as_category,
)
from org.parse import load_root_nodes
from org.query_language import (
    EvalContext,
    QueryParseError,
    QueryRuntimeError,
    Stream,
    compile_query_text,
)
from org.query_language.compiler import CompiledQuery
from org.timestamp import extract_timestamp_any
from org.validation import (
    parse_date_argument,
    parse_group_values,
    parse_property_filter,
    validate_and_parse_keys,
    validate_global_arguments,
)


MAP: dict[str, str] = {}

logger = logging.getLogger("org")

TAGS: set[str] = set()

HEADING = {
    "the",
    "to",
    "a",
    "for",
    "in",
    "of",
    "and",
    "on",
    "with",
    "some",
    "out",
    "&",
    "up",
    "from",
    "an",
    "into",
    "new",
    "why",
    "do",
    "ways",
    "say",
    "it",
    "this",
    "is",
    "no",
    "not",
    "that",
    "all",
    "but",
    "be",
    "use",
    "now",
    "will",
    "i",
    "as",
    "or",
    "by",
    "did",
    "can",
    "are",
    "was",
    "more",
    "until",
    "using",
    "when",
    "only",
    "at",
    "it's",
    "have",
    "about",
    "just",
    "get",
    "didn't",
    "can't",
    "my",
    "does",
    "etc",
    "there",
    "yet",
    "nope",
    "should",
    "i'll",
    "nah",
}


DEFAULT_EXCLUDE = TAGS.union(HEADING).union(
    {
        "end",
        "logbook",
        "cancelled",
        "scheduled",
        "suspended",
        "",
    }
)


CATEGORY_NAMES = {"tags": "tags", "heading": "heading words", "body": "body words"}


class FilterArgs(Protocol):
    """Protocol for filter-related CLI arguments."""

    filter_priority: str | None
    filter_level: int | None
    filter_repeats_above: int | None
    filter_repeats_below: int | None
    filter_date_from: str | None
    filter_date_until: str | None
    filter_properties: list[str] | None
    filter_tags: list[str] | None
    filter_headings: list[str] | None
    filter_bodies: list[str] | None
    filter_completed: bool
    filter_not_completed: bool


def is_valid_regex(pattern: str, use_multiline: bool = False) -> bool:
    """Check if a string is a valid regex pattern."""
    try:
        if use_multiline:
            re.compile(pattern, re.MULTILINE)
        else:
            re.compile(pattern)
    except re.error:
        return False
    return True


def get_top_day_info(time_range: TimeRange | None) -> tuple[str, int] | None:
    """Extract top day and its count from TimeRange.

    Args:
        time_range: TimeRange object or None

    Returns:
        Tuple of (date_string, count) or None if no timeline data
    """
    if not time_range or not time_range.timeline:
        return None
    max_count = max(time_range.timeline.values())
    top_day = min(d for d, count in time_range.timeline.items() if count == max_count)
    return (top_day.isoformat(), max_count)


def get_most_recent_timestamp(node: orgparse.node.OrgNode) -> datetime | None:
    """Get the most recent timestamp from a node.

    Args:
        node: Org-mode node

    Returns:
        Most recent datetime or None if no timestamps found
    """
    timestamps = extract_timestamp_any(node)
    return max(timestamps) if timestamps else None


def get_top_tasks(
    nodes: list[orgparse.node.OrgNode], max_results: int
) -> list[orgparse.node.OrgNode]:
    """Get top N nodes sorted by most recent timestamp.

    Args:
        nodes: List of org-mode nodes
        max_results: Maximum number of results to return

    Returns:
        List of nodes sorted by most recent timestamp (descending)
    """
    nodes_with_timestamps: list[tuple[orgparse.node.OrgNode, datetime]] = []
    for node in nodes:
        timestamp = get_most_recent_timestamp(node)
        if timestamp:
            nodes_with_timestamps.append((node, timestamp))

    sorted_nodes = sorted(nodes_with_timestamps, key=lambda x: x[1], reverse=True)

    return [node for node, _ in sorted_nodes[:max_results]]


FILTER_OPTIONS_WITH_VALUE = {
    "--filter-priority",
    "--filter-level",
    "--filter-repeats-above",
    "--filter-repeats-below",
    "--filter-date-from",
    "--filter-date-until",
    "--filter-property",
    "--filter-tag",
    "--filter-heading",
    "--filter-body",
}

FILTER_OPTIONS_FLAGS = {
    "--filter-completed",
    "--filter-not-completed",
}

WITH_OPTIONS_FLAGS = {
    "--with-gamify-category",
    "--with-numeric-gamify-exp",
    "--with-tags-as-category",
}

ORDER_BY_OPTION_TO_VALUE = {
    "--order-by-priority": "priority",
    "--order-by-level": "level",
    "--order-by-file-order": "file-order",
    "--order-by-file-order-reversed": "file-order-reversed",
    "--order-by-timestamp-asc": "timestamp-asc",
    "--order-by-timestamp-desc": "timestamp-desc",
}

ORDER_BY_DEST_TO_VALUE = {
    "order_by_priority": "priority",
    "order_by_level": "level",
    "order_by_file_order": "file-order",
    "order_by_file_order_reversed": "file-order-reversed",
    "order_by_timestamp_asc": "timestamp-asc",
    "order_by_timestamp_desc": "timestamp-desc",
}


@dataclass(frozen=True)
class CustomStageInvocation:
    """One custom switch occurrence parsed from CLI arguments."""

    name: str
    query: str
    arg_value: object


def parse_filter_order_from_argv(argv: list[str]) -> list[str]:
    """Parse filter option order from command-line arguments."""
    filter_order: list[str] = []
    for token in argv:
        if token in FILTER_OPTIONS_WITH_VALUE or token in FILTER_OPTIONS_FLAGS:
            filter_order.append(token)
            continue
        for option_name in FILTER_OPTIONS_WITH_VALUE:
            if token.startswith(f"{option_name}="):
                filter_order.append(option_name)
                break
    return filter_order


def _extract_option_token(token: str) -> str:
    """Return option token without inline assignment suffix."""
    if token.startswith("--") and "=" in token:
        return token.split("=", 1)[0]
    return token


def _custom_option_name(option: str, prefix: str) -> str | None:
    """Extract custom option name after a known prefix."""
    option_prefix = f"--{prefix}-"
    if not option.startswith(option_prefix):
        return None
    return option[len(option_prefix) :]


def _is_configured_custom_option(option: str) -> bool:
    """Return True when option matches one configured custom switch."""
    filter_name = _custom_option_name(option, "filter")
    if filter_name is not None and filter_name in config_module.CONFIG_CUSTOM_FILTERS:
        return True

    order_name = _custom_option_name(option, "order-by")
    if order_name is not None and order_name in config_module.CONFIG_CUSTOM_ORDER_BY:
        return True

    with_name = _custom_option_name(option, "with")
    return with_name is not None and with_name in config_module.CONFIG_CUSTOM_WITH


def _looks_like_path_token(token: str) -> bool:
    """Return True when token resembles a file or directory path."""
    return token in {".", ".."} or "/" in token or token.endswith(".org") or token.startswith("~")


def _is_probable_custom_arg(token: str) -> bool:
    """Return True when token is likely a custom switch argument, not a file path."""
    return not Path(token).exists() and not _looks_like_path_token(token)


def normalize_cli_files_for_custom_switches(files: list[str] | None) -> list[str] | None:
    """Remove configured custom switch tokens from FILE argument values.

    Commands use ``ignore_unknown_options`` to allow config-defined switches. Click still
    parses those unknown switch tokens as FILE values first, so this helper strips them
    before input path resolution.
    """
    if files is None:
        return None

    normalized: list[str] = []
    index = 0
    while index < len(files):
        token = files[index]
        option = _extract_option_token(token)
        if not _is_configured_custom_option(option):
            normalized.append(token)
            index += 1
            continue

        if token.startswith(f"{option}="):
            index += 1
            continue

        next_index = index + 1
        if next_index < len(files):
            next_token = files[next_index]
            if not next_token.startswith("-") and _is_probable_custom_arg(next_token):
                index += 2
                continue

        index += 1

    return normalized


def _consume_custom_optional_arg(
    argv: list[str],
    index: int,
    files: list[str] | None,
) -> tuple[str | None, int]:
    """Consume an optional argument token for a custom switch occurrence."""
    next_index = index + 1
    if next_index >= len(argv):
        return (None, index)

    next_token = argv[next_index]
    if next_token.startswith("-"):
        return (None, index)

    file_values = set(files or [])
    if next_token in file_values:
        return (None, index)

    return (next_token, next_index)


def _coerce_custom_arg_value(value: str | None) -> object:
    """Parse optional custom argument into runtime query value."""
    if value is None:
        return None

    lowered = value.lower()
    value_map: dict[str, object] = {
        "none": None,
        "true": True,
        "false": False,
    }
    if lowered in value_map:
        return value_map[lowered]

    if re.fullmatch(r"-?\d+", value):
        parsed_value: object = int(value)
    elif re.fullmatch(r"-?\d+\.\d+", value):
        parsed_value = float(value)
    else:
        parsed_value = value
    return parsed_value


def _build_custom_invocation(
    *,
    name: str,
    query: str,
    raw_arg: str | None,
) -> CustomStageInvocation:
    """Build one parsed custom invocation with typed context binding."""
    return CustomStageInvocation(
        name=name,
        query=query,
        arg_value=_coerce_custom_arg_value(raw_arg),
    )


def _custom_stage(query: str, arg_value: object) -> str:
    """Build one custom query stage preserving input item stream values."""
    arg_literal = _query_literal(arg_value)
    return f"., ({arg_literal} as $arg) | .[0] | ({query})"


def _query_literal(value: object) -> str:
    """Render a Python value as a query-language literal."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    return json.dumps(value)


def validate_custom_switches(argv: list[str], include_builtin_ordering: bool) -> None:
    """Validate prefixed custom switches against configured/built-in options."""
    builtin_order_options = set(ORDER_BY_OPTION_TO_VALUE) if include_builtin_ordering else set()
    allowed_filter_options = FILTER_OPTIONS_WITH_VALUE.union(FILTER_OPTIONS_FLAGS).union(
        {f"--filter-{name}" for name in config_module.CONFIG_CUSTOM_FILTERS}
    )
    allowed_order_options = builtin_order_options.union(
        {f"--order-by-{name}" for name in config_module.CONFIG_CUSTOM_ORDER_BY}
    )
    allowed_with_options = WITH_OPTIONS_FLAGS.union(
        {f"--with-{name}" for name in config_module.CONFIG_CUSTOM_WITH}
    )

    for token in argv:
        option = _extract_option_token(token)
        if option.startswith("--filter-") and option not in allowed_filter_options:
            raise click.NoSuchOption(option)
        if option.startswith("--order-by-") and option not in allowed_order_options:
            raise click.NoSuchOption(option)
        if option.startswith("--with-") and option not in allowed_with_options:
            raise click.NoSuchOption(option)


def parse_order_values_from_argv(argv: list[str]) -> list[str]:
    """Extract built-in ordering values in command-line argument order."""
    values: list[str] = []
    for token in argv:
        value = ORDER_BY_OPTION_TO_VALUE.get(token)
        if value is not None:
            values.append(value)
    return values


def parse_filter_entries_from_argv(
    argv: list[str],
    files: list[str] | None,
) -> list[str | CustomStageInvocation]:
    """Parse built-in and custom filter switch occurrences in argv order."""
    entries: list[str | CustomStageInvocation] = []
    index = 0
    builtins = FILTER_OPTIONS_WITH_VALUE.union(FILTER_OPTIONS_FLAGS)
    while index < len(argv):
        token = argv[index]
        option = _extract_option_token(token)

        if option in FILTER_OPTIONS_WITH_VALUE or option in FILTER_OPTIONS_FLAGS:
            entries.append(option)
            index += 1
            continue

        name = _custom_option_name(option, "filter")
        if name is None or name not in config_module.CONFIG_CUSTOM_FILTERS or option in builtins:
            index += 1
            continue

        query = config_module.CONFIG_CUSTOM_FILTERS[name]
        if token.startswith(f"{option}="):
            entries.append(
                _build_custom_invocation(
                    name=name,
                    query=query,
                    raw_arg=token.split("=", 1)[1],
                )
            )
            index += 1
            continue

        custom_arg, consumed_index = _consume_custom_optional_arg(argv, index, files)
        entries.append(
            _build_custom_invocation(
                name=name,
                query=query,
                raw_arg=custom_arg,
            )
        )
        index = consumed_index + 1

    return entries


def parse_order_entries_from_argv(
    argv: list[str],
    files: list[str] | None,
    include_builtin_ordering: bool,
) -> list[str | CustomStageInvocation]:
    """Parse built-in and custom ordering switch occurrences in argv order."""
    entries: list[str | CustomStageInvocation] = []
    index = 0
    builtin_options = set(ORDER_BY_OPTION_TO_VALUE) if include_builtin_ordering else set()
    while index < len(argv):
        token = argv[index]
        option = _extract_option_token(token)

        builtin_value = ORDER_BY_OPTION_TO_VALUE.get(option)
        if builtin_value is not None and include_builtin_ordering:
            entries.append(builtin_value)
            index += 1
            continue

        name = _custom_option_name(option, "order-by")
        if (
            name is None
            or name not in config_module.CONFIG_CUSTOM_ORDER_BY
            or option in builtin_options
        ):
            index += 1
            continue

        query = config_module.CONFIG_CUSTOM_ORDER_BY[name]
        if token.startswith(f"{option}="):
            entries.append(
                _build_custom_invocation(
                    name=name,
                    query=query,
                    raw_arg=token.split("=", 1)[1],
                )
            )
            index += 1
            continue

        custom_arg, consumed_index = _consume_custom_optional_arg(argv, index, files)
        entries.append(
            _build_custom_invocation(
                name=name,
                query=query,
                raw_arg=custom_arg,
            )
        )
        index = consumed_index + 1

    return entries


def parse_with_entries_from_argv(
    argv: list[str],
    files: list[str] | None,
) -> list[CustomStageInvocation]:
    """Parse custom enrichment switch occurrences in argv order."""
    entries: list[CustomStageInvocation] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        option = _extract_option_token(token)
        if option in WITH_OPTIONS_FLAGS:
            index += 1
            continue

        name = _custom_option_name(option, "with")
        if name is None or name not in config_module.CONFIG_CUSTOM_WITH:
            index += 1
            continue

        query = config_module.CONFIG_CUSTOM_WITH[name]
        if token.startswith(f"{option}="):
            entries.append(
                _build_custom_invocation(
                    name=name,
                    query=query,
                    raw_arg=token.split("=", 1)[1],
                )
            )
            index += 1
            continue

        custom_arg, consumed_index = _consume_custom_optional_arg(argv, index, files)
        entries.append(
            _build_custom_invocation(
                name=name,
                query=query,
                raw_arg=custom_arg,
            )
        )
        index = consumed_index + 1

    return entries


def count_filter_values(value: list[str] | None) -> int:
    """Count filter values for append-style filters."""
    return len(value) if value else 0


def extend_filter_order_with_defaults(
    filter_order: list[str | CustomStageInvocation], args: FilterArgs
) -> list[str | CustomStageInvocation]:
    """Extend filter order to include config-provided filters."""
    filter_headings = getattr(args, "filter_headings", None)
    filter_bodies = getattr(args, "filter_bodies", None)
    expected_counts = {
        "--filter-priority": 1 if args.filter_priority is not None else 0,
        "--filter-level": 1 if args.filter_level is not None else 0,
        "--filter-repeats-above": 1 if args.filter_repeats_above is not None else 0,
        "--filter-repeats-below": 1 if args.filter_repeats_below is not None else 0,
        "--filter-date-from": 1 if args.filter_date_from is not None else 0,
        "--filter-date-until": 1 if args.filter_date_until is not None else 0,
        "--filter-property": count_filter_values(args.filter_properties),
        "--filter-tag": count_filter_values(args.filter_tags),
        "--filter-heading": count_filter_values(filter_headings),
        "--filter-body": count_filter_values(filter_bodies),
        "--filter-completed": 1 if args.filter_completed else 0,
        "--filter-not-completed": 1 if args.filter_not_completed else 0,
    }

    full_order = list(filter_order)
    for arg_name, expected in expected_counts.items():
        existing = sum(1 for value in full_order if value == arg_name)
        missing = expected - existing
        if missing > 0:
            full_order.extend([arg_name] * missing)

    return full_order


def resolve_date_filters(args: FilterArgs) -> tuple[datetime | None, datetime | None]:
    """Resolve date filter arguments into parsed datetime values."""
    date_from = None
    date_until = None
    if args.filter_date_from is not None:
        date_from = parse_date_argument(args.filter_date_from, "--filter-date-from")
    if args.filter_date_until is not None:
        date_until = parse_date_argument(args.filter_date_until, "--filter-date-until")
    return date_from, date_until


def _quote_string(value: str) -> str:
    """Quote a value as query-language string literal."""
    return json.dumps(value)


def _simple_filter_stage(arg_name: str, args: FilterArgs) -> str | None:
    """Build query stage for non-indexed filter options."""
    stage: str | None = None
    if arg_name == "--filter-priority" and args.filter_priority is not None:
        stage = f"select(.priority == {_quote_string(args.filter_priority)})"
    elif arg_name == "--filter-level" and args.filter_level is not None:
        stage = f"select(.level == {args.filter_level})"
    elif arg_name == "--filter-repeats-above" and args.filter_repeats_above is not None:
        threshold = args.filter_repeats_above
        stage = f"select(.repeated_tasks | length > {threshold})"
    elif arg_name == "--filter-repeats-below" and args.filter_repeats_below is not None:
        threshold = args.filter_repeats_below
        stage = f"select(.repeated_tasks | length < {threshold})"
    elif arg_name == "--filter-date-from" and args.filter_date_from is not None:
        timestamp_value = _quote_string(args.filter_date_from)
        stage = (
            "select(.repeated_tasks + .deadline + .closed + .scheduled "
            f"| max >= timestamp({timestamp_value}))"
        )
    elif arg_name == "--filter-date-until" and args.filter_date_until is not None:
        timestamp_value = _quote_string(args.filter_date_until)
        stage = (
            "select(.repeated_tasks + .deadline + .closed + .scheduled "
            f"| max <= timestamp({timestamp_value}))"
        )
    # FIXME These two should also modify the .repeated_tasks property when mutation is added.
    elif arg_name == "--filter-completed" and args.filter_completed:
        stage = "select(((.repeated_tasks | map(.after)) + .todo)[] in $done_keys)"
    elif arg_name == "--filter-not-completed" and args.filter_not_completed:
        stage = "select(not(((.repeated_tasks | map(.after)) + .todo)[] in $done_keys))"
    return stage


def _indexed_filter_stage(
    arg_name: str, args: FilterArgs, index_trackers: dict[str, int]
) -> str | None:
    """Build query stage for indexed multi-value filter options."""
    if (
        arg_name == "--filter-property"
        and args.filter_properties
        and index_trackers["property"] < len(args.filter_properties)
    ):
        property_name, property_value = parse_property_filter(
            args.filter_properties[index_trackers["property"]]
        )
        index_trackers["property"] += 1
        return (
            "select(.properties["
            f"{_quote_string(property_name)}"
            f"] == {_quote_string(property_value)})"
        )

    if (
        arg_name == "--filter-tag"
        and args.filter_tags
        and index_trackers["tag"] < len(args.filter_tags)
    ):
        pattern = args.filter_tags[index_trackers["tag"]]
        index_trackers["tag"] += 1
        return f"select(.tags[] matches {_quote_string(pattern)})"

    if (
        arg_name == "--filter-heading"
        and args.filter_headings
        and index_trackers["heading"] < len(args.filter_headings)
    ):
        pattern = args.filter_headings[index_trackers["heading"]]
        index_trackers["heading"] += 1
        return f"select(.heading matches {_quote_string(pattern)})"

    if (
        arg_name == "--filter-body"
        and args.filter_bodies
        and index_trackers["body"] < len(args.filter_bodies)
    ):
        pattern = f"(?m){args.filter_bodies[index_trackers['body']]}"
        index_trackers["body"] += 1
        return f"select(.body matches {_quote_string(pattern)})"

    return None


def _filter_stage(arg_name: str, args: FilterArgs, index_trackers: dict[str, int]) -> str | None:
    """Build one query stage for a filter option occurrence."""
    simple_stage = _simple_filter_stage(arg_name, args)
    if simple_stage is not None:
        return simple_stage
    return _indexed_filter_stage(arg_name, args, index_trackers)


def build_filter_stages(
    args: FilterArgs,
    filter_order: list[str | CustomStageInvocation],
) -> list[str]:
    """Build query stages for filter pipeline."""
    filter_stages: list[str] = []
    index_trackers = {"property": 0, "tag": 0, "heading": 0, "body": 0}
    for entry in filter_order:
        if isinstance(entry, CustomStageInvocation):
            filter_stages.append(_custom_stage(entry.query, entry.arg_value))
            continue

        stage = _filter_stage(entry, args, index_trackers)
        if stage is not None:
            filter_stages.append(stage)
    return filter_stages


def extend_order_values_with_defaults(order_values: list[str], args: object) -> list[str]:
    """Append config-provided orderings not present in argv order."""
    expected_counts: dict[str, int] = dict.fromkeys(ORDER_BY_DEST_TO_VALUE.values(), 0)
    for dest_name, value in ORDER_BY_DEST_TO_VALUE.items():
        count = getattr(args, dest_name, 0)
        if isinstance(count, bool):
            expected_counts[value] += int(count)
        elif isinstance(count, int) and count > 0:
            expected_counts[value] += count

    full_order = list(order_values)
    for value, expected in expected_counts.items():
        existing = full_order.count(value)
        missing = expected - existing
        if missing > 0:
            full_order.extend([value] * missing)
    return full_order


def build_order_stages(
    args: object,
    argv: list[str],
    files: list[str] | None,
    include_builtin_ordering: bool,
) -> list[str]:
    """Build query stages for ordering pipeline."""
    order_entries = parse_order_entries_from_argv(argv, files, include_builtin_ordering)
    order_values: list[str | CustomStageInvocation]
    if include_builtin_ordering:
        builtin_order_values: list[str] = []
        for entry in order_entries:
            if isinstance(entry, str):
                builtin_order_values.append(entry)

        expected_builtins = extend_order_values_with_defaults(builtin_order_values, args)
        remaining_builtin_counts: dict[str, int] = {}
        for value in builtin_order_values:
            remaining_builtin_counts[value] = remaining_builtin_counts.get(value, 0) + 1

        missing_builtins: list[str] = []
        for value in expected_builtins:
            remaining = remaining_builtin_counts.get(value, 0)
            if remaining > 0:
                remaining_builtin_counts[value] = remaining - 1
                continue
            missing_builtins.append(value)

        order_values = [*order_entries, *missing_builtins]
        if not order_values:
            order_values = ["timestamp-desc"]
    else:
        order_values = list(order_entries)

    order_stages: list[str] = []
    for order_value in order_values:
        if isinstance(order_value, CustomStageInvocation):
            order_stages.append(_custom_stage(order_value.query, order_value.arg_value))
            continue

        order_stages.extend(_builtin_order_stages(order_value))
    return order_stages


def _builtin_order_stages(value: str) -> list[str]:
    """Build query stages for one built-in ordering value."""
    timestamp_key_expr = ".repeated_tasks + .deadline + .closed + .scheduled | max"
    order_stages: dict[str, list[str]] = {
        "file-order": ["."],
        "file-order-reversed": ["reverse"],
        "priority": ["sort_by(.priority)"],
        "level": ["sort_by(.level)"],
        "timestamp-asc": [
            f"sort_by({timestamp_key_expr})",
            "reverse",
            f"sort_by(({timestamp_key_expr}) != none)",
        ],
        "timestamp-desc": ["sort_by(.repeated_tasks + .deadline + .closed + .scheduled | max)"],
    }
    return order_stages.get(value, [])


def build_with_stages(argv: list[str], files: list[str] | None) -> list[str]:
    """Build query stages for custom enrichment pipeline."""
    invocations = parse_with_entries_from_argv(argv, files)
    stages: list[str] = []
    for invocation in invocations:
        stages.append(_custom_stage(invocation.query, invocation.arg_value))
    return stages


def collect_custom_context_vars(
    argv: list[str],
    files: list[str] | None,
    include_builtin_ordering: bool,
) -> dict[str, object]:
    """Collect custom switch argument values for query evaluation context."""
    del argv, files, include_builtin_ordering
    return {}


def build_query_text(
    args: FilterArgs,
    argv: list[str],
    include_ordering: bool,
    include_slice: bool,
) -> str:
    """Build query text for the configured filter/ordering pipeline."""
    validate_custom_switches(argv, include_ordering)

    files = getattr(args, "files", None)
    filter_order = parse_filter_entries_from_argv(argv, files)
    filter_order = extend_filter_order_with_defaults(filter_order, args)
    filter_stages = build_filter_stages(args, filter_order)
    with_stages = build_with_stages(argv, files)

    stages = [*with_stages, *filter_stages]
    stages.extend(build_order_stages(args, argv, files, include_builtin_ordering=include_ordering))

    pipeline_body = " | ".join(stages)
    base_query = f"[ .[] | {pipeline_body} ]" if pipeline_body else "[ .[] ]"

    if include_slice:
        return f"{base_query}[$offset:($offset + $limit)]"
    return base_query


def build_query(
    args: FilterArgs,
    argv: list[str],
    include_ordering: bool,
    include_slice: bool,
) -> CompiledQuery:
    """Compile query for configured filter/ordering pipeline."""
    query_text = build_query_text(args, argv, include_ordering, include_slice)
    logger.info("Query: %s", query_text)
    return compile_query_text(query_text)


def normalize_show_value(value: str, mapping: dict[str, str]) -> str:
    """Normalize a single show value to match heading/body analysis."""
    normalized = normalize({value}, mapping)
    return next(iter(normalized), "")


def dedupe_values(values: list[str]) -> list[str]:
    """Deduplicate values while preserving order."""
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def resolve_group_values(
    groups: list[str] | None, mapping: dict[str, str], category: str
) -> list[list[str]] | None:
    """Resolve explicit group values from CLI arguments."""
    if groups is None:
        return None

    resolved_groups: list[list[str]] = []
    for group_value in groups:
        raw_values = parse_group_values(group_value)
        if category == "tags":
            group_items = [mapping.get(value, value) for value in raw_values]
        else:
            group_items = []
            for value in raw_values:
                normalized_value = normalize_show_value(value, mapping)
                if normalized_value:
                    group_items.append(normalized_value)
        group_items = dedupe_values(group_items)
        if group_items:
            resolved_groups.append(group_items)

    return resolved_groups


def resolve_input_paths(inputs: list[str] | None) -> list[str]:
    """Resolve CLI inputs into a list of org files to process.

    Args:
        inputs: List of CLI path arguments (files and directories)

    Returns:
        List of file paths to process

    Raises:
        typer.BadParameter: If a path does not exist or no org files are found
    """
    resolved_files: list[str] = []
    searched_dirs: list[Path] = []

    targets = inputs or ["."]
    for raw_path in targets:
        path = Path(raw_path)
        if not path.exists():
            raise typer.BadParameter(f"Path '{raw_path}' not found")

        if path.is_dir():
            searched_dirs.append(path)
            resolved_files.extend(str(file_path) for file_path in sorted(path.glob("*.org")))
            continue

        if path.is_file():
            resolved_files.append(str(path))
            continue

        raise typer.BadParameter(f"Path '{raw_path}' is not a file or directory")

    if not resolved_files:
        if searched_dirs:
            searched_list = ", ".join(str(path) for path in searched_dirs)
            raise typer.BadParameter(f"No .org files found in: {searched_list}")
        raise typer.BadParameter("No .org files found")

    return resolved_files


def resolve_mapping(args: object) -> dict[str, str]:
    """Resolve mapping based on inline or file-based configuration."""
    mapping_inline = getattr(args, "mapping_inline", None)
    if mapping_inline is not None:
        return mapping_inline or MAP
    mapping_file = getattr(args, "mapping", None)
    return config_module.load_mapping(mapping_file) or MAP


def resolve_exclude_set(args: object) -> set[str]:
    """Resolve exclude set based on inline or file-based configuration."""
    exclude_inline = getattr(args, "exclude_inline", None)
    if exclude_inline is not None:
        return config_module.normalize_exclude_values(exclude_inline) or DEFAULT_EXCLUDE
    exclude_file = getattr(args, "exclude", None)
    return config_module.load_exclude_list(exclude_file) or DEFAULT_EXCLUDE


class DataLoadArgs(FilterArgs, Protocol):
    """Protocol for loading and preprocessing data."""

    files: list[str] | None
    todo_keys: str
    done_keys: str
    with_gamify_category: bool
    with_numeric_gamify_exp: bool
    with_tags_as_category: bool
    category_property: str


class SlicedDataLoadArgs(Protocol):
    """Protocol for args that support query slicing."""

    offset: int
    max_results: int


class RootDataLoadArgs(Protocol):
    """Protocol for loading root nodes without filters or enrichment."""

    files: list[str] | None
    todo_keys: str
    done_keys: str


def _resolve_and_load_roots(
    args: RootDataLoadArgs,
) -> tuple[list[orgparse.node.OrgRootNode], list[str], list[str]]:
    """Resolve inputs and load org roots after validating todo/done keys."""
    todo_keys = validate_and_parse_keys(args.todo_keys, "--todo-keys")
    done_keys = validate_and_parse_keys(args.done_keys, "--done-keys")
    return _load_roots_for_inputs(args.files, todo_keys, done_keys)


def _load_roots_for_inputs(
    files: list[str] | None, todo_keys: list[str], done_keys: list[str]
) -> tuple[list[orgparse.node.OrgRootNode], list[str], list[str]]:
    """Resolve file inputs and load all org root nodes."""
    filenames = resolve_input_paths(files)
    return load_root_nodes(filenames, todo_keys, done_keys)


def load_root_data(
    args: RootDataLoadArgs,
) -> tuple[list[orgparse.node.OrgRootNode], list[str], list[str]]:
    """Load org root nodes without filters, enrichment, or ordering."""
    return _resolve_and_load_roots(args)


def load_and_process_data(
    args: DataLoadArgs,
) -> tuple[list[orgparse.node.OrgNode], list[str], list[str]]:
    """Load nodes, preprocess, and apply query-based filters/ordering."""
    include_ordering = hasattr(args, "order_by_level")
    validate_custom_switches(sys.argv, include_ordering)

    normalized_files = normalize_cli_files_for_custom_switches(args.files)
    args.files = normalized_files

    todo_keys, done_keys = validate_global_arguments(args)
    roots, todo_keys, done_keys = _load_roots_for_inputs(normalized_files, todo_keys, done_keys)
    nodes = [node for root in roots for node in root[1:]]

    if args.with_numeric_gamify_exp:
        nodes = preprocess_numeric_gamify_exp(nodes)

    if args.with_gamify_category:
        nodes = preprocess_gamify_categories(nodes, args.category_property)

    if args.with_tags_as_category:
        nodes = preprocess_tags_as_category(nodes, args.category_property)

    include_slice = include_ordering and hasattr(args, "offset") and hasattr(args, "max_results")
    query = build_query(
        args, sys.argv, include_ordering=include_ordering, include_slice=include_slice
    )

    context_vars: dict[str, object] = {
        "todo_keys": todo_keys,
        "done_keys": done_keys,
    }
    context_vars.update(collect_custom_context_vars(sys.argv, normalized_files, include_ordering))
    if include_slice:
        sliced_args = cast(SlicedDataLoadArgs, args)
        context_vars["offset"] = sliced_args.offset
        context_vars["limit"] = sliced_args.max_results

    logger.info("Query context: %s", context_vars)

    try:
        results = query(Stream([nodes]), EvalContext(context_vars))
    except (QueryParseError, QueryRuntimeError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    flattened: list[object]
    if len(results) == 1 and isinstance(results[0], list):
        flattened = cast(list[object], results[0])
    else:
        flattened = list(results)
    nodes = [value for value in flattened if isinstance(value, orgparse.node.OrgNode)]

    return nodes, todo_keys, done_keys
