#!/usr/bin/env python
"""CLI interface for org - Org-mode archive file analysis."""

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TypeGuard, cast

import orgparse
from colorama import Style
from colorama import init as colorama_init

from org.analyze import (
    AnalysisResult,
    Group,
    Tag,
    TimeRange,
    analyze,
    clean,
)
from org.color import bright_white, dim_white, get_state_color, magenta, should_use_color
from org.filters import (
    filter_body,
    filter_category,
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
    preprocess_gamify_categories,
    preprocess_tags_as_category,
)
from org.histogram import RenderConfig, render_histogram
from org.plot import render_timeline_chart
from org.timestamp import extract_timestamp_any


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


@dataclass
class ConfigOptions:
    """Config option mapping metadata."""

    int_options: dict[str, tuple[str, int | None]]
    bool_options: dict[str, str]
    str_options: dict[str, str]
    list_options: dict[str, str]


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


def load_config(filepath: str) -> tuple[dict[str, object], bool]:
    """Load config from JSON file.

    Args:
        filepath: Path to config file

    Returns:
        Tuple of (config dict, malformed flag)
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        return ({}, False)
    except PermissionError:
        return ({}, True)
    except OSError:
        return ({}, True)
    except json.JSONDecodeError:
        return ({}, True)

    if not isinstance(config, dict):
        return ({}, True)

    return (config, False)


def is_valid_date_argument(value: str) -> bool:
    """Check if date string is valid for parse_date_argument."""
    if not value or not value.strip():
        return False

    try:
        datetime.fromisoformat(value)
        return True
    except ValueError:
        pass

    try:
        datetime.fromisoformat(value.replace(" ", "T"))
        return True
    except ValueError:
        return False


def is_valid_keys_string(value: str) -> bool:
    """Check if comma-separated keys string is valid."""
    if not value or not value.strip():
        return False

    keys = [k.strip() for k in value.split(",") if k.strip()]
    if not keys:
        return False

    return all("|" not in key for key in keys)


def is_string_list(value: object) -> TypeGuard[list[str]]:
    """Check if value is list[str]."""
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def is_string_dict(value: object) -> TypeGuard[dict[str, str]]:
    """Check if value is dict[str, str]."""
    return isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    )


def normalize_exclude_values(values: list[str]) -> set[str]:
    """Normalize exclude values to match file-based behavior."""
    return {line.strip() for line in values if line.strip()}


def parse_color_defaults(config: dict[str, object]) -> tuple[dict[str, object], bool]:
    """Parse color-related config defaults."""
    defaults: dict[str, object] = {}
    color_value = config.get("--color")
    no_color_value = config.get("--no-color")

    if "--color" in config and not isinstance(color_value, bool):
        return ({}, False)
    if "--no-color" in config and not isinstance(no_color_value, bool):
        return ({}, False)
    if (
        isinstance(color_value, bool)
        and isinstance(no_color_value, bool)
        and color_value
        and no_color_value
    ):
        return ({}, False)

    if color_value is True:
        defaults["color_flag"] = True
    if no_color_value is True:
        defaults["color_flag"] = False

    return (defaults, True)


def validate_int_option(value: object, min_value: int | None) -> int | None:
    """Validate integer option value."""
    if not isinstance(value, int):
        return None
    if min_value is not None and value < min_value:
        return None
    return value


def validate_str_option(key: str, value: object) -> str | None:
    """Validate string option value."""
    if not isinstance(value, str):
        return None
    if key == "--config" and not value.strip():
        return None
    if key == "--use" and value not in {"tags", "heading", "body"}:
        return None
    if key in ("--todo-keys", "--done-keys") and not is_valid_keys_string(value):
        return None
    if key in ("--filter-date-from", "--filter-date-until") and not is_valid_date_argument(value):
        return None
    return value


def validate_list_option(key: str, value: object) -> list[str] | None:
    """Validate list option value."""
    if not is_string_list(value):
        return None
    if key == "--filter-property" and any("=" not in item for item in value):
        return None
    if key == "--filter-tag" and any(not is_valid_regex(item) for item in value):
        return None
    if key == "--filter-heading" and any(not is_valid_regex(item) for item in value):
        return None
    if key == "--filter-body" and any(
        not is_valid_regex(item, use_multiline=True) for item in value
    ):
        return None
    return list(value)


def apply_mapping_config(value: object, defaults: dict[str, object]) -> bool:
    """Apply mapping config entry."""
    if isinstance(value, str):
        if not value.strip():
            return False
        defaults["mapping"] = value
        return True
    if is_string_dict(value):
        defaults["mapping_inline"] = value
        return True
    return False


def apply_exclude_config(value: object, defaults: dict[str, object]) -> bool:
    """Apply exclude config entry."""
    if isinstance(value, str):
        if not value.strip():
            return False
        defaults["exclude"] = value
        return True
    if is_string_list(value):
        defaults["exclude_inline"] = list(value)
        return True
    return False


def apply_config_entry_by_options(
    key: str,
    value: object,
    defaults: dict[str, object],
    append_defaults: dict[str, list[str]],
    options: ConfigOptions,
) -> bool:
    """Apply a config entry using option metadata."""
    valid = True

    if key in options.int_options:
        dest, min_value = options.int_options[key]
        int_value = validate_int_option(value, min_value)
        if int_value is None:
            valid = False
        else:
            defaults[dest] = int_value
    elif key in options.bool_options:
        if not isinstance(value, bool):
            valid = False
        else:
            defaults[options.bool_options[key]] = value
    elif key in options.str_options:
        str_value = validate_str_option(key, value)
        if str_value is None:
            valid = False
        else:
            defaults[options.str_options[key]] = str_value
    elif key in options.list_options:
        list_value = validate_list_option(key, value)
        if list_value is None:
            valid = False
        else:
            append_defaults[options.list_options[key]] = list_value

    return valid


def apply_config_entry(
    key: str,
    value: object,
    defaults: dict[str, object],
    append_defaults: dict[str, list[str]],
    options: ConfigOptions,
) -> bool:
    """Apply a config entry to defaults if valid."""
    if key == "--mapping":
        return apply_mapping_config(value, defaults)

    if key == "--exclude":
        return apply_exclude_config(value, defaults)

    return apply_config_entry_by_options(key, value, defaults, append_defaults, options)


def build_config_defaults(
    config: dict[str, object],
) -> tuple[dict[str, object], dict[str, list[str]]] | None:
    """Validate config values and build defaults.

    Args:
        config: Raw config dict

    Returns:
        Tuple of (defaults, append_defaults) or None if malformed
    """
    defaults: dict[str, object] = {}
    append_defaults: dict[str, list[str]] = {}
    valid = True

    color_defaults, color_valid = parse_color_defaults(config)
    if not color_valid:
        return None
    defaults.update(color_defaults)

    int_options: dict[str, tuple[str, int | None]] = {
        "--max-results": ("max_results", None),
        "--max-tags": ("max_tags", 0),
        "--max-relations": ("max_relations", 0),
        "--min-group-size": ("min_group_size", 0),
        "--max-groups": ("max_groups", 0),
        "--buckets": ("buckets", 20),
        "--filter-gamify-exp-above": ("filter_gamify_exp_above", None),
        "--filter-gamify-exp-below": ("filter_gamify_exp_below", None),
        "--filter-repeats-above": ("filter_repeats_above", None),
        "--filter-repeats-below": ("filter_repeats_below", None),
    }

    bool_options: dict[str, str] = {
        "--with-gamify-category": "with_gamify_category",
        "--with-tags-as-category": "with_tags_as_category",
        "--filter-completed": "filter_completed",
        "--filter-not-completed": "filter_not_completed",
    }

    str_options: dict[str, str] = {
        "--filter-category": "filter_category",
        "--category-property": "category_property",
        "--use": "use",
        "--todo-keys": "todo_keys",
        "--done-keys": "done_keys",
        "--filter-date-from": "filter_date_from",
        "--filter-date-until": "filter_date_until",
        "--config": "config",
    }

    list_options: dict[str, str] = {
        "--filter-property": "filter_properties",
        "--filter-tag": "filter_tags",
        "--filter-heading": "filter_headings",
        "--filter-body": "filter_bodies",
    }

    options = ConfigOptions(
        int_options=int_options,
        bool_options=bool_options,
        str_options=str_options,
        list_options=list_options,
    )

    for key, value in config.items():
        if key in ("--color", "--no-color"):
            continue

        if not apply_config_entry(key, value, defaults, append_defaults, options):
            valid = False
            break

    if not valid:
        return None

    return (defaults, append_defaults)


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
    config: tuple[int, int, int, datetime | None, datetime | None, TimeRange, int, set[str], bool],
    order_fn: Callable[[tuple[str, Tag]], int],
) -> None:
    """Display formatted output for a single category.

    Args:
        category_name: Display name for the category (e.g., "tags", "heading words")
        tags: Dictionary mapping tag names to Tag objects
        config: Tuple of (max_results, max_relations, num_buckets, date_from, date_until,
                         global_timerange, max_items, exclude_set, color_enabled)
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
        color_enabled,
    ) = config

    if max_items == 0:
        return
    cleaned = clean(exclude_set, tags)
    sorted_items = sorted(cleaned.items(), key=order_fn)[0:max_items]

    section_header = bright_white(f"\n{category_name.upper()}", color_enabled)
    print(section_header)

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
                    color_enabled,
                )
                print(f"  {date_line}")
                print(f"  {chart_line}")
                print(f"  {underline}")

        print(f"  {name}")
        total_tasks_value = magenta(str(tag.total_tasks), color_enabled)
        print(f"    Total tasks: {total_tasks_value}")
        if tag.time_range.earliest and tag.time_range.latest:
            avg_value = magenta(f"{tag.avg_tasks_per_day:.2f}", color_enabled)
            max_value = magenta(str(tag.max_single_day_count), color_enabled)
            print(f"    Average tasks per day: {avg_value}")
            print(f"    Max tasks on a single day: {max_value}")

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
    config: tuple[int, int, datetime | None, datetime | None, TimeRange, bool],
    max_groups: int,
) -> None:
    """Display tag groups with timelines.

    Args:
        groups: List of Group objects
        exclude_set: Set of tags to exclude
        config: Tuple of (min_group_size, num_buckets, date_from, date_until,
                         global_timerange, color_enabled)
        max_groups: Maximum number of groups to display (0 to omit section entirely)
    """
    if max_groups == 0:
        return

    min_group_size, num_buckets, date_from, date_until, global_timerange, color_enabled = config

    filtered_groups = []
    for group in groups:
        filtered_tags = [tag for tag in group.tags if tag not in exclude_set]
        if len(filtered_tags) >= min_group_size:
            filtered_groups.append((filtered_tags, group))

    filtered_groups.sort(key=lambda x: len(x[0]), reverse=True)
    filtered_groups = filtered_groups[:max_groups]

    section_header = bright_white("\nGROUPS", color_enabled)
    print(section_header)

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
                color_enabled,
            )
            print(f"  {date_line}")
            print(f"  {chart_line}")
            print(f"  {underline}")

        print(f"  {', '.join(group_tags)}")
        total_tasks_value = magenta(str(group.total_tasks), color_enabled)
        avg_value = magenta(f"{group.avg_tasks_per_day:.2f}", color_enabled)
        max_value = magenta(str(group.max_single_day_count), color_enabled)
        print(f"    Total tasks: {total_tasks_value}")
        print(f"    Average tasks per day: {avg_value}")
        print(f"    Max tasks on a single day: {max_value}")


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


