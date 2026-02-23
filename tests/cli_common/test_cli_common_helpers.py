"""Tests for cli_common helper utilities."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from org.cli_common import (
    dedupe_values,
    normalize_show_value,
    resolve_group_values,
    resolve_input_paths,
)
from org.validation import parse_group_values, parse_show_values


def test_parse_show_values_rejects_empty() -> None:
    """Empty show values should exit with error."""
    with pytest.raises(typer.BadParameter, match="--show cannot be empty"):
        parse_show_values("  , ")


def test_normalize_show_value_applies_mapping() -> None:
    """normalize_show_value should normalize and map values."""
    mapping = {"fix": "bugfix"}

    assert normalize_show_value("Fix", mapping) == "bugfix"


def test_dedupe_values_preserves_order() -> None:
    """dedupe_values should keep first occurrence order."""
    assert dedupe_values(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_parse_group_values_rejects_empty() -> None:
    """Empty group values should exit with error."""
    with pytest.raises(typer.BadParameter, match="--group cannot be empty"):
        parse_group_values(" ")


def test_resolve_group_values_maps_and_dedupes() -> None:
    """resolve_group_values should map and dedupe explicit groups."""
    mapping = {"foo": "bar"}
    groups = resolve_group_values(["foo,foo,bar"], mapping, "tags")

    assert groups == [["bar"]]


def test_resolve_input_paths_from_directory(tmp_path: Path) -> None:
    """resolve_input_paths should expand directory org files."""
    one = tmp_path / "one.org"
    two = tmp_path / "two.org"
    one.write_text("* DONE Test", encoding="utf-8")
    two.write_text("* DONE Test", encoding="utf-8")

    resolved = resolve_input_paths([str(tmp_path)])

    assert resolved == [str(one), str(two)]


def test_resolve_input_paths_missing(tmp_path: Path) -> None:
    """Missing paths should error."""
    missing = tmp_path / "missing"
    with pytest.raises(typer.BadParameter, match="not found"):
        resolve_input_paths([str(missing)])
