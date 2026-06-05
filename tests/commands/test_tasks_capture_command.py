"""Tests for capture command behavior."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import org_parser
import pytest
import typer

from org import config
from org.commands.tasks import capture


if TYPE_CHECKING:
    from pathlib import Path


def _make_capture_args(
    template_name: str | None,
    *,
    file: str | None = None,
    parent: str | None = None,
    set_values: list[str] | None = None,
) -> capture.TasksCaptureArgs:
    """Build capture args for tests."""
    return capture.TasksCaptureArgs(
        template_name=template_name,
        config=".org-cli.yaml",
        file=file,
        parent=parent,
        set_values=set_values,
    )


def _set_capture_templates(templates: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Replace global capture templates and return previous value."""
    previous = dict(config.CONFIG_CAPTURE_TEMPLATES)
    config.CONFIG_CAPTURE_TEMPLATES.clear()
    config.CONFIG_CAPTURE_TEMPLATES.update(templates)
    return previous


def _restore_capture_templates(previous: dict[str, dict[str, str]]) -> None:
    """Restore global capture templates from previous value."""
    config.CONFIG_CAPTURE_TEMPLATES.clear()
    config.CONFIG_CAPTURE_TEMPLATES.update(previous)


def test_run_capture_errors_when_no_templates_configured() -> None:
    """Capture should fail with a clear error when templates are missing."""
    previous = _set_capture_templates({})
    try:
        with pytest.raises(typer.BadParameter, match="No capture templates configured"):
            capture.run_tasks_capture(_make_capture_args(template_name="quick"))
    finally:
        _restore_capture_templates(previous)


def test_run_capture_errors_for_unknown_template_name() -> None:
    """Capture should list valid names when an unknown template is requested."""
    previous = _set_capture_templates(
        {
            "alpha": {"file": "tasks.org", "content": "* TODO {{title}}"},
            "beta": {"file": "tasks.org", "content": "* TODO {{title}}"},
        },
    )
    try:
        with pytest.raises(typer.BadParameter, match="Valid templates: alpha, beta"):
            capture.capture_task(_make_capture_args(template_name="missing"))
    finally:
        _restore_capture_templates(previous)


def test_capture_task_errors_when_template_omitted_in_noninteractive_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-interactive capture should require an explicit template name."""
    previous = _set_capture_templates(
        {"quick": {"file": "tasks.org", "content": "* TODO Static"}},
    )
    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.command._is_interactive_terminal",
            lambda: False,
        )
        with pytest.raises(typer.BadParameter, match="template name is required"):
            capture.capture_task(_make_capture_args(template_name=None))
    finally:
        _restore_capture_templates(previous)


def test_capture_task_errors_when_placeholders_missing_in_noninteractive_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-interactive capture should fail on unresolved placeholders."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {"quick": {"file": str(target), "content": "* TODO {{title}} @{{owner}}"}},
    )
    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.command._is_interactive_terminal",
            lambda: False,
        )
        with pytest.raises(
            typer.BadParameter,
            match="Missing placeholder values for: title, owner",
        ):
            capture.capture_task(_make_capture_args(template_name="quick"))
    finally:
        _restore_capture_templates(previous)


def test_capture_task_uses_interactive_template_selection_and_form(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interactive capture should use the selection app and form app helpers."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {
            "alpha": {"file": str(target), "content": "* TODO Alpha"},
            "beta": {"file": str(target), "content": "* TODO {{title}} @{{owner}}"},
        },
    )
    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.command._is_interactive_terminal",
            lambda: True,
        )
        monkeypatch.setattr(
            "org.commands.tasks.capture.command.run_template_selection_app",
            lambda _names: "beta",
        )
        monkeypatch.setattr(
            "org.commands.tasks.capture.command.run_capture_form_app",
            lambda plan: {**plan.values, "title": "Write docs", "owner": "Jane"},
        )

        result = capture.capture_task(_make_capture_args(template_name=None))
    finally:
        _restore_capture_templates(previous)

    assert result.template_name == "beta"
    assert result.interactive_used is True
    assert "* TODO Write docs @Jane" in target.read_text(encoding="utf-8")


def test_capture_task_uses_form_app_for_unresolved_placeholders(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interactive capture should use the form app when placeholders are unresolved."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {"quick": {"file": str(target), "content": "* TODO {{title}}"}},
    )
    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.command._is_interactive_terminal",
            lambda: True,
        )
        monkeypatch.setattr(
            "org.commands.tasks.capture.command.run_capture_form_app",
            lambda plan: {**plan.values, "title": "From form"},
        )

        result = capture.capture_task(_make_capture_args(template_name="quick"))
    finally:
        _restore_capture_templates(previous)

    assert result.interactive_used is True
    assert result.heading.title_text == "From form"


def test_capture_task_returns_created_heading_metadata_noninteractive(tmp_path: Path) -> None:
    """Non-interactive capture should return created heading metadata."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {"quick": {"file": str(target), "content": "* TODO {{title}}"}},
    )
    try:
        result = capture.capture_task(
            _make_capture_args(template_name="quick", set_values=["title=Write docs"]),
        )
    finally:
        _restore_capture_templates(previous)

    assert result.template_name == "quick"
    assert result.document.filename == str(target)
    assert result.heading.title_text == "Write docs"
    assert result.interactive_used is False


