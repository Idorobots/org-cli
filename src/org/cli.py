#!/usr/bin/env python
"""CLI interface for org - Org-mode archive file analysis."""

import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import TypeGuard

import orgparse
import typer
from colorama import Style
from colorama import init as colorama_init

from org.analyze import (
    AnalysisResult,
    Group,
    Tag,
    TimeRange,
    analyze,
    clean,
    normalize,
)
from org.color import bright_white, dim_white, get_state_color, magenta, should_use_color
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


COMMAND_OPTION_NAMES = {
    "buckets",
    "category_property",
    "color_flag",
    "config",
    "done_keys",
    "exclude",
    "filter_bodies",
    "filter_completed",
    "filter_date_from",
    "filter_date_until",
    "filter_gamify_exp_above",
    "filter_gamify_exp_below",
    "filter_headings",
    "filter_not_completed",
    "filter_properties",
    "filter_repeats_above",
    "filter_repeats_below",
    "filter_tags",
    "mapping",
    "max_groups",
    "max_relations",
    "max_results",
    "max_tags",
    "min_group_size",
    "todo_keys",
    "use",
    "with_gamify_category",
    "with_tags_as_category",
    "show",
    "groups",
}


CONFIG_APPEND_DEFAULTS: dict[str, list[str]] = {}
CONFIG_INLINE_DEFAULTS: dict[str, object] = {}


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


@dataclass
class ConfigContext:
    """Config default targets and option metadata."""

    defaults: dict[str, object]
    stats_defaults: dict[str, object]
    append_defaults: dict[str, list[str]]
    global_options: ConfigOptions
    stats_options: ConfigOptions


@dataclass
class ArgsPayload:
    """Payload for CLI argument values."""

    files: list[str] | None
    config: str
    exclude: str | None
    mapping: str | None
    todo_keys: str
    done_keys: str
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
    color_flag: bool | None
    max_results: int
    max_tags: int
    use: str
    with_gamify_category: bool
    with_tags_as_category: bool
    category_property: str
    max_relations: int
    min_group_size: int
    max_groups: int
    buckets: int
    show: str | None
    groups: list[str] | None


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
    stripped = value.strip()
    if key in ("--config", "--show") and not stripped:
        return None

    invalid_use = key == "--use" and value not in {"tags", "heading", "body"}
    invalid_keys = key in ("--todo-keys", "--done-keys") and not is_valid_keys_string(value)
    invalid_dates = key in (
        "--filter-date-from",
        "--filter-date-until",
    ) and not is_valid_date_argument(value)
    if invalid_use or invalid_keys or invalid_dates:
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
    context: ConfigContext,
) -> bool:
    """Apply a config entry to defaults if valid."""
    if key == "--mapping":
        return apply_mapping_config(value, context.defaults)

    if key == "--exclude":
        return apply_exclude_config(value, context.defaults)

    option_sets = (
        (context.global_options, context.defaults),
        (context.stats_options, context.stats_defaults),
    )

    for options, defaults in option_sets:
        if (
            key in options.int_options
            or key in options.bool_options
            or key in options.str_options
            or key in options.list_options
        ):
            return apply_config_entry_by_options(
                key, value, defaults, context.append_defaults, options
            )

    return False


def build_config_defaults(
    config: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, list[str]]] | None:
    """Validate config values and build defaults.

    Args:
        config: Raw config dict

    Returns:
        Tuple of (defaults, append_defaults) or None if malformed
    """
    defaults: dict[str, object] = {}
    stats_defaults: dict[str, object] = {}
    append_defaults: dict[str, list[str]] = {}
    valid = True

    color_defaults, color_valid = parse_color_defaults(config)
    if not color_valid:
        return None
    defaults.update(color_defaults)

    stats_int_options: dict[str, tuple[str, int | None]] = {
        "--max-results": ("max_results", None),
        "--max-tags": ("max_tags", 0),
        "--max-relations": ("max_relations", 0),
        "--min-group-size": ("min_group_size", 0),
        "--max-groups": ("max_groups", 0),
        "--buckets": ("buckets", 20),
    }

    global_int_options: dict[str, tuple[str, int | None]] = {
        "--filter-gamify-exp-above": ("filter_gamify_exp_above", None),
        "--filter-gamify-exp-below": ("filter_gamify_exp_below", None),
        "--filter-repeats-above": ("filter_repeats_above", None),
        "--filter-repeats-below": ("filter_repeats_below", None),
    }

    stats_bool_options: dict[str, str] = {
        "--with-gamify-category": "with_gamify_category",
        "--with-tags-as-category": "with_tags_as_category",
    }

    global_bool_options: dict[str, str] = {
        "--filter-completed": "filter_completed",
        "--filter-not-completed": "filter_not_completed",
    }

    stats_str_options: dict[str, str] = {
        "--category-property": "category_property",
        "--use": "use",
        "--show": "show",
    }

    global_str_options: dict[str, str] = {
        "--todo-keys": "todo_keys",
        "--done-keys": "done_keys",
        "--filter-date-from": "filter_date_from",
        "--filter-date-until": "filter_date_until",
        "--config": "config",
    }

    global_list_options: dict[str, str] = {
        "--filter-property": "filter_properties",
        "--filter-tag": "filter_tags",
        "--filter-heading": "filter_headings",
        "--filter-body": "filter_bodies",
    }

    global_options = ConfigOptions(
        int_options=global_int_options,
        bool_options=global_bool_options,
        str_options=global_str_options,
        list_options=global_list_options,
    )

    stats_options = ConfigOptions(
        int_options=stats_int_options,
        bool_options=stats_bool_options,
        str_options=stats_str_options,
        list_options={"--group": "groups"},
    )

    context = ConfigContext(
        defaults=defaults,
        stats_defaults=stats_defaults,
        append_defaults=append_defaults,
        global_options=global_options,
        stats_options=stats_options,
    )

    for key, value in config.items():
        if key in ("--color", "--no-color"):
            continue

        if not apply_config_entry(key, value, context):
            valid = False
            break

    if not valid:
        return None

    return (defaults, stats_defaults, append_defaults)


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


