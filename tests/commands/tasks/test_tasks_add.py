"""Tests for tasks add command."""

from __future__ import annotations

import io
import uuid
from typing import TYPE_CHECKING

import org_parser
import pytest
import typer

from org.commands.tasks import add as tasks_add


if TYPE_CHECKING:
    from pathlib import Path


def make_add_args(files: list[str], **overrides: object) -> tasks_add.AddArgs:
    """Build AddArgs with defaults and overrides."""
    args = tasks_add.AddArgs(
        files=files,
        config=".org-cli.json",
        level=None,
        todo="TODO",
        priority=None,
        comment=None,
        title="New task",
        counter=None,
        tags=None,
        heading=None,
        deadline=None,
        scheduled=None,
        closed=None,
        properties=None,
        category=None,
        id_value=None,
        body=None,
        parent=None,
        file=None,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_tasks_add_appends_top_level_heading_to_first_resolved_file(tmp_path: Path) -> None:
    """Create should append top-level heading in first resolved input file."""
    first = tmp_path / "first.org"
    second = tmp_path / "second.org"
    first.write_text("* TODO Existing\n", encoding="utf-8")
    second.write_text("* TODO Existing in second\n", encoding="utf-8")

    args = make_add_args(
        [str(first), str(second)],
        title="Update docs",
        tags="Docs",
        body="Body text",
    )

    tasks_add.run_tasks_add(args)

    first_root = org_parser.loads(first.read_text(encoding="utf-8"))
    first_nodes = list(first_root)
    assert len(first_nodes) == 2
    assert first_nodes[-1].level == 1
    assert first_nodes[-1].title_text.strip() == "Update docs"
    assert first_nodes[-1].tags == ["Docs"]

    second_root = org_parser.loads(second.read_text(encoding="utf-8"))
    assert len(list(second_root)) == 1


def test_run_tasks_add_uses_file_override_when_provided(tmp_path: Path) -> None:
    """Create should update --file target instead of default resolved file."""
    first = tmp_path / "first.org"
    second = tmp_path / "second.org"
    first.write_text("* TODO Existing\n", encoding="utf-8")
    second.write_text("* TODO Existing in second\n", encoding="utf-8")

    args = make_add_args(
        [str(first), str(second)],
        title="Target second",
        file=str(second),
    )

    tasks_add.run_tasks_add(args)

    assert "Target second" not in first.read_text(encoding="utf-8")
    assert "* TODO Target second" in second.read_text(encoding="utf-8")


def test_run_tasks_add_inserts_child_of_parent_title_with_default_level(tmp_path: Path) -> None:
    """Create should insert child under parent title with parent+1 level by default."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Parent\n** TODO Existing child\n* TODO Sibling\n",
        encoding="utf-8",
    )

    args = make_add_args([str(source)], title="Added child", parent="Parent")

    tasks_add.run_tasks_add(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    nodes = list(root)
    titles = [node.title_text.strip() for node in nodes]
    assert titles == ["Parent", "Existing child", "Added child", "Sibling"]

    added_child = next(node for node in nodes if node.title_text.strip() == "Added child")
    assert added_child.level == 2


def test_run_tasks_add_inserts_child_of_parent_id(tmp_path: Path) -> None:
    """Create should resolve --parent by heading ID before matching titles."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Parent\n:PROPERTIES:\n:ID: parent-1\n:END:\n\n* TODO Sibling\n",
        encoding="utf-8",
    )

    args = make_add_args([str(source)], title="Added child", parent="parent-1")

    tasks_add.run_tasks_add(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    nodes = list(root)
    titles = [node.title_text.strip() for node in nodes]
    assert titles == ["Parent", "Added child", "Sibling"]


def test_run_tasks_add_errors_when_parent_not_found(tmp_path: Path) -> None:
    """Create should report an error when parent selector has no matches."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_add_args([str(source)], title="Child", parent="missing")

    with pytest.raises(typer.BadParameter, match="was not found"):
        tasks_add.run_tasks_add(args)


def test_run_tasks_add_errors_when_parent_is_ambiguous(tmp_path: Path) -> None:
    """Create should report an error when parent selector matches multiple headings."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Same\n* TODO Same\n", encoding="utf-8")
    args = make_add_args([str(source)], title="Child", parent="Same")

    with pytest.raises(typer.BadParameter, match="ambiguous"):
        tasks_add.run_tasks_add(args)


