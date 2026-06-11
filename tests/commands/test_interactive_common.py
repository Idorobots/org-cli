"""Tests for shared interactive helpers still used in production."""

from __future__ import annotations

from typing import Any, cast

from org.commands.interactive_common import (
    HeadingLocator,
    InteractiveHelpEntry,
    heading_locator,
    render_interactive_help_panel_text,
    resolve_heading_locator,
)
from org.commands.tasks.common import todo_states_for_heading
from tests.conftest import node_from_org


def test_todo_states_for_heading_returns_stable_unique_order() -> None:
    """TODO states helper should deduplicate while preserving first appearance order."""

    class _FakeDocument:
        def __init__(self) -> None:
            self.all_states = ["TODO", "DONE", "TODO", "WAIT"]

    class _FakeHeading:
        document = _FakeDocument()

    fake_heading = cast("Any", _FakeHeading())
    assert todo_states_for_heading(fake_heading) == ["TODO", "DONE", "WAIT"]


def test_render_interactive_help_panel_text_includes_title_and_rows() -> None:
    """Rendered help text should include key-bindings title and entries."""
    entries = [
        InteractiveHelpEntry("Esc/q", "Exit the view and return to the shell."),
        InteractiveHelpEntry("?", "Open the key bindings modal."),
    ]

    output = render_interactive_help_panel_text(entries)

    assert "Key bindings:" in output
    assert "Esc/q" in output
    assert "Exit the view and return to the shell." in output


def test_heading_locator_uses_id_when_present() -> None:
    """Locator should preserve filename, ID, and title for a heading."""
    node = node_from_org("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n")[0]

    assert heading_locator(node) == HeadingLocator(
        filename=node.document.filename or "",
        heading_id="task-1",
        title="Keep",
    )


def test_resolve_heading_locator_prefers_id_after_title_change() -> None:
    """Locator resolution should follow heading ID after reloads change the title."""
    original = node_from_org("* TODO Keep\n:PROPERTIES:\n:ID: task-1\n:END:\n")[0]
    reloaded = node_from_org("* TODO Updated\n:PROPERTIES:\n:ID: task-1\n:END:\n")

    resolved = resolve_heading_locator(reloaded, heading_locator(original))

    assert resolved is reloaded[0]


def test_resolve_heading_locator_falls_back_to_title_without_id() -> None:
    """Locator resolution should use title when a heading has no ID."""
    original = node_from_org("* TODO Keep\n")[0]
    reloaded = node_from_org("* TODO Keep\n* TODO Other\n")

    resolved = resolve_heading_locator(reloaded, heading_locator(original))

    assert resolved is reloaded[0]


def test_resolve_heading_locator_returns_none_when_heading_disappears() -> None:
    """Locator resolution should fail cleanly when the target heading is gone."""
    original = node_from_org("* TODO Keep\n")[0]
    reloaded = node_from_org("* TODO Other\n")

    assert resolve_heading_locator(reloaded, heading_locator(original)) is None
