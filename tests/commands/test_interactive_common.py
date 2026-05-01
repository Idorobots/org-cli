"""Tests for shared interactive key-dispatch utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from org.commands.interactive_common import (
    BRACKETED_PASTE_DISABLE,
    BRACKETED_PASTE_ENABLE,
    KeyBinding,
    dispatch_key_binding,
    extract_bracketed_paste_text,
    key_binding_for_action,
    key_binding_requires_live_pause,
    read_input_event,
    set_bracketed_paste,
)


if TYPE_CHECKING:
    import pytest


def test_dispatch_key_binding_reports_unhandled_key() -> None:
    """Unknown key should be returned as unhandled with continue-loop default."""
    result = dispatch_key_binding("x", {})

    assert result.handled is False
    assert result.continue_loop is True
    assert result.requires_live_pause is False


def test_dispatch_key_binding_executes_handler() -> None:
    """Known key should execute callback and report handled result."""
    called = {"value": False}

    def _mark_called() -> None:
        called["value"] = True

    result = dispatch_key_binding("a", {"a": key_binding_for_action(_mark_called)})

    assert called["value"]
    assert result.handled is True
    assert result.continue_loop is True
    assert result.requires_live_pause is False


def test_dispatch_key_binding_can_exit_loop() -> None:
    """Handlers may return False to request interactive loop exit."""
    result = dispatch_key_binding("q", {"q": KeyBinding(lambda: False)})

    assert result.handled is True
    assert result.continue_loop is False


def test_key_binding_requires_live_pause_reads_binding_metadata() -> None:
    """Live pause helper should return binding pause metadata for key."""
    bindings = {
        "ENTER": key_binding_for_action(lambda: None, requires_live_pause=True),
        "x": key_binding_for_action(lambda: None),
    }

    assert key_binding_requires_live_pause("ENTER", bindings) is True
    assert key_binding_requires_live_pause("x", bindings) is False
    assert key_binding_requires_live_pause("missing", bindings) is False


def test_extract_bracketed_paste_text_decodes_payload() -> None:
    """Bracketed paste payload should decode inserted text."""
    payload = b"\x1b[200~Line one\nLine two\x1b[201~"
    assert extract_bracketed_paste_text(payload) == "Line one\nLine two"


def test_read_input_event_maps_bracketed_paste_to_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bracketed paste input should be surfaced as a TEXT event."""
    monkeypatch.setattr("org.commands.interactive_common.os.read", lambda _fd, _n: b"\x1b")
    monkeypatch.setattr(
        "org.commands.interactive_common.read_escape_sequence",
        lambda _fd: b"\x1b[200~Paste value",
    )
    monkeypatch.setattr(
        "org.commands.interactive_common.read_bracketed_paste_payload",
        lambda _fd, initial_payload: initial_payload + b"\x1b[201~",
    )
    assert read_input_event(0, ctrl_p_as_paste=True) == ("TEXT", "Paste value")


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
