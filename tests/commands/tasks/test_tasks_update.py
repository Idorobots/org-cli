"""Tests for tasks update command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import org_parser
import pytest
import typer
from org_parser.document import Heading

from org.commands.tasks import update as tasks_update


if TYPE_CHECKING:
    from pathlib import Path


def make_update_args(files: list[str], **overrides: object) -> tasks_update.UpdateArgs:
    """Build UpdateArgs with defaults and overrides."""
    args = tasks_update.UpdateArgs(
        files=files,
        config=".org-cli.json",
        query_title=None,
        query_id="task-1",
        level=None,
        todo=None,
        priority=None,
        comment=None,
        title=None,
        id_value=None,
        counter=None,
        deadline=None,
        scheduled=None,
        closed=None,
        category=None,
        body=None,
        parent=None,
        tags=None,
        properties=None,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_tasks_update_updates_title_by_id(tmp_path: Path) -> None:
    """Update should change heading title selected by --query-id."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")
    args = make_update_args([str(source)], title="Updated title")

    tasks_update.run_tasks_update(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = next(iter(root))
    assert node.title_text.strip() == "Updated title"


def test_run_tasks_update_updates_todo_and_closed_by_title(tmp_path: Path) -> None:
    """Update should support --query-title selector and planning updates."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Foo\n", encoding="utf-8")
    args = make_update_args(
        [str(source)],
        query_id=None,
        query_title="Foo",
        todo="DONE",
        closed="<2026-04-13>",
    )

    tasks_update.run_tasks_update(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = next(iter(root))
    assert node.todo == "DONE"
    assert str(node.closed) == "<2026-04-13>"


def test_run_tasks_update_requires_exactly_one_identifier(tmp_path: Path) -> None:
    """Update should require exactly one selector option."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n", encoding="utf-8")

    with pytest.raises(typer.BadParameter, match="exactly one task identifier"):
        tasks_update.run_tasks_update(
            make_update_args([str(source)], query_id=None, query_title=None),
        )

    with pytest.raises(typer.BadParameter, match="exactly one task identifier"):
        tasks_update.run_tasks_update(
            make_update_args([str(source)], query_id="task-1", query_title="Keep"),
        )


def test_run_tasks_update_errors_when_multiple_tasks_match(tmp_path: Path) -> None:
    """Update should fail when selector matches multiple tasks."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Same\n* TODO Same\n", encoding="utf-8")
    args = make_update_args([str(source)], query_id=None, query_title="Same", title="Updated")

    with pytest.raises(typer.BadParameter, match="multiple tasks match"):
        tasks_update.run_tasks_update(args)


def test_run_tasks_update_clears_supported_fields_with_empty_string(tmp_path: Path) -> None:
    """Empty-string options should clear clearable task fields."""
    source = tmp_path / "tasks.org"
    source.write_text(
        (
            "* TODO [#A] COMMENT Keep [1/2] :x:y:\n"
            "SCHEDULED: <2026-01-01> DEADLINE: <2026-01-02> CLOSED: <2026-01-03>\n"
            ":PROPERTIES:\n"
            ":ID: task-1\n"
            ":CATEGORY: Cat\n"
            ":K: V\n"
            ":END:\n"
            "Body line\n"
        ),
        encoding="utf-8",
    )
    args = make_update_args(
        [str(source)],
        todo="",
        priority="",
        title="",
        id_value="",
        counter="",
        deadline="",
        scheduled="",
        closed="",
        category="",
        tags="",
        properties="",
    )

    tasks_update.run_tasks_update(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = next(iter(root))
    assert node.todo is None
    assert node.priority is None
    assert node.title_text == ""
    assert node.id is None
    assert node.counter is None
    assert node.deadline is None
    assert node.scheduled is None
    assert node.closed is None
    assert node.category is None
    assert node.tags == []
    assert dict(node.properties) == {}


def test_run_tasks_update_rejects_invalid_comment_value(tmp_path: Path) -> None:
    """Update should reject comment values other than true/false."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")
    args = make_update_args([str(source)], comment="yes")

    with pytest.raises(typer.BadParameter, match="--comment must be either"):
        tasks_update.run_tasks_update(args)


def test_run_tasks_update_moves_to_parent_with_explicit_consistent_level(tmp_path: Path) -> None:
    """Update should allow explicit level when it is valid for target parent."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Parent\n** TODO Child\n*** TODO Grandchild\n* TODO Other\n",
        encoding="utf-8",
    )
    args = make_update_args(
        [str(source)],
        query_id=None,
        query_title="Child",
        parent="Other",
        level=3,
    )

    tasks_update.run_tasks_update(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    nodes = list(root)
    child = next(node for node in nodes if node.title_text.strip() == "Child")
    grandchild = next(node for node in nodes if node.title_text.strip() == "Grandchild")
    assert isinstance(child.parent, Heading)
    assert child.parent.title_text.strip() == "Other"
    assert child.level == 3
    assert grandchild.level == 4


def test_run_tasks_update_moves_to_top_level_when_parent_is_empty_string(tmp_path: Path) -> None:
    """Update should move heading to document root when --parent is empty."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n** TODO Child\n", encoding="utf-8")
    args = make_update_args([str(source)], query_id=None, query_title="Child", parent="")

    tasks_update.run_tasks_update(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    nodes = list(root)
    child = next(node for node in nodes if node.title_text.strip() == "Child")
    assert child.level == 1
    assert child.parent is root


def test_run_tasks_update_allows_explicit_top_level_level_above_one(tmp_path: Path) -> None:
    """Update should allow explicit level updates for top-level headings above one."""
    source = tmp_path / "tasks.org"
    source.write_text("** TODO Task\n", encoding="utf-8")
    args = make_update_args([str(source)], query_id=None, query_title="Task", level=3)

    tasks_update.run_tasks_update(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    task = next(iter(root))
    assert task.level == 3
    assert task.parent is root


def test_run_tasks_update_rejects_parent_descendant_loop(tmp_path: Path) -> None:
    """Update should reject moving a heading under one of its descendants."""
    source = tmp_path / "tasks.org"
    source.write_text("* A\n** B\n*** C\n", encoding="utf-8")
    args = make_update_args([str(source)], query_id=None, query_title="A", parent="C")

    with pytest.raises(typer.BadParameter, match="descendant"):
        tasks_update.run_tasks_update(args)


def test_run_tasks_update_applies_json_properties_object(tmp_path: Path) -> None:
    """Update should replace heading properties from JSON object."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")
    args = make_update_args([str(source)], properties='{"A":"1","B":"two"}')

    tasks_update.run_tasks_update(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = next(iter(root))
    assert dict(node.properties) == {"A": "1", "B": "two"}


def test_run_tasks_update_rejects_non_object_properties_json(tmp_path: Path) -> None:
    """Update should reject --properties values that are not JSON objects."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")
    args = make_update_args([str(source)], properties='["x"]')

    with pytest.raises(typer.BadParameter, match="JSON object"):
        tasks_update.run_tasks_update(args)
