"""Validation and parsing helpers for CLI arguments."""

from __future__ import annotations

import re
import sys
from datetime import datetime
from typing import Protocol


class GlobalArgs(Protocol):
    """Protocol for arguments used in global validation."""

    todo_keys: str
    done_keys: str
    filter_tags: list[str] | None
    filter_headings: list[str] | None
    filter_bodies: list[str] | None


class StatsArgs(Protocol):
    """Protocol for arguments used in stats validation."""

    use: str
    max_relations: int
    max_tags: int
    max_groups: int
    min_group_size: int
    buckets: int


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


def parse_group_values(value: str) -> list[str]:
    """Parse comma-separated group values."""
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values:
        print("Error: --group cannot be empty", file=sys.stderr)
        sys.exit(1)
    return values


def validate_global_arguments(args: GlobalArgs) -> tuple[list[str], list[str]]:
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


def validate_stats_arguments(args: StatsArgs) -> None:
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
