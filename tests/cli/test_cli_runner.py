"""CliRunner tests for the Typer CLI."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from typer.testing import CliRunner

from org import config
from org.cli import app


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class _CliResult(Protocol):
    """Typing protocol for CliRunner invocation results."""

    @property
    def stdout(self) -> str:
        """Captured stdout text."""
        ...

    @property
    def stderr(self) -> str:
        """Captured stderr text."""
        ...


def clean_combined_output(result: _CliResult) -> str:
    """Return stdout+stderr with ANSI escape sequences removed."""
    return ANSI_ESCAPE_RE.sub("", result.stdout + result.stderr)


def test_cli_runner_summary() -> None:
    """CliRunner should execute stats all."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())

    result = runner.invoke(app, ["stats", "all", "--no-color", fixture_path])

    assert result.exit_code == 0
    assert "Total tasks:" in result.stdout


def test_cli_runner_tags_tag() -> None:
    """CliRunner should filter tags with --tag."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())

    result = runner.invoke(app, ["stats", "tags", "--no-color", "--tag", "Test", fixture_path])

    assert result.exit_code == 0
    assert "Test" in result.stdout
    assert "Debugging" not in result.stdout


def test_cli_runner_groups_explicit() -> None:
    """CliRunner should render explicit groups."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "tag_groups_test.org").resolve())

    result = runner.invoke(
        app,
        [
            "stats",
            "groups",
            "--no-color",
            "--group",
            "python,programming",
            fixture_path,
        ],
    )

    assert result.exit_code == 0
    assert "python, programming" in result.stdout


def test_cli_runner_tasks_list_custom_filter_without_arg() -> None:
    """Custom filter switches should not be parsed as FILE arguments."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())
    original_filters = dict(config.CONFIG_CUSTOM_FILTERS)

    try:
        config.CONFIG_CUSTOM_FILTERS.clear()
        config.CONFIG_CUSTOM_FILTERS.update({"has-todo": "select(.todo != null)"})

        result = runner.invoke(
            app,
            ["tasks", "list", "--no-color", "--filter-has-todo", fixture_path],
        )

        assert result.exit_code == 0
        assert "* TODO Refactor" in result.stdout
        assert ":Maintenance:" in result.stdout
    finally:
        config.CONFIG_CUSTOM_FILTERS.clear()
        config.CONFIG_CUSTOM_FILTERS.update(original_filters)


def test_cli_runner_tasks_list_custom_filter_with_arg() -> None:
    """Custom filter argument value should not be parsed as FILE argument."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())
    original_filters = dict(config.CONFIG_CUSTOM_FILTERS)

    try:
        config.CONFIG_CUSTOM_FILTERS.clear()
        config.CONFIG_CUSTOM_FILTERS.update({"level-above": "select(.level > $arg)"})

        result = runner.invoke(
            app,
            ["tasks", "list", "--no-color", "--filter-level-above", "0", fixture_path],
        )

        assert result.exit_code == 0
        assert "* TODO Refactor" in result.stdout
        assert ":Maintenance:" in result.stdout
    finally:
        config.CONFIG_CUSTOM_FILTERS.clear()
        config.CONFIG_CUSTOM_FILTERS.update(original_filters)


def test_cli_runner_tasks_list_custom_filter_required_arg_error() -> None:
    """Custom filters with $arg should fail when the argument is missing."""
    runner = CliRunner()
    original_filters = dict(config.CONFIG_CUSTOM_FILTERS)

    try:
        config.CONFIG_CUSTOM_FILTERS.clear()
        config.CONFIG_CUSTOM_FILTERS.update({"level-above": "select(.level > $arg)"})

        result = runner.invoke(
            app,
            ["tasks", "list", "--no-color", "--filter-level-above"],
        )

        assert result.exit_code != 0
        # FIXME This is only required on CI for some reason.
        combined_output = clean_combined_output(result)
        assert "--filter-level-above requires exactly one argument" in combined_output
    finally:
        config.CONFIG_CUSTOM_FILTERS.clear()
        config.CONFIG_CUSTOM_FILTERS.update(original_filters)


def test_cli_runner_flow_board_renders_columns() -> None:
    """CliRunner should render board columns for flow board command."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "custom_states.org").resolve())

    result = runner.invoke(
        app,
        [
            "flow",
            "board",
            "--no-color",
            "--todo-states",
            "TODO,WAITING,IN-PROGRESS",
            "--done-states",
            "DONE,CANCELLED,ARCHIVED",
            "--width",
            "150",
            fixture_path,
        ],
    )

    assert result.exit_code == 0
    assert "NOT STARTED" in result.stdout
    assert "COMPLETED" in result.stdout
    assert "WAITING" in result.stdout


def test_cli_runner_agenda_renders_day_view() -> None:
    """CliRunner should render agenda day sections and items."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "agenda_sample.org").resolve())

    result = runner.invoke(
        app,
        [
            "agenda",
            "--no-color",
            "--date",
            "2025-01-15",
            fixture_path,
        ],
    )

    assert result.exit_code == 0
    plain_stdout = result.stdout.replace("…", "")
    assert "CATEGORY" in plain_stdout
    assert "TASK" in plain_stdout
    assert "2025-01-15" in plain_stdout
    assert "Timed agenda task" in plain_stdout


