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
        query=None,
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
        add_clock_entry=None,
        remove_clock_entry=None,
        add_repeat=None,
        remove_repeat=None,
        add_tag=None,
        remove_tag=None,
        add_property=None,
        remove_property=None,
        file=None,
        yes=True,
        color_flag=None,
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

    with pytest.raises(typer.BadParameter, match="exactly one task selector"):
        tasks_update.run_tasks_update(
            make_update_args([str(source)], query_id=None, query_title=None),
        )

    with pytest.raises(typer.BadParameter, match="exactly one task selector"):
        tasks_update.run_tasks_update(
            make_update_args([str(source)], query_id="task-1", query_title="Keep"),
        )


def test_run_tasks_update_supports_generic_query_selector(tmp_path: Path) -> None:
    """Update should support selecting task through --query predicate."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Foo\n", encoding="utf-8")
    args = make_update_args(
        [str(source)],
        query_id=None,
        query='str(.title_text) == "Foo"',
        title="Updated",
    )

    tasks_update.run_tasks_update(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = next(iter(root))
    assert node.title_text.strip() == "Updated"


def test_run_tasks_update_rejects_query_with_other_selectors(tmp_path: Path) -> None:
    """Update should reject --query combined with query-id/title selectors."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Foo\n", encoding="utf-8")

    with pytest.raises(typer.BadParameter, match="exactly one task selector"):
        tasks_update.run_tasks_update(
            make_update_args(
                [str(source)],
                query='str(.title_text) == "Foo"',
            ),
        )


def test_run_tasks_update_cancels_when_confirmation_declined(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Update should leave files unchanged when confirmation is declined."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Foo\n", encoding="utf-8")
    args = make_update_args(
        [str(source)],
        query_id=None,
        query='str(.title_text) == "Foo"',
        title="Updated",
        yes=False,
    )

    def _decline_confirmation(*_: object, **__: object) -> bool:
        return False

    monkeypatch.setattr("rich.prompt.Confirm.ask", _decline_confirmation)

    tasks_update.run_tasks_update(args)

    updated = source.read_text(encoding="utf-8")
    assert "* TODO Foo" in updated


def test_run_tasks_update_applies_to_all_matching_tasks(tmp_path: Path) -> None:
    """Update should apply to all tasks matched by selector."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Same\n* TODO Same\n* TODO Tail\n", encoding="utf-8")
    args = make_update_args([str(source)], query_id=None, query_title="Same", title="Updated")

    tasks_update.run_tasks_update(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    titles = [node.title_text.strip() for node in list(root)]
    assert titles == ["Updated", "Updated", "Tail"]


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


def test_run_tasks_update_moves_heading_to_another_file(tmp_path: Path) -> None:
    """Update should move task heading from source file to --file destination."""
    source = tmp_path / "source.org"
    destination = tmp_path / "destination.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    destination.write_text("* TODO Existing\n", encoding="utf-8")
    args = make_update_args([str(source), str(destination)], file=str(destination))

    tasks_update.run_tasks_update(args)

    source_root = org_parser.loads(source.read_text(encoding="utf-8"))
    destination_root = org_parser.loads(destination.read_text(encoding="utf-8"))

    assert all(node.title_text.strip() != "Keep" for node in list(source_root))
    assert any(node.title_text.strip() == "Keep" for node in list(destination_root))


def test_run_tasks_update_moves_heading_to_destination_parent(tmp_path: Path) -> None:
    """Update should resolve --parent in destination file when --file is provided."""
    source = tmp_path / "source.org"
    destination = tmp_path / "destination.org"
    source.write_text(
        "* TODO Child\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    destination.write_text(
        "* TODO Parent\n:PROPERTIES:\n:ID: parent-1\n:END:\n",
        encoding="utf-8",
    )
    args = make_update_args(
        [str(source), str(destination)],
        file=str(destination),
        parent="parent-1",
    )

    tasks_update.run_tasks_update(args)

    destination_root = org_parser.loads(destination.read_text(encoding="utf-8"))
    destination_nodes = list(destination_root)
    child = next(node for node in destination_nodes if node.title_text.strip() == "Child")
    assert isinstance(child.parent, Heading)
    assert child.parent.title_text.strip() == "Parent"
    assert child.level == 2


def test_run_tasks_update_rejects_file_target_when_missing(tmp_path: Path) -> None:
    """Update should reject --file values that do not exist."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    args = make_update_args([str(source)], file=str(tmp_path / "missing.org"))

    with pytest.raises(typer.BadParameter, match="not found"):
        tasks_update.run_tasks_update(args)