def display_top_tasks(
    nodes: list[orgparse.node.OrgNode],
    max_results: int,
    color_enabled: bool,
    done_keys: list[str],
    todo_keys: list[str],
) -> None:
    """Display top tasks sorted by most recent timestamp.

    Args:
        nodes: List of org-mode nodes
        max_results: Maximum number of results to display
        color_enabled: Whether to apply colors to the output
        done_keys: List of done state keywords
        todo_keys: List of todo state keywords
    """
    top_tasks = get_top_tasks(nodes, max_results)

    if not top_tasks:
        return

    section_header = bright_white("\nTASKS", color_enabled)
    print(section_header)
    for node in top_tasks:
        filename = node.env.filename if hasattr(node, "env") and node.env.filename else "unknown"
        colored_filename = dim_white(f"{filename}:", color_enabled)
        todo_state = node.todo if node.todo else ""
        heading = node.heading if node.heading else ""

        if todo_state:
            state_color = get_state_color(todo_state, done_keys, todo_keys, color_enabled)
            if color_enabled and state_color:
                colored_state = f"{state_color}{todo_state}{Style.RESET_ALL}"
            else:
                colored_state = todo_state
            print(f"  {colored_filename} {colored_state} {heading}".strip())
        else:
            print(f"  {colored_filename} {heading}".strip())


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        prog="org",
        description="Analyze Emacs Org-mode archive files for task statistics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--config",
        type=str,
        default=".org-cli.json",
        metavar="FILE",
        help="Config file name to load from current directory (default: .org-cli.json)",
    )

    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="Org-mode archive files or directories to analyze",
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
        help="Maximum number of tags to display in TAGS section (default: 5, use 0 to omit section)",
    )

    parser.add_argument(
        "--exclude",
        type=str,
        metavar="FILE",
        help="File containing words to exclude (one per line)",
    )

    parser.add_argument(
        "--filter-category",
        type=str,
        default="all",
        metavar="VALUE",
        help=(
            "Filter tasks by category property value (e.g., simple, regular, hard, none, "
            "or any custom value). Use 'all' to skip category filtering (default: all)"
        ),
    )

    parser.add_argument(
        "--use",
        type=str,
        choices=["tags", "heading", "body"],
        default="tags",
        metavar="CATEGORY",
        help="Category to display: tags, heading, or body (default: tags)",
    )

    parser.add_argument(
        "--with-gamify-category",
        action="store_true",
        help="Preprocess nodes to set category property based on gamify_exp value",
    )

    parser.add_argument(
        "--with-tags-as-category",
        action="store_true",
        help="Preprocess nodes to set category property based on first tag",
    )

    parser.add_argument(
        "--category-property",
        type=str,
        default="CATEGORY",
        metavar="PROPERTY",
        help="Property name to use for category histogram and filtering (default: CATEGORY)",
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

    color_group = parser.add_mutually_exclusive_group()
    color_group.add_argument(
        "--color",
        action="store_true",
        dest="color_flag",
        default=None,
        help="Force colored output (default: auto-detect based on TTY)",
    )

    color_group.add_argument(
        "--no-color",
        action="store_false",
        dest="color_flag",
        help="Disable colored output",
    )

    parser.set_defaults(mapping_inline=None, exclude_inline=None)

    return parser


def parse_config_argument(argv: list[str]) -> str:
    """Parse only the --config argument from argv."""
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=str, default=".org-cli.json")
    config_args, _ = config_parser.parse_known_args(argv[1:])
    return cast(str, config_args.config)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = create_parser()

    config_name = parse_config_argument(sys.argv)
    config_path = Path(config_name)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_name
    config, load_error = load_config(str(config_path))

    append_defaults: dict[str, list[str]] = {}
    if load_error:
        print("Malformed config", file=sys.stderr)
    else:
        config_defaults = build_config_defaults(config)
        if config_defaults is None:
            print("Malformed config", file=sys.stderr)
        else:
            defaults, append_defaults = config_defaults
            if defaults:
                parser.set_defaults(**defaults)

    args = parser.parse_args()

    for dest, values in append_defaults.items():
        if getattr(args, dest) is None:
            setattr(args, dest, values)

    return args


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


