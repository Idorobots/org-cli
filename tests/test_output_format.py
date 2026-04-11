"""Tests for output format helpers."""

from __future__ import annotations

import io
import logging
from datetime import datetime
from types import SimpleNamespace
from typing import cast

import org_parser
import pytest
from org_parser.document import Heading
from org_parser.element import Keyword
from org_parser.text import RichText
from rich.console import Console
from rich.syntax import Syntax

from org import output_format
from org.analyze import AnalysisResult, Group, Tag, TimeRange
from org.commands import query as query_command
from org.commands.tasks import list as tasks_list_command
from org.histogram import Histogram


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
        return SimpleNamespace(returncode=0, stdout=b"# converted", stderr=b"pandoc warning text\n")

    monkeypatch.setattr("org.output_format.subprocess.run", _fake_run)
    caplog.set_level(logging.INFO, logger="org")

    markdown_text = output_format._org_to_pandoc_format("* TODO test", "markdown", [])
    captured = capsys.readouterr()

    assert markdown_text == b"# converted"
    assert captured.err == ""
    assert "pandoc warning: pandoc warning text" in caplog.text


def test_org_to_pandoc_format_forwards_pandoc_output_args(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pandoc subprocess should receive requested output format and options."""
    seen: dict[str, object] = {}

    def _fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        seen["command"] = command
        seen["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout=b"converted", stderr=b"")

    monkeypatch.setattr("org.output_format.subprocess.run", _fake_run)

    rendered = output_format._org_to_pandoc_format(
        "* TODO test",
        "gfm",
        ["--wrap=none", "--columns=120"],
    )

    assert rendered == b"converted"
    assert seen["command"] == ["pandoc", "-f", "org", "-t", "gfm", "--wrap=none", "--columns=120"]
    assert seen["kwargs"] == {
        "input": b"* TODO test",
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
        return SimpleNamespace(returncode=22, stdout=b"", stderr=b"Unknown output format\n")

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


def test_normalize_syntax_theme_uses_default_for_empty_theme() -> None:
    """Empty syntax theme should fall back to default."""
    assert output_format._normalize_syntax_theme("") == output_format.DEFAULT_OUTPUT_THEME
    assert output_format._normalize_syntax_theme("  ") == output_format.DEFAULT_OUTPUT_THEME


def test_prepare_output_uses_syntax_when_color_and_mapped_format() -> None:
    """Mapped format with color enabled should prepare Syntax output."""
    console = _FakeConsole()
    prepared_output = output_format._prepare_output("# title", True, "gfm", "monokai")

    output_format.print_prepared_output(cast(Console, console), prepared_output)

    assert console.file.getvalue() == ""
    assert len(console.renderables) == 1
    syntax = console.renderables[0]
    assert isinstance(syntax, Syntax)
    assert syntax.lexer is not None
    assert syntax.lexer.name.lower() == "markdown"
    assert syntax.word_wrap is True


def test_prepare_output_falls_back_to_plain_when_not_mapped() -> None:
    """Unmapped formats should still prepare plain output."""
    console = _FakeConsole()
    prepared_output = output_format._prepare_output("payload", True, "not-real", "monokai")

    output_format.print_prepared_output(cast(Console, console), prepared_output)

    assert console.file.getvalue() == "payload\n"
    assert console.renderables == []


def test_prepare_output_falls_back_to_binary_write_on_decode_error() -> None:
    """Binary pandoc output should be emitted as raw bytes."""
    console = _FakeConsole()
    prepared_output = output_format._prepare_output(b"\x00\xe4\x10", True, "pdf", "monokai")

    assert len(prepared_output.operations) == 1
    operation = prepared_output.operations[0]
    assert operation.kind == "binary_write"
    assert operation.data == b"\x00\xe4\x10"

    with pytest.raises(output_format.OutputFormatError, match="binary output is not supported"):
        output_format.print_prepared_output(cast(Console, console), prepared_output)


def test_pandoc_query_formatter_uses_syntax_when_color_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pandoc query formatter should syntax-highlight mapped output formats."""
    console = _FakeConsole()
    formatter = query_command.PandocQueryOutputFormatter("gfm", None)

    monkeypatch.setattr(
        "org.commands.query._org_to_pandoc_format",
        lambda _org_text, _output, _args: "# title",
    )

    prepared_output = formatter.prepare(["* TODO test"], cast(Console, console), True, "monokai")
    output_format.print_prepared_output(cast(Console, console), prepared_output)

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
    formatter = query_command.JsonQueryOutputFormatter()

    prepared_output = formatter.prepare([{"ok": True}], cast(Console, console), True, "monokai")
    output_format.print_prepared_output(cast(Console, console), prepared_output)

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

    class _FakeNode:
        def __str__(self) -> str:
            return "* TODO task"

    console = _FakeConsole()
    formatter = tasks_list_command.PandocTasksListOutputFormatter("html5", None)

    monkeypatch.setattr(
        "org.commands.tasks.list._org_to_pandoc_format",
        lambda _org_text, _output, _args: "<h1>title</h1>",
    )

    prepared_output = formatter.prepare(
        tasks_list_command.TasksListRenderInput(
            nodes=[cast(Heading, _FakeNode())],
            console=cast(Console, console),
            color_enabled=True,
            done_states=["DONE"],
            todo_states=["TODO"],
            details=False,
            line_width=None,
            out_theme="monokai",
        )
    )
    output_format.print_prepared_output(cast(Console, console), prepared_output)

    assert console.file.getvalue() == ""
    assert len(console.renderables) == 1
    syntax = console.renderables[0]
    assert isinstance(syntax, Syntax)
    assert syntax.lexer is not None
    assert syntax.lexer.name.lower() == "html"
    assert syntax.word_wrap is True


def test_to_json_compatible_serializes_histogram_with_type_field() -> None:
    """Histogram should serialize to a JSON object with a type field."""
    histogram = Histogram(values={"DONE": 3, "TODO": 2})

    result = output_format._to_json_compatible(histogram)

    assert isinstance(result, dict)
    assert result["type"] == "Histogram"
    assert result["values"] == {"DONE": 3, "TODO": 2}


def test_to_json_compatible_serializes_timerange_with_type_field() -> None:
    """TimeRange should serialize to a JSON object with a type field."""
    tr = TimeRange()
    tr.update(datetime(2024, 3, 1, 10, 0))
    tr.update(datetime(2024, 3, 5, 12, 0))

    result = output_format._to_json_compatible(tr)

    assert isinstance(result, dict)
    assert result["type"] == "TimeRange"
    assert result["earliest"] == "2024-03-01T10:00:00"
    assert result["latest"] == "2024-03-05T12:00:00"
    assert isinstance(result["timeline"], dict)
    assert result["timeline"]["2024-03-01"] == 1
    assert result["timeline"]["2024-03-05"] == 1


def test_to_json_compatible_serializes_tag_with_type_field() -> None:
    """Tag should serialize to a JSON object with a type field and nested TimeRange."""
    tr = TimeRange()
    tr.update(datetime(2024, 6, 1))
    tag = Tag(
        name="python",
        total_tasks=5,
        avg_tasks_per_day=0.5,
        max_single_day_count=2,
        relations={"testing": 3},
        time_range=tr,
    )

    result = output_format._to_json_compatible(tag)

    assert isinstance(result, dict)
    assert result["type"] == "Tag"
    assert result["name"] == "python"
    assert result["total_tasks"] == 5
    assert result["avg_tasks_per_day"] == 0.5
    assert result["max_single_day_count"] == 2
    assert result["relations"] == {"testing": 3}
    time_range_result = result["time_range"]
    assert isinstance(time_range_result, dict)
    assert time_range_result["type"] == "TimeRange"


def test_to_json_compatible_serializes_group_with_type_field() -> None:
    """Group should serialize to a JSON object with a type field and nested TimeRange."""
    group = Group(
        tags=["python", "testing"],
        time_range=TimeRange(),
        total_tasks=7,
        avg_tasks_per_day=0.3,
        max_single_day_count=3,
    )

    result = output_format._to_json_compatible(group)

    assert isinstance(result, dict)
    assert result["type"] == "Group"
    assert result["tags"] == ["python", "testing"]
    assert result["total_tasks"] == 7
    time_range_result = result["time_range"]
    assert isinstance(time_range_result, dict)
    assert time_range_result["type"] == "TimeRange"


def test_to_json_compatible_serializes_analysis_result_with_type_field() -> None:
    """AnalysisResult should serialize to a JSON object with nested analysis types."""
    tr = TimeRange()
    tr.update(datetime(2024, 1, 15))
    tag = Tag(
        name="dev",
        total_tasks=4,
        avg_tasks_per_day=0.2,
        max_single_day_count=2,
        relations={},
        time_range=TimeRange(),
    )
    result = AnalysisResult(
        total_tasks=4,
        unique_tasks=4,
        task_states=Histogram(values={"DONE": 2, "TODO": 2}),
        task_categories=Histogram(values={}),
        task_priorities=Histogram(values={"A": 1}),
        task_days=Histogram(values={"Monday": 2}),
        timerange=tr,
        avg_tasks_per_day=0.2,
        max_single_day_count=2,
        max_repeat_count=1,
        tags={"dev": tag},
        tag_groups=[],
    )

    serialized = output_format._to_json_compatible(result)

    assert isinstance(serialized, dict)
    assert serialized["type"] == "AnalysisResult"
    assert serialized["total_tasks"] == 4
    assert serialized["unique_tasks"] == 4
    assert serialized["avg_tasks_per_day"] == 0.2

    task_states = serialized["task_states"]
    assert isinstance(task_states, dict)
    assert task_states["type"] == "Histogram"
    assert task_states["values"] == {"DONE": 2, "TODO": 2}

    timerange = serialized["timerange"]
    assert isinstance(timerange, dict)
    assert timerange["type"] == "TimeRange"

    tags = serialized["tags"]
    assert isinstance(tags, dict)
    assert "dev" in tags
    dev_tag = tags["dev"]
    assert isinstance(dev_tag, dict)
    assert dev_tag["type"] == "Tag"
    assert dev_tag["name"] == "dev"


def test_to_json_compatible_serializes_richtext_as_plain_string() -> None:
    """RichText values should serialize as their plain text."""
    assert output_format._to_json_compatible(RichText("hello")) == "hello"


def test_to_json_compatible_serializes_generic_element_with_type() -> None:
    """Generic org elements should serialize as typed JSON objects."""
    keyword = Keyword(key="TITLE", value=RichText("Doc"))

    result = output_format._to_json_compatible(keyword)

    assert isinstance(result, dict)
    assert result["type"] == "Keyword"
    assert result["key"] == "TITLE"
    assert result["value"] == "Doc"


def test_to_json_compatible_keeps_properties_as_mapping() -> None:
    """Properties should remain mapping-like JSON objects."""
    heading = next(iter(org_parser.loads("* Task\n:PROPERTIES:\n:key: 23\n:END:\n")))

    result = output_format._to_json_compatible(heading.properties)

    assert result == {"key": "23"}


def test_json_tasks_formatter_uses_json_syntax_when_color_enabled() -> None:
    """JSON tasks formatter should syntax-highlight JSON output with color."""
    console = _FakeConsole()
    formatter = tasks_list_command.JsonTasksListOutputFormatter()

    prepared_output = formatter.prepare(
        tasks_list_command.TasksListRenderInput(
            nodes=[],
            console=cast(Console, console),
            color_enabled=True,
            done_states=["DONE"],
            todo_states=["TODO"],
            details=False,
            line_width=None,
            out_theme="monokai",
        )
    )
    output_format.print_prepared_output(cast(Console, console), prepared_output)

    assert console.file.getvalue() == ""
    assert len(console.renderables) == 1
    syntax = console.renderables[0]
    assert isinstance(syntax, Syntax)
    assert syntax.lexer is not None
    assert syntax.lexer.name.lower() == "json"
    assert syntax.word_wrap is True
