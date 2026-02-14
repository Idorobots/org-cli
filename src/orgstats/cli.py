#!/usr/bin/env python
"""CLI interface for orgstats - Org-mode archive file analysis."""

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import orgparse

from orgstats.core import (
    AnalysisResult,
    Frequency,
    Relations,
    TimeRange,
    analyze,
    clean,
    filter_completed,
    filter_date_from,
    filter_date_until,
    filter_gamify_exp_above,
    filter_gamify_exp_below,
    filter_not_completed,
    filter_property,
    filter_repeats_above,
    filter_repeats_below,
    filter_tag,
    gamify_exp,
)


MAP = {
    "test": "testing",
    "sysadmin": "devops",
    "pldesign": "compilers",
    "webdev": "frontend",
    "unix": "linux",
    "gtd": "agile",
    "foof": "spartan",
    "typing": "documenting",
    "notestaking": "documenting",
    "computernetworks": "networking",
    "maintenance": "refactoring",
    "softwareengineering": "softwarearchitecture",
    "soa": "softwarearchitecture",
    "uml": "softwarearchitecture",
    "dia": "softwarearchitecture",
}


TAGS = {
    "comp",
    "computer",
    "uni",
    "out",
    "home",
    "exam",
    "note",
    "learn",
    "homework",
    "test",
    "blog",
    "plan",
    "lecture",
    "due",
    "cleaning",
    "germanvocabulary",
    "readingkorean",
    "readingenglish",
    "englishvocabulary",
    "lifehacking",
    "tinkering",
    "speakingenglish",
}


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
    "suspended",
    "hangul",
    "romanization",
    "do",
    "dishes",
    "medial",
    "clean",
    "tidy",
    "sweep",
    "living",
    "room",
    "bathroom",
    "kitchen",
    "ways",
    "say",
    "bill",
    "piwl",
    "piwm",
}


DEFAULT_EXCLUDE = TAGS.union(HEADING).union(
    {
        "end",
        "logbook",
        "cancelled",
        "scheduled",
        "suspended",
        "it",
        "this",
        "do",
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
        "an",
        "i",
        "as",
        "or",
        "by",
        "did",
        "can",
        "->",
        "are",
        "was",
        "[x]",
        "meh",
        "more",
        "until",
        "+",
        "using",
        "when",
        "into",
        "only",
        "at",
        "it's",
        "have",
        "about",
        "just",
        "2",
        "etc",
        "get",
        "didn't",
        "can't",
        "lu",
        "lu's",
        "lucyna",
        "alicja",
        "my",
        "does",
        "nah",
        "there",
        "yet",
        "nope",
        "should",
        "i'll",
        "khhhhaaaaannn't",
        "zrobiła",
        "robi",
        "dysze",
        "pon",
        "wto",
        "śro",
        "czw",
        "pią",
        "sob",
        "nie",
        "",
    }
)


CATEGORY_NAMES = {"tags": "tags", "heading": "heading words", "body": "body words"}


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
            return {line.strip().lower() for line in f if line.strip()}
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