def display_selected_items(
    tags: dict[str, Tag],
    show: list[str] | None,
    config: tuple[int, int, int, datetime | None, datetime | None, TimeRange, set[str], bool],
) -> None:
    """Display formatted output for a selected tag list without leading indent."""
    (
        max_results,
        max_relations,
        num_buckets,
        date_from,
        date_until,
        global_timerange,
        exclude_set,
        color_enabled,
    ) = config

    cleaned = clean(exclude_set, tags)

    if show is not None:
        selected_items = [(name, cleaned[name]) for name in show if name in cleaned]
        selected_items = selected_items[:max_results]
    else:
        selected_items = sorted(cleaned.items(), key=lambda item: -item[1].total_tasks)[
            0:max_results
        ]

    if not selected_items:
        print("No results")
        return

    for idx, (name, tag) in enumerate(selected_items):
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
                print(date_line)
                print(chart_line)
                print(underline)

        print(name)
        total_tasks_value = magenta(str(tag.total_tasks), color_enabled)
        print(f"  Total tasks: {total_tasks_value}")
        if tag.time_range.earliest and tag.time_range.latest:
            avg_value = magenta(f"{tag.avg_tasks_per_day:.2f}", color_enabled)
            max_value = magenta(str(tag.max_single_day_count), color_enabled)
            print(f"  Average tasks per day: {avg_value}")
            print(f"  Max tasks on a single day: {max_value}")

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
                print("  Top relations:")
                for related_name, count in sorted_relations:
                    print(f"    {related_name} ({count})")


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


def display_group_list(
    groups: list[Group],
    config: tuple[int, int, datetime | None, datetime | None, TimeRange, set[str], bool],
) -> None:
    """Display group stats without the leading indent."""
    (
        max_results,
        num_buckets,
        date_from,
        date_until,
        global_timerange,
        exclude_set,
        color_enabled,
    ) = config

    exclude_lower = {value.lower() for value in exclude_set}
    filtered_groups = []
    for group in groups:
        display_tags = [tag for tag in group.tags if tag.lower() not in exclude_lower]
        if display_tags:
            filtered_groups.append((display_tags, group))

    filtered_groups = filtered_groups[:max_results]

    if not filtered_groups:
        print("No results")
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
            print(date_line)
            print(chart_line)
            print(underline)

        print(f"{', '.join(group_tags)}")
        total_tasks_value = magenta(str(group.total_tasks), color_enabled)
        avg_value = magenta(f"{group.avg_tasks_per_day:.2f}", color_enabled)
        max_value = magenta(str(group.max_single_day_count), color_enabled)
        print(f"  Total tasks: {total_tasks_value}")
        print(f"  Average tasks per day: {avg_value}")
        print(f"  Max tasks on a single day: {max_value}")


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


def parse_config_argument(argv: list[str]) -> str:
    """Parse only the --config argument from argv."""
    default = ".org-cli.json"
    for idx, arg in enumerate(argv[1:], start=1):
        if arg == "--config" and idx + 1 < len(argv):
            return argv[idx + 1]
        if arg.startswith("--config="):
            return arg.split("=", 1)[1]
    return default


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


def parse_show_values(value: str) -> list[str]:
    """Parse comma-separated show values."""
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values:
        print("Error: --show cannot be empty", file=sys.stderr)
        sys.exit(1)
    return values


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


def parse_group_values(value: str) -> list[str]:
    """Parse comma-separated group values."""
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values:
        print("Error: --group cannot be empty", file=sys.stderr)
        sys.exit(1)
    return values


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


def extend_filter_order_with_defaults(filter_order: list[str], args: SimpleNamespace) -> list[str]:
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


def handle_simple_filter(arg_name: str, args: SimpleNamespace) -> list[Filter]:
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


def handle_date_filter(arg_name: str, args: SimpleNamespace) -> list[Filter]:
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


def handle_completion_filter(arg_name: str, args: SimpleNamespace) -> list[Filter]:
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
    args: SimpleNamespace,
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


def create_filter_specs_from_args(args: SimpleNamespace, filter_order: list[str]) -> list[Filter]:
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


def build_filter_chain(args: SimpleNamespace, argv: list[str]) -> list[Filter]:
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
    args: SimpleNamespace,
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


def display_task_summary(
    result: AnalysisResult,
    args: SimpleNamespace,
    display_config: tuple[datetime | None, datetime | None, list[str], list[str], bool],
) -> None:
    """Display global task statistics without tag/group sections.

    Args:
        result: Analysis results to display
        args: Command-line arguments containing display configuration
        display_config: Tuple of (date_from, date_until, done_keys, todo_keys, color_enabled)
    """
    date_from, date_until, done_keys, todo_keys, color_enabled = display_config

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


