"""Tests for org.config helpers."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
import typer

import org.config.app
import org.logging


if TYPE_CHECKING:
    from pathlib import Path


def test_load_config_missing_file_returns_empty(tmp_path: Path) -> None:
    """Missing config should return empty config without error."""
    missing = tmp_path / "missing.yaml"
    data, malformed = org.config.app.load_config(str(missing))

    assert data == {}
    assert malformed is False


def test_load_config_directory_path_is_malformed(tmp_path: Path) -> None:
    """Directory path should be treated as malformed config."""
    config_dir = tmp_path / "cfgdir"
    config_dir.mkdir()
    data, malformed = org.config.app.load_config(str(config_dir))

    assert data == {}
    assert malformed is True


def test_load_config_non_dict_is_malformed(tmp_path: Path) -> None:
    """Non-object YAML should be marked malformed."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("- 1\n- 2\n- 3\n", encoding="utf-8")

    data, malformed = org.config.app.load_config(str(config_path))

    assert data == {}
    assert malformed is True


def test_load_cli_config_parses_shared_and_section_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structured config should populate shared fields and command sections."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "color_flag: true\n"
            "filter_tags:\n"
            "  - work\n"
            "stats:\n"
            "  max_tags: 3\n"
            "  use: heading\n"
            "tasks:\n"
            '  pandoc_args: "--wrap=none"\n'
            "board:\n"
            "  view: kanban\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    loaded = org.config.app.load_cli_config(["org"])

    assert loaded.color_flag is True
    assert loaded.filter_tags == ["work"]
    assert loaded.stats.max_tags == 3
    assert loaded.stats.use == "heading"
    assert loaded.tasks.pandoc_args == "--wrap=none"
    assert loaded.board.view == "kanban"


def test_parse_config_argument_prefers_cli_value() -> None:
    """--config argument should override default config name."""
    argv = ["org", "stats", "all", "--config", "custom.yaml"]

    assert org.config.app.parse_config_argument(argv) == "custom.yaml"


def test_parse_config_argument_supports_equals_form() -> None:
    """--config=FILE format should be parsed."""
    argv = ["org", "stats", "all", "--config=inline.yaml"]

    assert org.config.app.parse_config_argument(argv) == "inline.yaml"


def test_parse_config_argument_default() -> None:
    """Default config name should be used when not specified."""
    assert org.config.app.parse_config_argument(["org", "stats", "all"]) == ".org-cli.yaml"


def test_load_cli_config_reads_structured_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """load_cli_config should load structured config values from config file."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "todo_states: TODO,WAITING\n"
            "mapping: examples/mapping_example.json\n"
            "stats:\n"
            "  max_results: 7\n"
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
    loaded = org.config.app.load_cli_config(["org"])

    assert loaded.todo_states == ["TODO", "WAITING"]
    assert loaded.mapping == "examples/mapping_example.json"
    assert loaded.stats.max_results == 7
    assert loaded.custom_filter_map() == {"custom-filter": ".[]"}
    assert loaded.custom_order_by_map() == {"custom-order": "."}
    assert loaded.custom_with_map() == {"custom-with": "."}
    assert loaded.capture_templates == {}
    assert loaded.board_views == {}


def test_load_cli_config_sections_are_optional(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only one structured command section should be enough for valid config."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text("stats:\n  max_results: 7\n", encoding="utf-8")

    monkeypatch.chdir(config_path.parent)
    loaded = org.config.app.load_cli_config(["org"])

    assert loaded.stats.max_results == 7
    assert loaded.custom_filter_map() == {}
    assert loaded.custom_order_by_map() == {}
    assert loaded.custom_with_map() == {}
    assert loaded.capture_templates == {}
    assert loaded.board_views == {}


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
    loaded = org.config.app.load_cli_config(["org"])

    assert loaded.capture_templates == {
        "quick": {"file": "tasks.org", "content": "* TODO {{title}}"},
        "under-project": {
            "file": "tasks.org",
            "content": "** TODO {{title}}",
            "parent": '.id == "project-1"',
        },
    }
    assert loaded.board_views == {}


def test_load_cli_config_parses_board_views(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board views should load from board.views section."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "board:\n"
            "  views:\n"
            "    - name: kanban\n"
            "      columns:\n"
            "        - name: Backlog\n"
            "          filter: .todo == null\n"
            "        - name: TODO\n"
            '          filter: .todo == "TODO"\n'
            "          order-by: .priority\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    loaded = org.config.app.load_cli_config(["org"])

    assert set(loaded.board_views) == {"kanban"}
    assert loaded.board_views["kanban"].name == "kanban"
    assert [column.name for column in loaded.board_views["kanban"].columns] == ["Backlog", "TODO"]
    assert [column.filter for column in loaded.board_views["kanban"].columns] == [
        ".todo == null",
        '.todo == "TODO"',
    ]
    assert [column.order_by for column in loaded.board_views["kanban"].columns] == [
        None,
        ".priority",
    ]


def test_load_cli_config_allows_empty_board_section(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board section may be present without views or overrides."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text("board: {}\n", encoding="utf-8")

    monkeypatch.chdir(config_path.parent)
    loaded = org.config.app.load_cli_config(["org"])

    assert loaded.board.views == {}


def test_load_cli_config_rejects_board_views_not_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board views must be a list."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text("board:\n  views: {}\n", encoding="utf-8")

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_rejects_duplicate_board_view_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board views must have unique non-empty names."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "board:\n"
            "  views:\n"
            "    - name: kanban\n"
            "      columns:\n"
            "        - name: TODO\n"
            '          filter: .todo == "TODO"\n'
            "    - name: kanban\n"
            "      columns:\n"
            "        - name: DONE\n"
            "          filter: .is_completed\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_rejects_empty_board_columns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each board view requires at least one column."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        "board:\n  views:\n    - name: kanban\n      columns: []\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_rejects_invalid_board_column_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board columns require non-empty name and filter fields."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "board:\n"
            "  views:\n"
            "    - name: kanban\n"
            "      columns:\n"
            '        - name: ""\n'
            '          filter: .todo == "TODO"\n'
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_rejects_unknown_board_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board schema should reject unknown keys at any level."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "board:\n"
            "  views:\n"
            "    - name: kanban\n"
            "      style: compact\n"
            "      columns:\n"
            "        - name: TODO\n"
            '          filter: .todo == "TODO"\n'
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_rejects_board_with_wrong_top_level_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board section must be an object with views."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text("board: []\n", encoding="utf-8")

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_rejects_empty_board_view_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board views require non-empty names."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "board:\n"
            "  views:\n"
            '    - name: ""\n'
            "      columns:\n"
            "        - name: TODO\n"
            '          filter: .todo == "TODO"\n'
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_rejects_missing_board_view_columns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board view objects must define columns."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        ("board:\n  views:\n    - name: kanban\n"),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_rejects_missing_board_column_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board column objects must define name."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "board:\n"
            "  views:\n"
            "    - name: kanban\n"
            "      columns:\n"
            '        - filter: .todo == "TODO"\n'
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_rejects_missing_board_column_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board column objects must define filter."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        ("board:\n  views:\n    - name: kanban\n      columns:\n        - name: TODO\n"),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_rejects_empty_board_column_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board column filter must be a non-empty string."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "board:\n"
            "  views:\n"
            "    - name: kanban\n"
            "      columns:\n"
            "        - name: TODO\n"
            '          filter: ""\n'
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_rejects_empty_board_column_order_by(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board column order-by must be non-empty when provided."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "board:\n"
            "  views:\n"
            "    - name: kanban\n"
            "      columns:\n"
            "        - name: TODO\n"
            '          filter: .todo == "TODO"\n'
            '          order-by: ""\n'
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_rejects_non_string_board_column_order_by(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board column order-by must be a string when provided."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        (
            "board:\n"
            "  views:\n"
            "    - name: kanban\n"
            "      columns:\n"
            "        - name: TODO\n"
            '          filter: .todo == "TODO"\n'
            "          order-by: 1\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


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
        org.config.app.load_cli_config(["org"])


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
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_rejects_invalid_custom_section_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Custom sections must be object[string -> string]."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text(
        "stats:\n  max_results: 7\nfilter:\n  custom-filter: 1\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_load_cli_config_malformed_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Malformed YAML config should raise a BadParameter error."""
    config_path = tmp_path / ".org-cli.yaml"
    config_path.write_text("stats: [1, 2\n", encoding="utf-8")

    monkeypatch.chdir(config_path.parent)
    with pytest.raises(typer.BadParameter, match="Malformed config"):
        org.config.app.load_cli_config(["org"])


