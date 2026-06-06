"""App tests for the agenda command."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

import org_parser
from textual.widgets import Input, Static

from org import config as config_module
from org.commands.agenda import command as agenda_command
from org.commands.agenda import events as agenda_events
from org.commands.agenda import layout as agenda_layout
from org.commands.agenda.app import AgendaApp, AgendaViewport
from org.commands.agenda.views import (
    AgendaViewContext,
    _compile_view_section_specs,
    _fallback_agenda_view,
)
from org.commands.tasks import capture as capture_command
from tests.commands.test_agenda_command import _make_args


if TYPE_CHECKING:
    import pytest
    from org_parser.document import Heading


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _make_app(
    args: agenda_command.AgendaArgs,
    nodes: list[Heading],
    *,
    color_enabled: bool = False,
) -> AgendaApp:
    view = _fallback_agenda_view()
    view_ctx = AgendaViewContext(section_specs=_compile_view_section_specs(view), name=view.name)
    render = agenda_layout.RenderContext(
        color_enabled=color_enabled,
        done_states=["DONE"],
        todo_states=["TODO"],
    )
    return AgendaApp(agenda_events.create_agenda_session(args, nodes, render, view_ctx))


def _body_lines(app: AgendaApp) -> list[str]:
    lines: list[str] = []
    for widget in app._body_widget().row_widgets():
        rendered = cast("Any", widget.render())
        lines.append(getattr(rendered, "plain", str(rendered)))
    return lines


def test_agenda_app_moves_selection_with_arrow_keys() -> None:
    """Arrow-key navigation should update the selected agenda row."""

    async def _run() -> None:
        fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
        args = _make_args([fixture_path], date="2025-01-15")
        app = _make_app(args, list(org_parser.load(fixture_path)))

        async with app.run_test() as pilot:
            await pilot.press("down")
            assert app.session.selected_row_index == 1

            await pilot.press("up")
            assert app.session.selected_row_index == 0

    asyncio.run(_run())


def test_agenda_app_search_prompt_filters_results_live_and_escape_restores() -> None:
    """Search modal should live-filter rows and escape should restore the previous search."""

    async def _run() -> None:
        fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
        args = _make_args([fixture_path], date="2025-01-15")
        app = _make_app(args, list(org_parser.load(fixture_path)))

        async with app.run_test() as pilot:
            app.action_prompt_search()
            await pilot.pause()

            prompt_input = app.screen.query_one(Input)
            prompt_input.value = "focus"
            prompt_screen = cast("Any", app.screen_stack[-1])
            prompt_screen.on_input_changed(Input.Changed(prompt_input, "focus"))

            assert app.session.search_text == "focus"
            visible_titles = [
                row.node.title_text.strip()
                for day_model in app.session.day_models
                for row in day_model.rows
                if row.kind == "task" and row.node is not None
            ]
            assert visible_titles == ["Timed agenda task"]

            await pilot.press("escape")
            await pilot.pause()

            assert app.is_running
            assert app.session.search_text == ""
            assert app.session.status_message == "Search cancelled"

    asyncio.run(_run())


def test_agenda_app_help_modal_forwards_key_to_app() -> None:
    """Help modal should close and forward the pressed key to the agenda app."""

    async def _run() -> None:
        fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
        args = _make_args([fixture_path], date="2025-01-15")
        app = _make_app(args, list(org_parser.load(fixture_path)))

        async with app.run_test() as pilot:
            app.action_show_help()
            await pilot.pause()

            assert app.screen.query_one("#help-content", Static) is not None
            await pilot.press("down")
            await pilot.pause()

            assert app.session.selected_row_index == 1
            assert app.screen.query_one("#agenda-body", AgendaViewport) is not None

    asyncio.run(_run())


def test_agenda_app_pages_date_window_with_right_key() -> None:
    """Right-arrow paging should move the agenda start date by the current span."""

    async def _run() -> None:
        fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
        args = _make_args([fixture_path], date="2025-01-15", days=2)
        app = _make_app(args, list(org_parser.load(fixture_path)))

        async with app.run_test() as pilot:
            await pilot.press("right")
            await pilot.pause()

            header = cast("Any", app.query_one("#agenda-header", Static).render())
            assert getattr(header, "plain", str(header)) == "Friday 2025-01-17"

    asyncio.run(_run())


def test_agenda_app_timer_refresh_updates_now_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Minute refresh should update the rendered NOW marker in the viewport."""

    async def _run() -> None:
        fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
        args = _make_args([fixture_path], date="2025-01-15")
        clock = {"value": datetime(2025, 1, 15, 10, 0)}
        monkeypatch.setattr(agenda_command, "local_now", lambda: clock["value"])
        monkeypatch.setattr(agenda_events, "local_now", lambda: clock["value"])
        monkeypatch.setattr(agenda_layout, "local_now", lambda: clock["value"])
        app = _make_app(args, list(org_parser.load(fixture_path)))

        async with app.run_test():
            assert any("10:00" in line and "NOW" in line for line in _body_lines(app))
            clock["value"] = datetime(2025, 1, 15, 10, 1)
            app._refresh_for_clock_tick()
            assert any("10:01" in line and "NOW" in line for line in _body_lines(app))

    asyncio.run(_run())


