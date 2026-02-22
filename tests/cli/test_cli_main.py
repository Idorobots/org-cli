"""Tests for org.cli main entrypoint wiring."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
import typer

from org import cli, config


def test_cli_main_builds_default_map(monkeypatch: pytest.MonkeyPatch) -> None:
    """main should load config defaults and pass default_map to Typer command."""
    recorded: dict[str, object] = {}

    class DummyCommand:
        def main(
            self, args: list[str], prog_name: str, standalone_mode: bool, default_map: object
        ) -> None:
            recorded["args"] = args
            recorded["prog_name"] = prog_name
            recorded["standalone_mode"] = standalone_mode
            recorded["default_map"] = default_map

    def fake_get_command(_app: object) -> DummyCommand:
        return DummyCommand()

    monkeypatch.setattr(config, "load_cli_config", lambda _argv: ({"max_results": 3}, {}, {}))
    monkeypatch.setattr(config, "build_default_map", lambda _defaults: {"stats": _defaults})
    monkeypatch.setattr(typer.main, "get_command", fake_get_command)

    monkeypatch.setattr(sys, "argv", ["org", "stats", "summary", "--no-color", "file.org"])
    cli.main()

    assert recorded["args"] == ["stats", "summary", "--no-color", "file.org"]
    assert recorded["prog_name"] == "org"
    assert recorded["standalone_mode"] is True
    assert recorded["default_map"] == {"stats": {"max_results": 3}}


def test_cli_main_updates_config_globals(monkeypatch: pytest.MonkeyPatch) -> None:
    """main should update config append and inline defaults."""
    original_append = dict(config.CONFIG_APPEND_DEFAULTS)
    original_inline = dict(config.CONFIG_INLINE_DEFAULTS)
    config.CONFIG_APPEND_DEFAULTS.clear()
    config.CONFIG_INLINE_DEFAULTS.clear()

    def fake_get_command(_app: object) -> SimpleNamespace:
        return SimpleNamespace(main=lambda **_: None)

    monkeypatch.setattr(
        config,
        "load_cli_config",
        lambda _argv: ({}, {"filter_tags": ["alpha"]}, {"mapping_inline": {"a": "b"}}),
    )
    monkeypatch.setattr(config, "build_default_map", lambda _defaults: {})
    monkeypatch.setattr(typer.main, "get_command", fake_get_command)
    monkeypatch.setattr(sys, "argv", ["org", "stats", "summary"])

    try:
        cli.main()

        assert config.CONFIG_APPEND_DEFAULTS == {"filter_tags": ["alpha"]}
        assert config.CONFIG_INLINE_DEFAULTS == {"mapping_inline": {"a": "b"}}
    finally:
        config.CONFIG_APPEND_DEFAULTS.clear()
        config.CONFIG_APPEND_DEFAULTS.update(original_append)
        config.CONFIG_INLINE_DEFAULTS.clear()
        config.CONFIG_INLINE_DEFAULTS.update(original_inline)
