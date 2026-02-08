#!/usr/bin/env python
"""CLI interface for orgstats - Org-mode archive file analysis."""

import argparse
import sys
from collections.abc import Callable

import orgparse

from orgstats.core import BODY, HEADING, TAGS, Frequency, Relations, TimeRange, analyze, clean


def load_stopwords(filepath: str | None) -> set[str]:
    """Load stopwords from a file (one word per line).

    Args:
        filepath: Path to stopwords file, or None for empty set

    Returns:
        Set of stopwords (lowercased, stripped)

    Raises:
        SystemExit: If file cannot be read
    """
    if filepath is None:
        return set()

    try:
        with open(filepath, encoding="utf-8") as f:
            return {line.strip().lower() for line in f if line.strip()}
    except FileNotFoundError:
        print(f"Error: Stopwords file '{filepath}' not found", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied for '{filepath}'", file=sys.stderr)
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
    order_fn: Callable[[tuple[str, Frequency]], tuple[int, int]],
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
        "--exclude-tags",
        type=str,
        metavar="FILE",
        help="File containing tags to exclude (one per line)",
    )

    parser.add_argument(
        "--exclude-heading",
        type=str,
        metavar="FILE",
        help="File containing heading words to exclude (one per line)",
    )

    parser.add_argument(
        "--exclude-body",
        type=str,
        metavar="FILE",
        help="File containing body words to exclude (one per line)",
    )

    parser.add_argument(
        "--tasks",
        type=str,
        choices=["simple", "regular", "hard", "total"],
        default="total",
        metavar="TYPE",
        help="Task type to display and sort by: simple, regular, hard, or total (default: total)",
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

    return parser.parse_args()


def main() -> None:
    """Main CLI entry point."""
    args = parse_arguments()

    if args.max_relations < 1:
        print("Error: --max-relations must be at least 1", file=sys.stderr)
        sys.exit(1)

    # Load stopwords from files or use defaults
    exclude_tags = load_stopwords(args.exclude_tags) or TAGS
    exclude_heading = load_stopwords(args.exclude_heading) or HEADING
    exclude_body = load_stopwords(args.exclude_body) or BODY

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

    # Analyze nodes
    result = analyze(nodes)

    def order_by_frequency(item: tuple[str, Frequency]) -> tuple[int, int]:
        """Sort by selected task type frequency (descending), then by total."""
        freq = item[1]
        primary = getattr(freq, args.tasks)
        secondary = freq.total
        return (-primary, -secondary)

    # Display results
    print("\nTotal tasks: ", result.total_tasks)
    print("\nDone tasks: ", result.done_tasks)

    # Display selected category
    if args.show == "tags":
        display_category(
            "tags",
            (result.tag_frequencies, result.tag_time_ranges, exclude_tags, result.tag_relations),
            args.max_results,
            args.max_relations,
            order_by_frequency,
        )
    elif args.show == "heading":
        display_category(
            "heading words",
            (
                result.heading_frequencies,
                result.heading_time_ranges,
                exclude_heading,
                result.heading_relations,
            ),
            args.max_results,
            args.max_relations,
            order_by_frequency,
        )
    else:
        display_category(
            "body words",
            (
                result.body_frequencies,
                result.body_time_ranges,
                exclude_body,
                result.body_relations,
            ),
            args.max_results,
            args.max_relations,
            order_by_frequency,
        )


if __name__ == "__main__":
    main()