def validate_global_arguments(args: SimpleNamespace) -> tuple[list[str], list[str]]:
    """Validate shared command-line arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        Tuple of (todo_keys, done_keys)

    Raises:
        SystemExit: If validation fails
    """
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


def validate_stats_arguments(args: SimpleNamespace) -> None:
    """Validate stats command arguments."""
    if args.use not in {"tags", "heading", "body"}:
        print("Error: --use must be one of: tags, heading, body", file=sys.stderr)
        sys.exit(1)

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


def resolve_mapping(args: SimpleNamespace) -> dict[str, str]:
    """Resolve mapping based on inline or file-based configuration."""
    mapping_inline = getattr(args, "mapping_inline", None)
    if mapping_inline is not None:
        return mapping_inline or MAP
    return load_mapping(args.mapping) or MAP


def resolve_exclude_set(args: SimpleNamespace) -> set[str]:
    """Resolve exclude set based on inline or file-based configuration."""
    exclude_inline = getattr(args, "exclude_inline", None)
    if exclude_inline is not None:
        return normalize_exclude_values(exclude_inline) or DEFAULT_EXCLUDE
    return load_exclude_list(args.exclude) or DEFAULT_EXCLUDE


def run_stats(args: SimpleNamespace) -> None:
    """Run the stats command."""
    color_enabled = should_use_color(args.color_flag)

    if color_enabled:
        colorama_init(autoreset=True, strip=False)

    todo_keys, done_keys = validate_global_arguments(args)
    validate_stats_arguments(args)

    mapping = resolve_mapping(args)
    exclude_set = resolve_exclude_set(args)

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


def run_stats_tasks(args: SimpleNamespace) -> None:
    """Run the stats tasks command."""
    color_enabled = should_use_color(args.color_flag)

    if color_enabled:
        colorama_init(autoreset=True, strip=False)

    todo_keys, done_keys = validate_global_arguments(args)
    validate_stats_arguments(args)

    mapping = resolve_mapping(args)

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

    display_task_summary(
        result,
        args,
        (date_from, date_until, done_keys, todo_keys, color_enabled),
    )


def run_stats_tags(args: SimpleNamespace) -> None:
    """Run the stats tags command."""
    color_enabled = should_use_color(args.color_flag)

    if color_enabled:
        colorama_init(autoreset=True, strip=False)

    todo_keys, done_keys = validate_global_arguments(args)
    validate_stats_arguments(args)

    mapping = resolve_mapping(args)
    exclude_set = resolve_exclude_set(args)

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

    show_values = None
    if args.show is not None:
        raw_values = parse_show_values(args.show)
        if args.use == "tags":
            show_values = [mapping.get(value.strip(), value.strip()) for value in raw_values]
        else:
            show_values = []
            for value in raw_values:
                normalized_value = normalize_show_value(value, mapping)
                if normalized_value:
                    show_values.append(normalized_value)

    display_selected_items(
        result.tags,
        show_values,
        (
            args.max_results,
            args.max_relations,
            args.buckets,
            date_from,
            date_until,
            result.timerange,
            exclude_set,
            color_enabled,
        ),
    )


def run_stats_groups(args: SimpleNamespace) -> None:
    """Run the stats groups command."""
    color_enabled = should_use_color(args.color_flag)

    if color_enabled:
        colorama_init(autoreset=True, strip=False)

    todo_keys, done_keys = validate_global_arguments(args)
    validate_stats_arguments(args)

    mapping = resolve_mapping(args)
    exclude_set = resolve_exclude_set(args)

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

    group_values = resolve_group_values(args.groups, mapping, args.use)

    if group_values is not None:
        tag_time_ranges = {tag_name: tag.time_range for tag_name, tag in result.tags.items()}
        groups = compute_explicit_groups(nodes, mapping, args.use, group_values, tag_time_ranges)
    else:
        groups = sorted(result.tag_groups, key=lambda group: len(group.tags), reverse=True)

    display_group_list(
        groups,
        (
            args.max_results,
            args.buckets,
            date_from,
            date_until,
            result.timerange,
            exclude_set,
            color_enabled,
        ),
    )


def apply_config_defaults(args: SimpleNamespace) -> None:
    """Apply config-provided defaults for append and inline values."""
    for dest, values in CONFIG_APPEND_DEFAULTS.items():
        if getattr(args, dest, None) is None:
            setattr(args, dest, values)

    mapping_inline = CONFIG_INLINE_DEFAULTS.get("mapping_inline")
    exclude_inline = CONFIG_INLINE_DEFAULTS.get("exclude_inline")
    args.mapping_inline = mapping_inline if mapping_inline is not None else None
    args.exclude_inline = exclude_inline if exclude_inline is not None else None


