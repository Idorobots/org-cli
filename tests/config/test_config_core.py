"""Tests for org.config helpers."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
import typer

from org import config


if TYPE_CHECKING:
    from pathlib import Path


def test_load_config_missing_file_returns_empty(tmp_path: Path) -> None:
    """Missing config should return empty config without error."""
    missing = tmp_path / "missing.yaml"
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
    """Non-object YAML should be marked malformed."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("- 1\n- 2\n- 3\n", encoding="utf-8")

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
        "--limit": 25,
        "--max-tags": 3,
        "--filter-tag": ["work", "team"],
        "--use": "heading",
        "--pandoc-args": "--wrap=none",
    }

    defaults = config.build_config_defaults(raw)

    assert defaults is not None
    default_values, stats_defaults, append_defaults = defaults
    assert stats_defaults["max_results"] == 25
    assert stats_defaults["max_tags"] == 3
    assert stats_defaults["use"] == "heading"
    assert default_values["pandoc_args"] == "--wrap=none"
    assert append_defaults["filter_tags"] == ["work", "team"]


def test_build_config_defaults_rejects_invalid_entry() -> None:
    """Invalid values should cause config defaults to be rejected."""
    raw: dict[str, object] = {"--limit": "not-a-number"}

    defaults = config.build_config_defaults(raw)

    assert defaults is None


def test_build_config_defaults_accepts_ordering_flags() -> None:
    """Ordering switches should support boolean config defaults."""
    raw: dict[str, object] = {
        "--order-by-priority": True,
        "--order-by-level": True,
        "--order-by-timestamp-desc": True,
    }

    defaults = config.build_config_defaults(raw)

    assert defaults is not None
    default_values, _stats_defaults, _append_defaults = defaults
    assert default_values["order_by_priority"] is True
    assert default_values["order_by_level"] is True
    assert default_values["order_by_timestamp_desc"] is True


def test_build_config_defaults_rejects_non_boolean_ordering_flags() -> None:
    """Ordering switch defaults must be boolean values."""
    raw: dict[str, object] = {"--order-by-level": "yes"}

    defaults = config.build_config_defaults(raw)

    assert defaults is None


def test_parse_config_argument_prefers_cli_value() -> None:
    """--config argument should override default config name."""
    argv = ["org", "stats", "all", "--config", "custom.yaml"]

    assert config.parse_config_argument(argv) == "custom.yaml"


def test_parse_config_argument_supports_equals_form() -> None:
    """--config=FILE format should be parsed."""
    argv = ["org", "stats", "all", "--config=inline.yaml"]

    assert config.parse_config_argument(argv) == "inline.yaml"


def test_parse_config_argument_default() -> None:
    """Default config name should be used when not specified."""
    assert config.parse_config_argument(["org", "stats", "all"]) == ".org-cli.yaml"


