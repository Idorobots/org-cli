#!/usr/bin/env python
"""CLI interface for orgstats - Org-mode archive file analysis."""

import argparse
import json
import sys
from collections.abc import Callable

import orgparse

from orgstats.core import (
    AnalysisResult,
    Frequency,
    Relations,
    TimeRange,
    analyze,
    clean,
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
    filtered_nodes = filter_nodes(nodes, args.filter)
    result = analyze(filtered_nodes, mapping, args.show, args.max_relations)

    display_results(result, args, exclude_set)


if __name__ == "__main__":
    main()