def build_args_namespace(payload: ArgsPayload) -> SimpleNamespace:
    """Build a namespace matching the legacy argparse shape."""
    args = SimpleNamespace(
        files=list(payload.files or []),
        config=payload.config,
        exclude=payload.exclude,
        mapping=payload.mapping,
        todo_keys=payload.todo_keys,
        done_keys=payload.done_keys,
        filter_gamify_exp_above=payload.filter_gamify_exp_above,
        filter_gamify_exp_below=payload.filter_gamify_exp_below,
        filter_repeats_above=payload.filter_repeats_above,
        filter_repeats_below=payload.filter_repeats_below,
        filter_date_from=payload.filter_date_from,
        filter_date_until=payload.filter_date_until,
        filter_properties=payload.filter_properties,
        filter_tags=payload.filter_tags,
        filter_headings=payload.filter_headings,
        filter_bodies=payload.filter_bodies,
        filter_completed=payload.filter_completed,
        filter_not_completed=payload.filter_not_completed,
        color_flag=payload.color_flag,
        max_results=payload.max_results,
        max_tags=payload.max_tags,
        use=payload.use,
        with_gamify_category=payload.with_gamify_category,
        with_tags_as_category=payload.with_tags_as_category,
        category_property=payload.category_property,
        max_relations=payload.max_relations,
        min_group_size=payload.min_group_size,
        max_groups=payload.max_groups,
        buckets=payload.buckets,
        show=payload.show,
        groups=payload.groups,
    )
    apply_config_defaults(args)
    return args


def load_cli_config(
    argv: list[str],
) -> tuple[dict[str, object], dict[str, list[str]], dict[str, object]]:
    """Load config defaults from the configured file path."""
    config_name = parse_config_argument(argv)
    config_path = Path(config_name)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_name
    config, load_error = load_config(str(config_path))

    if load_error:
        print("Malformed config", file=sys.stderr)
        return ({}, {}, {})

    config_defaults = build_config_defaults(config)
    if config_defaults is None:
        print("Malformed config", file=sys.stderr)
        return ({}, {}, {})

    defaults, stats_defaults, append_defaults = config_defaults

    inline_defaults: dict[str, object] = {}
    for key in ("mapping_inline", "exclude_inline"):
        if key in defaults:
            inline_defaults[key] = defaults[key]

    combined_defaults = {**defaults, **stats_defaults}
    filtered_defaults = {
        key: value for key, value in combined_defaults.items() if key in COMMAND_OPTION_NAMES
    }

    return (filtered_defaults, append_defaults, inline_defaults)


def build_default_map(defaults: dict[str, object]) -> dict[str, dict[str, dict[str, object]]]:
    """Build Click default_map for Typer commands."""
    summary_defaults = dict(defaults)
    summary_defaults.pop("show", None)
    summary_defaults.pop("groups", None)

    tasks_defaults = dict(defaults)
    for key in (
        "max_tags",
        "max_relations",
        "max_groups",
        "min_group_size",
        "use",
        "show",
        "groups",
    ):
        tasks_defaults.pop(key, None)

    tags_defaults = dict(defaults)
    for key in ("max_tags", "max_groups", "min_group_size", "groups"):
        tags_defaults.pop(key, None)

    groups_defaults = dict(defaults)
    for key in ("max_tags", "max_groups", "min_group_size", "show"):
        groups_defaults.pop(key, None)

    return {
        "stats": {
            "summary": summary_defaults,
            "tasks": tasks_defaults,
            "tags": tags_defaults,
            "groups": groups_defaults,
        }
    }


app = typer.Typer(
    help="Analyze Emacs Org-mode archive files for task statistics.",
    no_args_is_help=True,
)
stats_app = typer.Typer(
    help="Analyze Org-mode archive files for task statistics.",
    no_args_is_help=True,
)


@app.command("tasks")
def tasks() -> None:
    """Placeholder for future task commands."""
    return