def test_load_cli_config_reads_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """load_cli_config should load defaults from config file."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "defaults:\n"
            "  --limit: 7\n"
            "filter:\n"
            "  custom-filter: .[]\n"
            "order-by:\n"
            "  custom-order: .\n"
            "with:\n"
            "  custom-with: .\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    loaded = config.load_cli_config(["org"])

    assert loaded.defaults["max_results"] == 7
    assert loaded.append_defaults == {}
    assert loaded.inline_defaults == {}
    assert loaded.custom_filters == {"custom-filter": ".[]"}
    assert loaded.custom_order_by == {"custom-order": "."}
    assert loaded.custom_with == {"custom-with": "."}
    assert loaded.capture_templates == {}


def test_load_cli_config_sections_are_optional(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only defaults section should be enough for valid config."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text("defaults:\n  --limit: 7\n", encoding="utf-8")

    monkeypatch.chdir(config_path.parent)
    loaded = config.load_cli_config(["org"])

    assert loaded.defaults["max_results"] == 7
    assert loaded.custom_filters == {}
    assert loaded.custom_order_by == {}
    assert loaded.custom_with == {}
    assert loaded.capture_templates == {}


def test_load_cli_config_parses_capture_templates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture templates should load from capture.templates section."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "capture:\n"
            "  templates:\n"
            "    quick:\n"
            "      file: tasks.org\n"
            '      content: "* TODO {{title}}"\n'
            "    under-project:\n"
            "      file: tasks.org\n"
            '      content: "** TODO {{title}}"\n'
            '      parent: ".id == \\"project-1\\""\n'
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    loaded = config.load_cli_config(["org"])

    assert loaded.capture_templates == {
        "quick": {"file": "tasks.org", "content": "* TODO {{title}}"},
        "under-project": {
            "file": "tasks.org",
            "content": "** TODO {{title}}",
            "parent": '.id == "project-1"',
        },
    }


def test_load_cli_config_rejects_malformed_capture_templates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed capture.templates content should fail config loading."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        ("capture:\n  templates:\n    broken:\n      file: tasks.org\n"),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        config.load_cli_config(["org"])


def test_load_cli_config_rejects_unknown_capture_template_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture template objects should reject unknown keys."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "capture:\n"
            "  templates:\n"
            "    quick:\n"
            "      file: tasks.org\n"
            '      content: "* TODO {{title}}"\n'
            "      target: root\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        config.load_cli_config(["org"])


def test_load_cli_config_rejects_invalid_custom_section_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Custom sections must be object[string -> string]."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        "defaults:\n  --limit: 7\nfilter:\n  custom-filter: 1\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        config.load_cli_config(["org"])


def test_load_cli_config_malformed_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Malformed YAML config should raise a BadParameter error."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text("defaults: [1, 2\n", encoding="utf-8")

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        config.load_cli_config(["org"])


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
    assert config.validate_str_option("--out", "gfm") == "gfm"
    assert config.validate_str_option("--out", "") is None
    assert config.validate_str_option("--date", "2025-01-15") == "2025-01-15"
    assert config.validate_str_option("--date", "2025/01/15") is None
    assert config.validate_str_option("--todo-states", "TODO|WAIT") is None
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
        "tags": ["one"],
        "groups": ["a,b"],
    }

    default_map = config.build_default_map(defaults)

    summary_defaults = default_map["stats"]["all"]
    assert "tags" not in summary_defaults
    assert "groups" not in summary_defaults

    summary_defaults = default_map["stats"]["summary"]
    assert "max_tags" not in summary_defaults
    assert "max_relations" not in summary_defaults
    assert "tags" not in summary_defaults
    assert "groups" not in summary_defaults

    tags_defaults = default_map["stats"]["tags"]
    assert "max_tags" not in tags_defaults
    assert "max_groups" not in tags_defaults
    assert "min_group_size" not in tags_defaults
    assert "groups" not in tags_defaults

    groups_defaults = default_map["stats"]["groups"]
    assert "max_tags" not in groups_defaults
    assert "tags" not in groups_defaults


def test_build_default_map_keeps_ordering_boolean_defaults() -> None:
    """Tasks list and board ordering defaults should remain boolean flags."""
    default_map = config.build_default_map(
        {
            "order_by_level": True,
            "order_by_timestamp_desc": False,
        },
    )

    tasks_list_defaults = default_map["tasks"]["list"]
    assert tasks_list_defaults["order_by_level"] is True
    assert tasks_list_defaults["order_by_timestamp_desc"] is False

    board_defaults = default_map["board"]
    assert board_defaults["order_by_level"] is True
    assert board_defaults["order_by_timestamp_desc"] is False


def test_build_default_map_strips_flow_board_unsupported_defaults() -> None:
    """Board default map should omit list-only output options."""
    default_map = config.build_default_map(
        {
            "details": True,
            "max_results": 5,
            "offset": 2,
            "out": "json",
            "out_theme": "vim",
            "pandoc_args": "--wrap=none",
            "order_by_level": True,
        },
    )

    board_defaults = default_map["board"]
    assert "details" not in board_defaults
    assert board_defaults["max_results"] == 5
    assert board_defaults["offset"] == 2
    assert "out" not in board_defaults
    assert "out_theme" not in board_defaults
    assert "pandoc_args" not in board_defaults
    assert board_defaults["order_by_level"] is True


def test_build_default_map_includes_agenda_defaults() -> None:
    """Agenda default map should include agenda-specific and shared task options."""
    default_map = config.build_default_map(
        {
            "date": "2025-01-15",
            "days": 3,
            "no_completed": True,
            "no_overdue": True,
            "no_upcoming": True,
            "max_results": 5,
            "offset": 2,
            "order_by_level": True,
            "out": "json",
            "details": True,
            "max_tags": 5,
        },
    )

    agenda_defaults = default_map["agenda"]
    assert agenda_defaults["date"] == "2025-01-15"
    assert agenda_defaults["days"] == 3
    assert agenda_defaults["no_completed"] is True
    assert agenda_defaults["no_overdue"] is True
    assert agenda_defaults["no_upcoming"] is True
    assert agenda_defaults["max_results"] == 5
    assert agenda_defaults["offset"] == 2
    assert agenda_defaults["order_by_level"] is True
    assert "out" not in agenda_defaults
    assert "details" not in agenda_defaults
    assert "max_tags" not in agenda_defaults


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


def test_log_applied_config_defaults_logs_all_config_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Default logging should include all values loaded from config."""
    original_defaults = dict(config.CONFIG_DEFAULTS)
    original_append = dict(config.CONFIG_APPEND_DEFAULTS)
    original_inline = dict(config.CONFIG_INLINE_DEFAULTS)
    try:
        config.CONFIG_DEFAULTS.clear()
        config.CONFIG_APPEND_DEFAULTS.clear()
        config.CONFIG_INLINE_DEFAULTS.clear()

        config.CONFIG_DEFAULTS.update({"max_results": 10})
        config.CONFIG_APPEND_DEFAULTS.update({"filter_tags": ["work"]})
        config.CONFIG_INLINE_DEFAULTS.update({"mapping_inline": {"foo": "bar"}})

        args = SimpleNamespace(
            max_results=10,
            filter_tags=["work"],
            mapping_inline={"foo": "bar"},
        )

        with caplog.at_level(logging.INFO, logger="org"):
            config.log_applied_config_defaults(
                args,
                ["stats", "all", "--limit", "20"],
                "stats all",
            )

        assert "Config defaults applied (stats all):" in caplog.text
        assert "--limit=10" in caplog.text
        assert "--filter-tag=['work']" in caplog.text
        assert "--mapping='<Value ellided...>'" in caplog.text
    finally:
        config.CONFIG_DEFAULTS.clear()
        config.CONFIG_DEFAULTS.update(original_defaults)
        config.CONFIG_APPEND_DEFAULTS.clear()
        config.CONFIG_APPEND_DEFAULTS.update(original_append)
        config.CONFIG_INLINE_DEFAULTS.clear()
        config.CONFIG_INLINE_DEFAULTS.update(original_inline)


def test_log_command_arguments_logs_all_values(caplog: pytest.LogCaptureFixture) -> None:
    """Command argument logging should include all final argument values."""
    args = SimpleNamespace(max_results=10, filter_tags=["work"])

    with caplog.at_level(logging.INFO, logger="org"):
        config.log_command_arguments(args, "stats all")

    assert "Command arguments (stats all):" in caplog.text
    assert "max_results=10" in caplog.text
    assert "filter_tags=['work']" in caplog.text
