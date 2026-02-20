#!/usr/bin/env python
"""CLI interface for orgstats - Org-mode archive file analysis."""

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

import orgparse

from orgstats.analyze import (
    AnalysisResult,
    Group,
    Tag,
    TimeRange,
    analyze,
    clean,
)
from orgstats.filters import (
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
    get_gamify_category,
)
from orgstats.histogram import render_histogram
from orgstats.plot import render_timeline_chart
from orgstats.timestamp import extract_timestamp_any


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
            return {line.strip() for line in f if line.strip()}
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


def select_earliest_date(
    date_from: datetime | None,
    global_timerange: TimeRange,
    local_timerange: TimeRange,
) -> date | None:
    """Select earliest date using priority: user filter > global > local.

    Args:
        date_from: User-provided filter date or None
        global_timerange: Global timerange across all tasks
        local_timerange: Local timerange for specific item

    Returns:
        Selected earliest date or None if no dates available
    """
    if date_from:
        return date_from.date()
    if global_timerange.earliest:
        return global_timerange.earliest.date()
    if local_timerange.earliest:
        return local_timerange.earliest.date()
    return None


def select_latest_date(
    date_until: datetime | None,
    global_timerange: TimeRange,
    local_timerange: TimeRange,
) -> date | None:
    """Select latest date using priority: user filter > global > local.

    Args:
        date_until: User-provided filter date or None
        global_timerange: Global timerange across all tasks
        local_timerange: Local timerange for specific item

    Returns:
        Selected latest date or None if no dates available
    """
    if date_until:
        return date_until.date()
    if global_timerange.latest:
        return global_timerange.latest.date()
    if local_timerange.latest:
        return local_timerange.latest.date()
    if local_timerange.earliest:
        return local_timerange.earliest.date()
    return None


def display_category(
    category_name: str,
    tags: dict[str, Tag],
    config: tuple[int, int, int, datetime | None, datetime | None, TimeRange, int, set[str]],
    order_fn: Callable[[tuple[str, Tag]], int],
) -> None:
    """Display formatted output for a single category.

    Args:
        category_name: Display name for the category (e.g., "tags", "heading words")
        tags: Dictionary mapping tag names to Tag objects
        config: Tuple of (max_results, max_relations, num_buckets, date_from, date_until,
                         global_timerange, max_items, exclude_set)
        order_fn: Function to sort items by
    """
    (
        _max_results,
        max_relations,
        num_buckets,
        date_from,
        date_until,
        global_timerange,
        max_items,
        exclude_set,
    ) = config

    if max_items == 0:
        return
    cleaned = clean(exclude_set, tags)
    sorted_items = sorted(cleaned.items(), key=order_fn)[0:max_items]

    print(f"\nTop {category_name}:")

    if not sorted_items:
        print("  No results")
        return
    for idx, (name, tag) in enumerate(sorted_items):
        if idx > 0:
            print()

        time_range = tag.time_range

        if time_range and time_range.earliest and time_range.timeline:
            earliest_date = select_earliest_date(date_from, global_timerange, time_range)
            latest_date = select_latest_date(date_until, global_timerange, time_range)

            if earliest_date and latest_date:
                date_line, chart_line, underline = render_timeline_chart(
                    time_range.timeline,
                    earliest_date,
                    latest_date,
                    num_buckets,
                )
                print(f"  {date_line}")
                print(f"  {chart_line}")
                print(f"  {underline}")

        print(f"  {name}")
        print(f"    Total tasks: {tag.total_tasks}")
        if tag.time_range.earliest and tag.time_range.latest:
            print(f"    Average tasks per day: {tag.avg_tasks_per_day:.2f}")
            print(f"    Max tasks on a single day: {tag.max_single_day_count}")

        if max_relations > 0 and tag.relations:
            filtered_relations = {
                rel_name: count
                for rel_name, count in tag.relations.items()
                if rel_name.lower() not in {e.lower() for e in exclude_set}
            }
            sorted_relations = sorted(filtered_relations.items(), key=lambda x: x[1], reverse=True)[
                0:max_relations
            ]

            if sorted_relations:
                print("    Top relations:")
                for related_name, count in sorted_relations:
                    print(f"      {related_name} ({count})")


