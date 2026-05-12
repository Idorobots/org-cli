"""Tests for tasks remove command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import org_parser
import pytest
import typer

from org.commands.tasks import remove as tasks_remove


if TYPE_CHECKING:
    from pathlib import Path


def make_remove_args(files: list[str], **overrides: object) -> tasks_remove.RemoveArgs:
    """Build RemoveArgs with defaults and overrides."""
    args = tasks_remove.RemoveArgs(
        files=files,
        config=".org-cli.yaml",
        query_title=None,
        query_id=None,
        query=None,
        yes=True,
        color_flag=None,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_tasks_remove_removes_matching_title_subtree(tmp_path: Path) -> None:
    """Remove should remove a title match and all descendant headings."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n* TODO Remove me\n** TODO Child\n*** TODO Grandchild\n* TODO Tail\n",
        encoding="utf-8",
    )
    args = make_remove_args([str(source)], query_title="Remove me")

    tasks_remove.run_tasks_remove(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    titles = [node.title_text.strip() for node in list(root)]
    assert titles == ["Keep", "Tail"]


def test_run_tasks_remove_removes_matching_id_subtree(tmp_path: Path) -> None:
    """Remove should remove an ID match and all descendant headings."""
    source = tmp_path / "tasks.org"
    source.write_text(
        (
            "* TODO Keep\n"
            "* TODO Remove by id\n"
            ":PROPERTIES:\n"
            ":ID: task-123\n"
            ":END:\n"
            "** TODO Child\n"
            "* TODO Tail\n"
        ),
        encoding="utf-8",
    )
    args = make_remove_args([str(source)], query_id="task-123")

    tasks_remove.run_tasks_remove(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    titles = [node.title_text.strip() for node in list(root)]
    assert titles == ["Keep", "Tail"]


def test_run_tasks_remove_requires_at_least_one_identifier(tmp_path: Path) -> None:
    """Remove should require at least one selector option."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n", encoding="utf-8")
    args = make_remove_args([str(source)])

    with pytest.raises(typer.BadParameter, match="exactly one task selector"):
        tasks_remove.run_tasks_remove(args)


def test_run_tasks_remove_rejects_title_and_id_together(tmp_path: Path) -> None:
    """Remove should reject using both title and id selectors together."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n", encoding="utf-8")
    args = make_remove_args([str(source)], query_title="Keep", query_id="task-123")

    with pytest.raises(typer.BadParameter, match="exactly one task selector"):
        tasks_remove.run_tasks_remove(args)


def test_run_tasks_remove_deletes_all_matching_tasks(tmp_path: Path) -> None:
    """Remove should remove all tasks matched by selector."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Same\n* TODO Same\n* TODO Tail\n", encoding="utf-8")
    args = make_remove_args([str(source)], query_title="Same")

    tasks_remove.run_tasks_remove(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    titles = [node.title_text.strip() for node in list(root)]
    assert titles == ["Tail"]


def test_run_tasks_remove_selects_query_title_with_escaped_characters(tmp_path: Path) -> None:
    """Remove should support --query-title values containing quotes and backslashes."""
    source = tmp_path / "tasks.org"
    title = 'Remove "quoted" path\\name'
    source.write_text(f"* TODO Keep\n* TODO {title}\n* TODO Tail\n", encoding="utf-8")
    args = make_remove_args([str(source)], query_title=title)

    tasks_remove.run_tasks_remove(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    titles = [node.title_text.strip() for node in list(root)]
    assert titles == ["Keep", "Tail"]


def test_run_tasks_remove_errors_when_no_tasks_match(tmp_path: Path) -> None:
    """Remove should fail when no tasks satisfy selectors."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n", encoding="utf-8")
    args = make_remove_args([str(source)], query_title="Missing")

    with pytest.raises(typer.BadParameter, match="No task matches"):
        tasks_remove.run_tasks_remove(args)


def test_run_tasks_remove_removes_matching_query_subtree(tmp_path: Path) -> None:
    """Remove should remove one task selected by --query expression."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n* TODO Remove me\n** TODO Child\n* TODO Tail\n",
        encoding="utf-8",
    )
    args = make_remove_args([str(source)], query='str(.title_text) == "Remove me"')

    tasks_remove.run_tasks_remove(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    titles = [node.title_text.strip() for node in list(root)]
    assert titles == ["Keep", "Tail"]


def test_run_tasks_remove_rejects_multiple_selector_switches(tmp_path: Path) -> None:
    """Remove should require exactly one selector among title/id/query."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n", encoding="utf-8")
    args = make_remove_args(
        [str(source)],
        query_title="Keep",
        query='str(.title_text) == "Keep"',
    )

    with pytest.raises(typer.BadParameter, match="exactly one task selector"):
        tasks_remove.run_tasks_remove(args)


def test_run_tasks_remove_cancels_when_confirmation_declined(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove should leave files unchanged when confirmation is declined."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n* TODO Remove me\n", encoding="utf-8")
    args = make_remove_args([str(source)], query_title="Remove me", yes=False)

    def _decline_confirmation(*_: object, **__: object) -> bool:
        return False

    monkeypatch.setattr("rich.prompt.Confirm.ask", _decline_confirmation)

    tasks_remove.run_tasks_remove(args)

    updated = source.read_text(encoding="utf-8")
    assert "Remove me" in updated