def resolve_input_paths(inputs: list[str]) -> list[str]:
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
        "--filter-category",
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


def extend_filter_order_with_defaults(
    filter_order: list[str], args: argparse.Namespace
) -> list[str]:
    """Extend filter order to include config-provided filters."""
    filter_headings = getattr(args, "filter_headings", None)
    filter_bodies = getattr(args, "filter_bodies", None)
    expected_counts = {
        "--filter-category": 1 if args.filter_category != "all" else 0,
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


def handle_preset_filter(preset: str, category_property: str) -> list[Filter]:
    """Handle --filter-category preset expansion.

    Args:
        preset: Category value to filter by (e.g., simple, regular, hard, none, etc.)
        category_property: Name of property to check

    Returns:
        List of Filter objects for the preset
    """

    return [Filter(lambda nodes: filter_category(nodes, category_property, preset))]


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
        if arg_name == "--filter-category":
            filter_specs.extend(handle_preset_filter(args.filter_category, args.category_property))
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
    filter_order = extend_filter_order_with_defaults(filter_order, args)
    return create_filter_specs_from_args(args, filter_order)


def display_results(
    result: AnalysisResult,
    nodes: list[orgparse.node.OrgNode],
    args: argparse.Namespace,
    display_config: tuple[set[str], datetime | None, datetime | None, list[str], list[str], bool],
) -> None:
    """Display analysis results in formatted output.

    Args:
        result: Analysis results to display
        nodes: Filtered org-mode nodes used for analysis
        args: Command-line arguments containing display configuration
        display_config: Tuple of (exclude_set, date_from, date_until, done_keys, todo_keys,
                                  color_enabled)
    """
    exclude_set, date_from, date_until, done_keys, todo_keys, color_enabled = display_config
    if result.timerange.earliest and result.timerange.latest and result.timerange.timeline:
        earliest_date = date_from.date() if date_from else result.timerange.earliest.date()
        latest_date = date_until.date() if date_until else result.timerange.latest.date()
        date_line, chart_line, underline = render_timeline_chart(
            result.timerange.timeline,
            earliest_date,
            latest_date,
            args.buckets,
            color_enabled,
        )
        print()
        print(date_line)
        print(chart_line)
        print(underline)

    total_tasks_value = magenta(str(result.total_tasks), color_enabled)
    print(f"Total tasks: {total_tasks_value}")

    if result.timerange.earliest and result.timerange.latest:
        avg_value = magenta(f"{result.avg_tasks_per_day:.2f}", color_enabled)
        max_single_value = magenta(str(result.max_single_day_count), color_enabled)
        max_repeat_value = magenta(str(result.max_repeat_count), color_enabled)
        print(f"Average tasks per day: {avg_value}")
        print(f"Max tasks on a single day: {max_single_value}")
        print(f"Max repeats of a single task: {max_repeat_value}")

    task_states_header = bright_white("\nTask states:", color_enabled)
    print(task_states_header)
    remaining_states = sorted(
        set(result.task_states.values.keys()) - set(done_keys) - set(todo_keys)
    )
    state_order = done_keys + todo_keys + remaining_states
    histogram_lines = render_histogram(
        result.task_states,
        args.buckets,
        state_order,
        RenderConfig(
            color_enabled=color_enabled,
            histogram_type="task_states",
            done_keys=done_keys,
            todo_keys=todo_keys,
        ),
    )
    for line in histogram_lines:
        print(f"  {line}")

    task_categories_header = bright_white("\nTask categories:", color_enabled)
    print(task_categories_header)
    category_order = sorted(result.task_categories.values.keys())
    histogram_lines = render_histogram(
        result.task_categories,
        args.buckets,
        category_order,
        RenderConfig(color_enabled=color_enabled),
    )
    for line in histogram_lines:
        print(f"  {line}")

    task_days_header = bright_white("\nTask occurrence by day of week:", color_enabled)
    print(task_days_header)
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
    histogram_lines = render_histogram(
        result.task_days, args.buckets, day_order, RenderConfig(color_enabled=color_enabled)
    )
    for line in histogram_lines:
        print(f"  {line}")

    display_top_tasks(nodes, args.max_results, color_enabled, done_keys, todo_keys)

    category_name = CATEGORY_NAMES[args.use]

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
            color_enabled,
        ),
        order_by_total,
    )

    display_groups(
        result.tag_groups,
        exclude_set,
        (args.min_group_size, args.buckets, date_from, date_until, result.timerange, color_enabled),
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

    color_enabled = should_use_color(args.color_flag)

    if color_enabled:
        colorama_init(autoreset=True, strip=False)

    todo_keys, done_keys = validate_arguments(args)

    mapping_inline = args.mapping_inline
    if mapping_inline is not None:
        mapping = mapping_inline or MAP
    else:
        mapping = load_mapping(args.mapping) or MAP

    exclude_inline = args.exclude_inline
    if exclude_inline is not None:
        exclude_set = normalize_exclude_values(exclude_inline) or DEFAULT_EXCLUDE
    else:
        exclude_set = load_exclude_list(args.exclude) or DEFAULT_EXCLUDE

    filters = build_filter_chain(args, sys.argv)

    filenames = resolve_input_paths(args.files)
    nodes, todo_keys, done_keys = load_nodes(filenames, todo_keys, done_keys, [])

    if args.with_gamify_category:
        nodes = preprocess_gamify_categories(nodes, args.category_property)

    if args.with_tags_as_category:
        nodes = preprocess_tags_as_category(nodes, args.category_property)

    for filter_spec in filters:
        nodes = filter_spec.filter(nodes)

    if not nodes:
        print("No results")
        return

    result = analyze(nodes, mapping, args.use, args.max_relations, args.category_property)

    date_from = None
    date_until = None
    if args.filter_date_from is not None:
        date_from = parse_date_argument(args.filter_date_from, "--filter-date-from")
    if args.filter_date_until is not None:
        date_until = parse_date_argument(args.filter_date_until, "--filter-date-until")

    display_results(
        result,
        nodes,
        args,
        (exclude_set, date_from, date_until, done_keys, todo_keys, color_enabled),
    )


if __name__ == "__main__":
    main()
