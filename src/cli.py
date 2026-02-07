#!/usr/bin/env python
"""CLI interface for orgstats - Org-mode archive file analysis."""

import argparse
import sys

import orgparse

from core import BODY, HEADING, TAGS, Frequency, analyze, clean


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
        nargs="*",
        metavar="FILE",
        help="Org-mode archive files to analyze",
    )

    parser.add_argument(
        "--max-results",
        "-n",
        type=int,
        default=100,
        metavar="N",
        help="Maximum number of results to display (default: 100)",
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

    return parser.parse_args()


def main() -> None:
    """Main CLI entry point."""
    args = parse_arguments()

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

    def order_by_frequency(item: tuple[str, Frequency]) -> int:
        """Sort by frequency (descending)."""
        return -item[1].total

    # Display results
    print("\nTotal tasks: ", result.total_tasks)
    print("\nDone tasks: ", result.done_tasks)
    print(
        "\nTop tags:\n",
        sorted(clean(exclude_tags, result.tag_frequencies).items(), key=order_by_frequency)[
            0 : args.max_results
        ],
    )
    print(
        "\nTop words in headline:\n",
        sorted(clean(exclude_heading, result.heading_frequencies).items(), key=order_by_frequency)[
            0 : args.max_results
        ],
    )
    print(
        "\nTop words in body:\n",
        sorted(clean(exclude_body, result.body_frequencies).items(), key=order_by_frequency)[
            0 : args.max_results
        ],
    )


if __name__ == "__main__":
    main()
