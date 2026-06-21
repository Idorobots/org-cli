"""Tests for org.cli main entrypoint wiring."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import typer

import org.config.app
from org import cli


if TYPE_CHECKING:
    import pytest


def test_cli_main_invokes_typer_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """main should load config, build the app, and invoke the Typer command."""
    recorded: dict[str, object] = {}

    class DummyCommand:
        def main(
            self,
            args: list[str],
            prog_name: str,
            standalone_mode: bool,
        ) -> None:
            recorded["args"] = args
            recorded["prog_name"] = prog_name
            recorded["standalone_mode"] = standalone_mode

    def fake_get_command(_app: object) -> DummyCommand:
        return DummyCommand()

    loaded_config = org.config.app.build_default_app_config()
    loaded_config.stats.max_results = 3

    monkeypatch.setattr(
        org.config.app,
        "load_cli_config",
        lambda _argv: loaded_config,
    )
    monkeypatch.setattr(typer.main, "get_command", fake_get_command)

    monkeypatch.setattr(sys, "argv", ["org", "stats", "all", "--no-color", "file.org"])
    cli.main()

    assert recorded["args"] == ["stats", "all", "--no-color", "file.org"]
    assert recorded["prog_name"] == "org"
    assert recorded["standalone_mode"] is True


def test_build_app_callback_stores_loaded_config() -> None:
    """The root callback should place the loaded AppConfig in ctx.obj."""
    config = org.config.app.build_default_app_config()
    app = cli.build_app(config)
    assert app.registered_callback is not None
    callback = app.registered_callback.callback
    assert callback is not None

    ctx = typer.Context(typer.main.get_command(app))
    callback(ctx, None)

    assert ctx.obj is config