def display_groups(
    groups: list[Group],
    exclude_set: set[str],
    config: tuple[int, int, datetime | None, datetime | None, TimeRange],
    max_groups: int,
) -> None:
    """Display tag groups with timelines.

    Args:
        groups: List of Group objects
        exclude_set: Set of tags to exclude
        config: Tuple of (min_group_size, num_buckets, date_from, date_until, global_timerange)
        max_groups: Maximum number of groups to display (0 to omit section entirely)
    """
    if max_groups == 0:
        return

    min_group_size, num_buckets, date_from, date_until, global_timerange = config

    filtered_groups = []
    for group in groups:
        filtered_tags = [tag for tag in group.tags if tag not in exclude_set]
        if len(filtered_tags) >= min_group_size:
            filtered_groups.append((filtered_tags, group))

    filtered_groups.sort(key=lambda x: len(x[0]), reverse=True)
    filtered_groups = filtered_groups[:max_groups]

    print("\nTag groups:")

    if not filtered_groups:
        print("  No results")
        return
    for idx, (group_tags, group) in enumerate(filtered_groups):
        if idx > 0:
            print()

        earliest_date = select_earliest_date(date_from, global_timerange, group.time_range)
        latest_date = select_latest_date(date_until, global_timerange, group.time_range)

        if earliest_date and latest_date:
            date_line, chart_line, underline = render_timeline_chart(
                group.time_range.timeline,
                earliest_date,
                latest_date,
                num_buckets,
            )
            print(f"  {date_line}")
            print(f"  {chart_line}")
            print(f"  {underline}")

        print(f"  {', '.join(group_tags)}")
        print(f"    Total tasks: {group.total_tasks}")
        print(f"    Average tasks per day: {group.avg_tasks_per_day:.2f}")
        print(f"    Max tasks on a single day: {group.max_single_day_count}")


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


def display_top_tasks(nodes: list[orgparse.node.OrgNode], max_results: int) -> None:
    """Display top tasks sorted by most recent timestamp.

    Args:
        nodes: List of org-mode nodes
        max_results: Maximum number of results to display
    """
    top_tasks = get_top_tasks(nodes, max_results)

    if not top_tasks:
        return

    print("\nTop tasks:")
    for node in top_tasks:
        filename = node.env.filename if hasattr(node, "env") and node.env.filename else "unknown"
        todo_state = node.todo if node.todo else ""
        heading = node.heading if node.heading else ""
        print(f"  {filename}: {todo_state} {heading}".strip())