@stats_app.command("summary")
def stats_summary(  # noqa: PLR0913
    files: list[str] | None = typer.Argument(  # noqa: B008
        None, metavar="FILE", help="Org-mode archive files or directories to analyze"
    ),
    config: str = typer.Option(
        ".org-cli.json",
        "--config",
        metavar="FILE",
        help="Config file name to load from current directory",
    ),
    exclude: str | None = typer.Option(
        None,
        "--exclude",
        metavar="FILE",
        help="File containing words to exclude (one per line)",
    ),
    mapping: str | None = typer.Option(
        None,
        "--mapping",
        metavar="FILE",
        help="JSON file containing tag mappings (dict[str, str])",
    ),
    todo_keys: str = typer.Option(
        "TODO",
        "--todo-keys",
        metavar="KEYS",
        help="Comma-separated list of incomplete task states",
    ),
    done_keys: str = typer.Option(
        "DONE",
        "--done-keys",
        metavar="KEYS",
        help="Comma-separated list of completed task states",
    ),
    filter_gamify_exp_above: int | None = typer.Option(
        None,
        "--filter-gamify-exp-above",
        metavar="N",
        help="Filter tasks where gamify_exp > N (non-inclusive, missing defaults to 10)",
    ),
    filter_gamify_exp_below: int | None = typer.Option(
        None,
        "--filter-gamify-exp-below",
        metavar="N",
        help="Filter tasks where gamify_exp < N (non-inclusive, missing defaults to 10)",
    ),
    filter_repeats_above: int | None = typer.Option(
        None,
        "--filter-repeats-above",
        metavar="N",
        help="Filter tasks where repeat count > N (non-inclusive)",
    ),
    filter_repeats_below: int | None = typer.Option(
        None,
        "--filter-repeats-below",
        metavar="N",
        help="Filter tasks where repeat count < N (non-inclusive)",
    ),
    filter_date_from: str | None = typer.Option(
        None,
        "--filter-date-from",
        metavar="TIMESTAMP",
        help=(
            "Filter tasks with timestamps after date (inclusive). "
            "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
            "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
        ),
    ),
    filter_date_until: str | None = typer.Option(
        None,
        "--filter-date-until",
        metavar="TIMESTAMP",
        help=(
            "Filter tasks with timestamps before date (inclusive). "
            "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
            "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
        ),
    ),
    filter_properties: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-property",
        metavar="KEY=VALUE",
        help="Filter tasks with exact property match (case-sensitive, can specify multiple)",
    ),
    filter_tags: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-tag",
        metavar="REGEX",
        help="Filter tasks where any tag matches regex (case-sensitive, can specify multiple)",
    ),
    filter_headings: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-heading",
        metavar="REGEX",
        help="Filter tasks where heading matches regex (case-sensitive, can specify multiple)",
    ),
    filter_bodies: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-body",
        metavar="REGEX",
        help="Filter tasks where body matches regex (case-sensitive, multiline, can specify multiple)",
    ),
    filter_completed: bool = typer.Option(
        False,
        "--filter-completed",
        help="Filter tasks with todo state in done keys",
    ),
    filter_not_completed: bool = typer.Option(
        False,
        "--filter-not-completed",
        help="Filter tasks with todo state in todo keys or without a todo state",
    ),
    color_flag: bool | None = typer.Option(
        None,
        "--color/--no-color",
        help="Force colored output",
    ),
    max_results: int = typer.Option(
        10,
        "--max-results",
        "-n",
        metavar="N",
        help="Maximum number of results to display",
    ),
    max_tags: int = typer.Option(
        5,
        "--max-tags",
        metavar="N",
        help="Maximum number of tags to display in TAGS section (use 0 to omit section)",
    ),
    use: str = typer.Option(
        "tags",
        "--use",
        metavar="CATEGORY",
        help="Category to display: tags, heading, or body",
    ),
    with_gamify_category: bool = typer.Option(
        False,
        "--with-gamify-category",
        help="Preprocess nodes to set category property based on gamify_exp value",
    ),
    with_tags_as_category: bool = typer.Option(
        False,
        "--with-tags-as-category",
        help="Preprocess nodes to set category property based on first tag",
    ),
    category_property: str = typer.Option(
        "CATEGORY",
        "--category-property",
        metavar="PROPERTY",
        help="Property name to use for category histogram and filtering",
    ),
    max_relations: int = typer.Option(
        5,
        "--max-relations",
        metavar="N",
        help="Maximum number of relations to display per item (use 0 to omit sections)",
    ),
    min_group_size: int = typer.Option(
        2,
        "--min-group-size",
        metavar="N",
        help="Minimum group size to display",
    ),
    max_groups: int = typer.Option(
        5,
        "--max-groups",
        metavar="N",
        help="Maximum number of tag groups to display (use 0 to omit section)",
    ),
    buckets: int = typer.Option(
        50,
        "--buckets",
        metavar="N",
        help="Number of time buckets for timeline charts (minimum: 20)",
    ),
) -> None:
    """Show overall task stats."""
    args = build_args_namespace(
        ArgsPayload(
            files=files,
            config=config,
            exclude=exclude,
            mapping=mapping,
            todo_keys=todo_keys,
            done_keys=done_keys,
            filter_gamify_exp_above=filter_gamify_exp_above,
            filter_gamify_exp_below=filter_gamify_exp_below,
            filter_repeats_above=filter_repeats_above,
            filter_repeats_below=filter_repeats_below,
            filter_date_from=filter_date_from,
            filter_date_until=filter_date_until,
            filter_properties=filter_properties,
            filter_tags=filter_tags,
            filter_headings=filter_headings,
            filter_bodies=filter_bodies,
            filter_completed=filter_completed,
            filter_not_completed=filter_not_completed,
            color_flag=color_flag,
            max_results=max_results,
            max_tags=max_tags,
            use=use,
            with_gamify_category=with_gamify_category,
            with_tags_as_category=with_tags_as_category,
            category_property=category_property,
            max_relations=max_relations,
            min_group_size=min_group_size,
            max_groups=max_groups,
            buckets=buckets,
            show=None,
            groups=None,
        )
    )
    run_stats(args)


