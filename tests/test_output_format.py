"""Tests for output format helpers."""

from __future__ import annotations

import logging
import warnings

import pytest

from org import output_format


def test_org_to_markdown_suppresses_warning_and_logs_info(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pandoc warnings should be logged and not written to stderr."""

    class _FakePandoc:
        @staticmethod
        def read(text: str, format: str) -> object:
            del text
            del format
            warnings.warn(
                "Pandoc version 3.5 is not supported, proceeding as 3.2.1",
                UserWarning,
                stacklevel=1,
            )
            return object()

        @staticmethod
        def write(document: object, format: str) -> str:
            del document
            del format
            return "# converted"

    monkeypatch.setattr(output_format, "import_module", lambda _: _FakePandoc)
    caplog.set_level(logging.INFO, logger="org")

    markdown_text = output_format._org_to_markdown("* TODO test")
    captured = capsys.readouterr()

    assert markdown_text == "# converted"
    assert captured.err == ""
    assert "pandoc warning: Pandoc version 3.5 is not supported" in caplog.text
