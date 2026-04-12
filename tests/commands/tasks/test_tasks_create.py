"""Tests for tasks create command."""

from __future__ import annotations

from pathlib import Path

import org_parser
import pytest
import typer

from org.commands.tasks import create as tasks_create


def make_create_args(files: list[str], **overrides: object) -> tasks_create.CreateArgs:
    """Build CreateArgs with defaults and overrides."""
    args = tasks_create.CreateArgs(
        files=files,
        config=".org-cli.json",
        level=None,
        todo="TODO",
        priority=None,
        is_comment=False,
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


def test_run_tasks_create_appends_top_level_heading_to_first_resolved_file(tmp_path: Path) -> None:
    """Create should append top-level heading in first resolved input file."""
    first = tmp_path / "first.org"
    second = tmp_path / "second.org"
    first.write_text("* TODO Existing\n", encoding="utf-8")
    second.write_text("* TODO Existing in second\n", encoding="utf-8")

    args = make_create_args(
        [str(first), str(second)],
        title="Update docs",
        tags=["Docs"],
        body="Body text",
    )

    tasks_create.run_tasks_create(args)

    first_root = org_parser.loads(first.read_text(encoding="utf-8"))
    first_nodes = list(first_root)
    assert len(first_nodes) == 2
    assert first_nodes[-1].level == 1
    assert first_nodes[-1].title_text.strip() == "Update docs"
    assert first_nodes[-1].tags == ["Docs"]

    second_root = org_parser.loads(second.read_text(encoding="utf-8"))
    assert len(list(second_root)) == 1


def test_run_tasks_create_uses_file_override_when_provided(tmp_path: Path) -> None:
    """Create should update --file target instead of default resolved file."""
    first = tmp_path / "first.org"
    second = tmp_path / "second.org"
    first.write_text("* TODO Existing\n", encoding="utf-8")
    second.write_text("* TODO Existing in second\n", encoding="utf-8")

    args = make_create_args(
        [str(first), str(second)],
        title="Target second",
        file=str(second),
    )

    tasks_create.run_tasks_create(args)

    assert "Target second" not in first.read_text(encoding="utf-8")
    assert "* TODO Target second" in second.read_text(encoding="utf-8")


def test_run_tasks_create_inserts_child_of_parent_title_with_default_level(tmp_path: Path) -> None:
    """Create should insert child under parent title with parent+1 level by default."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Parent\n** TODO Existing child\n* TODO Sibling\n",
        encoding="utf-8",
    )

    args = make_create_args([str(source)], title="Added child", parent="Parent")

    tasks_create.run_tasks_create(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    nodes = list(root)
    titles = [node.title_text.strip() for node in nodes]
    assert titles == ["Parent", "Existing child", "Added child", "Sibling"]

    added_child = next(node for node in nodes if node.title_text.strip() == "Added child")
    assert added_child.level == 2


def test_run_tasks_create_inserts_child_of_parent_id(tmp_path: Path) -> None:
    """Create should resolve --parent by heading ID before matching titles."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Parent\n:PROPERTIES:\n:ID: parent-1\n:END:\n\n* TODO Sibling\n",
        encoding="utf-8",
    )

    args = make_create_args([str(source)], title="Added child", parent="parent-1")

    tasks_create.run_tasks_create(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    nodes = list(root)
    titles = [node.title_text.strip() for node in nodes]
    assert titles == ["Parent", "Added child", "Sibling"]


def test_run_tasks_create_errors_when_parent_not_found(tmp_path: Path) -> None:
    """Create should report an error when parent selector has no matches."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_create_args([str(source)], title="Child", parent="missing")

    with pytest.raises(typer.BadParameter, match="was not found"):
        tasks_create.run_tasks_create(args)


def test_run_tasks_create_errors_when_parent_is_ambiguous(tmp_path: Path) -> None:
    """Create should report an error when parent selector matches multiple headings."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Same\n* TODO Same\n", encoding="utf-8")
    args = make_create_args([str(source)], title="Child", parent="Same")

    with pytest.raises(typer.BadParameter, match="ambiguous"):
        tasks_create.run_tasks_create(args)


def test_run_tasks_create_rejects_heading_with_mutually_exclusive_switches(tmp_path: Path) -> None:
    """Create should reject --heading combined with structured heading switches."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_create_args([str(source)], heading="* TODO One", title="Two")

    with pytest.raises(typer.BadParameter, match="--heading cannot be combined"):
        tasks_create.run_tasks_create(args)


def test_run_tasks_create_requires_at_least_one_heading_component(tmp_path: Path) -> None:
    """Create should require --heading or one structured heading component."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_create_args(
        [str(source)],
        heading=None,
        todo=None,
        is_comment=False,
        title=None,
    )

    with pytest.raises(typer.BadParameter, match="Task heading is empty"):
        tasks_create.run_tasks_create(args)


def test_run_tasks_create_surfaces_invalid_template_parse_errors(tmp_path: Path) -> None:
    """Create should validate generated source with Heading.from_source."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_create_args([str(source)], title="Two", scheduled="not-a-timestamp")

    with pytest.raises(typer.BadParameter, match="Invalid task template"):
        tasks_create.run_tasks_create(args)


def test_run_tasks_create_allows_heading_without_title_when_metadata_is_set(tmp_path: Path) -> None:
    """Create should support metadata-only heading lines without requiring --title."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Parent\n", encoding="utf-8")
    args = make_create_args([str(source)], title=None, todo="TODO", priority="A", is_comment=True)

    tasks_create.run_tasks_create(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = list(root)[-1]
    assert node.todo == "TODO"
    assert node.priority == "A"
    assert node.is_comment
    assert node.title_text == ""
