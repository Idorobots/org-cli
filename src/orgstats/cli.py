#!/usr/bin/env python
"""CLI interface for orgstats - Org-mode archive file analysis."""

import argparse
import json
import sys
from collections.abc import Callable

import orgparse

from orgstats.core import Frequency, Relations, TimeRange, analyze, clean, gamify_exp


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

    return parser.parse_args()


def main() -> None:
    """Main CLI entry point."""
    args = parse_arguments()

    if args.max_relations < 1:
        print("Error: --max-relations must be at least 1", file=sys.stderr)
        sys.exit(1)

    if args.min_group_size < 0:
        print("Error: --min-group-size must be non-negative", file=sys.stderr)
        sys.exit(1)

    # Load mapping from file or use default
    mapping = load_mapping(args.mapping) or MAP

    # Load exclude list from file or use default
    exclude_set = load_exclude_list(args.exclude) or DEFAULT_EXCLUDE

    # Process org files
    nodes: list[orgparse.node.OrgNode] = []

    for name in args.files:
        with open(name, encoding="utf-8") as f:
            print("Processing " + name + "...")

            # NOTE Making the file parseable.
            contents = f.read().replace("24:00", "00:00")

            ns = orgparse.loads(contents)
            if ns is not None:
                nodes = nodes + list(ns[1:])

    # Filter nodes based on task type
    filtered_nodes = filter_nodes(nodes, args.filter)

    # Analyze filtered nodes with custom mapping for the selected category
    result = analyze(filtered_nodes, mapping, args.show, args.max_relations)

    def order_by_total(item: tuple[str, Frequency]) -> int:
        """Sort by total count (descending)."""
        return -item[1].total

    # Display results
    print("\nTotal tasks: ", result.total_tasks)
    print("\nDone tasks: ", result.done_tasks)

    # Select appropriate category name
    category_names = {"tags": "tags", "heading": "heading words", "body": "body words"}
    category_name = category_names[args.show]

    # Display results (always use tag_* fields, which hold the selected category's data)
    display_category(
        category_name,
        (result.tag_frequencies, result.tag_time_ranges, exclude_set, result.tag_relations),
        args.max_results,
        args.max_relations,
        order_by_total,
    )

    # Display tag groups
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


if __name__ == "__main__":
    main()