def test_validate_helpers() -> None:
    """Validation helpers should accept valid values and reject invalid ones."""
    assert org.config.app.is_valid_date_argument("2025-01-15") is True
    assert org.config.app.is_valid_date_argument("2025/01/15") is False

    assert org.config.app.is_valid_keys_string("TODO,DONE") is True
    assert org.config.app.is_valid_keys_string("TODO|WAIT") is False

    assert org.config.app.validate_int_option(3, 0) == 3
    assert org.config.app.validate_int_option(-1, 0) is None
    assert org.config.app.validate_int_option("nope", 0) is None

    assert org.config.app.validate_str_option("--use", "tags") == "tags"
    assert org.config.app.validate_str_option("--use", "nope") is None
    assert org.config.app.validate_str_option("--out", "gfm") == "gfm"
    assert org.config.app.validate_str_option("--out", "") is None
    assert org.config.app.validate_str_option("--date", "2025-01-15") == "2025-01-15"
    assert org.config.app.validate_str_option("--date", "2025/01/15") is None
    assert org.config.app.validate_str_option("--todo-states", "TODO|WAIT") is None
    assert org.config.app.validate_str_option("--filter-date-from", "2025/01/15") is None

    assert org.config.app.validate_list_option("--filter-property", ["key=value"]) == ["key=value"]
    assert org.config.app.validate_list_option("--filter-property", ["novalue"]) is None
    assert org.config.app.validate_list_option("--filter-tag", ["["]) is None
    assert org.config.app.validate_list_option("--filter-body", ["["]) is None


def test_log_command_config_logs_all_config_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Config logging should include values loaded for a command."""
    config = org.config.app.build_default_app_config()
    config.stats.max_results = 10
    config.filter_tags = ["work"]
    config.mapping_inline = {"foo": "bar"}

    org.logging.logger.setLevel(logging.INFO)
    org.logging.logger.propagate = True
    with caplog.at_level(logging.INFO, logger="org"):
        org.logging.log_command_config(config, "stats all")

    assert "Command config (stats all):" in caplog.text
    assert "filter_tags=['work']" in caplog.text
    assert "mapping_inline='<Value ellided...>'" in caplog.text


def test_log_command_arguments_logs_all_values(caplog: pytest.LogCaptureFixture) -> None:
    """Command argument logging should include all final argument values."""
    args = SimpleNamespace(max_results=10, filter_tags=["work"])

    org.logging.logger.setLevel(logging.INFO)
    org.logging.logger.propagate = True
    with caplog.at_level(logging.INFO, logger="org"):
        org.logging.log_command_arguments(args, "stats all")

    assert "Command arguments (stats all):" in caplog.text
    assert "max_results=10" in caplog.text
    assert "filter_tags=['work']" in caplog.text
