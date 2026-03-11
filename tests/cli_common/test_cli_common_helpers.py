"""Tests for cli_common helper utilities."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import typer

from org.cli_common import (
    dedupe_values,
    normalize_show_value,
    resolve_group_values,
    resolve_input_paths,
)
from org.validation import parse_group_values


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
    """All-missing paths should error."""
    missing = tmp_path / "missing"
    with pytest.raises(typer.BadParameter, match="All input paths are missing"):
        resolve_input_paths([str(missing)])


def test_resolve_input_paths_warns_and_keeps_existing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Missing paths should warn while existing files are still processed."""
    existing = tmp_path / "one.org"
    missing = tmp_path / "missing.org"
    existing.write_text("* DONE Test", encoding="utf-8")

    resolved = resolve_input_paths([str(missing), str(existing)])
    captured = capsys.readouterr()

    assert resolved == [str(existing)]
    assert f"Warning: Path '{missing}' not found" in captured.err


def test_resolve_input_paths_skips_missing_globbed_files_in_verbose(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Missing files discovered from directory glob should be logged and skipped."""
    existing = tmp_path / "one.org"
    broken = tmp_path / ".#one.org"
    missing_target = tmp_path / "missing-target.org"
    existing.write_text("* DONE Test", encoding="utf-8")
    try:
        broken.symlink_to(missing_target)
    except OSError:
        pytest.skip("symlinks are not supported on this platform")

    with caplog.at_level(logging.INFO, logger="org"):
        resolved = resolve_input_paths([str(tmp_path)])

    assert resolved == [str(existing)]
    assert f"Warning: Path '{broken}' not found" in caplog.text
