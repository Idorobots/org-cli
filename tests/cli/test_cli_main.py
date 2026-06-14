"""Tests for org.cli main entrypoint wiring."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING

import typer

import org.config.app
from org import cli


if TYPE_CHECKING:
    import pytest


def test_cli_main_builds_default_map(monkeypatch: pytest.MonkeyPatch) -> None:
    """main should load config defaults and pass default_map to Typer command."""
    recorded: dict[str, object] = {}

    class DummyCommand:
        def main(
            self,
            args: list[str],
            prog_name: str,
            standalone_mode: bool,
            default_map: object,
        ) -> None:
            recorded["args"] = args
            recorded["prog_name"] = prog_name
            recorded["standalone_mode"] = standalone_mode
            recorded["default_map"] = default_map

    def fake_get_command(_app: object) -> DummyCommand:
        return DummyCommand()

    monkeypatch.setattr(
        org.config.app,
        "load_cli_config",
        lambda _argv: org.config.app.LoadedCliConfig(
            defaults={"max_results": 3},
            append_defaults={},
            inline_defaults={},
            custom_filters={},
            custom_order_by={},
            custom_with={},
            capture_templates={},
            board_views={},
            agenda_views={},
        ),
    )
    monkeypatch.setattr(
        org.config.app,
        "build_default_map",
        lambda _defaults: {"stats": _defaults, "agenda": {}},
    )
    monkeypatch.setattr(typer.main, "get_command", fake_get_command)

    monkeypatch.setattr(sys, "argv", ["org", "stats", "all", "--no-color", "file.org"])
    cli.main()

    assert recorded["args"] == ["stats", "all", "--no-color", "file.org"]
    assert recorded["prog_name"] == "org"
    assert recorded["standalone_mode"] is True
    assert recorded["default_map"] == {"stats": {"max_results": 3}, "agenda": {}}


def test_cli_main_updates_config_globals(monkeypatch: pytest.MonkeyPatch) -> None:
    """main should update config append and inline defaults."""
    original_append = dict(org.config.app.CONFIG_APPEND_DEFAULTS)
    original_inline = dict(org.config.app.CONFIG_INLINE_DEFAULTS)
    original_custom_filters = dict(org.config.app.CONFIG_CUSTOM_FILTERS)
    original_custom_order_by = dict(org.config.app.CONFIG_CUSTOM_ORDER_BY)
    original_custom_with = dict(org.config.app.CONFIG_CUSTOM_WITH)
    original_capture_templates = dict(org.config.app.CONFIG_CAPTURE_TEMPLATES)
    original_board_views = dict(org.config.app.CONFIG_BOARD_VIEWS)
    org.config.app.CONFIG_APPEND_DEFAULTS.clear()
    org.config.app.CONFIG_INLINE_DEFAULTS.clear()
    org.config.app.CONFIG_CUSTOM_FILTERS.clear()
    org.config.app.CONFIG_CUSTOM_ORDER_BY.clear()
    org.config.app.CONFIG_CUSTOM_WITH.clear()
    org.config.app.CONFIG_CAPTURE_TEMPLATES.clear()
    org.config.app.CONFIG_BOARD_VIEWS.clear()

    def fake_get_command(_app: object) -> SimpleNamespace:
        return SimpleNamespace(main=lambda **_: None)

    monkeypatch.setattr(
        org.config.app,
        "load_cli_config",
        lambda _argv: org.config.app.LoadedCliConfig(
            defaults={},
            append_defaults={"filter_tags": ["alpha"]},
            inline_defaults={"mapping_inline": {"a": "b"}},
            custom_filters={"my-filter": ".[]"},
            custom_order_by={"my-order": "."},
            custom_with={"my-with": "."},
            capture_templates={"quick": {"file": "tasks.org", "content": "* TODO {{title}}"}},
            board_views={
                "kanban": org.config.app.BoardViewConfig(
                    name="kanban",
                    columns=[
                        org.config.app.BoardColumnConfig(name="TODO", filter='.todo == "TODO"'),
                    ],
                ),
            },
            agenda_views={},
        ),
    )
    monkeypatch.setattr(org.config.app, "build_default_map", lambda _defaults: {})
    monkeypatch.setattr(typer.main, "get_command", fake_get_command)
    monkeypatch.setattr(sys, "argv", ["org", "stats", "all"])

    try:
        cli.main()

        assert org.config.app.CONFIG_APPEND_DEFAULTS == {"filter_tags": ["alpha"]}
        assert org.config.app.CONFIG_INLINE_DEFAULTS == {"mapping_inline": {"a": "b"}}
        assert org.config.app.CONFIG_CUSTOM_FILTERS == {"my-filter": ".[]"}
        assert org.config.app.CONFIG_CUSTOM_ORDER_BY == {"my-order": "."}
        assert org.config.app.CONFIG_CUSTOM_WITH == {"my-with": "."}
        assert org.config.app.CONFIG_CAPTURE_TEMPLATES == {
            "quick": {"file": "tasks.org", "content": "* TODO {{title}}"},
        }
        assert set(org.config.app.CONFIG_BOARD_VIEWS) == {"kanban"}
        assert org.config.app.CONFIG_BOARD_VIEWS["kanban"].name == "kanban"
    finally:
        org.config.app.CONFIG_APPEND_DEFAULTS.clear()
        org.config.app.CONFIG_APPEND_DEFAULTS.update(original_append)
        org.config.app.CONFIG_INLINE_DEFAULTS.clear()
        org.config.app.CONFIG_INLINE_DEFAULTS.update(original_inline)
        org.config.app.CONFIG_CUSTOM_FILTERS.clear()
        org.config.app.CONFIG_CUSTOM_FILTERS.update(original_custom_filters)
        org.config.app.CONFIG_CUSTOM_ORDER_BY.clear()
        org.config.app.CONFIG_CUSTOM_ORDER_BY.update(original_custom_order_by)
        org.config.app.CONFIG_CUSTOM_WITH.clear()
        org.config.app.CONFIG_CUSTOM_WITH.update(original_custom_with)
        org.config.app.CONFIG_CAPTURE_TEMPLATES.clear()
        org.config.app.CONFIG_CAPTURE_TEMPLATES.update(original_capture_templates)
        org.config.app.CONFIG_BOARD_VIEWS.clear()
        org.config.app.CONFIG_BOARD_VIEWS.update(original_board_views)