@stats_app.command("tags")
def stats_tags(  # noqa: PLR0913
    files: list[str] | None = typer.Argument(  # noqa: B008
        None, metavar="FILE", help="Org-mode archive files or directories to analyze"
    ),
    config: str = typer.Option(
        ".org-cli.json",
        "--config",
        metavar="FILE",
        help="Config file name to load from current directory",
    ),
    exclude: str | None = typer.Option(
        None,
        "--exclude",
        metavar="FILE",
        help="File containing words to exclude (one per line)",
    ),
    mapping: str | None = typer.Option(
        None,
        "--mapping",
        metavar="FILE",
        help="JSON file containing tag mappings (dict[str, str])",
    ),
    todo_keys: str = typer.Option(
        "TODO",
        "--todo-keys",
        metavar="KEYS",
        help="Comma-separated list of incomplete task states",
    ),
    done_keys: str = typer.Option(
        "DONE",
        "--done-keys",
        metavar="KEYS",
        help="Comma-separated list of completed task states",
    ),
    filter_gamify_exp_above: int | None = typer.Option(
        None,
        "--filter-gamify-exp-above",
        metavar="N",
        help="Filter tasks where gamify_exp > N (non-inclusive, missing defaults to 10)",
    ),
    filter_gamify_exp_below: int | None = typer.Option(
        None,
        "--filter-gamify-exp-below",
        metavar="N",
        help="Filter tasks where gamify_exp < N (non-inclusive, missing defaults to 10)",
    ),
    filter_repeats_above: int | None = typer.Option(
        None,
        "--filter-repeats-above",
        metavar="N",
        help="Filter tasks where repeat count > N (non-inclusive)",
    ),
    filter_repeats_below: int | None = typer.Option(
        None,
        "--filter-repeats-below",
        metavar="N",
        help="Filter tasks where repeat count < N (non-inclusive)",
    ),
    filter_date_from: str | None = typer.Option(
        None,
        "--filter-date-from",
        metavar="TIMESTAMP",
        help=(
            "Filter tasks with timestamps after date (inclusive). "
            "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
            "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
        ),
    ),
    filter_date_until: str | None = typer.Option(
        None,
        "--filter-date-until",
        metavar="TIMESTAMP",
        help=(
            "Filter tasks with timestamps before date (inclusive). "
            "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
            "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
        ),
    ),
    filter_properties: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-property",
        metavar="KEY=VALUE",
        help="Filter tasks with exact property match (case-sensitive, can specify multiple)",
    ),
    filter_tags: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-tag",
        metavar="REGEX",
        help="Filter tasks where any tag matches regex (case-sensitive, can specify multiple)",
    ),
    filter_headings: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-heading",
        metavar="REGEX",
        help="Filter tasks where heading matches regex (case-sensitive, can specify multiple)",
    ),
    filter_bodies: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-body",
        metavar="REGEX",
        help="Filter tasks where body matches regex (case-sensitive, multiline, can specify multiple)",
    ),
    filter_completed: bool = typer.Option(
        False,
        "--filter-completed",
        help="Filter tasks with todo state in done keys",
    ),
    filter_not_completed: bool = typer.Option(
        False,
        "--filter-not-completed",
        help="Filter tasks with todo state in todo keys or without a todo state",
    ),
    color_flag: bool | None = typer.Option(
        None,
        "--color/--no-color",
        help="Force colored output",
    ),
    max_results: int = typer.Option(
        10,
        "--max-results",
        "-n",
        metavar="N",
        help="Maximum number of results to display",
    ),
    use: str = typer.Option(
        "tags",
        "--use",
        metavar="CATEGORY",
        help="Category to display: tags, heading, or body",
    ),
    show: str | None = typer.Option(
        None,
        "--show",
        metavar="TAGS",
        help="Comma-separated list of tags to display (default: top results)",
    ),
    with_gamify_category: bool = typer.Option(
        False,
        "--with-gamify-category",
        help="Preprocess nodes to set category property based on gamify_exp value",
    ),
    with_tags_as_category: bool = typer.Option(
        False,
        "--with-tags-as-category",
        help="Preprocess nodes to set category property based on first tag",
    ),
    category_property: str = typer.Option(
        "CATEGORY",
        "--category-property",
        metavar="PROPERTY",
        help="Property name to use for category histogram and filtering",
    ),
    max_relations: int = typer.Option(
        5,
        "--max-relations",
        metavar="N",
        help="Maximum number of relations to display per item (use 0 to omit sections)",
    ),
    buckets: int = typer.Option(
        50,
        "--buckets",
        metavar="N",
        help="Number of time buckets for timeline charts (minimum: 20)",
    ),
) -> None:
    """Show tag stats for selected tags or top results."""
    args = build_args_namespace(
        ArgsPayload(
            files=files,
            config=config,
            exclude=exclude,
            mapping=mapping,
            todo_keys=todo_keys,
            done_keys=done_keys,
            filter_gamify_exp_above=filter_gamify_exp_above,
            filter_gamify_exp_below=filter_gamify_exp_below,
            filter_repeats_above=filter_repeats_above,
            filter_repeats_below=filter_repeats_below,
            filter_date_from=filter_date_from,
            filter_date_until=filter_date_until,
            filter_properties=filter_properties,
            filter_tags=filter_tags,
            filter_headings=filter_headings,
            filter_bodies=filter_bodies,
            filter_completed=filter_completed,
            filter_not_completed=filter_not_completed,
            color_flag=color_flag,
            max_results=max_results,
            max_tags=0,
            use=use,
            with_gamify_category=with_gamify_category,
            with_tags_as_category=with_tags_as_category,
            category_property=category_property,
            max_relations=max_relations,
            min_group_size=2,
            max_groups=0,
            buckets=buckets,
            show=show,
            groups=None,
        )
    )
    run_stats_tags(args)


