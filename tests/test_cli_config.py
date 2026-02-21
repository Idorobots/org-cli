"""Tests for CLI config file support."""

import json
import os
import subprocess
import sys
from pathlib import Path

from pytest import CaptureFixture, MonkeyPatch


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def write_config(path: Path, data: dict[str, object]) -> None:
    """Write JSON config to path."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def test_config_applies_defaults(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Config values should become defaults when CLI omits them."""
    from orgstats.cli import parse_arguments

    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    config_path = tmp_path / ".org-cli.json"
    write_config(config_path, {"--use": "heading"})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["orgstats", fixture_path])

    args = parse_arguments()
    assert args.use == "heading"


def test_cli_overrides_config(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """CLI arguments should override config defaults."""
    from orgstats.cli import parse_arguments

    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    config_path = tmp_path / ".org-cli.json"
    write_config(config_path, {"--use": "heading"})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["orgstats", "--use", "body", fixture_path])

    args = parse_arguments()
    assert args.use == "body"


def test_malformed_json_prints_and_ignored(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    """Malformed JSON should print warning and use defaults."""
    from orgstats.cli import parse_arguments

    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    config_path = tmp_path / ".org-cli.json"
    with config_path.open("w", encoding="utf-8") as f:
        f.write("{bad json")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["orgstats", fixture_path])

    args = parse_arguments()
    captured = capsys.readouterr()
    assert "Malformed config" in captured.err
    assert args.use == "tags"


def test_malformed_value_prints_and_ignored(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    """Malformed config values should print warning and use defaults."""
    from orgstats.cli import parse_arguments

    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    config_path = tmp_path / ".org-cli.json"
    write_config(config_path, {"--max-results": "ten"})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["orgstats", fixture_path])

    args = parse_arguments()
    captured = capsys.readouterr()
    assert "Malformed config" in captured.err
    assert args.max_results == 10


def test_config_filter_applies_with_no_cli_order(tmp_path: Path) -> None:
    """Config filter values should apply when CLI omits filters."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    config_path = tmp_path / ".org-cli.json"
    write_config(config_path, {"--filter-tag": ["this-tag-does-not-exist"]})

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--no-color", fixture_path],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "No results" in result.stdout


def test_config_custom_name(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Custom config name should be respected."""
    from orgstats.cli import parse_arguments

    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    config_path = tmp_path / "custom.json"
    write_config(config_path, {"--use": "heading"})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["orgstats", "--config", "custom.json", fixture_path])

    args = parse_arguments()
    assert args.use == "heading"


def test_config_absolute_path(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Absolute config path should be respected."""
    from orgstats.cli import parse_arguments

    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    config_path = tmp_path / "absolute.json"
    write_config(config_path, {"--use": "body"})

    monkeypatch.chdir("/")
    monkeypatch.setattr(
        sys,
        "argv",
        ["orgstats", "--config", str(config_path.resolve()), fixture_path],
    )

    args = parse_arguments()
    assert args.use == "body"


def test_config_inline_mapping(tmp_path: Path) -> None:
    """Inline mapping should be used when provided as object."""
    fixture_path = os.path.join(FIXTURES_DIR, "mapping_test.org")
    config_path = tmp_path / ".org-cli.json"
    write_config(
        config_path,
        {"--mapping": {"foo": "bar", "testing": "test", "python": "py"}},
    )

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--no-color", fixture_path],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "bar" in result.stdout
    assert "test" in result.stdout
    assert "py" in result.stdout


def test_config_inline_exclude(tmp_path: Path) -> None:
    """Inline exclude list should be used when provided as array."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    config_path = tmp_path / ".org-cli.json"
    write_config(config_path, {"--exclude": ["test", "debugging"]})

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--no-color", fixture_path],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "  test\n" not in result.stdout
    assert "  debugging\n" not in result.stdout
