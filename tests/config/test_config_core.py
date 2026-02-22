"""Tests for org.config helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from org import config


def test_load_config_missing_file_returns_empty(tmp_path: Path) -> None:
    """Missing config should return empty config without error."""
    missing = tmp_path / "missing.json"
    data, malformed = config.load_config(str(missing))

    assert data == {}
    assert malformed is False


def test_load_config_directory_path_is_malformed(tmp_path: Path) -> None:
    """Directory path should be treated as malformed config."""
    config_dir = tmp_path / "cfgdir"
    config_dir.mkdir()
    data, malformed = config.load_config(str(config_dir))

    assert data == {}
    assert malformed is True


def test_load_config_non_dict_is_malformed(tmp_path: Path) -> None:
    """Non-object JSON should be marked malformed."""
    config_path = tmp_path / "config.json"
    config_path.write_text("[1, 2, 3]", encoding="utf-8")

    data, malformed = config.load_config(str(config_path))

    assert data == {}
    assert malformed is True


def test_parse_color_defaults_conflict() -> None:
    """Conflicting color flags should be rejected."""
    defaults, valid = config.parse_color_defaults({"--color": True, "--no-color": True})

    assert defaults == {}
    assert valid is False


def test_parse_color_defaults_invalid_value() -> None:
    """Non-boolean color flag should be rejected."""
    defaults, valid = config.parse_color_defaults({"--color": "yes"})

    assert defaults == {}
    assert valid is False


def test_build_config_defaults_applies_values() -> None:
    """Config defaults should populate summary/task defaults and append defaults."""
    raw: dict[str, object] = {
        "--max-results": 25,
        "--max-tags": 3,
        "--filter-tag": ["work", "team"],
        "--with-gamify-category": True,
        "--use": "heading",
    }

    defaults = config.build_config_defaults(raw)

    assert defaults is not None
    default_values, stats_defaults, append_defaults = defaults
    assert stats_defaults["max_results"] == 25
    assert stats_defaults["max_tags"] == 3
    assert stats_defaults["with_gamify_category"] is True
    assert stats_defaults["use"] == "heading"
    assert append_defaults["filter_tags"] == ["work", "team"]


def test_build_config_defaults_rejects_invalid_entry() -> None:
    """Invalid values should cause config defaults to be rejected."""
    raw: dict[str, object] = {"--max-results": "not-a-number"}

    defaults = config.build_config_defaults(raw)

    assert defaults is None


def test_parse_config_argument_prefers_cli_value() -> None:
    """--config argument should override default config name."""
    argv = ["org", "stats", "summary", "--config", "custom.json"]

    assert config.parse_config_argument(argv) == "custom.json"


def test_parse_config_argument_supports_equals_form() -> None:
    """--config=FILE format should be parsed."""
    argv = ["org", "stats", "summary", "--config=inline.json"]

    assert config.parse_config_argument(argv) == "inline.json"


def test_parse_config_argument_default() -> None:
    """Default config name should be used when not specified."""
    assert config.parse_config_argument(["org", "stats", "summary"]) == ".org-cli.json"


def test_load_cli_config_reads_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """load_cli_config should load defaults from config file."""
    config_path = tmp_path / ".org-cli.json"
    config_path.write_text(json.dumps({"--max-results": 7}), encoding="utf-8")

    monkeypatch.chdir(config_path.parent)
    defaults, append_defaults, inline_defaults = config.load_cli_config(["org"])

    assert defaults["max_results"] == 7
    assert append_defaults == {}
    assert inline_defaults == {}


def test_load_cli_config_malformed_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Malformed config should emit warning and return empty defaults."""
    config_path = tmp_path / ".org-cli.json"
    config_path.write_text("{bad json", encoding="utf-8")

    monkeypatch.chdir(config_path.parent)
    defaults, append_defaults, inline_defaults = config.load_cli_config(["org"])

    captured = capsys.readouterr().err
    assert "Malformed config" in captured
    assert defaults == {}
    assert append_defaults == {}
    assert inline_defaults == {}