def test_run_tasks_add_rejects_heading_with_mutually_exclusive_switches(tmp_path: Path) -> None:
    """Create should reject --heading combined with structured heading switches."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_add_args([str(source)], heading="* TODO One", title="Two")

    with pytest.raises(typer.BadParameter, match="--heading cannot be combined"):
        tasks_add.run_tasks_add(args)


def test_run_tasks_add_reads_task_source_from_stdin_when_heading_components_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create should read and parse task source from stdin when heading source is omitted."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_add_args(
        [str(source)],
        heading=None,
        todo=None,
        comment=None,
        title=None,
    )

    monkeypatch.setattr("sys.stdin", io.StringIO("* TODO From stdin\n"))

    tasks_add.run_tasks_add(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    created = list(root)[-1]
    assert created.todo == "TODO"
    assert created.title_text.strip() == "From stdin"


def test_run_tasks_add_applies_edits_to_stdin_task_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create should apply non-heading-source switches as edits on stdin task input."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_add_args(
        [str(source)],
        heading=None,
        todo=None,
        comment=None,
        title=None,
        level=2,
        priority="A",
        tags="new,docs",
        scheduled="<2026-04-20>",
        deadline="<2026-04-21>",
        closed="<2026-04-22>",
        properties='{"A":"1"}',
        category="Work",
        id_value="task-99",
        body="Updated body",
    )

    monkeypatch.setattr("sys.stdin", io.StringIO("* TODO Base :old:\n** TODO Child\n"))

    tasks_add.run_tasks_add(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    nodes = list(root)
    created = next(node for node in nodes if node.title_text.strip() == "Base")
    child = next(node for node in nodes if node.title_text.strip() == "Child")
    assert created.level == 2
    assert child.level == 3
    assert created.priority == "A"
    assert created.tags == ["new", "docs"]
    assert str(created.scheduled) == "<2026-04-20>"
    assert str(created.deadline) == "<2026-04-21>"
    assert str(created.closed) == "<2026-04-22>"
    assert created.id == "task-99"
    assert created.category == "Work"
    assert created.properties["A"] == "1"
    assert "Updated body" in source.read_text(encoding="utf-8")


def test_run_tasks_add_stdin_uses_same_parent_level_validation_as_level(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create should enforce parent-level constraints for stdin-provided heading levels."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_add_args(
        [str(source)],
        heading=None,
        todo=None,
        comment=None,
        title=None,
        parent="Parent",
    )

    monkeypatch.setattr("sys.stdin", io.StringIO("* TODO Child\n"))

    with pytest.raises(typer.BadParameter, match="--level must be greater than parent level"):
        tasks_add.run_tasks_add(args)


def test_run_tasks_add_errors_when_stdin_task_source_is_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create should report an error when heading source is omitted and stdin is empty."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_add_args(
        [str(source)],
        heading=None,
        todo=None,
        comment=None,
        title=None,
    )

    monkeypatch.setattr("sys.stdin", io.StringIO("  \n\t\n"))

    with pytest.raises(typer.BadParameter, match="Task heading is empty"):
        tasks_add.run_tasks_add(args)


def test_run_tasks_add_surfaces_invalid_template_parse_errors(tmp_path: Path) -> None:
    """Create should validate generated source with Heading.from_source."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_add_args([str(source)], title="Two", scheduled="not-a-timestamp")

    with pytest.raises(typer.BadParameter, match="Invalid task template"):
        tasks_add.run_tasks_add(args)


def test_run_tasks_add_allows_heading_without_title_when_metadata_is_set(tmp_path: Path) -> None:
    """Create should support metadata-only heading lines without requiring --title."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_add_args([str(source)], title=None, todo="TODO", priority="A", comment="true")

    tasks_add.run_tasks_add(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = list(root)[-1]
    assert node.todo == "TODO"
    assert node.priority == "A"
    assert node.is_comment
    assert node.title_text == ""


def test_run_tasks_add_rejects_invalid_comment_value(tmp_path: Path) -> None:
    """Create should reject comment values other than true/false."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_add_args([str(source)], todo=None, title=None, comment="yes")

    with pytest.raises(typer.BadParameter, match="--comment must be either"):
        tasks_add.run_tasks_add(args)


def test_run_tasks_add_applies_json_properties_and_generates_default_id(tmp_path: Path) -> None:
    """Create should parse --properties JSON and generate ID when missing."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_add_args(
        [str(source)],
        title="Child",
        properties='{"A":"1"}',
        id_value=None,
    )

    tasks_add.run_tasks_add(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = list(root)[-1]
    assert node.properties["A"] == "1"
    generated_id = node.properties["ID"]
    assert generated_id
    uuid.UUID(str(generated_id))


def test_run_tasks_add_rejects_invalid_properties_json(tmp_path: Path) -> None:
    """Create should reject --properties values that are not JSON objects."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_add_args([str(source)], properties='["x"]')

    with pytest.raises(typer.BadParameter, match="--properties must be a JSON object"):
        tasks_add.run_tasks_add(args)
