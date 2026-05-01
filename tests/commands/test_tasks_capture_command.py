"""Tests for capture command behavior."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import org_parser
import pytest
import typer

from org import config
from org.commands import interactive_common
from org.commands.tasks import capture


if TYPE_CHECKING:
    from pathlib import Path
    from typing import Self


def _make_capture_args(
    template_name: str | None,
    *,
    file: str | None = None,
    parent: str | None = None,
    set_values: list[str] | None = None,
) -> capture.TasksCaptureArgs:
    """Build capture args for tests."""
    return capture.TasksCaptureArgs(
        template_name=template_name,
        config=".org-cli.yaml",
        file=file,
        parent=parent,
        set_values=set_values,
    )


def _set_capture_templates(templates: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Replace global capture templates and return previous value."""
    previous = dict(config.CONFIG_CAPTURE_TEMPLATES)
    config.CONFIG_CAPTURE_TEMPLATES.clear()
    config.CONFIG_CAPTURE_TEMPLATES.update(templates)
    return previous


def _restore_capture_templates(previous: dict[str, dict[str, str]]) -> None:
    """Restore global capture templates from previous value."""
    config.CONFIG_CAPTURE_TEMPLATES.clear()
    config.CONFIG_CAPTURE_TEMPLATES.update(previous)


def test_run_capture_errors_when_no_templates_configured() -> None:
    """Capture should fail with a clear error when templates are missing."""
    previous = _set_capture_templates({})
    try:
        with pytest.raises(typer.BadParameter, match="No capture templates configured"):
            capture.run_tasks_capture(_make_capture_args(template_name=None))
    finally:
        _restore_capture_templates(previous)


def test_run_capture_errors_for_unknown_template_name() -> None:
    """Capture should list valid names when an unknown template is requested."""
    previous = _set_capture_templates(
        {
            "alpha": {"file": "tasks.org", "content": "* TODO {{title}}"},
            "beta": {"file": "tasks.org", "content": "* TODO {{title}}"},
        },
    )
    try:
        with pytest.raises(typer.BadParameter, match="Valid templates: alpha, beta"):
            capture.run_tasks_capture(_make_capture_args(template_name="missing"))
    finally:
        _restore_capture_templates(previous)


def test_run_capture_selects_template_by_numeric_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture should resolve template selection from numeric interactive input."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {
            "alpha": {"file": str(target), "content": "* TODO From alpha"},
            "beta": {"file": str(target), "content": "* TODO From beta"},
        },
    )
    try:
        monkeypatch.setattr("org.commands.tasks.capture.typer.prompt", lambda _msg: "2")
        capture.run_tasks_capture(_make_capture_args(template_name=None))
    finally:
        _restore_capture_templates(previous)

    updated = target.read_text(encoding="utf-8")
    assert "From beta" in updated
    assert "From alpha" not in updated


def test_run_capture_prompts_non_static_placeholder_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated non-static placeholders should be prompted once and reused."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {
            "quick": {
                "file": str(target),
                "content": "* TODO {{title}} then {{title}}",
            },
        },
    )

    calls: list[str] = []

    def _prompt(message: str, **_kwargs: object) -> str:
        calls.append(message)
        return "Write docs"

    try:
        monkeypatch.setattr("org.commands.tasks.capture.typer.prompt", _prompt)
        capture.run_tasks_capture(_make_capture_args(template_name="quick"))
    finally:
        _restore_capture_templates(previous)

    updated = target.read_text(encoding="utf-8")
    assert "* TODO Write docs then Write docs" in updated
    assert calls == ["Value for 'title'"]


def test_render_template_preview_tracks_placeholder_spans() -> None:
    """Template preview should map placeholders to rendered output positions."""
    preview = capture._render_template_preview(
        "* TODO {{title}} [{{title}}] {{owner}}",
        {"title": "Write docs"},
    )

    assert preview.text == "* TODO Write docs [Write docs] {{owner}}"
    title_spans = preview.placeholder_spans["title"]
    owner_spans = preview.placeholder_spans["owner"]

    assert title_spans == [(7, 17), (19, 29)]
    assert owner_spans == [(31, 40)]