def test_run_tasks_capture_noninteractive_prints_created_task_id(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Non-interactive capture should print new task ID when available."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {
            "quick": {
                "file": str(target),
                "content": "* TODO {{title}}\n:PROPERTIES:\n:ID: task-42\n:END:",
            },
        },
    )
    try:
        capture.run_tasks_capture(_make_capture_args("quick", set_values=["title=From set"]))
    finally:
        _restore_capture_templates(previous)

    assert capsys.readouterr().out.strip() == "task-42"


def test_run_tasks_capture_interactive_does_not_print_identifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Interactive capture should not print identifier output."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {"quick": {"file": str(target), "content": "* TODO {{title}}"}},
    )
    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.command._is_interactive_terminal",
            lambda: True,
        )
        monkeypatch.setattr(
            "org.commands.tasks.capture.command.run_capture_form_app",
            lambda plan: {**plan.values, "title": "Write docs"},
        )
        capture.run_tasks_capture(_make_capture_args(template_name="quick"))
    finally:
        _restore_capture_templates(previous)

    assert capsys.readouterr().out.strip() == ""


def test_render_template_preview_tracks_placeholder_spans() -> None:
    """Template preview should map placeholders to rendered output positions."""
    preview = capture._render_template_preview(
        "* TODO {{title}} [{{title}}] {{owner}}",
        {"title": "Write docs"},
    )

    assert preview.text == "* TODO Write docs [Write docs] {{owner}}"
    assert preview.placeholder_spans["title"] == [(7, 17), (19, 29)]
    assert preview.placeholder_spans["owner"] == [(31, 40)]


def test_prepare_capture_plan_uses_document_and_parent_placeholders(
    tmp_path: Path,
) -> None:
    """Prepared capture plan should resolve document and parent placeholder values."""
    target = tmp_path / "tasks.org"
    target.write_text(
        "#+TITLE: Project File\n"
        "#+AUTHOR: Jane Doe\n"
        "#+DESCRIPTION: Sprint tasks\n"
        "#+CATEGORY: Work\n"
        "* TODO Parent\n:PROPERTIES:\n:ID: parent-1\n:CATEGORY: Projects\n:END:\n",
        encoding="utf-8",
    )
    previous = _set_capture_templates(
        {
            "child": {
                "file": str(target),
                "parent": '.id == "parent-1"',
                "content": (
                    "** TODO doc={{document_title}} cat={{document_category}} "
                    "parent={{parent_title}} parent_id={{parent_id}}"
                ),
            },
        },
    )
    try:
        plan = capture.prepare_capture_plan(_make_capture_args("child"), "child")
    finally:
        _restore_capture_templates(previous)

    assert plan.values["document_title"] == "Project File"
    assert plan.values["document_category"] == "Work"
    assert plan.values["parent_title"] == "Parent"
    assert plan.values["parent_id"] == "parent-1"
    assert plan.unresolved_placeholders == []