@stats_app.command("groups")
def stats_groups(  # noqa: PLR0913
    files: list[str] | None = typer.Argument(  # noqa: B008
        None, metavar="FILE", help="Org-mode archive files or directories to analyze"
    ),
    config: str = typer.Option(
        ".org-cli.json",
        "--config",
        metavar="FILE",
        help="Config file name to load from current directory",
    ),
    exclude: str | None = typer.Option(
        None,
        "--exclude",
        metavar="FILE",
        help="File containing words to exclude (one per line)",
    ),
    mapping: str | None = typer.Option(
        None,
        "--mapping",
        metavar="FILE",
        help="JSON file containing tag mappings (dict[str, str])",
    ),
    todo_keys: str = typer.Option(
        "TODO",
        "--todo-keys",
        metavar="KEYS",
        help="Comma-separated list of incomplete task states",
    ),
    done_keys: str = typer.Option(
        "DONE",
        "--done-keys",
        metavar="KEYS",
        help="Comma-separated list of completed task states",
    ),
    filter_gamify_exp_above: int | None = typer.Option(
        None,
        "--filter-gamify-exp-above",
        metavar="N",
        help="Filter tasks where gamify_exp > N (non-inclusive, missing defaults to 10)",
    ),
    filter_gamify_exp_below: int | None = typer.Option(
        None,
        "--filter-gamify-exp-below",
        metavar="N",
        help="Filter tasks where gamify_exp < N (non-inclusive, missing defaults to 10)",
    ),
    filter_repeats_above: int | None = typer.Option(
        None,
        "--filter-repeats-above",
        metavar="N",
        help="Filter tasks where repeat count > N (non-inclusive)",
    ),
    filter_repeats_below: int | None = typer.Option(
        None,
        "--filter-repeats-below",
        metavar="N",
        help="Filter tasks where repeat count < N (non-inclusive)",
    ),
    filter_date_from: str | None = typer.Option(
        None,
        "--filter-date-from",
        metavar="TIMESTAMP",
        help=(
            "Filter tasks with timestamps after date (inclusive). "
            "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
            "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
        ),
    ),
    filter_date_until: str | None = typer.Option(
        None,
        "--filter-date-until",
        metavar="TIMESTAMP",
        help=(
            "Filter tasks with timestamps before date (inclusive). "
            "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
            "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
        ),
    ),
    filter_properties: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-property",
        metavar="KEY=VALUE",
        help="Filter tasks with exact property match (case-sensitive, can specify multiple)",
    ),
    filter_tags: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-tag",
        metavar="REGEX",
        help="Filter tasks where any tag matches regex (case-sensitive, can specify multiple)",
    ),
    filter_headings: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-heading",
        metavar="REGEX",
        help="Filter tasks where heading matches regex (case-sensitive, can specify multiple)",
    ),
    filter_bodies: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-body",
        metavar="REGEX",
        help="Filter tasks where body matches regex (case-sensitive, multiline, can specify multiple)",
    ),
    filter_completed: bool = typer.Option(
        False,
        "--filter-completed",
        help="Filter tasks with todo state in done keys",
    ),
    filter_not_completed: bool = typer.Option(
        False,
        "--filter-not-completed",
        help="Filter tasks with todo state in todo keys or without a todo state",
    ),
    color_flag: bool | None = typer.Option(
        None,
        "--color/--no-color",
        help="Force colored output",
    ),
    max_results: int = typer.Option(
        10,
        "--max-results",
        "-n",
        metavar="N",
        help="Maximum number of results to display",
    ),
    use: str = typer.Option(
        "tags",
        "--use",
        metavar="CATEGORY",
        help="Category to display: tags, heading, or body",
    ),
    groups: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--group",
        metavar="TAGS",
        help="Comma-separated list of tags to group (can specify multiple)",
    ),
    with_gamify_category: bool = typer.Option(
        False,
        "--with-gamify-category",
        help="Preprocess nodes to set category property based on gamify_exp value",
    ),
    with_tags_as_category: bool = typer.Option(
        False,
        "--with-tags-as-category",
        help="Preprocess nodes to set category property based on first tag",
    ),
    category_property: str = typer.Option(
        "CATEGORY",
        "--category-property",
        metavar="PROPERTY",
        help="Property name to use for category histogram and filtering",
    ),
    max_relations: int = typer.Option(
        5,
        "--max-relations",
        metavar="N",
        help="Maximum number of relations to consider per item (use 0 to omit sections)",
    ),
    buckets: int = typer.Option(
        50,
        "--buckets",
        metavar="N",
        help="Number of time buckets for timeline charts (minimum: 20)",
    ),
) -> None:
    """Show tag groups for selected groups or top results."""
    args = build_args_namespace(
        ArgsPayload(
            files=files,
            config=config,
            exclude=exclude,
            mapping=mapping,
            todo_keys=todo_keys,
            done_keys=done_keys,
            filter_gamify_exp_above=filter_gamify_exp_above,
            filter_gamify_exp_below=filter_gamify_exp_below,
            filter_repeats_above=filter_repeats_above,
            filter_repeats_below=filter_repeats_below,
            filter_date_from=filter_date_from,
            filter_date_until=filter_date_until,
            filter_properties=filter_properties,
            filter_tags=filter_tags,
            filter_headings=filter_headings,
            filter_bodies=filter_bodies,
            filter_completed=filter_completed,
            filter_not_completed=filter_not_completed,
            color_flag=color_flag,
            max_results=max_results,
            max_tags=0,
            use=use,
            with_gamify_category=with_gamify_category,
            with_tags_as_category=with_tags_as_category,
            category_property=category_property,
            max_relations=max_relations,
            min_group_size=0,
            max_groups=0,
            buckets=buckets,
            show=None,
            groups=groups,
        )
    )
    run_stats_groups(args)