def display_category(
    category_name: str,
    data: tuple[dict[str, Frequency], dict[str, TimeRange], set[str], dict[str, Relations]],
    max_results: int,
    max_relations: int,
    order_fn: Callable[[tuple[str, Frequency]], int],
) -> None:
    """Display formatted output for a single category.

    Args:
        category_name: Display name for the category (e.g., "tags", "heading words")
        data: Tuple of (frequencies, time_ranges, exclude_set, relations_dict)
        max_results: Maximum number of results to display
        max_relations: Maximum number of relations to display per item
        order_fn: Function to sort items by
    """
    frequencies, time_ranges, exclude_set, relations_dict = data
    cleaned = clean(exclude_set, frequencies)
    sorted_items = sorted(cleaned.items(), key=order_fn)[0:max_results]

    print(f"\nTop {category_name}:")
    for name, freq in sorted_items:
        time_range = time_ranges.get(name)

        parts = [f"count={freq.total}"]

        if time_range and time_range.earliest:
            parts.append(f"earliest={time_range.earliest.date().isoformat()}")
            if time_range.latest:
                parts.append(f"latest={time_range.latest.date().isoformat()}")

            top_day_info = get_top_day_info(time_range)
            if top_day_info:
                parts.append(f"top_day={top_day_info[0]} ({top_day_info[1]})")

        print(f"  {name}: {', '.join(parts)}")

        if name in relations_dict and relations_dict[name].relations:
            filtered_relations = {
                rel_name: count
                for rel_name, count in relations_dict[name].relations.items()
                if rel_name not in exclude_set
            }
            sorted_relations = sorted(filtered_relations.items(), key=lambda x: x[1], reverse=True)[
                0:max_relations
            ]

            for related_name, count in sorted_relations:
                print(f"    {related_name} ({count})")


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

    filtered = []
    for node in nodes:
        exp = gamify_exp(node)

        if exp is None:
            if task_type == "regular":
                filtered.append(node)
        elif (
            (task_type == "simple" and exp < 10)
            or (task_type == "regular" and 10 <= exp < 20)
            or (task_type == "hard" and exp >= 20)
        ):
            filtered.append(node)

    return filtered


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
        default=3,
        metavar="N",
        help="Maximum number of relations to display per item (default: 3, must be >= 1)",
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
        default=3,
        metavar="N",
        help="Minimum group size to display (default: 3)",
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
        metavar="YYYY-MM-DD",
        help="Filter tasks with timestamps after date (non-inclusive)",
    )

    parser.add_argument(
        "--filter-date-until",
        type=str,
        metavar="YYYY-MM-DD",
        help="Filter tasks with timestamps before date (non-inclusive)",
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
        metavar="TAG",
        help="Filter tasks with exact tag match (case-sensitive, can specify multiple)",
    )

    parser.add_argument(
        "--filter-completed",
        action="store_true",
        help="Filter tasks with todo state in done keys",
    )

    parser.add_argument(
        "--filter-not-completed",
        action="store_true",
        help="Filter tasks with todo state in todo keys",
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


def load_org_files(
    filenames: list[str], todo_keys: list[str], done_keys: list[str]
) -> list[orgparse.node.OrgNode]:
    """Load and parse org-mode files.

    Args:
        filenames: List of file paths to load
        todo_keys: List of TODO state keywords
        done_keys: List of DONE state keywords

    Returns:
        List of parsed org-mode nodes

    Raises:
        SystemExit: If file cannot be read
    """
    nodes: list[orgparse.node.OrgNode] = []

    for name in filenames:
        try:
            with open(name, encoding="utf-8") as f:
                print(f"Processing {name}...")

                contents = f.read().replace("24:00", "00:00")

                todo_config = f"#+TODO: {' '.join(todo_keys)} | {' '.join(done_keys)}\n\n"
                contents = todo_config + contents

                ns = orgparse.loads(contents)
                if ns is not None:
                    nodes = nodes + list(ns[1:])
        except FileNotFoundError:
            print(f"Error: File '{name}' not found", file=sys.stderr)
            sys.exit(1)
        except PermissionError:
            print(f"Error: Permission denied for '{name}'", file=sys.stderr)
            sys.exit(1)

    return nodes


def parse_date_argument(date_str: str, arg_name: str) -> date:
    """Parse and validate date argument in YYYY-MM-DD format.

    Args:
        date_str: Date string to parse
        arg_name: Argument name for error messages

    Returns:
        Parsed date object

    Raises:
        SystemExit: If date format is invalid
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        print(
            f"Error: {arg_name} must be in YYYY-MM-DD format, got '{date_str}'",
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


@dataclass
class FilterSpec:
    """Specification for a single filter operation."""

    filter_type: str
    value: Any
    position: float


def parse_filter_order_from_argv(argv: list[str]) -> list[tuple[str, int]]:
    """Parse command-line order of filter arguments.

    Returns list of (arg_name, position) tuples in command-line order.

    Args:
        argv: sys.argv (command-line arguments)

    Returns:
        List of tuples: (filter_arg_name, position_in_argv)
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
        "--filter-completed",
        "--filter-not-completed",
    ]

    filter_positions = []
    for i, arg in enumerate(argv):
        if arg in filter_args:
            filter_positions.append((arg, i))

    return sorted(filter_positions, key=lambda x: x[1])


