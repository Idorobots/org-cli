"""Tests for tasks edit command."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import org_parser
import pytest
import typer

from org.commands import editor as editor_command
from org.commands.tasks import edit as tasks_edit


if TYPE_CHECKING:
    from org_parser.document import Heading


def make_edit_args(files: list[str], **overrides: object) -> tasks_edit.EditArgs:
    """Build EditArgs with defaults and overrides."""
    args = tasks_edit.EditArgs(
        files=files,
        config=".org-cli.yaml",
        query_title=None,
        query_id="task-1",
        query=None,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_tasks_edit_replaces_subtree_by_query_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edit should persist and reload the original document content."""
    source = tmp_path / "tasks.org"
    source.write_text(
        ("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n** TODO Old child\n* TODO Tail\n"),
        encoding="utf-8",
    )

    def _fake_edit(_heading: Heading) -> editor_command.DocumentEditResult:
        source.write_text(
            (
                "* TODO Updated\n"
                ":PROPERTIES:\n"
                ":ID: task-1\n"
                ":END:\n"
                "** TODO New child\n"
                "*** TODO Grandchild\n"
                "* TODO Tail\n"
            ),
            encoding="utf-8",
        )
        return editor_command.DocumentEditResult(changed=True)

    monkeypatch.setattr(tasks_edit, "edit_heading_subtree_in_external_editor", _fake_edit)
    tasks_edit.run_tasks_edit(make_edit_args([str(source)]))

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    titles = [node.title_text.strip() for node in list(root)]
    assert titles == ["Updated", "New child", "Grandchild", "Tail"]


def test_run_tasks_edit_supports_query_title(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edit should select heading via --query-title."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n", encoding="utf-8")

    def _fake_edit(_heading: Heading) -> editor_command.DocumentEditResult:
        source.write_text("* TODO Updated\n", encoding="utf-8")
        return editor_command.DocumentEditResult(changed=True)

    monkeypatch.setattr(tasks_edit, "edit_heading_subtree_in_external_editor", _fake_edit)
    tasks_edit.run_tasks_edit(make_edit_args([str(source)], query_id=None, query_title="Keep"))

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    assert next(iter(root)).title_text.strip() == "Updated"


def test_run_tasks_edit_supports_generic_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edit should select heading via --query predicate."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n", encoding="utf-8")

    def _fake_edit(_heading: Heading) -> editor_command.DocumentEditResult:
        source.write_text("* TODO Updated\n", encoding="utf-8")
        return editor_command.DocumentEditResult(changed=True)

    monkeypatch.setattr(tasks_edit, "edit_heading_subtree_in_external_editor", _fake_edit)
    tasks_edit.run_tasks_edit(
        make_edit_args(
            [str(source)],
            query_id=None,
            query='str(.title_text) == "Keep"',
        ),
    )

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    assert next(iter(root)).title_text.strip() == "Updated"


def test_run_tasks_edit_requires_exactly_one_selector(tmp_path: Path) -> None:
    """Edit should require exactly one selector option."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n", encoding="utf-8")

    with pytest.raises(typer.BadParameter, match="exactly one task selector"):
        tasks_edit.run_tasks_edit(make_edit_args([str(source)], query_id=None, query_title=None))

    with pytest.raises(typer.BadParameter, match="exactly one task selector"):
        tasks_edit.run_tasks_edit(
            make_edit_args(
                [str(source)],
                query_title="Keep",
            ),
        )


def test_run_tasks_edit_rejects_multiple_matches(tmp_path: Path) -> None:
    """Edit should reject selectors matching more than one task."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Same\n* TODO Same\n", encoding="utf-8")

    with pytest.raises(typer.BadParameter, match="matches exactly one task"):
        tasks_edit.run_tasks_edit(make_edit_args([str(source)], query_id=None, query_title="Same"))


def test_run_tasks_edit_rejects_invalid_edited_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edit should fail when edited source is not one valid heading subtree."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")

    def _raise_invalid(_heading: Heading) -> editor_command.DocumentEditResult:
        raise typer.BadParameter(
            "Edited document content is invalid: Unexpected parse tree structure",
        )

    monkeypatch.setattr(tasks_edit, "edit_heading_subtree_in_external_editor", _raise_invalid)
    with pytest.raises(typer.BadParameter, match="Edited document content is invalid"):
        tasks_edit.run_tasks_edit(make_edit_args([str(source)]))


def test_run_tasks_edit_requires_editor_environment_variable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edit should error when $EDITOR is missing."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")

    monkeypatch.delenv("EDITOR", raising=False)
    with pytest.raises(typer.BadParameter, match=r"\$EDITOR is not defined"):
        tasks_edit.run_tasks_edit(make_edit_args([str(source)]))


