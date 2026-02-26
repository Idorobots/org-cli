"""Shared CLI helpers and data processing utilities."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Protocol, cast

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

    filter_gamify_exp_above: int | None
    filter_gamify_exp_below: int | None
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
    "--filter-gamify-exp-above",
    "--filter-gamify-exp-below",
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

ORDER_BY_OPTION = "--order-by"

ORDER_BY_VALUES = {
    "file-order",
    "file-order-reversed",
    "level",
    "timestamp-asc",
    "timestamp-desc",
    "gamify-exp-asc",
    "gamify-exp-desc",
}


def _parse_option_order_from_argv(argv: list[str], option_name: str) -> list[str]:
    """Extract option values in command-line order."""
    values: list[str] = []
    for index, token in enumerate(argv):
        if token == option_name and index + 1 < len(argv):
            values.append(argv[index + 1])
        elif token.startswith(f"{option_name}="):
            values.append(token.split("=", 1)[1])
    return values


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


def normalize_order_by_values(order_by: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """Normalize order-by values into a list."""
    if order_by is None:
        return []
    if isinstance(order_by, list):
        return order_by
    if isinstance(order_by, tuple):
        return list(order_by)
    return [order_by]


def validate_order_by_values(order_by: list[str]) -> None:
    """Validate order-by values."""
    invalid = [value for value in order_by if value not in ORDER_BY_VALUES]
    if not invalid:
        return
    supported = ", ".join(sorted(ORDER_BY_VALUES))
    invalid_list = ", ".join(invalid)
    raise typer.BadParameter(f"--order-by must be one of: {supported}\nGot: {invalid_list}")


def count_filter_values(value: list[str] | None) -> int:
    """Count filter values for append-style filters."""
    return len(value) if value else 0


def extend_filter_order_with_defaults(filter_order: list[str], args: FilterArgs) -> list[str]:
    """Extend filter order to include config-provided filters."""
    filter_headings = getattr(args, "filter_headings", None)
    filter_bodies = getattr(args, "filter_bodies", None)
    expected_counts = {
        "--filter-gamify-exp-above": 1 if args.filter_gamify_exp_above is not None else 0,
        "--filter-gamify-exp-below": 1 if args.filter_gamify_exp_below is not None else 0,
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
        existing = full_order.count(arg_name)
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
    if arg_name == "--filter-gamify-exp-above" and args.filter_gamify_exp_above is not None:
        threshold = args.filter_gamify_exp_above
        stage = f'select(.properties["gamify_exp"] > {threshold})'
    elif arg_name == "--filter-gamify-exp-below" and args.filter_gamify_exp_below is not None:
        threshold = args.filter_gamify_exp_below
        stage = f'select(.properties["gamify_exp"] < {threshold})'
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


def build_filter_stages(args: FilterArgs, filter_order: list[str]) -> list[str]:
    """Build query stages for filter pipeline."""
    filter_stages: list[str] = []
    index_trackers = {"property": 0, "tag": 0, "heading": 0, "body": 0}
    for arg_name in filter_order:
        stage = _filter_stage(arg_name, args, index_trackers)
        if stage is not None:
            filter_stages.append(stage)
    return filter_stages


def extend_order_values_with_defaults(order_values: list[str], args: object) -> list[str]:
    """Append config-provided orderings not present in argv order."""
    desired = normalize_order_by_values(getattr(args, "order_by", None))
    if not desired:
        return order_values

    full_order = list(order_values)
    for value in desired:
        if full_order.count(value) < desired.count(value):
            full_order.append(value)
    return full_order


def build_order_stages(args: object, argv: list[str]) -> list[str]:
    """Build query stages for ordering pipeline."""
    order_values = _parse_option_order_from_argv(argv, ORDER_BY_OPTION)
    order_values = extend_order_values_with_defaults(order_values, args)
    validate_order_by_values(order_values)

    order_stages: list[str] = []
    for value in order_values:
        if value == "file-order":
            order_stages.append(".")
        elif value == "file-order-reversed":
            order_stages.append("reverse")
        elif value == "level":
            order_stages.append("sort_by(.level)")
        elif value == "gamify-exp-asc":
            order_stages.append('sort_by(.properties["gamify_exp"])')
            order_stages.append("reverse")
        elif value == "gamify-exp-desc":
            order_stages.append('sort_by(.properties["gamify_exp"])')
        elif value == "timestamp-asc":
            order_stages.append("sort_by(.repeated_tasks + .deadline + .closed + .scheduled | max)")
            order_stages.append("reverse")
        elif value == "timestamp-desc":
            order_stages.append("sort_by(.repeated_tasks + .deadline + .closed + .scheduled | max)")
    return order_stages


def build_query_text(
    args: FilterArgs,
    argv: list[str],
    include_ordering: bool,
    include_slice: bool,
) -> str:
    """Build query text for the configured filter/ordering pipeline."""
    filter_order = parse_filter_order_from_argv(argv)
    filter_order = extend_filter_order_with_defaults(filter_order, args)
    filter_stages = build_filter_stages(args, filter_order)

    stages = [*filter_stages]
    if include_ordering:
        stages.extend(build_order_stages(args, argv))

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
    todo_keys, done_keys = validate_global_arguments(args)
    roots, todo_keys, done_keys = _load_roots_for_inputs(args.files, todo_keys, done_keys)
    nodes = [node for root in roots for node in root[1:]]

    if args.with_numeric_gamify_exp:
        nodes = preprocess_numeric_gamify_exp(nodes)

    if args.with_gamify_category:
        nodes = preprocess_gamify_categories(nodes, args.category_property)

    if args.with_tags_as_category:
        nodes = preprocess_tags_as_category(nodes, args.category_property)

    include_ordering = hasattr(args, "order_by")
    include_slice = include_ordering and hasattr(args, "offset") and hasattr(args, "max_results")
    query = build_query(
        args, sys.argv, include_ordering=include_ordering, include_slice=include_slice
    )

    context_vars: dict[str, object] = {
        "todo_keys": todo_keys,
        "done_keys": done_keys,
    }
    if include_slice:
        sliced_args = cast(SlicedDataLoadArgs, args)
        context_vars["offset"] = sliced_args.offset
        context_vars["limit"] = sliced_args.max_results

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