def test_cli_runner_tasks_add_writes_heading(tmp_path: Path) -> None:
    """CliRunner should create a new task heading in the selected file."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text("* TODO Existing\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "tasks",
            "add",
            "--todo",
            "TODO",
            "--title",
            "Update docs",
            "--tags",
            "Docs",
            str(fixture_path),
        ],
    )

    assert result.exit_code == 0
    updated = fixture_path.read_text(encoding="utf-8")
    assert "* TODO Update docs :Docs:" in updated


def test_cli_runner_tasks_add_reads_from_stdin_when_heading_components_missing(
    tmp_path: Path,
) -> None:
    """CliRunner should read task source from stdin when heading source is omitted."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text("* TODO Existing\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "tasks",
            "add",
            str(fixture_path),
        ],
        input="* TODO From stdin\n",
    )

    assert result.exit_code == 0
    updated = fixture_path.read_text(encoding="utf-8")
    assert "* TODO From stdin" in updated


def test_cli_runner_tasks_add_applies_edits_to_stdin_task(tmp_path: Path) -> None:
    """CliRunner should apply edit switches on stdin-provided task source."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text("* TODO Existing\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "tasks",
            "add",
            "--priority",
            "A",
            "--tags",
            "new,docs",
            str(fixture_path),
        ],
        input="* TODO From stdin :old:\n",
    )

    assert result.exit_code == 0
    updated = fixture_path.read_text(encoding="utf-8")
    assert "* TODO [#A] From stdin :new:docs:" in updated


def test_cli_runner_tasks_remove_removes_heading(tmp_path: Path) -> None:
    """CliRunner should delete a task heading and its subtree."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text(
        "* TODO Keep\n* TODO Remove me\n** TODO Child\n* TODO Tail\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "tasks",
            "remove",
            "--query-title",
            "Remove me",
            "--yes",
            str(fixture_path),
        ],
    )

    assert result.exit_code == 0
    assert "Deleted 1 tasks." in result.stdout
    updated = fixture_path.read_text(encoding="utf-8")
    assert "Remove me" not in updated
    assert "Child" not in updated
    assert "Keep" in updated
    assert "Tail" in updated


def test_cli_runner_tasks_remove_requires_identifier(tmp_path: Path) -> None:
    """CliRunner should reject tasks remove without selector options."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text("* TODO Keep\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "tasks",
            "remove",
            str(fixture_path),
        ],
    )

    assert result.exit_code != 0
    combined_output = clean_combined_output(result)
    assert "exactly one task selector" in combined_output


def test_cli_runner_tasks_remove_rejects_title_and_id_together(tmp_path: Path) -> None:
    """CliRunner should reject tasks remove when multiple selectors are provided."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "tasks",
            "remove",
            "--query-title",
            "Keep",
            "--query-id",
            "task-1",
            "--yes",
            str(fixture_path),
        ],
    )

    assert result.exit_code != 0
    combined_output = clean_combined_output(result)
    assert "exactly one task selector" in combined_output


def test_cli_runner_tasks_remove_supports_query_selector(tmp_path: Path) -> None:
    """CliRunner should delete using generic --query selector."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text(
        "* TODO Keep\n* TODO Remove me\n* TODO Tail\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "tasks",
            "remove",
            "--query",
            'str(.title_text) == "Remove me"',
            "--yes",
            str(fixture_path),
        ],
    )

    assert result.exit_code == 0
    assert "Deleted 1 tasks." in result.stdout
    updated = fixture_path.read_text(encoding="utf-8")
    assert "Remove me" not in updated
    assert "Keep" in updated
    assert "Tail" in updated


def test_cli_runner_tasks_update_updates_heading(tmp_path: Path) -> None:
    """CliRunner should update a task heading selected by query ID."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "tasks",
            "update",
            "--query-id",
            "task-1",
            "--title",
            "Updated",
            "--yes",
            str(fixture_path),
        ],
    )

    assert result.exit_code == 0
    assert "Updated 1 tasks." in result.stdout
    updated = fixture_path.read_text(encoding="utf-8")
    assert "* TODO Updated" in updated