def handle_preset_filter(preset: str, position: int) -> list[FilterSpec]:
    """Handle --filter preset expansion.

    Args:
        preset: Preset name (simple, regular, hard, all)
        position: Position in command line

    Returns:
        List of FilterSpec objects for the preset
    """
    if preset == "simple":
        return [FilterSpec("gamify_exp_below", 10, position)]
    if preset == "regular":
        return [
            FilterSpec("gamify_exp_above", 9, position),
            FilterSpec("gamify_exp_below", 20, position + 0.1),
        ]
    if preset == "hard":
        return [FilterSpec("gamify_exp_above", 19, position)]
    return []


def handle_simple_filter(
    arg_name: str, args: argparse.Namespace, position: int
) -> list[FilterSpec]:
    """Handle simple filter arguments (gamify_exp, repeats).

    Args:
        arg_name: Argument name
        args: Parsed arguments
        position: Position in command line

    Returns:
        List of FilterSpec objects (0 or 1 item)
    """
    filter_map = {
        "--filter-gamify-exp-above": ("gamify_exp_above", args.filter_gamify_exp_above),
        "--filter-gamify-exp-below": ("gamify_exp_below", args.filter_gamify_exp_below),
        "--filter-repeats-above": ("repeats_above", args.filter_repeats_above),
        "--filter-repeats-below": ("repeats_below", args.filter_repeats_below),
    }

    if arg_name in filter_map:
        filter_type, value = filter_map[arg_name]
        if value is not None:
            return [FilterSpec(filter_type, value, position)]

    return []


def handle_date_filter(
    arg_name: str, args: argparse.Namespace, position: int, done_keys: list[str]
) -> list[FilterSpec]:
    """Handle date filter arguments.

    Args:
        arg_name: Argument name
        args: Parsed arguments
        position: Position in command line
        done_keys: List of completion state keywords

    Returns:
        List of FilterSpec objects (0 or 1 item)
    """
    if arg_name == "--filter-date-from" and args.filter_date_from:
        date_from = parse_date_argument(args.filter_date_from, "--filter-date-from")
        return [FilterSpec("date_from", (date_from, done_keys), position)]

    if arg_name == "--filter-date-until" and args.filter_date_until:
        date_until = parse_date_argument(args.filter_date_until, "--filter-date-until")
        return [FilterSpec("date_until", (date_until, done_keys), position)]

    return []


def handle_completion_filter(
    arg_name: str,
    args: argparse.Namespace,
    position: int,
    done_keys: list[str],
    todo_keys: list[str],
) -> list[FilterSpec]:
    """Handle completion status filter arguments.

    Args:
        arg_name: Argument name
        args: Parsed arguments
        position: Position in command line
        done_keys: List of completion state keywords
        todo_keys: List of TODO state keywords

    Returns:
        List of FilterSpec objects (0 or 1 item)
    """
    if arg_name == "--filter-completed" and args.filter_completed:
        return [FilterSpec("completed", done_keys, position)]

    if arg_name == "--filter-not-completed" and args.filter_not_completed:
        return [FilterSpec("not_completed", todo_keys, position)]

    return []


