#!/usr/bin/env python
"""CLI interface for orgstats - Org-mode archive file analysis."""

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

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
    render_histogram,
    render_timeline_chart,
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
    config: tuple[int, int, int, datetime | None, datetime | None],
    order_fn: Callable[[tuple[str, Frequency]], int],
) -> None:
    """Display formatted output for a single category.

    Args:
        category_name: Display name for the category (e.g., "tags", "heading words")
        data: Tuple of (frequencies, time_ranges, exclude_set, relations_dict)
        config: Tuple of (max_results, max_relations, num_buckets, date_from, date_until)
        order_fn: Function to sort items by
    """
    max_results, max_relations, num_buckets, date_from, date_until = config
    frequencies, time_ranges, exclude_set, relations_dict = data
    cleaned = clean(exclude_set, frequencies)
    sorted_items = sorted(cleaned.items(), key=order_fn)[0:max_results]

    print(f"\nTop {category_name}:")
    for idx, (name, freq) in enumerate(sorted_items):
        if idx > 0:
            print()

        time_range = time_ranges.get(name)

        if time_range and time_range.earliest and time_range.timeline:
            earliest_date = date_from.date() if date_from else time_range.earliest.date()
            latest_date = (
                date_until.date()
                if date_until
                else (time_range.latest.date() if time_range.latest else time_range.earliest.date())
            )
            date_line, chart_line, underline = render_timeline_chart(
                time_range.timeline,
                earliest_date,
                latest_date,
                num_buckets,
            )
            print(f"  {date_line}")
            print(f"  {chart_line}")
            print(f"  {underline}")

        print(f"  {name} ({freq.total})")

        if name in relations_dict and relations_dict[name].relations:
            filtered_relations = {
                rel_name: count
                for rel_name, count in relations_dict[name].relations.items()
                if rel_name not in exclude_set
            }
            sorted_relations = sorted(filtered_relations.items(), key=lambda x: x[1], reverse=True)[
                0:max_relations
            ]

            if sorted_relations:
                print("    Top relations:")
                for related_name, count in sorted_relations:
                    print(f"      {related_name} ({count})")


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


@dataclass
class Filter:
    """Specification for a single filter operation."""

    filter: Callable[[list[orgparse.node.OrgNode]], list[orgparse.node.OrgNode]]


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


def handle_date_filter(
    arg_name: str, args: argparse.Namespace, done_keys: list[str]
) -> list[Filter]:
    """Handle date filter arguments.

    Args:
        arg_name: Argument name
        args: Parsed arguments
        done_keys: List of completion state keywords

    Returns:
        List of Filter objects (0 or 1 item)
    """
    if arg_name == "--filter-date-from" and args.filter_date_from is not None:
        date_from = parse_date_argument(args.filter_date_from, "--filter-date-from")
        keys = done_keys
        return [Filter(lambda nodes: filter_date_from(nodes, date_from, keys))]

    if arg_name == "--filter-date-until" and args.filter_date_until is not None:
        date_until = parse_date_argument(args.filter_date_until, "--filter-date-until")
        keys = done_keys
        return [Filter(lambda nodes: filter_date_until(nodes, date_until, keys))]

    return []


def handle_completion_filter(
    arg_name: str,
    args: argparse.Namespace,
    done_keys: list[str],
    todo_keys: list[str],
) -> list[Filter]:
    """Handle completion status filter arguments.

    Args:
        arg_name: Argument name
        args: Parsed arguments
        done_keys: List of completion state keywords
        todo_keys: List of TODO state keywords

    Returns:
        List of Filter objects (0 or 1 item)
    """
    if arg_name == "--filter-completed" and args.filter_completed:
        keys = done_keys
        return [Filter(lambda nodes: filter_completed(nodes, keys))]

    if arg_name == "--filter-not-completed" and args.filter_not_completed:
        keys = todo_keys
        return [Filter(lambda nodes: filter_not_completed(nodes, keys))]

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


def handle_tag_filter(tag: str) -> list[Filter]:
    """Handle tag filter arguments.

    Args:
        tag: Tag name

    Returns:
        List of Filter objects (1 item)
    """
    return [Filter(lambda nodes: filter_tag(nodes, tag))]