def test_run_tasks_update_rejects_file_target_when_not_file(tmp_path: Path) -> None:
    """Update should reject --file values that are directories."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    args = make_update_args([str(source)], file=str(tmp_path))

    with pytest.raises(typer.BadParameter, match="not a file"):
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


def test_run_tasks_update_applies_fine_grained_tag_updates(tmp_path: Path) -> None:
    """Update should support adding and removing individual tags."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep :a:\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    args = make_update_args([str(source)], add_tag=["b"], remove_tag=["a"])

    tasks_update.run_tasks_update(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = next(iter(root))
    assert node.tags == ["b"]


def test_run_tasks_update_rejects_remove_tag_when_target_missing(tmp_path: Path) -> None:
    """Update should error when --remove-tag target does not exist."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    args = make_update_args([str(source)], remove_tag=["missing"])

    with pytest.raises(typer.BadParameter, match="--remove-tag target"):
        tasks_update.run_tasks_update(args)


def test_run_tasks_update_applies_fine_grained_property_updates(tmp_path: Path) -> None:
    """Update should support adding and removing individual properties."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:OLD: value\n:END:\n",
        encoding="utf-8",
    )
    args = make_update_args(
        [str(source)],
        add_property=["A=1", "B=two"],
        remove_property=["OLD"],
    )

    tasks_update.run_tasks_update(args)

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = next(iter(root))
    assert dict(node.properties) == {"ID": "task-1", "A": "1", "B": "two"}


def test_run_tasks_update_rejects_remove_property_when_target_missing(tmp_path: Path) -> None:
    """Update should error when --remove-property target does not exist."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    args = make_update_args([str(source)], remove_property=["MISSING"])

    with pytest.raises(typer.BadParameter, match="--remove-property target"):
        tasks_update.run_tasks_update(args)


def test_run_tasks_update_rejects_add_property_without_separator(tmp_path: Path) -> None:
    """Update should reject --add-property values that are not KEY=VALUE."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    args = make_update_args([str(source)], add_property=["NOPE"])

    with pytest.raises(typer.BadParameter, match="--add-property must be in KEY=VALUE"):
        tasks_update.run_tasks_update(args)


def test_run_tasks_update_applies_fine_grained_clock_entry_updates(tmp_path: Path) -> None:
    """Update should support adding and removing individual clock entries."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    clock_entry = "CLOCK: [2026-04-14 Tue 09:00]--[2026-04-14 Tue 10:00] =>  1:00"

    tasks_update.run_tasks_update(make_update_args([str(source)], add_clock_entry=[clock_entry]))

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = next(iter(root))
    assert len(node.clock_entries) == 1

    tasks_update.run_tasks_update(make_update_args([str(source)], remove_clock_entry=[clock_entry]))

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = next(iter(root))
    assert len(node.clock_entries) == 0


def test_run_tasks_update_rejects_remove_clock_entry_when_target_missing(tmp_path: Path) -> None:
    """Update should error when --remove-clock-entry target does not exist."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    clock_entry = "CLOCK: [2026-04-14 Tue 09:00]--[2026-04-14 Tue 10:00] =>  1:00"
    args = make_update_args([str(source)], remove_clock_entry=[clock_entry])

    with pytest.raises(typer.BadParameter, match="--remove-clock-entry target"):
        tasks_update.run_tasks_update(args)


def test_run_tasks_update_rejects_invalid_clock_entry_string(tmp_path: Path) -> None:
    """Update should reject malformed clock entry strings."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    args = make_update_args([str(source)], add_clock_entry=["[2026-04-14 Tue 09:00]"])

    with pytest.raises(typer.BadParameter, match="valid Org clock entry"):
        tasks_update.run_tasks_update(args)


def test_run_tasks_update_applies_fine_grained_repeat_updates(tmp_path: Path) -> None:
    """Update should support adding and removing individual repeats."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    repeat = '- State "DONE" from "TODO" [2026-04-14 Tue 09:00]'

    tasks_update.run_tasks_update(make_update_args([str(source)], add_repeat=[repeat]))

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = next(iter(root))
    assert len(node.repeats) == 1
    assert node.repeats[0].before == "TODO"
    assert node.repeats[0].after == "DONE"

    tasks_update.run_tasks_update(make_update_args([str(source)], remove_repeat=[repeat]))

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    node = next(iter(root))
    assert len(node.repeats) == 0


def test_run_tasks_update_rejects_remove_repeat_when_target_missing(tmp_path: Path) -> None:
    """Update should error when --remove-repeat target does not exist."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    repeat = '- State "DONE" from "TODO" [2026-04-14 Tue 09:00]'
    args = make_update_args([str(source)], remove_repeat=[repeat])

    with pytest.raises(typer.BadParameter, match="--remove-repeat target"):
        tasks_update.run_tasks_update(args)


def test_run_tasks_update_rejects_invalid_repeat_string(tmp_path: Path) -> None:
    """Update should reject malformed repeat entry strings."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    args = make_update_args([str(source)], add_repeat=["- [ ] not-a-repeat"])

    with pytest.raises(typer.BadParameter, match="valid Org repeat entry"):
        tasks_update.run_tasks_update(args)


def test_run_tasks_update_rejects_mixed_bulk_and_fine_grained_tag_updates(tmp_path: Path) -> None:
    """Update should reject --tags together with --add-tag/--remove-tag."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )

    with pytest.raises(typer.BadParameter, match="--tags cannot be combined"):
        tasks_update.run_tasks_update(make_update_args([str(source)], tags="a", add_tag=["b"]))


def test_run_tasks_update_rejects_mixed_bulk_and_fine_grained_properties(tmp_path: Path) -> None:
    """Update should reject --properties with --add-property/--remove-property."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )

    with pytest.raises(typer.BadParameter, match="--properties cannot be combined"):
        tasks_update.run_tasks_update(
            make_update_args([str(source)], properties='{"A":"1"}', add_property=["B=2"]),
        )
