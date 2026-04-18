"""Tests for tasks delete command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import org_parser
import pytest
import typer

from org.commands.tasks import delete as tasks_delete


if TYPE_CHECKING:
    from pathlib import Path


def make_delete_args(files: list[str], **overrides: object) -> tasks_delete.DeleteArgs:
    """Build DeleteArgs with defaults and overrides."""
    args = tasks_delete.DeleteArgs(
        files=files,
        config=".org-cli.json",
        query_title=None,
        query_id=None,
        query=None,
        yes=True,
        color_flag=None,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_tasks_delete_removes_matching_title_subtree(tmp_path: Path) -> None:
    """Delete should remove a title match and all descendant headings."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n* TODO Remove me\n** TODO Child\n*** TODO Grandchild\n* TODO Tail\n",
        encoding="utf-8",
    )
    args = make_delete_args([str(source)], query_title="Remove me")

    tasks_delete.run_tasks_delete(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    titles = [node.title_text.strip() for node in list(root)]
    assert titles == ["Keep", "Tail"]


def test_run_tasks_delete_removes_matching_id_subtree(tmp_path: Path) -> None:
    """Delete should remove an ID match and all descendant headings."""
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
    args = make_delete_args([str(source)], query_id="task-123")

    tasks_delete.run_tasks_delete(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    titles = [node.title_text.strip() for node in list(root)]
    assert titles == ["Keep", "Tail"]


def test_run_tasks_delete_requires_at_least_one_identifier(tmp_path: Path) -> None:
    """Delete should require at least one selector option."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n", encoding="utf-8")
    args = make_delete_args([str(source)])

    with pytest.raises(typer.BadParameter, match="exactly one task selector"):
        tasks_delete.run_tasks_delete(args)


def test_run_tasks_delete_rejects_title_and_id_together(tmp_path: Path) -> None:
    """Delete should reject using both title and id selectors together."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n", encoding="utf-8")
    args = make_delete_args([str(source)], query_title="Keep", query_id="task-123")

    with pytest.raises(typer.BadParameter, match="exactly one task selector"):
        tasks_delete.run_tasks_delete(args)


def test_run_tasks_delete_deletes_all_matching_tasks(tmp_path: Path) -> None:
    """Delete should remove all tasks matched by selector."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Same\n* TODO Same\n* TODO Tail\n", encoding="utf-8")
    args = make_delete_args([str(source)], query_title="Same")

    tasks_delete.run_tasks_delete(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    titles = [node.title_text.strip() for node in list(root)]
    assert titles == ["Tail"]


def test_run_tasks_delete_errors_when_no_tasks_match(tmp_path: Path) -> None:
    """Delete should fail when no tasks satisfy selectors."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n", encoding="utf-8")
    args = make_delete_args([str(source)], query_title="Missing")

    with pytest.raises(typer.BadParameter, match="No task matches"):
        tasks_delete.run_tasks_delete(args)


def test_run_tasks_delete_removes_matching_query_subtree(tmp_path: Path) -> None:
    """Delete should remove one task selected by --query expression."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n* TODO Remove me\n** TODO Child\n* TODO Tail\n",
        encoding="utf-8",
    )
    args = make_delete_args([str(source)], query='str(.title_text) == "Remove me"')

    tasks_delete.run_tasks_delete(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    titles = [node.title_text.strip() for node in list(root)]
    assert titles == ["Keep", "Tail"]


def test_run_tasks_delete_rejects_multiple_selector_switches(tmp_path: Path) -> None:
    """Delete should require exactly one selector among title/id/query."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n", encoding="utf-8")
    args = make_delete_args(
        [str(source)],
        query_title="Keep",
        query='str(.title_text) == "Keep"',
    )

    with pytest.raises(typer.BadParameter, match="exactly one task selector"):
        tasks_delete.run_tasks_delete(args)


def test_run_tasks_delete_cancels_when_confirmation_declined(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delete should leave files unchanged when confirmation is declined."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n* TODO Remove me\n", encoding="utf-8")
    args = make_delete_args([str(source)], query_title="Remove me", yes=False)

    def _decline_confirmation(*_: object, **__: object) -> bool:
        return False

    monkeypatch.setattr("rich.prompt.Confirm.ask", _decline_confirmation)

    tasks_delete.run_tasks_delete(args)

    updated = source.read_text(encoding="utf-8")
    assert "Remove me" in updated