def filter_nodes(nodes: list[orgparse.node.OrgNode], task_type: str) -> list[orgparse.node.OrgNode]:
    """Filter nodes based on task difficulty type.

    Args:
        nodes: List of org-mode nodes to filter
        task_type: Type of tasks to include ("simple", "regular", "hard", or "all")

    Returns:
        Filtered list of nodes
    """
    if task_type == "all":
        return nodes

    return [node for node in nodes if task_type == get_gamify_category(node)]


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        prog="orgstats",
        description="Analyze Emacs Org-mode archive files for task statistics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="Org-mode archive files to analyze",
    )

    parser.add_argument(
        "--max-results",
        "-n",
        type=int,
        default=10,
        metavar="N",
        help="Maximum number of results to display (default: 10)",
    )

    parser.add_argument(
        "--max-tags",
        type=int,
        default=5,
        metavar="N",
        help="Maximum number of tags to display in Top tags section (default: 5, use 0 to omit section)",
    )

    parser.add_argument(
        "--exclude",
        type=str,
        metavar="FILE",
        help="File containing words to exclude (one per line)",
    )

    parser.add_argument(
        "--filter",
        "-f",
        type=str,
        choices=["simple", "regular", "hard", "all"],
        default="all",
        metavar="TYPE",
        help="Filter tasks by difficulty: simple, regular, hard, or all (default: all)",
    )

    parser.add_argument(
        "--show",
        type=str,
        choices=["tags", "heading", "body"],
        default="tags",
        metavar="CATEGORY",
        help="Category to display: tags, heading, or body (default: tags)",
    )

    parser.add_argument(
        "--max-relations",
        type=int,
        default=5,
        metavar="N",
        help="Maximum number of relations to display per item (default: 5, use 0 to omit sections)",
    )

    parser.add_argument(
        "--mapping",
        type=str,
        metavar="FILE",
        help="JSON file containing tag mappings (dict[str, str])",
    )

    parser.add_argument(
        "--min-group-size",
        type=int,
        default=2,
        metavar="N",
        help="Minimum group size to display (default: 2)",
    )

    parser.add_argument(
        "--max-groups",
        type=int,
        default=5,
        metavar="N",
        help="Maximum number of tag groups to display (default: 5, use 0 to omit section)",
    )

    parser.add_argument(
        "--todo-keys",
        type=str,
        default="TODO",
        metavar="KEYS",
        help="Comma-separated list of incomplete task states (default: TODO)",
    )

    parser.add_argument(
        "--done-keys",
        type=str,
        default="DONE",
        metavar="KEYS",
        help="Comma-separated list of completed task states (default: DONE)",
    )

    parser.add_argument(
        "--filter-gamify-exp-above",
        type=int,
        metavar="N",
        help="Filter tasks where gamify_exp > N (non-inclusive, missing defaults to 10)",
    )

    parser.add_argument(
        "--filter-gamify-exp-below",
        type=int,
        metavar="N",
        help="Filter tasks where gamify_exp < N (non-inclusive, missing defaults to 10)",
    )

    parser.add_argument(
        "--filter-repeats-above",
        type=int,
        metavar="N",
        help="Filter tasks where repeat count > N (non-inclusive)",
    )

    parser.add_argument(
        "--filter-repeats-below",
        type=int,
        metavar="N",
        help="Filter tasks where repeat count < N (non-inclusive)",
    )

    parser.add_argument(
        "--filter-date-from",
        type=str,
        metavar="TIMESTAMP",
        help=(
            "Filter tasks with timestamps after date (inclusive). "
            "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
            "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
        ),
    )

    parser.add_argument(
        "--filter-date-until",
        type=str,
        metavar="TIMESTAMP",
        help=(
            "Filter tasks with timestamps before date (inclusive). "
            "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
            "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
        ),
    )

    parser.add_argument(
        "--filter-property",
        action="append",
        dest="filter_properties",
        metavar="KEY=VALUE",
        help="Filter tasks with exact property match (case-sensitive, can specify multiple)",
    )

    parser.add_argument(
        "--filter-tag",
        action="append",
        dest="filter_tags",
        metavar="REGEX",
        help="Filter tasks where any tag matches regex (case-sensitive, can specify multiple)",
    )

    parser.add_argument(
        "--filter-heading",
        action="append",
        dest="filter_headings",
        metavar="REGEX",
        help="Filter tasks where heading matches regex (case-sensitive, can specify multiple)",
    )

    parser.add_argument(
        "--filter-body",
        action="append",
        dest="filter_bodies",
        metavar="REGEX",
        help="Filter tasks where body matches regex (case-sensitive, multiline, can specify multiple)",
    )

    parser.add_argument(
        "--filter-completed",
        action="store_true",
        help="Filter tasks with todo state in done keys",
    )

    parser.add_argument(
        "--filter-not-completed",
        action="store_true",
        help="Filter tasks with todo state in todo keys or without a todo state",
    )

    parser.add_argument(
        "--buckets",
        type=int,
        default=50,
        metavar="N",
        help="Number of time buckets for timeline charts (default: 50, minimum: 20)",
    )

    return parser.parse_args()


def validate_and_parse_keys(keys_str: str, option_name: str) -> list[str]:
    """Parse and validate comma-separated keys.

    Args:
        keys_str: Comma-separated string of keys
        option_name: Name of the option for error messages

    Returns:
        List of validated keys

    Raises:
        SystemExit: If validation fails
    """
    keys = [k.strip() for k in keys_str.split(",") if k.strip()]
    if not keys:
        print(f"Error: {option_name} cannot be empty", file=sys.stderr)
        sys.exit(1)

    for key in keys:
        if "|" in key:
            print(f"Error: {option_name} cannot contain pipe character: '{key}'", file=sys.stderr)
            sys.exit(1)

    return keys


def validate_pattern(pattern: str, option_name: str, use_multiline: bool = False) -> None:
    """Validate that a string is a valid regex pattern.

    Args:
        pattern: Regex pattern string to validate
        option_name: Name of the option for error messages
        use_multiline: Whether to validate with re.MULTILINE flag

    Raises:
        SystemExit: If pattern is not a valid regex
    """
    try:
        if use_multiline:
            re.compile(pattern, re.MULTILINE)
        else:
            re.compile(pattern)
    except re.error as e:
        print(f"Error: Invalid regex pattern for {option_name}: '{pattern}'\n{e}", file=sys.stderr)
        sys.exit(1)