@stats_app.command("tasks")
def stats_tasks(  # noqa: PLR0913
    files: list[str] | None = typer.Argument(  # noqa: B008
        None, metavar="FILE", help="Org-mode archive files or directories to analyze"
    ),
    config: str = typer.Option(
        ".org-cli.json",
        "--config",
        metavar="FILE",
        help="Config file name to load from current directory",
    ),
    exclude: str | None = typer.Option(
        None,
        "--exclude",
        metavar="FILE",
        help="File containing words to exclude (one per line)",
    ),
    mapping: str | None = typer.Option(
        None,
        "--mapping",
        metavar="FILE",
        help="JSON file containing tag mappings (dict[str, str])",
    ),
    todo_keys: str = typer.Option(
        "TODO",
        "--todo-keys",
        metavar="KEYS",
        help="Comma-separated list of incomplete task states",
    ),
    done_keys: str = typer.Option(
        "DONE",
        "--done-keys",
        metavar="KEYS",
        help="Comma-separated list of completed task states",
    ),
    filter_gamify_exp_above: int | None = typer.Option(
        None,
        "--filter-gamify-exp-above",
        metavar="N",
        help="Filter tasks where gamify_exp > N (non-inclusive, missing defaults to 10)",
    ),
    filter_gamify_exp_below: int | None = typer.Option(
        None,
        "--filter-gamify-exp-below",
        metavar="N",
        help="Filter tasks where gamify_exp < N (non-inclusive, missing defaults to 10)",
    ),
    filter_repeats_above: int | None = typer.Option(
        None,
        "--filter-repeats-above",
        metavar="N",
        help="Filter tasks where repeat count > N (non-inclusive)",
    ),
    filter_repeats_below: int | None = typer.Option(
        None,
        "--filter-repeats-below",
        metavar="N",
        help="Filter tasks where repeat count < N (non-inclusive)",
    ),
    filter_date_from: str | None = typer.Option(
        None,
        "--filter-date-from",
        metavar="TIMESTAMP",
        help=(
            "Filter tasks with timestamps after date (inclusive). "
            "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
            "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
        ),
    ),
    filter_date_until: str | None = typer.Option(
        None,
        "--filter-date-until",
        metavar="TIMESTAMP",
        help=(
            "Filter tasks with timestamps before date (inclusive). "
            "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
            "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
        ),
    ),
    filter_properties: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-property",
        metavar="KEY=VALUE",
        help="Filter tasks with exact property match (case-sensitive, can specify multiple)",
    ),
    filter_tags: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-tag",
        metavar="REGEX",
        help="Filter tasks where any tag matches regex (case-sensitive, can specify multiple)",
    ),
    filter_headings: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-heading",
        metavar="REGEX",
        help="Filter tasks where heading matches regex (case-sensitive, can specify multiple)",
    ),
    filter_bodies: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--filter-body",
        metavar="REGEX",
        help="Filter tasks where body matches regex (case-sensitive, multiline, can specify multiple)",
    ),
    filter_completed: bool = typer.Option(
        False,
        "--filter-completed",
        help="Filter tasks with todo state in done keys",
    ),
    filter_not_completed: bool = typer.Option(
        False,
        "--filter-not-completed",
        help="Filter tasks with todo state in todo keys or without a todo state",
    ),
    color_flag: bool | None = typer.Option(
        None,
        "--color/--no-color",
        help="Force colored output",
    ),
    max_results: int = typer.Option(
        10,
        "--max-results",
        "-n",
        metavar="N",
        help="Maximum number of results to display",
    ),
    with_gamify_category: bool = typer.Option(
        False,
        "--with-gamify-category",
        help="Preprocess nodes to set category property based on gamify_exp value",
    ),
    with_tags_as_category: bool = typer.Option(
        False,
        "--with-tags-as-category",
        help="Preprocess nodes to set category property based on first tag",
    ),
    category_property: str = typer.Option(
        "CATEGORY",
        "--category-property",
        metavar="PROPERTY",
        help="Property name to use for category histogram and filtering",
    ),
    buckets: int = typer.Option(
        50,
        "--buckets",
        metavar="N",
        help="Number of time buckets for timeline charts (minimum: 20)",
    ),
) -> None:
    """Show overall task stats without tag sections."""
    args = build_args_namespace(
        ArgsPayload(
            files=files,
            config=config,
            exclude=exclude,
            mapping=mapping,
            todo_keys=todo_keys,
            done_keys=done_keys,
            filter_gamify_exp_above=filter_gamify_exp_above,
            filter_gamify_exp_below=filter_gamify_exp_below,
            filter_repeats_above=filter_repeats_above,
            filter_repeats_below=filter_repeats_below,
            filter_date_from=filter_date_from,
            filter_date_until=filter_date_until,
            filter_properties=filter_properties,
            filter_tags=filter_tags,
            filter_headings=filter_headings,
            filter_bodies=filter_bodies,
            filter_completed=filter_completed,
            filter_not_completed=filter_not_completed,
            color_flag=color_flag,
            max_results=max_results,
            max_tags=5,
            use="tags",
            with_gamify_category=with_gamify_category,
            with_tags_as_category=with_tags_as_category,
            category_property=category_property,
            max_relations=5,
            min_group_size=2,
            max_groups=5,
            buckets=buckets,
            show=None,
            groups=None,
        )
    )
    run_stats_tasks(args)


app.add_typer(stats_app, name="stats")


def main() -> None:
    """Main CLI entry point."""
    defaults, append_defaults, inline_defaults = load_cli_config(sys.argv)
    CONFIG_APPEND_DEFAULTS.clear()
    CONFIG_APPEND_DEFAULTS.update(append_defaults)
    CONFIG_INLINE_DEFAULTS.clear()
    CONFIG_INLINE_DEFAULTS.update(inline_defaults)

    command = typer.main.get_command(app)
    default_map = build_default_map(defaults) if defaults else None
    command.main(
        args=sys.argv[1:],
        prog_name="org",
        standalone_mode=True,
        default_map=default_map,
    )


if __name__ == "__main__":
    main()