def test_resolve_placeholder_values_uses_live_preview_when_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interactive placeholders should route through live preview when available."""
    calls: list[tuple[str, list[str], dict[str, str]]] = []

    def _fake_live_prompt(
        template_content: str,
        placeholders: list[str],
        values: dict[str, str],
    ) -> dict[str, str]:
        calls.append((template_content, placeholders, values))
        return {
            **values,
            "title": "From live preview",
        }

    monkeypatch.setattr("org.commands.tasks.capture._supports_live_template_prompt", lambda: True)
    monkeypatch.setattr("org.commands.tasks.capture._prompt_with_live_preview", _fake_live_prompt)

    result = capture._resolve_placeholder_values(
        "* TODO {{title}}",
        ["title"],
        set_values={},
        static_values={},
        document_values={},
    )

    assert result == {"title": "From live preview"}
    assert calls == [("* TODO {{title}}", ["title"], {})]


def test_prompt_with_live_preview_updates_current_field_sequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live prompt should update preview in field order and finalize after input."""

    class _FakeLive:
        def __init__(self, initial_renderable: object, **kwargs: object) -> None:
            self.initial_renderable = initial_renderable
            self.updates: list[object] = []
            self.kwargs = kwargs

            class _FakeSize:
                width = 80

            class _FakeConsole:
                size = _FakeSize()

            self.console = _FakeConsole()

        def __enter__(self) -> Self:
            return self

        def __exit__(
            self,
            _exc_type: type[BaseException] | None,
            _exc: BaseException | None,
            _tb: object,
        ) -> None:
            return None

        def update(self, renderable: object, *, refresh: bool) -> None:
            assert refresh
            self.updates.append(renderable)

    fake_live: _FakeLive | None = None

    def _live_factory(initial_renderable: object, **kwargs: object) -> _FakeLive:
        nonlocal fake_live
        fake_live = _FakeLive(initial_renderable, **kwargs)
        return fake_live

    def _renderable(
        _template_content: str,
        values: dict[str, str],
        footer_state: capture._FooterState,
        console_width: int,
    ) -> tuple[dict[str, str], capture._FooterState, int]:
        return (
            dict(values),
            footer_state,
            console_width,
        )

    entered_values = iter(["Write docs", "Jane"])

    def _read_value(
        _live: _FakeLive,
        _template_content: str,
        _resolved_values: dict[str, str],
        _active_field: capture._ActiveField,
    ) -> str:
        return next(entered_values)

    live_path = "org.commands.tasks.capture.Live"
    render_path = "org.commands.tasks.capture._build_fullscreen_capture_renderable"
    read_value_path = "org.commands.tasks.capture._read_live_placeholder_value"
    width_path = "org.commands.tasks.capture._resolve_terminal_width"
    fileno_path = "org.commands.tasks.capture.sys.stdin.fileno"
    tcgetattr_path = "org.commands.tasks.capture.termios.tcgetattr"

    monkeypatch.setattr(live_path, _live_factory)
    monkeypatch.setattr(render_path, _renderable)
    monkeypatch.setattr(read_value_path, _read_value)
    monkeypatch.setattr(width_path, lambda: 80)
    monkeypatch.setattr(fileno_path, lambda: 0)
    monkeypatch.setattr(tcgetattr_path, lambda _fd: [0, 0, 0, 0, 0, 0])

    resolved = capture._prompt_with_live_preview(
        "* TODO {{title}} @{{owner}}",
        ["title", "owner"],
        {},
    )

    assert resolved == {"title": "Write docs", "owner": "Jane"}
    assert fake_live is not None
    assert fake_live.initial_renderable == (
        {},
        capture._FooterState(
            current_placeholder="title",
            current_input_value="",
            cursor_position=0,
            current_field_index=1,
            total_fields=2,
        ),
        80,
    )
    assert fake_live.kwargs["screen"] is True
    assert fake_live.kwargs["refresh_per_second"] == 12
    assert fake_live.kwargs["auto_refresh"] is False
    assert fake_live.kwargs["transient"] is False
    assert fake_live.updates == [
        (
            {"title": "Write docs", "owner": "Jane"},
            capture._FooterState(
                current_placeholder=None,
                current_input_value="",
                cursor_position=0,
                current_field_index=None,
                total_fields=2,
            ),
            80,
        ),
    ]


def test_build_footer_prompt_includes_field_index_marker() -> None:
    """Footer prompt should render editable value input only."""
    footer = capture._build_footer_prompt(
        capture._FooterState(
            current_placeholder="owner",
            current_input_value="Jane",
            cursor_position=4,
            current_field_index=2,
            total_fields=5,
        ),
    )
    assert footer.plain.startswith("Value for 'owner': Jane")


