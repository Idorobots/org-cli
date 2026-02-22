"""Tests for python -m org entrypoint behavior."""

from __future__ import annotations

import runpy

import pytest

from org import cli


def test_module_entrypoint_invokes_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running org.__main__ should call cli.main."""
    called = {"value": False}

    def fake_main() -> None:
        called["value"] = True

    monkeypatch.setattr(cli, "main", fake_main)

    runpy.run_module("org.__main__", run_name="__main__")

    assert called["value"] is True
