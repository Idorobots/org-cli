"""Tests for cli_common validation helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
import typer

from org.validation import (
    GlobalArgs,
    StatsArgs,
    parse_date_argument,
    parse_property_filter,
    validate_and_parse_keys,
    validate_global_arguments,
    validate_stats_arguments,
)


def test_validate_and_parse_keys_rejects_empty() -> None:
    """validate_and_parse_keys should exit on empty values."""
    with pytest.raises(typer.BadParameter, match="--todo-keys cannot be empty"):
        validate_and_parse_keys("", "--todo-keys")


def test_validate_and_parse_keys_rejects_pipe() -> None:
    """validate_and_parse_keys should reject pipe characters."""
    with pytest.raises(typer.BadParameter, match="pipe character"):
        validate_and_parse_keys("TODO|WAIT", "--todo-keys")


def test_parse_date_argument_invalid_format() -> None:
    """parse_date_argument should exit on invalid date formats."""
    with pytest.raises(typer.BadParameter, match="must be in one of these formats"):
        parse_date_argument("2025/01/15", "--filter-date-from")


def test_parse_property_filter_requires_equals() -> None:
    """parse_property_filter should enforce KEY=VALUE format."""
    with pytest.raises(typer.BadParameter, match="KEY=VALUE"):
        parse_property_filter("nope")


def test_validate_global_arguments_invalid_regex() -> None:
    """validate_global_arguments should reject invalid regex patterns."""
    args = SimpleNamespace(
        todo_keys="TODO",
        done_keys="DONE",
        filter_tags=["["],
        filter_headings=None,
        filter_bodies=None,
    )

    with pytest.raises(typer.BadParameter, match="Invalid regex pattern"):
        validate_global_arguments(cast(GlobalArgs, args))


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ("use", "--use must be one of"),
        ("max_results", "--max-results must be non-negative"),
        ("max_relations", "--max-relations must be non-negative"),
        ("max_tags", "--max-tags must be non-negative"),
        ("max_groups", "--max-groups must be non-negative"),
        ("min_group_size", "--min-group-size must be non-negative"),
        ("buckets", "--buckets must be at least 20"),
    ],
)
def test_validate_stats_arguments_errors(override: str, message: str) -> None:
    """validate_stats_arguments should reject invalid values."""
    args = SimpleNamespace(
        use="tags",
        max_results=1,
        max_relations=1,
        max_tags=1,
        max_groups=1,
        min_group_size=1,
        buckets=20,
    )

    if override == "use":
        args.use = "bad"
    elif override == "max_results":
        args.max_results = -1
    elif override == "max_relations":
        args.max_relations = -1
    elif override == "max_tags":
        args.max_tags = -1
    elif override == "max_groups":
        args.max_groups = -1
    elif override == "min_group_size":
        args.min_group_size = -1
    elif override == "buckets":
        args.buckets = 10

    with pytest.raises(typer.BadParameter, match=message):
        validate_stats_arguments(cast(StatsArgs, args))