def test_agenda_app_enter_on_non_task_row_reports_status() -> None:
    """Enter on a non-task row should keep the app running and set a status message."""

    async def _run() -> None:
        fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
        args = _make_args([fixture_path], date="2025-01-15")
        app = _make_app(args, list(org_parser.load(fixture_path)))
        app.session.selected_row_index = next(
            index
            for index, (day_index, row_index) in enumerate(app.session.row_locations)
            if app.session.day_models[day_index].rows[row_index].kind == "hour_marker"
        )

        async with app.run_test():
            app.action_edit_selected()
            assert app.session.status_message == "Action available only on task rows"
            assert app.is_running

    asyncio.run(_run())


def test_agenda_app_capture_from_timed_row_schedules_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture on a timed agenda row should schedule the created task for that row time."""

    async def _run() -> None:
        fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
        args = _make_args([fixture_path], date="2025-01-15")
        captured_node = next(iter(org_parser.loads("* TODO Captured\n")))
        monkeypatch.setattr(
            config_module,
            "CONFIG_CAPTURE_TEMPLATES",
            {"quick": {"file": "tasks.org", "content": "* TODO Captured"}},
        )

        def _fake_capture(_args: object) -> capture_command.TasksCaptureResult:
            return capture_command.TasksCaptureResult(
                template_name="quick",
                heading=captured_node,
                document=captured_node.document,
            )

        monkeypatch.setattr(agenda_events, "capture_task", _fake_capture)
        monkeypatch.setattr(agenda_events, "_save_document_changes", lambda _document: None)
        monkeypatch.setattr(agenda_events, "_reload_session_nodes", lambda _session: None)

        app = _make_app(args, list(org_parser.load(fixture_path)))
        monkeypatch.setattr(agenda_events, "refresh_session", lambda _session, _identity: None)
        app.session.selected_row_index = next(
            index
            for index, (day_index, row_index) in enumerate(app.session.row_locations)
            if (
                app.session.day_models[day_index].rows[row_index].kind == "task"
                and ":" in app.session.day_models[day_index].rows[row_index].time_text
            )
        )
        selected_row = agenda_events.selected_row(app.session)
        assert selected_row is not None
        expected_timestamp = f"<2025-01-15 Wed {selected_row.time_text}>"

        async with app.run_test() as pilot:
            app.action_prompt_capture()
            await pilot.pause()
            app.screen_stack[-1].dismiss("1")
            await pilot.pause()

            assert str(captured_node.scheduled) == expected_timestamp
            assert (
                app.session.status_message
                == f"Task captured and scheduled for {expected_timestamp}"
            )

    asyncio.run(_run())


def test_run_agenda_interactive_uses_app_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Interactive agenda path should delegate to the Textual app runner."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15")
    called = {"value": False}

    def _fake_run(
        passed_args: agenda_command.AgendaArgs,
        nodes: list[Heading],
        render: agenda_layout.RenderContext,
        view_ctx: AgendaViewContext,
    ) -> None:
        called["value"] = True
        assert passed_args.files == [fixture_path]
        assert nodes
        assert render.todo_states == ["TODO"]
        assert view_ctx.name == "default"

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("org.commands.agenda.command.run_agenda_app", _fake_run)

    agenda_command.run_agenda(args)

    assert called["value"] is True