def test_run_capture_inserts_under_parent_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture should support parent selection with query language expression."""
    target = tmp_path / "tasks.org"
    target.write_text(
        "* TODO Project\n:PROPERTIES:\n:ID: project-1\n:END:\n\n* TODO Other\n",
        encoding="utf-8",
    )
    previous = _set_capture_templates(
        {
            "child": {
                "file": str(target),
                "content": "** TODO {{title}}",
                "parent": '.id == "project-1"',
            },
        },
    )
    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.command._is_interactive_terminal",
            lambda: True,
        )
        monkeypatch.setattr(
            "org.commands.tasks.capture.command.run_capture_form_app",
            lambda plan: {**plan.values, "title": "Child task"},
        )
        capture.run_tasks_capture(_make_capture_args(template_name="child"))
    finally:
        _restore_capture_templates(previous)

    root = org_parser.loads(target.read_text(encoding="utf-8"))
    titles = [node.title_text.strip() for node in list(root)]
    assert titles == ["Project", "Child task", "Other"]


def test_run_capture_cli_file_override_takes_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture should use CLI --file over template file."""
    configured_target = tmp_path / "configured.org"
    override_target = tmp_path / "override.org"
    configured_target.write_text("* TODO Configured\n", encoding="utf-8")
    override_target.write_text("* TODO Override\n", encoding="utf-8")

    previous = _set_capture_templates(
        {
            "quick": {
                "file": str(configured_target),
                "content": "* TODO {{title}}",
            },
        },
    )
    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.command._is_interactive_terminal",
            lambda: True,
        )
        monkeypatch.setattr(
            "org.commands.tasks.capture.command.run_capture_form_app",
            lambda plan: {**plan.values, "title": "From override"},
        )
        capture.run_tasks_capture(_make_capture_args("quick", file=str(override_target)))
    finally:
        _restore_capture_templates(previous)

    assert "From override" not in configured_target.read_text(encoding="utf-8")
    assert "From override" in override_target.read_text(encoding="utf-8")


def test_run_capture_set_values_reject_invalid_format(tmp_path: Path) -> None:
    """Capture should reject --set entries that are not KEY=VALUE."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {
            "quick": {
                "file": str(target),
                "content": "* TODO {{title}}",
            },
        },
    )
    try:
        with pytest.raises(typer.BadParameter, match="--set must be KEY=VALUE"):
            capture.run_tasks_capture(_make_capture_args("quick", set_values=["title"]))
    finally:
        _restore_capture_templates(previous)


def test_run_capture_static_placeholders_use_org_timestamp_format(tmp_path: Path) -> None:
    """Capture should render {{today}} and {{now}} as Org-mode timestamps."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {
            "quick": {
                "file": str(target),
                "content": "* TODO today={{today}} now={{now}}",
            },
        },
    )
    try:
        capture.run_tasks_capture(_make_capture_args("quick"))
    finally:
        _restore_capture_templates(previous)

    updated = target.read_text(encoding="utf-8")
    assert re.search(r"today=<\d{4}-\d{2}-\d{2} (Mon|Tue|Wed|Thu|Fri|Sat|Sun)>", updated)
    assert re.search(
        r"now=<\d{4}-\d{2}-\d{2} (Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{2}:\d{2}>",
        updated,
    )


def test_run_capture_static_id_placeholder_uses_next_heading_number(tmp_path: Path) -> None:
    """Capture should render {{id}} as next heading count value."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO One\n* TODO Two\n", encoding="utf-8")
    previous = _set_capture_templates(
        {
            "quick": {
                "file": str(target),
                "content": "* TODO Added\n:PROPERTIES:\n:ID: {{id}}\n:END:",
            },
        },
    )
    try:
        capture.run_tasks_capture(_make_capture_args("quick"))
    finally:
        _restore_capture_templates(previous)

    assert ":ID: 3" in target.read_text(encoding="utf-8")
