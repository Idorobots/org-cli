"""Tests for tasks edit command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import org_parser
import pytest
import typer
from org_parser.document import Heading

from org.commands import editor as editor_command
from org.commands.tasks import edit as tasks_edit


if TYPE_CHECKING:
    from pathlib import Path


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


def _replace_heading_with_source(heading: Heading, source: str) -> Heading:
    """Replace selected heading with parsed source and return replacement."""
    updated_heading = Heading.from_source(source)
    parent = heading.parent
    assert parent is not None
    children = list(parent.children)
    for index, child in enumerate(children):
        if child is heading:
            children[index] = updated_heading
            parent.children = children
            return updated_heading
    raise AssertionError("selected heading not found in parent children")


def test_run_tasks_edit_replaces_subtree_by_query_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edit should replace selected heading subtree content."""
    source = tmp_path / "tasks.org"
    source.write_text(
        ("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n** TODO Old child\n* TODO Tail\n"),
        encoding="utf-8",
    )

    def _fake_edit(heading: Heading) -> editor_command.HeadingEditResult:
        updated_heading = _replace_heading_with_source(
            heading,
            (
                "* TODO Updated\n"
                ":PROPERTIES:\n"
                ":ID: task-1\n"
                ":END:\n"
                "** TODO New child\n"
                "*** TODO Grandchild\n"
            ),
        )
        return editor_command.HeadingEditResult(heading=updated_heading, changed=True)

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

    def _fake_edit(heading: Heading) -> editor_command.HeadingEditResult:
        updated_heading = _replace_heading_with_source(heading, "* TODO Updated\n")
        return editor_command.HeadingEditResult(heading=updated_heading, changed=True)

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

    def _fake_edit(heading: Heading) -> editor_command.HeadingEditResult:
        updated_heading = _replace_heading_with_source(heading, "* TODO Updated\n")
        return editor_command.HeadingEditResult(heading=updated_heading, changed=True)

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

    def _raise_invalid(_: Heading) -> editor_command.HeadingEditResult:
        raise typer.BadParameter("Edited task content is invalid: Unexpected parse tree structure")

    monkeypatch.setattr(tasks_edit, "edit_heading_subtree_in_external_editor", _raise_invalid)
    with pytest.raises(typer.BadParameter, match="Edited task content is invalid"):
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
    """Edit should error when editor exits with non-zero status."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")

    monkeypatch.setenv("EDITOR", "sh -c 'exit 7'")
    with pytest.raises(typer.BadParameter, match="Editing failed"):
        tasks_edit.run_tasks_edit(make_edit_args([str(source)]))


def test_run_tasks_edit_skips_save_when_content_is_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Edit should not save when external editor returns unchanged subtree content."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")
    original_text = source.read_text(encoding="utf-8")

    def _fake_no_change(heading: Heading) -> editor_command.HeadingEditResult:
        return editor_command.HeadingEditResult(heading=heading, changed=False)

    def _fail_save(_: object) -> None:
        raise AssertionError("save_document should not be called")

    monkeypatch.setattr(tasks_edit, "edit_heading_subtree_in_external_editor", _fake_no_change)
    monkeypatch.setattr(tasks_edit, "save_document", _fail_save)

    tasks_edit.run_tasks_edit(make_edit_args([str(source)]))

    assert capsys.readouterr().out.strip() == "No changes."
    assert source.read_text(encoding="utf-8") == original_text