def create_filter_specs_from_args(
    args: argparse.Namespace,
    filter_order: list[tuple[str, int]],
    done_keys: list[str],
    todo_keys: list[str],
) -> list[FilterSpec]:
    """Create filter specifications from parsed arguments.

    Args:
        args: Parsed command-line arguments
        filter_order: List of (arg_name, position) tuples
        done_keys: List of completion state keywords
        todo_keys: List of TODO state keywords

    Returns:
        List of FilterSpec objects in command-line order
    """
    filter_specs: list[FilterSpec] = []
    property_index = 0
    tag_index = 0

    for arg_name, position in filter_order:
        if arg_name == "--filter":
            filter_specs.extend(handle_preset_filter(args.filter, position))

        elif arg_name in (
            "--filter-gamify-exp-above",
            "--filter-gamify-exp-below",
            "--filter-repeats-above",
            "--filter-repeats-below",
        ):
            filter_specs.extend(handle_simple_filter(arg_name, args, position))

        elif arg_name in ("--filter-date-from", "--filter-date-until"):
            filter_specs.extend(handle_date_filter(arg_name, args, position, done_keys))

        elif arg_name == "--filter-property":
            if args.filter_properties and property_index < len(args.filter_properties):
                prop_name, prop_value = parse_property_filter(
                    args.filter_properties[property_index]
                )
                filter_specs.append(FilterSpec("property", (prop_name, prop_value), position))
                property_index += 1

        elif arg_name == "--filter-tag":
            if args.filter_tags and tag_index < len(args.filter_tags):
                filter_specs.append(FilterSpec("tag", args.filter_tags[tag_index], position))
                tag_index += 1

        elif arg_name in ("--filter-completed", "--filter-not-completed"):
            filter_specs.extend(
                handle_completion_filter(arg_name, args, position, done_keys, todo_keys)
            )

    filter_specs.sort(key=lambda x: x.position)
    return filter_specs


def convert_spec_to_function(
    spec: FilterSpec,
) -> Callable[[list[orgparse.node.OrgNode]], list[orgparse.node.OrgNode]]:
    """Convert a FilterSpec to an actual filter function.

    Args:
        spec: FilterSpec object

    Returns:
        Filter function that takes and returns list of nodes
    """
    simple_filters: dict[
        str, Callable[[Any], Callable[[list[orgparse.node.OrgNode]], list[orgparse.node.OrgNode]]]
    ] = {
        "gamify_exp_above": lambda t: lambda nodes: filter_gamify_exp_above(nodes, t),
        "gamify_exp_below": lambda t: lambda nodes: filter_gamify_exp_below(nodes, t),
        "repeats_above": lambda t: lambda nodes: filter_repeats_above(nodes, t),
        "repeats_below": lambda t: lambda nodes: filter_repeats_below(nodes, t),
        "tag": lambda t: lambda nodes: filter_tag(nodes, t),
        "completed": lambda k: lambda nodes: filter_completed(nodes, k),
        "not_completed": lambda k: lambda nodes: filter_not_completed(nodes, k),
    }

    if spec.filter_type in simple_filters:
        return simple_filters[spec.filter_type](spec.value)

    if spec.filter_type == "date_from":
        date_val, keys = spec.value

        def date_from_filter(
            nodes: list[orgparse.node.OrgNode],
            d: date = date_val,
            k: list[str] = keys,
        ) -> list[orgparse.node.OrgNode]:
            return filter_date_from(nodes, d, k)

        return date_from_filter

    if spec.filter_type == "date_until":
        date_val, keys = spec.value

        def date_until_filter(
            nodes: list[orgparse.node.OrgNode],
            d: date = date_val,
            k: list[str] = keys,
        ) -> list[orgparse.node.OrgNode]:
            return filter_date_until(nodes, d, k)

        return date_until_filter

    if spec.filter_type == "property":
        prop_name, prop_value = spec.value

        def property_filter(
            nodes: list[orgparse.node.OrgNode],
            n: str = prop_name,
            v: str = prop_value,
        ) -> list[orgparse.node.OrgNode]:
            return filter_property(nodes, n, v)

        return property_filter

    def identity_filter(nodes: list[orgparse.node.OrgNode]) -> list[orgparse.node.OrgNode]:
        return nodes

    return identity_filter


def build_filter_chain(
    args: argparse.Namespace, argv: list[str], done_keys: list[str], todo_keys: list[str]
) -> list[Callable[[list[orgparse.node.OrgNode]], list[orgparse.node.OrgNode]]]:
    """Build ordered list of filter functions from CLI arguments.

    Processes filters in command-line order. Expands --filter presets inline
    at their position.

    Args:
        args: Parsed command-line arguments
        argv: Raw sys.argv to determine ordering
        done_keys: List of completion state keywords
        todo_keys: List of TODO state keywords

    Returns:
        List of filter functions to apply sequentially
    """
    filter_order = parse_filter_order_from_argv(argv)
    filter_specs = create_filter_specs_from_args(args, filter_order, done_keys, todo_keys)
    return [convert_spec_to_function(spec) for spec in filter_specs]