def test_cli_runner_tasks_update_supports_query_selector(tmp_path: Path) -> None:
    """CliRunner should update a task selected by generic --query."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text("* TODO Keep\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "tasks",
            "update",
            "--query",
            'str(.title_text) == "Keep"',
            "--title",
            "Updated",
            "--yes",
            str(fixture_path),
        ],
    )

    assert result.exit_code == 0
    updated = fixture_path.read_text(encoding="utf-8")
    assert "* TODO Updated" in updated


def test_cli_runner_tasks_update_requires_identifier(tmp_path: Path) -> None:
    """CliRunner should reject tasks update without selector options."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text("* TODO Keep\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "tasks",
            "update",
            "--title",
            "Updated",
            str(fixture_path),
        ],
    )

    assert result.exit_code != 0
    combined_output = clean_combined_output(result)
    assert "exactly one task selector" in combined_output


def test_cli_runner_tasks_update_rejects_invalid_comment(tmp_path: Path) -> None:
    """CliRunner should reject --comment values other than true or false."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "tasks",
            "update",
            "--query-id",
            "task-1",
            "--comment",
            "maybe",
            "--yes",
            str(fixture_path),
        ],
    )

    assert result.exit_code != 0
    combined_output = clean_combined_output(result)
    assert "--comment must be either" in combined_output


def test_cli_runner_tasks_update_supports_fine_grained_repeatable_switches(tmp_path: Path) -> None:
    """CliRunner should support repeatable fine-grained update switches."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text(
        "* TODO Keep :old:\n:PROPERTIES:\n:ID: task-1\n:OLD: value\n:END:\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "tasks",
            "update",
            "--query-id",
            "task-1",
            "--add-tag",
            "new",
            "--remove-tag",
            "old",
            "--add-property",
            "A=1",
            "--remove-property",
            "OLD",
            "--yes",
            str(fixture_path),
        ],
    )

    assert result.exit_code == 0
    updated = fixture_path.read_text(encoding="utf-8")
    assert ":new:" in updated
    assert ":old:" not in updated
    assert ":A: 1" in updated
    assert ":OLD: value" not in updated


def test_cli_runner_tasks_update_moves_task_to_file(tmp_path: Path) -> None:
    """CliRunner should move selected task to destination file with --file."""
    runner = CliRunner()
    source_path = tmp_path / "source.org"
    destination_path = tmp_path / "destination.org"
    source_path.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    destination_path.write_text("* TODO Existing\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "tasks",
            "update",
            "--query-id",
            "task-1",
            "--file",
            str(destination_path),
            "--yes",
            str(source_path),
        ],
    )

    assert result.exit_code == 0
    assert "* TODO Keep" not in source_path.read_text(encoding="utf-8")
    assert "* TODO Keep" in destination_path.read_text(encoding="utf-8")


def test_cli_runner_tasks_remove_shows_confirmation_prompt_with_count(tmp_path: Path) -> None:
    """CliRunner should ask y/n confirmation with affected task count."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text("* TODO Same\n* TODO Same\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "tasks",
            "remove",
            "--query-title",
            "Same",
            "--no-color",
            str(fixture_path),
        ],
        input="n\n",
    )

    assert result.exit_code == 0
    combined_output = clean_combined_output(result)
    assert "Delete 2 tasks?" in combined_output
    updated = fixture_path.read_text(encoding="utf-8")
    assert updated.count("* TODO Same") == 2


def test_cli_runner_tasks_update_shows_confirmation_prompt_with_count(tmp_path: Path) -> None:
    """CliRunner should ask y/n confirmation with affected task count."""
    runner = CliRunner()
    fixture_path = tmp_path / "tasks.org"
    fixture_path.write_text("* TODO Same\n* TODO Same\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "tasks",
            "update",
            "--query-title",
            "Same",
            "--title",
            "Updated",
            "--no-color",
            str(fixture_path),
        ],
        input="n\n",
    )

    assert result.exit_code == 0
    combined_output = clean_combined_output(result)
    assert "Update 2 tasks?" in combined_output
    updated = fixture_path.read_text(encoding="utf-8")
    assert updated.count("* TODO Same") == 2


def test_cli_runner_allows_missing_files_when_some_exist() -> None:
    """Missing file paths should warn while command still succeeds."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())
    missing_path = str((FIXTURES_DIR / "missing.org").resolve())

    result = runner.invoke(app, ["query", ".[] | .children | length", missing_path, fixture_path])

    assert result.exit_code == 0
    assert result.stdout.strip() == "3"


def test_cli_runner_accepts_width_override() -> None:
    """Commands should accept --width values at or above 50."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())

    result = runner.invoke(app, ["query", "1", "--width", "50", fixture_path])

    assert result.exit_code == 0
    assert result.stdout.strip() == "1"


def test_cli_runner_rejects_width_below_minimum() -> None:
    """Commands should reject --width values below 50."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())

    result = runner.invoke(app, ["query", "1", "--width", "49", fixture_path])

    assert result.exit_code != 0
    combined_output = clean_combined_output(result)
    assert "Invalid value for '--width'" in combined_output
