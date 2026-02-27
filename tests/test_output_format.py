"""Tests for output format helpers."""

from __future__ import annotations

import io
import logging
from types import SimpleNamespace
from typing import cast

import pytest
from rich.console import Console
from rich.syntax import Syntax

from org import output_format


class _FakeConsole:
    def __init__(self) -> None:
        self.file = io.StringIO()
        self.renderables: list[object] = []

    def print(self, renderable: object, **kwargs: object) -> None:
        del kwargs
        self.renderables.append(renderable)


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


def test_resolve_syntax_language_uses_renderable_map() -> None:
    """Syntax language should be resolved through renderable format map."""
    assert output_format._resolve_syntax_language("gfm") == "markdown"
    assert output_format._resolve_syntax_language("html5") == "html"
    assert output_format._resolve_syntax_language("unknown-format") is None


def test_render_output_uses_syntax_when_color_and_mapped_format() -> None:
    """Mapped format with color enabled should render through Syntax."""
    console = _FakeConsole()

    output_format._render_output(cast(Console, console), "# title", True, "gfm")

    assert console.file.getvalue() == ""
    assert len(console.renderables) == 1
    syntax = console.renderables[0]
    assert isinstance(syntax, Syntax)
    assert syntax.lexer is not None
    assert syntax.lexer.name.lower() == "markdown"
    assert syntax.word_wrap is True


def test_render_output_falls_back_to_plain_when_not_mapped() -> None:
    """Unmapped formats should still render without syntax highlighting."""
    console = _FakeConsole()

    output_format._render_output(cast(Console, console), "payload", True, "not-real")

    assert console.file.getvalue() == "payload\n"
    assert console.renderables == []


def test_pandoc_query_formatter_uses_syntax_when_color_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pandoc query formatter should syntax-highlight mapped output formats."""
    console = _FakeConsole()
    formatter = output_format.PandocQueryOutputFormatter("gfm", None)

    monkeypatch.setattr(
        "org.output_format._org_to_pandoc_format",
        lambda _org_text, _output, _args: "# title",
    )

    formatter.render(["* TODO test"], cast(Console, console), True)

    assert console.file.getvalue() == ""
    assert len(console.renderables) == 1
    syntax = console.renderables[0]
    assert isinstance(syntax, Syntax)
    assert syntax.lexer is not None
    assert syntax.lexer.name.lower() == "markdown"
    assert syntax.word_wrap is True


def test_json_query_formatter_uses_json_syntax_when_color_enabled() -> None:
    """JSON query formatter should syntax-highlight JSON output with color."""
    console = _FakeConsole()
    formatter = output_format.JsonQueryOutputFormatter()

    formatter.render([{"ok": True}], cast(Console, console), True)

    assert console.file.getvalue() == ""
    assert len(console.renderables) == 1
    syntax = console.renderables[0]
    assert isinstance(syntax, Syntax)
    assert syntax.lexer is not None
    assert syntax.lexer.name.lower() == "json"
    assert syntax.word_wrap is True


def test_pandoc_tasks_formatter_uses_syntax_when_color_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pandoc tasks formatter should syntax-highlight mapped output formats."""
    console = _FakeConsole()
    formatter = output_format.PandocTasksListOutputFormatter("html5", None)

    monkeypatch.setattr(
        "org.output_format._org_to_pandoc_format",
        lambda _org_text, _output, _args: "<h1>title</h1>",
    )

    formatter.render(
        output_format.TasksListRenderInput(
            nodes=[],
            console=cast(Console, console),
            color_enabled=True,
            done_keys=["DONE"],
            todo_keys=["TODO"],
            details=False,
            buckets=10,
        )
    )

    assert console.file.getvalue() == ""
    assert len(console.renderables) == 1
    syntax = console.renderables[0]
    assert isinstance(syntax, Syntax)
    assert syntax.lexer is not None
    assert syntax.lexer.name.lower() == "html"
    assert syntax.word_wrap is True


def test_json_tasks_formatter_uses_json_syntax_when_color_enabled() -> None:
    """JSON tasks formatter should syntax-highlight JSON output with color."""
    console = _FakeConsole()
    formatter = output_format.JsonTasksListOutputFormatter()

    formatter.render(
        output_format.TasksListRenderInput(
            nodes=[],
            console=cast(Console, console),
            color_enabled=True,
            done_keys=["DONE"],
            todo_keys=["TODO"],
            details=False,
            buckets=10,
        )
    )

    assert console.file.getvalue() == ""
    assert len(console.renderables) == 1
    syntax = console.renderables[0]
    assert isinstance(syntax, Syntax)
    assert syntax.lexer is not None
    assert syntax.lexer.name.lower() == "json"
    assert syntax.word_wrap is True