def test_run_tasks_edit_errors_on_non_zero_editor_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edit should report a clear error when line-open fallback is declined."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")

    prompts: list[str] = []

    def _confirm(prompt: str) -> bool:
        prompts.append(prompt)
        return False

    monkeypatch.setenv("EDITOR", "sh -c 'exit 7'")
    monkeypatch.setattr(editor_command, "_confirm_temporary_file_edit", _confirm)

    with pytest.raises(typer.BadParameter, match="Editor failed to open"):
        tasks_edit.run_tasks_edit(make_edit_args([str(source)]))

    assert prompts == [
        "Opening the original file at the task line failed. Edit a temporary copy instead?",
    ]


def test_run_tasks_edit_skips_save_when_content_is_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Edit should not save when external editor returns unchanged subtree content."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")
    original_text = source.read_text(encoding="utf-8")

    def _fake_no_change(_heading: Heading) -> editor_command.DocumentEditResult:
        return editor_command.DocumentEditResult(changed=False)

    monkeypatch.setattr(tasks_edit, "edit_heading_subtree_in_external_editor", _fake_no_change)

    tasks_edit.run_tasks_edit(make_edit_args([str(source)]))

    assert capsys.readouterr().out.strip() == "No changes."
    assert source.read_text(encoding="utf-8") == original_text


def test_edit_heading_subtree_opens_original_file_at_task_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Helper should prefer editing the original file at the task line."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")
    root = org_parser.load(str(source))
    heading = root.heading_by_id("task-1")
    assert heading is not None

    seen_line: int | None = None

    def _edit_file(filename: str, line: int) -> int:
        nonlocal seen_line
        seen_line = line
        Path(filename).write_text(
            "* TODO Updated\n:PROPERTIES:\n:ID: task-1\n:END:\n",
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr(editor_command, "_run_editor_at_line", _edit_file)

    result = editor_command.edit_heading_subtree_in_external_editor(heading)

    assert seen_line == heading.line
    assert result.changed is True
    updated_root = org_parser.load(str(source))
    updated_heading = updated_root.heading_by_id("task-1")
    assert updated_heading is not None
    assert updated_heading.title_text.strip() == "Updated"


def test_edit_heading_subtree_prompts_for_temp_file_when_document_has_no_filename(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Helper should prompt before using temp-file editing without a backing file."""
    root = org_parser.loads("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n")
    heading = root.heading_by_id("task-1")
    assert heading is not None

    prompts: list[str] = []

    def _confirm(prompt: str) -> bool:
        prompts.append(prompt)
        return True

    monkeypatch.setattr(editor_command, "_confirm_temporary_file_edit", _confirm)
    monkeypatch.setattr(
        editor_command,
        "edit_text_in_external_editor",
        lambda _text: "* TODO Updated\n:PROPERTIES:\n:ID: task-1\n:END:\n",
    )

    result = editor_command.edit_heading_subtree_in_external_editor(heading)

    assert prompts == ["This task is not associated with a file. Edit a temporary copy instead?"]
    assert result.changed is True
    assert heading.title_text.strip() == "Keep"


def test_edit_heading_subtree_falls_back_to_temp_file_after_line_open_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Helper should prompt and write back edited temp-file content after line-open failure."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")
    root = org_parser.load(str(source))
    heading = root.heading_by_id("task-1")
    assert heading is not None

    prompts: list[str] = []

    def _confirm(prompt: str) -> bool:
        prompts.append(prompt)
        return True

    monkeypatch.setattr(editor_command, "_run_editor_at_line", lambda _filename, _line: 7)
    monkeypatch.setattr(
        editor_command,
        "_confirm_temporary_file_edit",
        _confirm,
    )
    monkeypatch.setattr(
        editor_command,
        "edit_text_in_external_editor",
        lambda _text: "* TODO Updated\n:PROPERTIES:\n:ID: task-1\n:END:\n",
    )

    result = editor_command.edit_heading_subtree_in_external_editor(heading)

    assert prompts == [
        "Opening the original file at the task line failed. Edit a temporary copy instead?",
    ]
    assert result.changed is True
    assert source.read_text(encoding="utf-8").startswith("* TODO Updated\n")


def test_edit_heading_subtree_rejects_invalid_full_document_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Helper should validate the reloaded full document after editing."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")
    root = org_parser.load(str(source))
    heading = root.heading_by_id("task-1")
    assert heading is not None

    monkeypatch.setattr(editor_command, "_run_editor_at_line", lambda _filename, _line: 7)
    monkeypatch.setattr(editor_command, "_confirm_temporary_file_edit", lambda _prompt: True)
    monkeypatch.setattr(editor_command, "edit_text_in_external_editor", lambda _text: "***")
    monkeypatch.setattr(
        org_parser,
        "loads",
        lambda _text: (_ for _ in ()).throw(ValueError("boom")),
    )

    with pytest.raises(typer.BadParameter, match="Edited document content is invalid"):
        editor_command.edit_heading_subtree_in_external_editor(heading)
