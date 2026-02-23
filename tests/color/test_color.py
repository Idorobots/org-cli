"""Tests for org.color utilities."""

from __future__ import annotations

import sys

import pytest

from org import color


def test_should_use_color_respects_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit color flag should override TTY detection."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

    assert color.should_use_color(True) is True
    assert color.should_use_color(False) is False


def test_should_use_color_uses_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """When flag is None, use TTY detection."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    assert color.should_use_color(None) is True


def test_colorize_noop_when_disabled() -> None:
    """colorize should return original text when disabled."""
    assert color.colorize("hello", "green", False) == "hello"


def test_colorize_wraps_when_enabled() -> None:
    """colorize should wrap text with color codes when enabled."""
    assert color.colorize("hello", "green", True) == "[green]hello[/]"


def test_get_state_color_done_and_cancelled() -> None:
    """DONE states should be green, CANCELLED should be red."""
    done_keys = ["DONE", "CANCELLED"]
    todo_keys = ["TODO"]

    assert color.get_state_color("DONE", done_keys, todo_keys, True) == "bold green"
    assert color.get_state_color("CANCELLED", done_keys, todo_keys, True) == "bold red"


def test_get_state_color_todo_and_unknown() -> None:
    """TODO/empty states should be dim white, unknown should be yellow."""
    done_keys = ["DONE"]
    todo_keys = ["TODO"]

    assert color.get_state_color("TODO", done_keys, todo_keys, True) == "dim white"
    assert color.get_state_color("", done_keys, todo_keys, True) == "dim white"
    assert color.get_state_color("BLOCKED", done_keys, todo_keys, True) == "bold yellow"


def test_get_state_color_disabled_returns_empty() -> None:
    """When colors are disabled, no color should be returned."""
    assert color.get_state_color("DONE", ["DONE"], ["TODO"], False) == ""