def test_build_footer_status_line_displays_marker_and_controls() -> None:
    """Footer status line should show left marker and right controls."""
    footer_state = capture._FooterState(
        current_placeholder="owner",
        current_input_value="Jane",
        cursor_position=4,
        current_field_index=2,
        total_fields=5,
    )
    status_line = capture._build_footer_status_line(footer_state)
    assert status_line.columns[1].justify == "right"
    assert capture._value_progress_marker(footer_state) == "Value 2/5"


def test_count_wrapped_prompt_lines_expands_with_long_input() -> None:
    """Long prompt values should wrap to multiple footer lines."""
    prompt = capture._build_footer_prompt(
        capture._FooterState(
            current_placeholder="title",
            current_input_value="x" * 120,
            cursor_position=120,
            current_field_index=1,
            total_fields=2,
        ),
    )
    wrapped_lines = capture._count_wrapped_prompt_lines(prompt, console_width=40)
    assert wrapped_lines > 1


def test_apply_input_event_supports_cursor_keys_and_backspace() -> None:
    """Input editing should support insertion, cursor motion, and deletion."""
    value = ""
    cursor = 0

    events = [
        ("TEXT", "a"),
        ("TEXT", "c"),
        ("LEFT", ""),
        ("TEXT", "b"),
        ("LEFT", ""),
        ("DELETE", ""),
        ("RIGHT", ""),
        ("BACKSPACE", ""),
        ("TEXT", "b"),
        ("ENTER", ""),
    ]

    done = False
    for event_name, event_text in events:
        value, cursor, done = capture._apply_input_event(value, cursor, event_name, event_text)

    assert done
    assert value == "ab"
    assert cursor == 2


def test_extract_bracketed_paste_text_decodes_payload() -> None:
    """Bracketed paste payload should decode to inserted prompt text."""
    payload = b"\x1b[200~Line one\nLine two\x1b[201~"
    assert interactive_common.extract_bracketed_paste_text(payload) == "Line one\nLine two"


def test_read_input_event_maps_bracketed_paste_to_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bracketed paste input should be surfaced as TEXT event."""
    monkeypatch.setattr("org.commands.interactive_common.os.read", lambda _fd, _n: b"\x1b")
    monkeypatch.setattr(
        "org.commands.interactive_common.read_escape_sequence",
        lambda _fd: b"\x1b[200~Paste value",
    )
    monkeypatch.setattr(
        "org.commands.interactive_common.read_bracketed_paste_payload",
        lambda _fd, initial_payload: initial_payload + b"\x1b[201~",
    )

    assert interactive_common.read_input_event(0, ctrl_p_as_paste=True) == ("TEXT", "Paste value")


def test_set_bracketed_paste_writes_terminal_sequences(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bracketed paste toggles should emit proper terminal sequences."""

    class _FakeStdout:
        def __init__(self) -> None:
            self.writes: list[str] = []

        def isatty(self) -> bool:
            return True

        def write(self, value: str) -> int:
            self.writes.append(value)
            return len(value)

        def flush(self) -> None:
            return None

    fake_stdout = _FakeStdout()
    monkeypatch.setattr("org.commands.interactive_common.sys.stdout", fake_stdout)

    interactive_common.set_bracketed_paste(True)
    interactive_common.set_bracketed_paste(False)

    assert fake_stdout.writes == ["\x1b[?2004h", "\x1b[?2004l"]


def test_run_capture_rejects_invalid_render_without_file_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid rendered heading should fail before file mutation."""
    target = tmp_path / "tasks.org"
    original = "* TODO Existing\n"
    target.write_text(original, encoding="utf-8")
    previous = _set_capture_templates(
        {
            "broken": {
                "file": str(target),
                "content": "not a heading {{title}}",
            },
        },
    )

    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.typer.prompt",
            lambda _msg, **_kwargs: "Anything",
        )
        with pytest.raises(typer.BadParameter, match="Invalid rendered capture heading"):
            capture.run_tasks_capture(_make_capture_args(template_name="broken"))
    finally:
        _restore_capture_templates(previous)

    assert target.read_text(encoding="utf-8") == original


def test_run_capture_inserts_under_parent_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture should support parent selection with query language expression."""
    target = tmp_path / "tasks.org"
    target.write_text(
        "* TODO Project\n:PROPERTIES:\n:ID: project-1\n:END:\n\n* TODO Other\n",
        encoding="utf-8",
    )
    previous = _set_capture_templates(
        {
            "child": {
                "file": str(target),
                "content": "** TODO {{title}}",
                "parent": '.id == "project-1"',
            },
        },
    )

    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.typer.prompt",
            lambda _msg, **_kwargs: "Child task",
        )
        capture.run_tasks_capture(_make_capture_args(template_name="child"))
    finally:
        _restore_capture_templates(previous)

    root = org_parser.loads(target.read_text(encoding="utf-8"))
    titles = [node.title_text.strip() for node in list(root)]
    assert titles == ["Project", "Child task", "Other"]