def load_nodes(
    filenames: list[str], todo_keys: list[str], done_keys: list[str], filters: list[Filter]
) -> tuple[list[orgparse.node.OrgNode], list[str], list[str]]:
    """Load, parse, and filter org-mode files.

    Processes each file separately: preprocess → parse → filter → extract keys → combine.

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


def parse_date_argument(date_str: str, arg_name: str) -> datetime:
    """Parse and validate timestamp argument in multiple supported formats.

    Supported formats:
    - YYYY-MM-DD
    - YYYY-MM-DDThh:mm
    - YYYY-MM-DDThh:mm:ss
    - YYYY-MM-DD hh:mm
    - YYYY-MM-DD hh:mm:ss

    Args:
        date_str: Date/timestamp string to parse
        arg_name: Argument name for error messages

    Returns:
        Parsed datetime object

    Raises:
        SystemExit: If format is invalid
    """
    if not date_str or not date_str.strip():
        supported_formats = [
            "YYYY-MM-DD",
            "YYYY-MM-DDThh:mm",
            "YYYY-MM-DDThh:mm:ss",
            "YYYY-MM-DD hh:mm",
            "YYYY-MM-DD hh:mm:ss",
        ]
        formats_str = ", ".join(supported_formats)
        print(
            f"Error: {arg_name} must be in one of these formats: {formats_str}\nGot: '{date_str}'",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        pass

    try:
        return datetime.fromisoformat(date_str.replace(" ", "T"))
    except ValueError:
        pass

    supported_formats = [
        "YYYY-MM-DD",
        "YYYY-MM-DDThh:mm",
        "YYYY-MM-DDThh:mm:ss",
        "YYYY-MM-DD hh:mm",
        "YYYY-MM-DD hh:mm:ss",
    ]
    formats_str = ", ".join(supported_formats)
    print(
        f"Error: {arg_name} must be in one of these formats: {formats_str}\nGot: '{date_str}'",
        file=sys.stderr,
    )
    sys.exit(1)


def parse_property_filter(property_str: str) -> tuple[str, str]:
    """Parse property filter argument in KEY=VALUE format.

    Splits on first '=' to support values containing '='.

    Args:
        property_str: Property filter string

    Returns:
        Tuple of (property_name, property_value)

    Raises:
        SystemExit: If format is invalid (no '=' found)
    """
    if "=" not in property_str:
        print(
            f"Error: --filter-property must be in KEY=VALUE format, got '{property_str}'",
            file=sys.stderr,
        )
        sys.exit(1)

    parts = property_str.split("=", 1)
    return (parts[0], parts[1])


def parse_filter_order_from_argv(argv: list[str]) -> list[str]:
    """Parse command-line order of filter arguments.

    Returns list of (arg_name, position) tuples in command-line order.

    Args:
        argv: sys.argv (command-line arguments)

    Returns:
        List of filter arguments
    """
    filter_args = [
        "--filter",
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


def handle_preset_filter(preset: str) -> list[Filter]:
    """Handle --filter preset expansion.

    Args:
        preset: Preset name (simple, regular, hard, all)

    Returns:
        List of Filter objects for the preset
    """
    if preset == "simple":
        return [Filter(lambda nodes: filter_gamify_exp_below(nodes, 10))]
    if preset == "regular":
        return [
            Filter(lambda nodes: filter_gamify_exp_above(nodes, 9)),
            Filter(lambda nodes: filter_gamify_exp_below(nodes, 20)),
        ]
    if preset == "hard":
        return [Filter(lambda nodes: filter_gamify_exp_above(nodes, 19))]
    return []


def handle_simple_filter(arg_name: str, args: argparse.Namespace) -> list[Filter]:
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


def handle_date_filter(arg_name: str, args: argparse.Namespace) -> list[Filter]:
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


def handle_completion_filter(arg_name: str, args: argparse.Namespace) -> list[Filter]:
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
    args: argparse.Namespace,
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


def create_filter_specs_from_args(
    args: argparse.Namespace, filter_order: list[str]
) -> list[Filter]:
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
        if arg_name == "--filter":
            filter_specs.extend(handle_preset_filter(args.filter))
        elif arg_name in (
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


def build_filter_chain(args: argparse.Namespace, argv: list[str]) -> list[Filter]:
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
    return create_filter_specs_from_args(args, filter_order)


def display_results(
    result: AnalysisResult,
    nodes: list[orgparse.node.OrgNode],
    args: argparse.Namespace,
    display_config: tuple[set[str], datetime | None, datetime | None, list[str], list[str]],
) -> None:
    """Display analysis results in formatted output.

    Args:
        result: Analysis results to display
        nodes: Filtered org-mode nodes used for analysis
        args: Command-line arguments containing display configuration
        display_config: Tuple of (exclude_set, date_from, date_until, done_keys, todo_keys)
    """
    exclude_set, date_from, date_until, done_keys, todo_keys = display_config
    if result.timerange.earliest and result.timerange.latest and result.timerange.timeline:
        earliest_date = date_from.date() if date_from else result.timerange.earliest.date()
        latest_date = date_until.date() if date_until else result.timerange.latest.date()
        date_line, chart_line, underline = render_timeline_chart(
            result.timerange.timeline,
            earliest_date,
            latest_date,
            args.buckets,
        )
        print()
        print(date_line)
        print(chart_line)
        print(underline)

    print(f"Total tasks: {result.total_tasks}")

    if result.timerange.earliest and result.timerange.latest:
        print(f"Average tasks per day: {result.avg_tasks_per_day:.2f}")
        print(f"Max tasks on a single day: {result.max_single_day_count}")
        print(f"Max repeats of a single task: {result.max_repeat_count}")

    print("\nTask states:")
    remaining_states = sorted(
        set(result.task_states.values.keys()) - set(done_keys) - set(todo_keys)
    )
    state_order = done_keys + todo_keys + remaining_states
    histogram_lines = render_histogram(result.task_states, args.buckets, state_order)
    for line in histogram_lines:
        print(f"  {line}")

    print("\nTask categories:")
    category_order = ["simple", "regular", "hard"]
    histogram_lines = render_histogram(result.task_categories, args.buckets, category_order)
    for line in histogram_lines:
        print(f"  {line}")

    print("\nTask occurence day of week:")
    day_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "unknown",
    ]
    histogram_lines = render_histogram(result.task_days, args.buckets, day_order)
    for line in histogram_lines:
        print(f"  {line}")

    display_top_tasks(nodes, args.max_results)

    category_name = CATEGORY_NAMES[args.show]

    def order_by_total(item: tuple[str, Tag]) -> int:
        """Sort by total count (descending)."""
        return -item[1].total_tasks

    display_category(
        category_name,
        result.tags,
        (
            args.max_results,
            args.max_relations,
            args.buckets,
            date_from,
            date_until,
            result.timerange,
            args.max_tags,
            exclude_set,
        ),
        order_by_total,
    )

    display_groups(
        result.tag_groups,
        exclude_set,
        (args.min_group_size, args.buckets, date_from, date_until, result.timerange),
        args.max_groups,
    )


def validate_arguments(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    """Validate command-line arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        Tuple of (todo_keys, done_keys)

    Raises:
        SystemExit: If validation fails
    """
    if args.max_relations < 0:
        print("Error: --max-relations must be non-negative", file=sys.stderr)
        sys.exit(1)

    if args.max_tags < 0:
        print("Error: --max-tags must be non-negative", file=sys.stderr)
        sys.exit(1)

    if args.max_groups < 0:
        print("Error: --max-groups must be non-negative", file=sys.stderr)
        sys.exit(1)

    if args.min_group_size < 0:
        print("Error: --min-group-size must be non-negative", file=sys.stderr)
        sys.exit(1)

    if args.buckets < 20:
        print("Error: --buckets must be at least 20", file=sys.stderr)
        sys.exit(1)

    todo_keys = validate_and_parse_keys(args.todo_keys, "--todo-keys")
    done_keys = validate_and_parse_keys(args.done_keys, "--done-keys")

    if args.filter_tags:
        for pattern in args.filter_tags:
            validate_pattern(pattern, "--filter-tag")

    if args.filter_headings:
        for pattern in args.filter_headings:
            validate_pattern(pattern, "--filter-heading")

    if args.filter_bodies:
        for pattern in args.filter_bodies:
            validate_pattern(pattern, "--filter-body", use_multiline=True)

    return (todo_keys, done_keys)


def main() -> None:
    """Main CLI entry point."""
    args = parse_arguments()

    todo_keys, done_keys = validate_arguments(args)

    mapping = load_mapping(args.mapping) or MAP
    exclude_set = load_exclude_list(args.exclude) or DEFAULT_EXCLUDE

    filters = build_filter_chain(args, sys.argv)

    nodes, todo_keys, done_keys = load_nodes(args.files, todo_keys, done_keys, filters)

    if not nodes:
        print("No results")
        return

    result = analyze(nodes, mapping, args.show, args.max_relations)

    date_from = None
    date_until = None
    if args.filter_date_from is not None:
        date_from = parse_date_argument(args.filter_date_from, "--filter-date-from")
    if args.filter_date_until is not None:
        date_until = parse_date_argument(args.filter_date_until, "--filter-date-until")

    display_results(result, nodes, args, (exclude_set, date_from, date_until, done_keys, todo_keys))


if __name__ == "__main__":
    main()
