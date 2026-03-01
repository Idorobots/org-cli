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

    monkeypatch.setattr(
        config,
        "load_cli_config",
        lambda _argv: config.LoadedCliConfig(
            defaults={"max_results": 3},
            append_defaults={},
            inline_defaults={},
            custom_filters={},
            custom_order_by={},
            custom_with={},
        ),
    )
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
    original_custom_filters = dict(config.CONFIG_CUSTOM_FILTERS)
    original_custom_order_by = dict(config.CONFIG_CUSTOM_ORDER_BY)
    original_custom_with = dict(config.CONFIG_CUSTOM_WITH)
    config.CONFIG_APPEND_DEFAULTS.clear()
    config.CONFIG_INLINE_DEFAULTS.clear()
    config.CONFIG_CUSTOM_FILTERS.clear()
    config.CONFIG_CUSTOM_ORDER_BY.clear()
    config.CONFIG_CUSTOM_WITH.clear()

    def fake_get_command(_app: object) -> SimpleNamespace:
        return SimpleNamespace(main=lambda **_: None)

    monkeypatch.setattr(
        config,
        "load_cli_config",
        lambda _argv: config.LoadedCliConfig(
            defaults={},
            append_defaults={"filter_tags": ["alpha"]},
            inline_defaults={"mapping_inline": {"a": "b"}},
            custom_filters={"my-filter": ".[]"},
            custom_order_by={"my-order": "."},
            custom_with={"my-with": "."},
        ),
    )
    monkeypatch.setattr(config, "build_default_map", lambda _defaults: {})
    monkeypatch.setattr(typer.main, "get_command", fake_get_command)
    monkeypatch.setattr(sys, "argv", ["org", "stats", "summary"])

    try:
        cli.main()

        assert config.CONFIG_APPEND_DEFAULTS == {"filter_tags": ["alpha"]}
        assert config.CONFIG_INLINE_DEFAULTS == {"mapping_inline": {"a": "b"}}
        assert config.CONFIG_CUSTOM_FILTERS == {"my-filter": ".[]"}
        assert config.CONFIG_CUSTOM_ORDER_BY == {"my-order": "."}
        assert config.CONFIG_CUSTOM_WITH == {"my-with": "."}
    finally:
        config.CONFIG_APPEND_DEFAULTS.clear()
        config.CONFIG_APPEND_DEFAULTS.update(original_append)
        config.CONFIG_INLINE_DEFAULTS.clear()
        config.CONFIG_INLINE_DEFAULTS.update(original_inline)
        config.CONFIG_CUSTOM_FILTERS.clear()
        config.CONFIG_CUSTOM_FILTERS.update(original_custom_filters)
        config.CONFIG_CUSTOM_ORDER_BY.clear()
        config.CONFIG_CUSTOM_ORDER_BY.update(original_custom_order_by)
        config.CONFIG_CUSTOM_WITH.clear()
        config.CONFIG_CUSTOM_WITH.update(original_custom_with)