def test_run_capture_cli_file_override_takes_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture should use CLI --file over template file."""
    configured_target = tmp_path / "configured.org"
    override_target = tmp_path / "override.org"
    configured_target.write_text("* TODO Configured\n", encoding="utf-8")
    override_target.write_text("* TODO Override\n", encoding="utf-8")

    previous = _set_capture_templates(
        {
            "quick": {
                "file": str(configured_target),
                "content": "* TODO {{title}}",
            },
        },
    )
    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.typer.prompt",
            lambda _msg, **_kwargs: "From override",
        )
        capture.run_tasks_capture(_make_capture_args("quick", file=str(override_target)))
    finally:
        _restore_capture_templates(previous)

    assert "From override" not in configured_target.read_text(encoding="utf-8")
    assert "From override" in override_target.read_text(encoding="utf-8")


def test_run_capture_cli_parent_override_takes_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture should use CLI --parent selector over template parent selector."""
    target = tmp_path / "tasks.org"
    target.write_text(
        "* TODO One\n:PROPERTIES:\n:ID: one\n:END:\n\n* TODO Two\n:PROPERTIES:\n:ID: two\n:END:\n",
        encoding="utf-8",
    )

    previous = _set_capture_templates(
        {
            "child": {
                "file": str(target),
                "content": "** TODO {{title}}",
                "parent": '.id == "one"',
            },
        },
    )
    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.typer.prompt",
            lambda _msg, **_kwargs: "Override child",
        )
        capture.run_tasks_capture(_make_capture_args("child", parent='.id == "two"'))
    finally:
        _restore_capture_templates(previous)

    root = org_parser.loads(target.read_text(encoding="utf-8"))
    nodes = list(root)
    titles = [node.title_text.strip() for node in nodes]
    assert titles == ["One", "Two", "Override child"]


def test_run_capture_set_values_bypass_prompt(tmp_path: Path) -> None:
    """Capture should use --set values without prompting."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {
            "quick": {
                "file": str(target),
                "content": "* TODO {{title}} ({{title}})",
            },
        },
    )
    try:
        capture.run_tasks_capture(_make_capture_args("quick", set_values=["title=From set"]))
    finally:
        _restore_capture_templates(previous)

    assert "* TODO From set (From set)" in target.read_text(encoding="utf-8")


def test_run_capture_set_values_ignores_unknown_parameter(tmp_path: Path) -> None:
    """Capture should ignore --set keys absent from template placeholders."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {
            "quick": {
                "file": str(target),
                "content": "* TODO Static",
            },
        },
    )
    try:
        capture.run_tasks_capture(_make_capture_args("quick", set_values=["foo=bar"]))
    finally:
        _restore_capture_templates(previous)

    assert "* TODO Static" in target.read_text(encoding="utf-8")


def test_run_capture_set_values_reject_invalid_format(tmp_path: Path) -> None:
    """Capture should reject --set entries that are not KEY=VALUE."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {
            "quick": {
                "file": str(target),
                "content": "* TODO {{title}}",
            },
        },
    )
    try:
        with pytest.raises(typer.BadParameter, match="--set must be KEY=VALUE"):
            capture.run_tasks_capture(_make_capture_args("quick", set_values=["title"]))
    finally:
        _restore_capture_templates(previous)


def test_run_capture_static_placeholders_use_org_timestamp_format(tmp_path: Path) -> None:
    """Capture should render {{today}} and {{now}} as Org-mode timestamps."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    previous = _set_capture_templates(
        {
            "quick": {
                "file": str(target),
                "content": "* TODO today={{today}} now={{now}}",
            },
        },
    )
    try:
        capture.run_tasks_capture(_make_capture_args("quick"))
    finally:
        _restore_capture_templates(previous)

    updated = target.read_text(encoding="utf-8")
    assert re.search(r"today=<\d{4}-\d{2}-\d{2} (Mon|Tue|Wed|Thu|Fri|Sat|Sun)>", updated)
    assert re.search(
        r"now=<\d{4}-\d{2}-\d{2} (Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{2}:\d{2}>",
        updated,
    )