def test_validate_helpers() -> None:
    """Validation helpers should accept valid values and reject invalid ones."""
    assert config.is_valid_date_argument("2025-01-15") is True
    assert config.is_valid_date_argument("2025/01/15") is False

    assert config.is_valid_keys_string("TODO,DONE") is True
    assert config.is_valid_keys_string("TODO|WAIT") is False

    assert config.validate_int_option(3, 0) == 3
    assert config.validate_int_option(-1, 0) is None
    assert config.validate_int_option("nope", 0) is None

    assert config.validate_str_option("--use", "tags") == "tags"
    assert config.validate_str_option("--use", "nope") is None
    assert config.validate_str_option("--todo-keys", "TODO|WAIT") is None
    assert config.validate_str_option("--filter-date-from", "2025/01/15") is None

    assert config.validate_list_option("--filter-property", ["key=value"]) == ["key=value"]
    assert config.validate_list_option("--filter-property", ["novalue"]) is None
    assert config.validate_list_option("--filter-tag", ["["]) is None
    assert config.validate_list_option("--filter-body", ["["]) is None


def test_apply_mapping_and_exclude_config() -> None:
    """Mapping/exclude config should support string and inline forms."""
    defaults: dict[str, object] = {}

    assert config.apply_mapping_config("mapping.json", defaults) is True
    assert defaults["mapping"] == "mapping.json"

    defaults.clear()
    assert config.apply_mapping_config({"foo": "bar"}, defaults) is True
    assert defaults["mapping_inline"] == {"foo": "bar"}

    defaults.clear()
    assert config.apply_mapping_config("", defaults) is False

    defaults.clear()
    assert config.apply_exclude_config("exclude.txt", defaults) is True
    assert defaults["exclude"] == "exclude.txt"

    defaults.clear()
    assert config.apply_exclude_config(["alpha", "beta"], defaults) is True
    assert defaults["exclude_inline"] == ["alpha", "beta"]


def test_build_default_map_strips_command_specific_values() -> None:
    """build_default_map should drop irrelevant defaults per command."""
    defaults = {
        "max_results": 10,
        "max_tags": 5,
        "max_relations": 2,
        "max_groups": 1,
        "min_group_size": 2,
        "use": "tags",
        "show": "one",
        "groups": ["a,b"],
    }

    default_map = config.build_default_map(defaults)

    summary_defaults = default_map["stats"]["summary"]
    assert "show" not in summary_defaults
    assert "groups" not in summary_defaults

    tasks_defaults = default_map["stats"]["tasks"]
    assert "max_tags" not in tasks_defaults
    assert "max_relations" not in tasks_defaults
    assert "show" not in tasks_defaults
    assert "groups" not in tasks_defaults

    tags_defaults = default_map["stats"]["tags"]
    assert "max_tags" not in tags_defaults
    assert "max_groups" not in tags_defaults
    assert "min_group_size" not in tags_defaults
    assert "groups" not in tags_defaults

    groups_defaults = default_map["stats"]["groups"]
    assert "max_tags" not in groups_defaults
    assert "show" not in groups_defaults


def test_apply_config_defaults_applies_inline_and_append_defaults() -> None:
    """apply_config_defaults should fill append and inline values."""
    original_append = dict(config.CONFIG_APPEND_DEFAULTS)
    original_inline = dict(config.CONFIG_INLINE_DEFAULTS)
    try:
        config.CONFIG_APPEND_DEFAULTS.clear()
        config.CONFIG_INLINE_DEFAULTS.clear()

        config.CONFIG_APPEND_DEFAULTS["filter_tags"] = ["alpha"]
        config.CONFIG_INLINE_DEFAULTS["mapping_inline"] = {"foo": "bar"}

        args = SimpleNamespace(filter_tags=None, mapping_inline=None, exclude_inline=None)
        config.apply_config_defaults(args)

        assert args.filter_tags == ["alpha"]
        assert args.mapping_inline == {"foo": "bar"}
        assert args.exclude_inline is None
    finally:
        config.CONFIG_APPEND_DEFAULTS.clear()
        config.CONFIG_APPEND_DEFAULTS.update(original_append)
        config.CONFIG_INLINE_DEFAULTS.clear()
        config.CONFIG_INLINE_DEFAULTS.update(original_inline)
