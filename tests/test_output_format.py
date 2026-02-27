"""Tests for output format helpers."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from org import output_format


def test_org_to_pandoc_format_suppresses_warning_and_logs_info(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pandoc warnings should be logged and not written to stderr."""

    def _fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        del args
        del kwargs
        return SimpleNamespace(returncode=0, stdout="# converted", stderr="pandoc warning text\n")

    monkeypatch.setattr("org.output_format.subprocess.run", _fake_run)
    caplog.set_level(logging.INFO, logger="org")

    markdown_text = output_format._org_to_pandoc_format("* TODO test", "markdown", [])
    captured = capsys.readouterr()

    assert markdown_text == "# converted"
    assert captured.err == ""
    assert "pandoc warning: pandoc warning text" in caplog.text


def test_org_to_pandoc_format_forwards_pandoc_output_args(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pandoc subprocess should receive requested output format and options."""
    seen: dict[str, object] = {}

    def _fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        seen["command"] = command
        seen["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="converted", stderr="")

    monkeypatch.setattr("org.output_format.subprocess.run", _fake_run)

    rendered = output_format._org_to_pandoc_format(
        "* TODO test",
        "gfm",
        ["--wrap=none", "--columns=120"],
    )

    assert rendered == "converted"
    assert seen["command"] == ["pandoc", "-f", "org", "-t", "gfm", "--wrap=none", "--columns=120"]
    assert seen["kwargs"] == {
        "input": "* TODO test",
        "text": True,
        "capture_output": True,
        "check": False,
    }


def test_org_to_pandoc_format_raises_output_error_on_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pandoc stderr should be forwarded as formatter error on failure."""

    def _fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        del args
        del kwargs
        return SimpleNamespace(returncode=22, stdout="", stderr="Unknown output format\n")

    monkeypatch.setattr("org.output_format.subprocess.run", _fake_run)

    with pytest.raises(output_format.OutputFormatError, match="Unknown output format"):
        output_format._org_to_pandoc_format("* TODO test", "invalid-format", [])


def test_org_to_pandoc_format_raises_output_error_when_pandoc_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing pandoc executable should produce formatter error."""

    def _fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        del args
        del kwargs
        raise FileNotFoundError("pandoc not found")

    monkeypatch.setattr("org.output_format.subprocess.run", _fake_run)

    with pytest.raises(output_format.OutputFormatError, match="pandoc not found"):
        output_format._org_to_pandoc_format("* TODO test", "gfm", [])


def test_parse_pandoc_args_uses_shell_splitting() -> None:
    """Pandoc args parser should split command-line style string."""
    parsed = output_format._parse_pandoc_args('--wrap=none --metadata title="My Doc"')

    assert parsed == ["--wrap=none", "--metadata", "title=My Doc"]