def test_run_capture_static_id_placeholder_uses_next_heading_number(tmp_path: Path) -> None:
    """Capture should render {{id}} as next heading count value."""
    target = tmp_path / "tasks.org"
    target.write_text("* TODO One\n* TODO Two\n", encoding="utf-8")
    previous = _set_capture_templates(
        {
            "quick": {
                "file": str(target),
                "content": "* TODO Added\n:PROPERTIES:\n:ID: {{id}}\n:END:",
            },
        },
    )
    try:
        capture.run_tasks_capture(_make_capture_args("quick"))
    finally:
        _restore_capture_templates(previous)

    assert ":ID: 3" in target.read_text(encoding="utf-8")


def test_run_capture_document_fields_are_available_for_templating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture should render explicit document metadata placeholders without prompting."""
    target = tmp_path / "tasks.org"
    target.write_text(
        "#+TITLE: Project File\n"
        "#+AUTHOR: Jane Doe\n"
        "#+DESCRIPTION: Sprint tasks\n"
        "#+CATEGORY: Work\n"
        "* TODO Existing\n",
        encoding="utf-8",
    )
    previous = _set_capture_templates(
        {
            "quick": {
                "file": str(target),
                "content": (
                    "* TODO "
                    "cat={{document_category}} file={{document_filename}} "
                    "title={{document_title}} author={{document_author}} "
                    "desc={{document_description}}"
                ),
            },
        },
    )
    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.typer.prompt",
            lambda _msg, **_kwargs: (_ for _ in ()).throw(AssertionError("prompt not expected")),
        )
        capture.run_tasks_capture(_make_capture_args("quick"))
    finally:
        _restore_capture_templates(previous)

    updated = target.read_text(encoding="utf-8")
    assert "cat=Work" in updated
    assert f"file={target}" in updated
    assert "title=Project File" in updated
    assert "author=Jane Doe" in updated
    assert "desc=Sprint tasks" in updated


def test_run_capture_parent_fields_are_available_with_template_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture should expose parent_ placeholders when template parent is configured."""
    target = tmp_path / "tasks.org"
    target.write_text(
        "* TODO Project Parent\n:PROPERTIES:\n:ID: project-1\n:CATEGORY: Projects\n:END:\n",
        encoding="utf-8",
    )
    previous = _set_capture_templates(
        {
            "child": {
                "file": str(target),
                "parent": '.id == "project-1"',
                "content": (
                    "** TODO parent_cat={{parent_category}} "
                    "parent_title={{parent_title}} parent_todo={{parent_todo}} "
                    "parent_id={{parent_id}}"
                ),
            },
        },
    )
    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.typer.prompt",
            lambda _msg, **_kwargs: (_ for _ in ()).throw(AssertionError("prompt not expected")),
        )
        capture.run_tasks_capture(_make_capture_args("child"))
    finally:
        _restore_capture_templates(previous)

    updated = target.read_text(encoding="utf-8")
    assert "parent_cat=Projects" in updated
    assert "parent_title=Project Parent" in updated
    assert "parent_todo=TODO" in updated
    assert "parent_id=project-1" in updated


def test_run_capture_parent_fields_are_available_with_cli_parent_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture should expose parent_ placeholders with CLI --parent selector."""
    target = tmp_path / "tasks.org"
    target.write_text(
        "* TODO One\n:PROPERTIES:\n:ID: one\n:END:\n\n"
        "* TODO Two\n:PROPERTIES:\n:ID: two\n:CATEGORY: Focus\n:END:\n",
        encoding="utf-8",
    )
    previous = _set_capture_templates(
        {
            "child": {
                "file": str(target),
                "content": (
                    "** TODO parent_cat={{parent_category}} "
                    "parent_title={{parent_title}} parent_todo={{parent_todo}} "
                    "parent_id={{parent_id}}"
                ),
            },
        },
    )
    try:
        monkeypatch.setattr(
            "org.commands.tasks.capture.typer.prompt",
            lambda _msg, **_kwargs: (_ for _ in ()).throw(AssertionError("prompt not expected")),
        )
        capture.run_tasks_capture(_make_capture_args("child", parent='.id == "two"'))
    finally:
        _restore_capture_templates(previous)

    updated = target.read_text(encoding="utf-8")
    assert "parent_cat=Focus" in updated
    assert "parent_title=Two" in updated
    assert "parent_todo=TODO" in updated
    assert "parent_id=two" in updated
