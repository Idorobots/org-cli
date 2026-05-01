"""Tests for shared interactive key-dispatch utilities."""

from __future__ import annotations

from org.commands.interactive_common import (
    KeyBinding,
    dispatch_key_binding,
    key_binding_for_action,
    key_binding_requires_live_pause,
)


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