def create_filter_specs_from_args(
    args: argparse.Namespace,
    filter_order: list[str],
    done_keys: list[str],
    todo_keys: list[str],
) -> list[Filter]:
    """Create filter specifications from parsed arguments.

    Args:
        args: Parsed command-line arguments
        filter_order: List of arg_name tuples
        done_keys: List of completion state keywords
        todo_keys: List of TODO state keywords

    Returns:
        List of Filter objects in command-line order
    """
    filter_specs: list[Filter] = []
    property_index = 0
    tag_index = 0

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
            filter_specs.extend(handle_date_filter(arg_name, args, done_keys))

        elif arg_name == "--filter-property":
            if args.filter_properties and property_index < len(args.filter_properties):
                prop_name, prop_value = parse_property_filter(
                    args.filter_properties[property_index]
                )

                filter_specs.extend(handle_property_filter(prop_name, prop_value))

                property_index += 1

        elif arg_name == "--filter-tag":
            if args.filter_tags and tag_index < len(args.filter_tags):
                tag_name = args.filter_tags[tag_index]

                filter_specs.extend(handle_tag_filter(tag_name))

                tag_index += 1

        elif arg_name in ("--filter-completed", "--filter-not-completed"):
            filter_specs.extend(handle_completion_filter(arg_name, args, done_keys, todo_keys))

    return filter_specs


def build_filter_chain(
    args: argparse.Namespace, argv: list[str], done_keys: list[str], todo_keys: list[str]
) -> list[Filter]:
    """Build ordered list of filter functions from CLI arguments.

    Processes filters in command-line order. Expands --filter presets inline
    at their position.

    Args:
        args: Parsed command-line arguments
        argv: Raw sys.argv to determine ordering
        done_keys: List of completion state keywords
        todo_keys: List of TODO state keywords

    Returns:
        List of filter specs to apply sequentially
    """
    filter_order = parse_filter_order_from_argv(argv)
    return create_filter_specs_from_args(args, filter_order, done_keys, todo_keys)


def display_results(
    result: AnalysisResult,
    args: argparse.Namespace,
    exclude_set: set[str],
    date_range: tuple[datetime | None, datetime | None],
    task_keys: tuple[list[str], list[str]],
) -> None:
    """Display analysis results in formatted output.

    Args:
        result: Analysis results to display
        args: Command-line arguments containing display configuration
        exclude_set: Set of items to exclude from display
        date_range: Tuple of (date_from, date_until) for chart display range
        task_keys: Tuple of (done_keys, todo_keys) state keywords
    """
    date_from, date_until = date_range
    done_keys, todo_keys = task_keys
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
        print(f"Average tasks completed per day: {result.avg_tasks_per_day:.2f}")
        print(f"Max tasks completed on a single day: {result.max_single_day_count}")
        print(f"Max repeats of a single task: {result.max_repeat_count}")

    print("\nTask states:")
    remaining_states = sorted(
        set(result.task_states.values.keys()) - set(done_keys) - set(todo_keys)
    )
    state_order = done_keys + todo_keys + remaining_states
    histogram_lines = render_histogram(result.task_states, args.buckets, state_order)
    for line in histogram_lines:
        print(f"  {line}")

    print("\nTask completion by day of week:")
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

    category_name = CATEGORY_NAMES[args.show]

    def order_by_total(item: tuple[str, Frequency]) -> int:
        """Sort by total count (descending)."""
        return -item[1].total

    display_category(
        category_name,
        (result.tag_frequencies, result.tag_time_ranges, exclude_set, result.tag_relations),
        (args.max_results, args.max_relations, args.buckets, date_from, date_until),
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

    if args.buckets < 20:
        print("Error: --buckets must be at least 20", file=sys.stderr)
        sys.exit(1)

    todo_keys = validate_and_parse_keys(args.todo_keys, "--todo-keys")
    done_keys = validate_and_parse_keys(args.done_keys, "--done-keys")

    mapping = load_mapping(args.mapping) or MAP
    exclude_set = load_exclude_list(args.exclude) or DEFAULT_EXCLUDE

    nodes = load_org_files(args.files, todo_keys, done_keys)

    filters = build_filter_chain(args, sys.argv, done_keys, todo_keys)

    filtered_nodes = nodes
    for f in filters:
        filtered_nodes = f.filter(filtered_nodes)

    if not filtered_nodes:
        print("No results")
        return

    result = analyze(filtered_nodes, mapping, args.show, args.max_relations, done_keys)

    date_from = None
    date_until = None
    if args.filter_date_from is not None:
        date_from = parse_date_argument(args.filter_date_from, "--filter-date-from")
    if args.filter_date_until is not None:
        date_until = parse_date_argument(args.filter_date_until, "--filter-date-until")

    display_results(result, args, exclude_set, (date_from, date_until), (done_keys, todo_keys))


if __name__ == "__main__":
    main()