def display_results(
    result: AnalysisResult, args: argparse.Namespace, exclude_set: set[str]
) -> None:
    """Display analysis results in formatted output.

    Args:
        result: Analysis results to display
        args: Command-line arguments containing display configuration
        exclude_set: Set of items to exclude from display
    """
    total_tasks_str = f"\nTotal tasks: count={result.total_tasks}"

    if result.timerange.earliest and result.timerange.latest:
        earliest_str = result.timerange.earliest.date().isoformat()
        latest_str = result.timerange.latest.date().isoformat()
        total_tasks_str += f", earliest={earliest_str}, latest={latest_str}"

        if result.timerange.timeline:
            max_count = max(result.timerange.timeline.values())
            top_day = min(d for d, count in result.timerange.timeline.items() if count == max_count)
            top_day_str = top_day.isoformat()
            total_tasks_str += f", top_day={top_day_str} ({max_count})"

    print(total_tasks_str)

    if result.timerange.earliest and result.timerange.latest:
        print(f"  Average tasks completed per day: {result.avg_tasks_per_day:.2f}")
        print(f"  Max tasks completed on a single day: {result.max_single_day_count}")
        print(f"  Max repeats of a single task: {result.max_repeat_count}")

    print("\nTask states:")
    sorted_states = sorted(
        result.task_states.values.items(), key=lambda item: item[1], reverse=True
    )
    for state, count in sorted_states:
        print(f"  {state}: {count}")

    print("\nTask completion by day of week:")
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for day in day_order:
        count = result.task_days.values.get(day, 0)
        print(f"  {day}: {count}")

    unknown_count = result.task_days.values.get("unknown", 0)
    if unknown_count > 0:
        print(f"  unknown: {unknown_count}")

    category_name = CATEGORY_NAMES[args.show]

    def order_by_total(item: tuple[str, Frequency]) -> int:
        """Sort by total count (descending)."""
        return -item[1].total

    display_category(
        category_name,
        (result.tag_frequencies, result.tag_time_ranges, exclude_set, result.tag_relations),
        args.max_results,
        args.max_relations,
        order_by_total,
    )

    if result.tag_groups:
        filtered_groups = []
        for group in result.tag_groups:
            filtered_tags = [tag for tag in group.tags if tag not in exclude_set]
            if len(filtered_tags) >= args.min_group_size:
                filtered_groups.append(filtered_tags)

        if filtered_groups:
            print("\nTag groups:")
            for group_tags in filtered_groups:
                print(f"  {', '.join(group_tags)}")
                print()


def main() -> None:
    """Main CLI entry point."""
    args = parse_arguments()

    if args.max_relations < 1:
        print("Error: --max-relations must be at least 1", file=sys.stderr)
        sys.exit(1)

    if args.min_group_size < 0:
        print("Error: --min-group-size must be non-negative", file=sys.stderr)
        sys.exit(1)

    todo_keys = validate_and_parse_keys(args.todo_keys, "--todo-keys")
    done_keys = validate_and_parse_keys(args.done_keys, "--done-keys")

    mapping = load_mapping(args.mapping) or MAP
    exclude_set = load_exclude_list(args.exclude) or DEFAULT_EXCLUDE

    nodes = load_org_files(args.files, todo_keys, done_keys)

    filter_functions = build_filter_chain(args, sys.argv, done_keys, todo_keys)

    filtered_nodes = nodes
    for filter_fn in filter_functions:
        filtered_nodes = filter_fn(filtered_nodes)

    if not filtered_nodes:
        print("No results")
        return

    result = analyze(filtered_nodes, mapping, args.show, args.max_relations, done_keys)

    display_results(result, args, exclude_set)


if __name__ == "__main__":
    main()
