"""Tests for tasks archive command."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import org_parser
import pytest
import typer
from org_parser.document import Heading

from org.commands.tasks import archive as tasks_archive


if TYPE_CHECKING:
    from pathlib import Path


def make_archive_args(files: list[str], **overrides: object) -> tasks_archive.ArchiveArgs:
    """Build ArchiveArgs with defaults and overrides."""
    args = tasks_archive.ArchiveArgs(
        files=files,
        config=".org-cli.yaml",
        query_title=None,
        query_id="task-1",
        query=None,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_tasks_archive_uses_default_archive_pattern(tmp_path: Path) -> None:
    """Archive should fallback to %s_archive:: destination pattern."""
    source = tmp_path / "tasks.org"
    archive = tmp_path / "tasks.org_archive"
    source.write_text("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n", encoding="utf-8")
    archive.write_text("", encoding="utf-8")

    tasks_archive.run_tasks_archive(make_archive_args([str(source)]))

    source_root = org_parser.loads(source.read_text(encoding="utf-8"))
    archive_root = org_parser.loads(archive.read_text(encoding="utf-8"))
    assert list(source_root) == []
    assert [node.title_text.strip() for node in list(archive_root)] == ["Keep"]


def test_run_tasks_archive_prefers_heading_archive_property(tmp_path: Path) -> None:
    """Heading ARCHIVE property should override document-level ARCHIVE keyword."""
    source = tmp_path / "tasks.org"
    by_property = tmp_path / "property_target.org"
    by_keyword = tmp_path / "keyword_target.org"
    source.write_text(
        (
            "#+ARCHIVE: keyword_target.org::\n"
            "* TODO Keep\n"
            ":PROPERTIES:\n"
            ":ID: task-1\n"
            ":ARCHIVE: property_target.org::\n"
            ":END:\n"
        ),
        encoding="utf-8",
    )
    by_property.write_text("", encoding="utf-8")
    by_keyword.write_text("", encoding="utf-8")

    tasks_archive.run_tasks_archive(make_archive_args([str(source)]))

    property_root = org_parser.loads(by_property.read_text(encoding="utf-8"))
    keyword_root = org_parser.loads(by_keyword.read_text(encoding="utf-8"))
    assert [node.title_text.strip() for node in list(property_root)] == ["Keep"]
    assert list(keyword_root) == []


def test_run_tasks_archive_uses_document_archive_keyword(tmp_path: Path) -> None:
    """Document ARCHIVE keyword should be used when heading property is absent."""
    source = tmp_path / "tasks.org"
    destination = tmp_path / "archive_target.org"
    source.write_text(
        "#+ARCHIVE: archive_target.org::\n* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    destination.write_text("", encoding="utf-8")

    tasks_archive.run_tasks_archive(make_archive_args([str(source)]))

    destination_root = org_parser.loads(destination.read_text(encoding="utf-8"))
    assert [node.title_text.strip() for node in list(destination_root)] == ["Keep"]


def test_run_tasks_archive_moves_to_named_parent_heading_in_same_file(tmp_path: Path) -> None:
    """Archive target with ::Heading should move subtree under that heading."""
    source = tmp_path / "tasks.org"
    source.write_text(
        ("#+ARCHIVE: %s::Archive\n* TODO Archive\n* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n"),
        encoding="utf-8",
    )

    tasks_archive.run_tasks_archive(make_archive_args([str(source)]))

    root = org_parser.loads(source.read_text(encoding="utf-8"))
    nodes = list(root)
    archive_heading = next(node for node in nodes if node.title_text.strip() == "Archive")
    keep_heading = next(node for node in nodes if node.title_text.strip() == "Keep")
    assert isinstance(keep_heading.parent, Heading)
    assert keep_heading.parent is archive_heading
    assert keep_heading.level == archive_heading.level + 1


def test_run_tasks_archive_moves_to_named_parent_heading_in_other_file(tmp_path: Path) -> None:
    """Archive target file::Heading should move subtree under destination heading."""
    source = tmp_path / "tasks.org"
    destination = tmp_path / "archive.org"
    source.write_text(
        (
            "#+ARCHIVE: archive.org::Archived\n"
            "* TODO Keep\n"
            ":PROPERTIES:\n"
            ":ID: task-1\n"
            ":END:\n"
            "** TODO Child\n"
        ),
        encoding="utf-8",
    )
    destination.write_text("* TODO Archived\n", encoding="utf-8")

    tasks_archive.run_tasks_archive(make_archive_args([str(source)]))

    source_root = org_parser.loads(source.read_text(encoding="utf-8"))
    destination_root = org_parser.loads(destination.read_text(encoding="utf-8"))
    assert all(node.title_text.strip() != "Keep" for node in list(source_root))

    destination_nodes = list(destination_root)
    archived = next(node for node in destination_nodes if node.title_text.strip() == "Keep")
    assert isinstance(archived.parent, Heading)
    assert archived.parent.title_text.strip() == "Archived"
    assert any(node.title_text.strip() == "Child" for node in list(destination_root))


def test_run_tasks_archive_requires_exactly_one_selector(tmp_path: Path) -> None:
    """Archive should require exactly one selector option."""
    source = tmp_path / "tasks.org"
    source.write_text("* TODO Keep\n", encoding="utf-8")

    with pytest.raises(typer.BadParameter, match="exactly one task selector"):
        tasks_archive.run_tasks_archive(make_archive_args([str(source)], query_id=None))

    with pytest.raises(typer.BadParameter, match="exactly one task selector"):
        tasks_archive.run_tasks_archive(
            make_archive_args(
                [str(source)],
                query_title="Keep",
                query='str(.title_text) == "Keep"',
            ),
        )


def test_run_tasks_archive_supports_query_title_and_query(tmp_path: Path) -> None:
    """Archive should support --query-title and generic --query selectors."""
    source = tmp_path / "tasks.org"
    archive = tmp_path / "tasks.org_archive"
    source.write_text("* TODO A\n* TODO B\n", encoding="utf-8")
    archive.write_text("", encoding="utf-8")

    tasks_archive.run_tasks_archive(
        make_archive_args([str(source)], query_id=None, query_title="A"),
    )
    tasks_archive.run_tasks_archive(
        make_archive_args(
            [str(source)],
            query_id=None,
            query='str(.title_text) == "B"',
        ),
    )

    source_root = org_parser.loads(source.read_text(encoding="utf-8"))
    archive_root = org_parser.loads(archive.read_text(encoding="utf-8"))
    assert list(source_root) == []
    assert [node.title_text.strip() for node in list(archive_root)] == ["A", "B"]


def test_run_tasks_archive_reports_missing_archive_file(tmp_path: Path) -> None:
    """Archive should error when resolved destination file does not exist."""
    source = tmp_path / "tasks.org"
    source.write_text(
        "#+ARCHIVE: missing_target.org::\n* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )

    with pytest.raises(typer.BadParameter, match="not found"):
        tasks_archive.run_tasks_archive(make_archive_args([str(source)]))


def test_run_tasks_archive_reports_missing_archive_heading(tmp_path: Path) -> None:
    """Archive should error when destination heading title does not exist."""
    source = tmp_path / "tasks.org"
    destination = tmp_path / "archive.org"
    source.write_text(
        "#+ARCHIVE: archive.org::Missing\n* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n",
        encoding="utf-8",
    )
    destination.write_text("* TODO Other\n", encoding="utf-8")

    with pytest.raises(typer.BadParameter, match="--parent 'Missing' was not found"):
        tasks_archive.run_tasks_archive(make_archive_args([str(source)]))


def test_run_tasks_archive_skips_descendant_matches_when_parent_selected(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Archive should move only root selected subtree when descendants are also selected."""
    source = tmp_path / "tasks.org"
    archive = tmp_path / "tasks.org_archive"
    source.write_text(
        "* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n** TODO Child\n",
        encoding="utf-8",
    )
    archive.write_text("", encoding="utf-8")

    tasks_archive.run_tasks_archive(
        make_archive_args(
            [str(source)],
            query_id=None,
            query='str(.title_text) == "Keep" or str(.title_text) == "Child"',
        ),
    )

    assert capsys.readouterr().out.strip() == "Archived 1 tasks."
    archive_root = org_parser.loads(archive.read_text(encoding="utf-8"))
    assert [node.title_text.strip() for node in list(archive_root)] == ["Keep", "Child"]


def test_run_tasks_archive_sets_archive_metadata_properties(tmp_path: Path) -> None:
    """Archive should set ARCHIVE_* metadata on archived heading."""
    source = tmp_path / "tasks.org"
    archive = tmp_path / "tasks.org_archive"
    source.write_text(
        ("* DONE Keep\n:PROPERTIES:\n:ID: task-1\n:CATEGORY: refile\n:END:\n"),
        encoding="utf-8",
    )
    archive.write_text("", encoding="utf-8")

    tasks_archive.run_tasks_archive(make_archive_args([str(source)]))

    archive_root = org_parser.loads(archive.read_text(encoding="utf-8"))
    archived_heading = next(iter(archive_root))
    assert str(archived_heading.properties["ARCHIVE_FILE"]) == str(source)
    assert str(archived_heading.properties["ARCHIVE_CATEGORY"]) == "refile"
    assert str(archived_heading.properties["ARCHIVE_TODO"]) == "DONE"
    assert (
        re.fullmatch(
            r"\d{4}-\d{2}-\d{2} \w+ \d{2}:\d{2}",
            str(archived_heading.properties["ARCHIVE_TIME"]),
        )
        is not None
    )
