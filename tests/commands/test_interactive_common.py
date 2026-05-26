"""Tests for shared interactive helpers."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING, Any, cast

from rich.console import Console

from org.commands.interactive_common import (
    BRACKETED_PASTE_DISABLE,
    BRACKETED_PASTE_ENABLE,
    FooterPromptState,
    HeadingLocator,
    InputEvent,
    InteractiveHelpEntry,
    InteractivePromptState,
    KeypressEvent,
    create_interactive_prompt_state,
    extract_bracketed_paste_text,
    handle_active_prompt_event,
    heading_locator,
    read_input_event,
    render_interactive_help_modal,
    render_interactive_help_panel_text,
    resolve_heading_locator,
    set_bracketed_paste,
)
from org.commands.tasks.common import resolve_todo_state_selection, todo_states_for_heading
from tests.conftest import node_from_org


if TYPE_CHECKING:
    import pytest


class _PromptConfig:
    def __init__(self, label: str) -> None:
        self.prompt = FooterPromptState(label=label)
        self.cancel_status = "Cancelled"
        self.invalid_status = "Invalid"


class _PromptOwner:
    def __init__(self, prompt: InteractivePromptState | None) -> None:
        self.active_prompt = prompt
        self.status_message = ""


def _submit_and_close(values: list[str], value: str) -> bool:
    values.append(value)
    return False


def test_create_interactive_prompt_state_uses_submit_and_preview_callbacks() -> None:
    """Prompt state should forward current value to submit and preview callbacks."""
    previewed: list[str] = []
    submitted: list[str] = []

    prompt = create_interactive_prompt_state(
        _PromptConfig("Search"),
        submit_value=lambda value: _submit_and_close(submitted, value),
        preview_value=previewed.append,
    )
    prompt.prompt.value = "needle"

    assert prompt.preview is not None
    prompt.preview()
    keep_open = prompt.submit_callback()

    assert previewed == ["needle"]
    assert submitted == ["needle"]
    assert keep_open is False


def test_handle_active_prompt_event_closes_prompt_on_escape() -> None:
    """Escape should close active prompt and set cancel status by default."""
    owner = _PromptOwner(
        InteractivePromptState(
            prompt=FooterPromptState(label="Search"),
            cancel_status="Cancelled",
            invalid_status="Invalid",
            submit_callback=lambda: False,
        ),
    )

    assert handle_active_prompt_event(owner, KeypressEvent("ESC")) is True
    assert owner.active_prompt is None
    assert owner.status_message == "Cancelled"


def test_handle_active_prompt_event_applies_input_and_submit() -> None:
    """Prompt event handling should update prompt text and close after submit."""
    submitted: list[str] = []
    prompt = create_interactive_prompt_state(
        _PromptConfig("Search"),
        submit_value=lambda value: _submit_and_close(submitted, value),
    )
    owner = _PromptOwner(prompt)

    assert handle_active_prompt_event(owner, InputEvent("abc")) is True
    assert owner.active_prompt is not None
    assert owner.active_prompt.prompt.value == "abc"

    assert handle_active_prompt_event(owner, KeypressEvent("ENTER")) is True
    assert submitted == ["abc"]
    assert owner.active_prompt is None


def test_extract_bracketed_paste_text_decodes_payload() -> None:
    """Bracketed paste payload should decode inserted text."""
    payload = b"\x1b[200~Line one\nLine two\x1b[201~"
    assert extract_bracketed_paste_text(payload) == "Line one\nLine two"


def test_read_input_event_maps_bracketed_paste_to_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bracketed paste input should be surfaced as a TEXT event."""
    monkeypatch.setattr("org.commands.interactive_common.sys.stdin.fileno", lambda: 0)
    monkeypatch.setattr("org.commands.interactive_common.os.read", lambda _fd, _n: b"\x1b")
    monkeypatch.setattr(
        "org.commands.interactive_common.read_escape_sequence",
        lambda _fd: b"\x1b[200~Paste value",
    )
    monkeypatch.setattr(
        "org.commands.interactive_common.read_bracketed_paste_payload",
        lambda _fd, initial_payload: initial_payload + b"\x1b[201~",
    )
    assert read_input_event(ctrl_p_as_paste=True) == ("TEXT", "Paste value")


def test_read_input_event_returns_none_when_timeout_expires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timed input reads should return None when no input arrives."""

    def _fake_select(
        _readers: object,
        _writers: object,
        _errors: object,
        _timeout: object,
    ) -> tuple[list[int], list[int], list[int]]:
        return ([], [], [])

    monkeypatch.setattr("org.commands.interactive_common.select.select", _fake_select)
    monkeypatch.setattr("org.commands.interactive_common.sys.stdin.fileno", lambda: 0)

    assert read_input_event(timeout_seconds=0.1) is None


def test_set_bracketed_paste_writes_terminal_sequences(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bracketed paste toggles should emit proper terminal sequences."""

    class _FakeStdout:
        def __init__(self) -> None:
            self.writes: list[str] = []

        def isatty(self) -> bool:
            return True

        def write(self, value: str) -> int:
            self.writes.append(value)
            return len(value)

        def flush(self) -> None:
            return None

    fake_stdout = _FakeStdout()
    monkeypatch.setattr("org.commands.interactive_common.sys.stdout", fake_stdout)

    set_bracketed_paste(True)
    set_bracketed_paste(False)

    assert fake_stdout.writes == [BRACKETED_PASTE_ENABLE, BRACKETED_PASTE_DISABLE]


def test_resolve_todo_state_selection_supports_number_and_value() -> None:
    """State selection should resolve numeric indexes and explicit values."""
    states = ["TODO", "NEXT", "DONE"]

    assert resolve_todo_state_selection("2", states) == "NEXT"
    assert resolve_todo_state_selection("DONE", states) == "DONE"
    assert resolve_todo_state_selection("", states) is None
    assert resolve_todo_state_selection("99", states) is None
    assert resolve_todo_state_selection("UNKNOWN", states) is None


def test_todo_states_for_heading_returns_stable_unique_order() -> None:
    """TODO states helper should deduplicate while preserving first appearance order."""

    class _FakeDocument:
        def __init__(self) -> None:
            self.all_states = ["TODO", "DONE", "TODO", "WAIT"]

    class _FakeHeading:
        document = _FakeDocument()

    fake_heading = cast("Any", _FakeHeading())
    assert todo_states_for_heading(fake_heading) == ["TODO", "DONE", "WAIT"]


def test_render_interactive_help_modal_keeps_key_column_wide_without_ellipsis() -> None:
    """Help modal should avoid key ellipsis and keep long key text visible."""
    entries = [
        InteractiveHelpEntry(
            "CTRL-SHIFT-SUPER-LEFT",
            "Very long description text that should wrap instead of being cut with ellipsis.",
        ),
    ]
    renderable = render_interactive_help_modal(entries, color_enabled=False)
    output_stream = StringIO()
    output_console = Console(file=output_stream, width=40, force_terminal=False, no_color=True)
    output_console.print(renderable)
    output = output_stream.getvalue()

    assert "..." not in output
    assert "CTRL-SHIFT-SUPER-LEFT" in output


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
