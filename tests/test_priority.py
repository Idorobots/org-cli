"""Tests for priority histogram and display functionality."""

from __future__ import annotations

from rich.text import Text

from org.analyze import compute_priority_histogram
from org.histogram import visual_len
from org.tui import TaskLineConfig, format_task_line
from tests.conftest import node_from_org


def test_compute_priority_histogram_with_priorities() -> None:
    """compute_priority_histogram should count tasks by priority."""
    nodes = node_from_org(
        """
* TODO [#A] Task A

* TODO [#B] Task B

* TODO [#A] Another A
""",
    )

    histogram = compute_priority_histogram(nodes)

    assert histogram.values.get("A") == 2
    assert histogram.values.get("B") == 1


def test_compute_priority_histogram_without_priorities() -> None:
    """compute_priority_histogram should count tasks without priorities as null."""
    nodes = node_from_org(
        """
* TODO Task without priority

* TODO Another task
""",
    )

    histogram = compute_priority_histogram(nodes)

    assert histogram.values.get("null") == 2


def test_format_task_line_with_priority() -> None:
    """format_task_line should display priority after todo state."""
    nodes = node_from_org(
        """
* TODO [#A] Task with priority
""",
    )

    line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=False,
            done_states=["DONE"],
            todo_states=["TODO"],
        ),
    )

    assert "[#A]" in line
    assert "TODO" in line


def test_format_task_line_without_priority() -> None:
    """format_task_line should not display priority when absent."""
    nodes = node_from_org(
        """
* TODO Task without priority
""",
    )

    line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=False,
            done_states=["DONE"],
            todo_states=["TODO"],
        ),
    )

    assert "[#" not in line
    assert "TODO" in line


def test_format_task_line_with_tags() -> None:
    """format_task_line should display tags aligned to right."""
    nodes = node_from_org(
        """
* TODO Task with tags  :TAG1:TAG2:
""",
    )

    line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=False,
            done_states=["DONE"],
            todo_states=["TODO"],
            line_width=80,
        ),
    )

    assert ":TAG1:TAG2:" in line
    assert "TODO" in line


def test_format_task_line_without_tags() -> None:
    """format_task_line should work without tags."""
    nodes = node_from_org(
        """
* TODO Task without tags
""",
    )

    line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=False,
            done_states=["DONE"],
            todo_states=["TODO"],
            line_width=80,
        ),
    )

    assert "TODO" in line
    assert ":" not in line or "<string>:" in line


def test_format_task_line_with_priority_and_tags() -> None:
    """format_task_line should display both priority and tags."""
    nodes = node_from_org(
        """
* TODO [#B] Task with both  :TAG1:
""",
    )

    line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=False,
            done_states=["DONE"],
            todo_states=["TODO"],
            line_width=80,
        ),
    )

    assert "[#B]" in line
    assert ":TAG1:" in line
    assert "TODO" in line


def test_format_task_line_renders_org_rich_text_title_content() -> None:
    """Short task list title should render from rich title parts."""
    nodes = node_from_org(
        """
* TODO *Bold* /Italic/ _Underline_ +Strike+ =Verbatim= ~InlineCode~ src_python{1+1} call_fn(1)
""",
    )

    line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=False,
            done_states=["DONE"],
            todo_states=["TODO"],
        ),
    )

    assert "Bold" in line and "*Bold*" not in line
    assert "Italic" in line and "/Italic/" not in line
    assert "Underline" in line and "_Underline_" not in line
    assert "Strike" in line and "+Strike+" not in line
    assert "Verbatim" in line and "=Verbatim=" not in line
    assert "InlineCode" in line and "~InlineCode~" not in line
    assert "src_python{1+1}" in line
    assert "call_fn(1)" in line


def test_format_task_line_supports_links_and_preserves_sub_superscript_literals() -> None:
    """Task list titles should include links and literal sub/superscript text."""
    nodes = node_from_org(
        """
* TODO [[https://example.com/docs][Docs]] and https://example.com x^{2} H_{2}O
""",
    )

    plain_line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=False,
            done_states=["DONE"],
            todo_states=["TODO"],
        ),
    )
    color_line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=True,
            done_states=["DONE"],
            todo_states=["TODO"],
        ),
    )

    assert "Docs" in plain_line
    assert "[[https://example.com/docs][Docs]]" not in plain_line
    assert "https://example.com" in plain_line
    assert "x^{2}" in plain_line
    assert "H_{2}O" in plain_line
    assert "[link " in color_line


def test_format_task_line_keeps_tag_alignment_with_rich_markup_heading() -> None:
    """Rich-marked headings should align tags by visual width."""
    nodes = node_from_org(
        """
* TODO 修正 *太字タイトル* の確認 :開発:
""",
    )

    line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=True,
            done_states=["DONE"],
            todo_states=["TODO"],
            line_width=50,
        ),
    )

    assert visual_len(line) == 50
    assert Text.from_markup(line).plain.endswith(":開発:")
