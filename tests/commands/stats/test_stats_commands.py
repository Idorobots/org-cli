"""Unit tests for stats command handlers."""

from __future__ import annotations

import os
import sys

import pytest

from org.cli_common import ArgsPayload, build_args_namespace
from org.commands.stats import groups as stats_groups
from org.commands.stats import summary as stats_summary
from org.commands.stats import tags as stats_tags
from org.commands.stats import tasks as stats_tasks


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures")


def make_payload(files: list[str], **overrides: object) -> ArgsPayload:
    """Build ArgsPayload with defaults and overrides."""
    payload = ArgsPayload(
        files=files,
        config=".org-cli.json",
        exclude=None,
        mapping=None,
        todo_keys="TODO",
        done_keys="DONE",
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from=None,
        filter_date_until=None,
        filter_properties=None,
        filter_tags=None,
        filter_headings=None,
        filter_bodies=None,
        filter_completed=False,
        filter_not_completed=False,
        color_flag=False,
        max_results=10,
        max_tags=5,
        use="tags",
        with_gamify_category=False,
        with_tags_as_category=False,
        category_property="CATEGORY",
        max_relations=5,
        min_group_size=2,
        max_groups=5,
        buckets=50,
        show=None,
        groups=None,
    )
    for key, value in overrides.items():
        setattr(payload, key, value)
    return payload


def test_run_stats_summary_outputs_sections(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary command should output totals and sections."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = build_args_namespace(make_payload([fixture_path]))

    monkeypatch.setattr(sys, "argv", ["org", "stats", "summary"])
    stats_summary.run_stats(args)
    captured = capsys.readouterr().out

    assert "Total tasks:" in captured
    assert "Task states:" in captured
    assert "TAGS" in captured


def test_run_stats_tasks_excludes_tag_sections(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tasks command should omit TAGS/GROUPS output."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = build_args_namespace(make_payload([fixture_path]))

    monkeypatch.setattr(sys, "argv", ["org", "stats", "tasks"])
    stats_tasks.run_stats_tasks(args)
    captured = capsys.readouterr().out

    assert "Task states:" in captured
    assert "TAGS" not in captured
    assert "GROUPS" not in captured


def test_run_stats_tasks_no_results(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tasks command should report when filters return no results."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    payload = make_payload([fixture_path], filter_tags=["nomatch$"])
    args = build_args_namespace(payload)

    monkeypatch.setattr(sys, "argv", ["org", "stats", "tasks"])
    stats_tasks.run_stats_tasks(args)
    captured = capsys.readouterr().out

    assert "No results" in captured


def test_run_stats_tags_respects_show_filter(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tags command should filter to selected tags when --show is used."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    payload = make_payload([fixture_path], show="Test")
    args = build_args_namespace(payload)

    monkeypatch.setattr(sys, "argv", ["org", "stats", "tags", "--show", "Test"])
    stats_tags.run_stats_tags(args)
    captured = capsys.readouterr().out

    assert "Test" in captured
    assert "Debugging" not in captured


def test_run_stats_tags_show_heading(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tags command should normalize --show for heading usage."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    payload = make_payload([fixture_path], use="heading", show="Simple")
    args = build_args_namespace(payload)

    monkeypatch.setattr(sys, "argv", ["org", "stats", "tags", "--show", "Simple"])
    stats_tags.run_stats_tags(args)
    captured = capsys.readouterr().out

    assert "simple" in captured


def test_run_stats_groups_explicit_group(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Groups command should display explicit group selection."""
    fixture_path = os.path.join(FIXTURES_DIR, "tag_groups_test.org")
    payload = make_payload([fixture_path], groups=["python,programming"])
    args = build_args_namespace(payload)

    monkeypatch.setattr(sys, "argv", ["org", "stats", "groups", "--group", "python,programming"])
    stats_groups.run_stats_groups(args)
    captured = capsys.readouterr().out

    assert "python, programming" in captured


def test_run_stats_summary_no_results(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary command should print No results when filtered away."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    payload = make_payload([fixture_path], filter_tags=["nomatch$"])
    args = build_args_namespace(payload)

    monkeypatch.setattr(sys, "argv", ["org", "stats", "summary"])
    stats_summary.run_stats(args)
    captured = capsys.readouterr().out

    assert "No results" in captured


def test_run_stats_summary_preprocessors(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary command should handle category preprocessors."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    payload = make_payload(
        [fixture_path],
        with_gamify_category=True,
        with_tags_as_category=True,
    )
    args = build_args_namespace(payload)

    monkeypatch.setattr(sys, "argv", ["org", "stats", "summary"])
    stats_summary.run_stats(args)
    captured = capsys.readouterr().out

    assert "Task categories:" in captured
