"""Shared CLI helpers and data processing utilities."""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import orgparse

from org.analyze import Group, TimeRange, normalize
from org.filters import (
    filter_body,
    filter_completed,
    filter_date_from,
    filter_date_until,
    filter_gamify_exp_above,
    filter_gamify_exp_below,
    filter_heading,
    filter_not_completed,
    filter_property,
    filter_repeats_above,
    filter_repeats_below,
    filter_tag,
)
from org.timestamp import extract_timestamp_any
from org.validation import parse_date_argument, parse_group_values, parse_property_filter


MAP: dict[str, str] = {}

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


@dataclass
class Filter:
    """Specification for a single filter operation."""

    filter: Callable[[list[orgparse.node.OrgNode]], list[orgparse.node.OrgNode]]


class FilterArgs(Protocol):
    """Protocol for filter-related CLI arguments."""

    filter_gamify_exp_above: int | None
    filter_gamify_exp_below: int | None
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


def load_exclude_list(filepath: str | None) -> set[str]:
    """Load exclude list from a file (one word per line).

    Args:
        filepath: Path to exclude list file, or None for empty set

    Returns:
        Set of excluded tags (lowercased, stripped)

    Raises:
        SystemExit: If file cannot be read
    """
    if filepath is None:
        return set()

    try:
        with open(filepath, encoding="utf-8") as f:
            return normalize_exclude_values(list(f))
    except FileNotFoundError:
        print(f"Error: Exclude list file '{filepath}' not found", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied for '{filepath}'", file=sys.stderr)
        sys.exit(1)


def load_mapping(filepath: str | None) -> dict[str, str]:
    """Load tag mapping from a JSON file.

    Args:
        filepath: Path to JSON mapping file, or None for empty dict

    Returns:
        Dictionary mapping tags to canonical forms

    Raises:
        SystemExit: If file cannot be read or JSON is invalid
    """
    if filepath is None:
        return {}

    try:
        with open(filepath, encoding="utf-8") as f:
            mapping = json.load(f)

        if not isinstance(mapping, dict):
            print(f"Error: Mapping file '{filepath}' must contain a JSON object", file=sys.stderr)
            sys.exit(1)

        for key, value in mapping.items():
            if not isinstance(key, str) or not isinstance(value, str):
                print(
                    f"Error: All keys and values in '{filepath}' must be strings",
                    file=sys.stderr,
                )
                sys.exit(1)

        return mapping

    except FileNotFoundError:
        print(f"Error: Mapping file '{filepath}' not found", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied for '{filepath}'", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)


def normalize_exclude_values(values: list[str]) -> set[str]:
    """Normalize exclude values to match file-based behavior."""
    return {line.strip() for line in values if line.strip()}


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


def extract_items_for_category(
    node: orgparse.node.OrgNode, mapping: dict[str, str], category: str
) -> set[str]:
    """Extract normalized items from a node based on category."""
    if category == "tags":
        stripped_tags = {t.strip() for t in node.tags}
        return {mapping.get(t, t) for t in stripped_tags}
    if category == "heading":
        return normalize(set(node.heading.split()), mapping)
    return normalize(set(node.body.split()), mapping)


def combine_time_ranges(tag_time_ranges: dict[str, TimeRange], tags: list[str]) -> TimeRange:
    """Combine time ranges from multiple tags into a single TimeRange."""
    combined = TimeRange()

    for tag in tags:
        if tag not in tag_time_ranges:
            continue

        time_range = tag_time_ranges[tag]

        if time_range.earliest is not None and (
            combined.earliest is None or time_range.earliest < combined.earliest
        ):
            combined.earliest = time_range.earliest

        if time_range.latest is not None and (
            combined.latest is None or time_range.latest > combined.latest
        ):
            combined.latest = time_range.latest

        for date_key, count in time_range.timeline.items():
            combined.timeline[date_key] = combined.timeline.get(date_key, 0) + count

    return combined


def compute_max_single_day(timerange: TimeRange) -> int:
    """Get the maximum number of tasks completed on a single day."""
    if not timerange.timeline:
        return 0
    return max(timerange.timeline.values())


def compute_avg_tasks_per_day(timerange: TimeRange, total_count: int) -> float:
    """Compute average tasks per day for a timerange."""
    if timerange.earliest is None or timerange.latest is None:
        return 0.0

    days_spanned = (timerange.latest.date() - timerange.earliest.date()).days + 1
    if days_spanned <= 0:
        return 0.0

    return total_count / days_spanned


def compute_explicit_groups(
    nodes: list[orgparse.node.OrgNode],
    mapping: dict[str, str],
    category: str,
    group_items: list[list[str]],
    tag_time_ranges: dict[str, TimeRange],
) -> list[Group]:
    """Compute group statistics based on explicit tag lists."""
    groups: list[Group] = []

    for group in group_items:
        present_tags = [tag for tag in group if tag in tag_time_ranges]
        if not present_tags:
            continue

        group_set = set(present_tags)
        total_tasks = 0

        for node in nodes:
            node_items = extract_items_for_category(node, mapping, category)
            if node_items & group_set:
                total_tasks += max(1, len(node.repeated_tasks))

        if total_tasks == 0:
            continue

        time_range = combine_time_ranges(tag_time_ranges, present_tags)
        avg_tasks_per_day = compute_avg_tasks_per_day(time_range, total_tasks)
        max_single_day = compute_max_single_day(time_range)

        groups.append(
            Group(
                tags=present_tags,
                time_range=time_range,
                total_tasks=total_tasks,
                avg_tasks_per_day=avg_tasks_per_day,
                max_single_day_count=max_single_day,
            )
        )

    return groups


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


def parse_filter_order_from_argv(argv: list[str]) -> list[str]:
    """Parse command-line order of filter arguments.

    Returns list of (arg_name, position) tuples in command-line order.

    Args:
        argv: sys.argv (command-line arguments)

    Returns:
        List of filter arguments
    """
    filter_args = [
        "--filter-gamify-exp-above",
        "--filter-gamify-exp-below",
        "--filter-repeats-above",
        "--filter-repeats-below",
        "--filter-date-from",
        "--filter-date-until",
        "--filter-property",
        "--filter-tag",
        "--filter-heading",
        "--filter-body",
        "--filter-completed",
        "--filter-not-completed",
    ]

    return [arg for arg in argv if arg in filter_args]


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


def handle_simple_filter(arg_name: str, args: FilterArgs) -> list[Filter]:
    """Handle simple filter arguments (gamify_exp, repeats).

    Args:
        arg_name: Argument name
        args: Parsed arguments

    Returns:
        List of Filter objects (0 or 1 item)
    """
    if arg_name == "--filter-gamify-exp-above" and args.filter_gamify_exp_above is not None:
        threshold = args.filter_gamify_exp_above
        return [Filter(lambda nodes: filter_gamify_exp_above(nodes, threshold))]

    if arg_name == "--filter-gamify-exp-below" and args.filter_gamify_exp_below is not None:
        threshold = args.filter_gamify_exp_below
        return [Filter(lambda nodes: filter_gamify_exp_below(nodes, threshold))]

    if arg_name == "--filter-repeats-above" and args.filter_repeats_above is not None:
        threshold = args.filter_repeats_above
        return [Filter(lambda nodes: filter_repeats_above(nodes, threshold))]

    if arg_name == "--filter-repeats-below" and args.filter_repeats_below is not None:
        threshold = args.filter_repeats_below
        return [Filter(lambda nodes: filter_repeats_below(nodes, threshold))]

    return []


def handle_date_filter(arg_name: str, args: FilterArgs) -> list[Filter]:
    """Handle date filter arguments.

    Args:
        arg_name: Argument name
        args: Parsed arguments

    Returns:
        List of Filter objects (0 or 1 item)
    """
    if arg_name == "--filter-date-from" and args.filter_date_from is not None:
        date_from = parse_date_argument(args.filter_date_from, "--filter-date-from")
        return [Filter(lambda nodes: filter_date_from(nodes, date_from))]

    if arg_name == "--filter-date-until" and args.filter_date_until is not None:
        date_until = parse_date_argument(args.filter_date_until, "--filter-date-until")
        return [Filter(lambda nodes: filter_date_until(nodes, date_until))]

    return []


def handle_completion_filter(arg_name: str, args: FilterArgs) -> list[Filter]:
    """Handle completion status filter arguments.

    Args:
        arg_name: Argument name
        args: Parsed arguments

    Returns:
        List of Filter objects (0 or 1 item)
    """
    if arg_name == "--filter-completed" and args.filter_completed:
        return [Filter(filter_completed)]

    if arg_name == "--filter-not-completed" and args.filter_not_completed:
        return [Filter(filter_not_completed)]

    return []


def handle_property_filter(name: str, value: str) -> list[Filter]:
    """Handle property filter arguments.

    Args:
        name: Property name
        value: Property value

    Returns:
        List of Filter objects (1 item)
    """
    return [Filter(lambda nodes: filter_property(nodes, name, value))]


def handle_tag_filter(pattern: str) -> list[Filter]:
    """Handle tag filter arguments.

    Args:
        pattern: Regex pattern to match tags

    Returns:
        List of Filter objects (1 item)
    """
    return [Filter(lambda nodes: filter_tag(nodes, pattern))]


def handle_heading_filter(pattern: str) -> list[Filter]:
    """Handle heading filter arguments.

    Args:
        pattern: Regex pattern to match headings

    Returns:
        List of Filter objects (1 item)
    """
    return [Filter(lambda nodes: filter_heading(nodes, pattern))]


def handle_body_filter(pattern: str) -> list[Filter]:
    """Handle body filter arguments.

    Args:
        pattern: Regex pattern to match body text

    Returns:
        List of Filter objects (1 item)
    """
    return [Filter(lambda nodes: filter_body(nodes, pattern))]


def handle_indexed_filter(
    arg_name: str,
    args: FilterArgs,
    index_trackers: dict[str, int],
) -> list[Filter]:
    """Handle indexed filter arguments (property, tag, heading, body).

    Args:
        arg_name: Filter argument name
        args: Parsed arguments
        index_trackers: Dictionary tracking current index for each filter type

    Returns:
        List of Filter objects (0 or 1 item)
    """
    if (
        arg_name == "--filter-property"
        and args.filter_properties
        and index_trackers["property"] < len(args.filter_properties)
    ):
        prop_name, prop_value = parse_property_filter(
            args.filter_properties[index_trackers["property"]]
        )
        index_trackers["property"] += 1
        return handle_property_filter(prop_name, prop_value)

    if (
        arg_name == "--filter-tag"
        and args.filter_tags
        and index_trackers["tag"] < len(args.filter_tags)
    ):
        tag_pattern = args.filter_tags[index_trackers["tag"]]
        index_trackers["tag"] += 1
        return handle_tag_filter(tag_pattern)

    if (
        arg_name == "--filter-heading"
        and args.filter_headings
        and index_trackers["heading"] < len(args.filter_headings)
    ):
        heading_pattern = args.filter_headings[index_trackers["heading"]]
        index_trackers["heading"] += 1
        return handle_heading_filter(heading_pattern)

    if (
        arg_name == "--filter-body"
        and args.filter_bodies
        and index_trackers["body"] < len(args.filter_bodies)
    ):
        body_pattern = args.filter_bodies[index_trackers["body"]]
        index_trackers["body"] += 1
        return handle_body_filter(body_pattern)

    return []


def create_filter_specs_from_args(args: FilterArgs, filter_order: list[str]) -> list[Filter]:
    """Create filter specifications from parsed arguments.

    Args:
        args: Parsed command-line arguments
        filter_order: List of arg_name tuples

    Returns:
        List of Filter objects in command-line order
    """
    filter_specs: list[Filter] = []
    index_trackers = {"property": 0, "tag": 0, "heading": 0, "body": 0}

    for arg_name in filter_order:
        if arg_name in (
            "--filter-gamify-exp-above",
            "--filter-gamify-exp-below",
            "--filter-repeats-above",
            "--filter-repeats-below",
        ):
            filter_specs.extend(handle_simple_filter(arg_name, args))
        elif arg_name in ("--filter-date-from", "--filter-date-until"):
            filter_specs.extend(handle_date_filter(arg_name, args))
        elif arg_name in ("--filter-property", "--filter-tag", "--filter-heading", "--filter-body"):
            filter_specs.extend(handle_indexed_filter(arg_name, args, index_trackers))
        elif arg_name in ("--filter-completed", "--filter-not-completed"):
            filter_specs.extend(handle_completion_filter(arg_name, args))

    return filter_specs


def build_filter_chain(args: FilterArgs, argv: list[str]) -> list[Filter]:
    """Build ordered list of filter functions from CLI arguments.

    Processes filters in command-line order. Expands --filter presets inline
    at their position.

    Args:
        args: Parsed command-line arguments
        argv: Raw sys.argv to determine ordering

    Returns:
        List of filter specs to apply sequentially
    """
    filter_order = parse_filter_order_from_argv(argv)
    filter_order = extend_filter_order_with_defaults(filter_order, args)
    return create_filter_specs_from_args(args, filter_order)


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


def load_nodes(
    filenames: list[str], todo_keys: list[str], done_keys: list[str], filters: list[Filter]
) -> tuple[list[orgparse.node.OrgNode], list[str], list[str]]:
    """Load, parse, and filter org-mode files.

    Processes each file separately: preprocess -> parse -> filter -> extract keys -> combine.

    Args:
        filenames: List of file paths to load
        todo_keys: List of TODO state keywords to prepend to files
        done_keys: List of DONE state keywords to prepend to files
        filters: List of filter specs to apply to nodes from each file

    Returns:
        Tuple of (filtered nodes, all todo keys, all done keys)

    Raises:
        SystemExit: If file cannot be read
    """
    all_nodes: list[orgparse.node.OrgNode] = []
    all_todo_keys: set[str] = set(todo_keys)
    all_done_keys: set[str] = set(done_keys)

    for name in filenames:
        try:
            with open(name, encoding="utf-8") as f:
                print(f"Processing {name}...")

                contents = f.read().replace("24:00", "00:00")

                todo_config = f"#+TODO: {' '.join(todo_keys)} | {' '.join(done_keys)}\n\n"
                contents = todo_config + contents

                ns = orgparse.loads(contents, filename=name)
                if ns is not None:
                    all_todo_keys = all_todo_keys.union(set(ns.env.todo_keys))
                    all_done_keys = all_done_keys.union(set(ns.env.done_keys))

                    file_nodes = list(ns[1:])

                    for filter_spec in filters:
                        file_nodes = filter_spec.filter(file_nodes)

                    all_nodes = all_nodes + file_nodes
        except FileNotFoundError:
            print(f"Error: File '{name}' not found", file=sys.stderr)
            sys.exit(1)
        except PermissionError:
            print(f"Error: Permission denied for '{name}'", file=sys.stderr)
            sys.exit(1)

    return all_nodes, list(all_todo_keys), list(all_done_keys)


def resolve_input_paths(inputs: list[str] | None) -> list[str]:
    """Resolve CLI inputs into a list of org files to process.

    Args:
        inputs: List of CLI path arguments (files and directories)

    Returns:
        List of file paths to process

    Raises:
        SystemExit: If a path does not exist or no org files are found
    """
    resolved_files: list[str] = []
    searched_dirs: list[Path] = []

    targets = inputs or ["."]
    for raw_path in targets:
        path = Path(raw_path)
        if not path.exists():
            print(f"Error: Path '{raw_path}' not found", file=sys.stderr)
            sys.exit(1)

        if path.is_dir():
            searched_dirs.append(path)
            resolved_files.extend(str(file_path) for file_path in sorted(path.glob("*.org")))
            continue

        if path.is_file():
            resolved_files.append(str(path))
            continue

        print(f"Error: Path '{raw_path}' is not a file or directory", file=sys.stderr)
        sys.exit(1)

    if not resolved_files:
        if searched_dirs:
            searched_list = ", ".join(str(path) for path in searched_dirs)
            print(f"Error: No .org files found in: {searched_list}", file=sys.stderr)
        else:
            print("Error: No .org files found", file=sys.stderr)
        sys.exit(1)

    return resolved_files


def resolve_mapping(args: object) -> dict[str, str]:
    """Resolve mapping based on inline or file-based configuration."""
    mapping_inline = getattr(args, "mapping_inline", None)
    if mapping_inline is not None:
        return mapping_inline or MAP
    mapping_file = getattr(args, "mapping", None)
    return load_mapping(mapping_file) or MAP


def resolve_exclude_set(args: object) -> set[str]:
    """Resolve exclude set based on inline or file-based configuration."""
    exclude_inline = getattr(args, "exclude_inline", None)
    if exclude_inline is not None:
        return normalize_exclude_values(exclude_inline) or DEFAULT_EXCLUDE
    exclude_file = getattr(args, "exclude", None)
    return load_exclude_list(exclude_file) or DEFAULT_EXCLUDE
