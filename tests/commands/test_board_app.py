"""App tests for the board command."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import TYPE_CHECKING, Any, cast

from textual.widgets import Input, Static

from org import config as config_module
from org.commands import editor as editor_command
from org.commands.board import command as board_command
from org.commands.board import events as board_events
from org.commands.board.app import BoardApp, BoardViewport
from org.commands.interactive_common import heading_locator
from org.commands.tasks import capture as capture_command
from tests.commands.test_board import make_board_args
from tests.conftest import node_from_org


if TYPE_CHECKING:
    import pytest
    from org_parser.document import Heading


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _col(title: str, nodes: list[Heading]) -> board_events.BoardColumn:
    return board_events.BoardColumn(title, nodes)


def _make_session(
    args: board_command.BoardArgs,
    nodes: list[Heading],
    **overrides: object,
) -> board_events.BoardSession:
    resolved_columns = cast("list[board_events.BoardColumn] | None", overrides.pop("columns", None))
    resolved_all_columns = cast(
        "list[board_events.BoardColumn] | None",
        overrides.pop("all_columns", None),
    )
    session = board_events.BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[_col("TODO", nodes)] if resolved_columns is None else resolved_columns,
        color_enabled=False,
        selected_column_index=0,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
        all_columns=[],
        search_text="",
    )
    session.all_columns = session.columns if resolved_all_columns is None else resolved_all_columns
    for key, value in overrides.items():
        setattr(session, key, value)
    return session


def _make_app(session: board_events.BoardSession) -> BoardApp:
    return BoardApp(session)


def _visible_board_titles_by_column(app: BoardApp) -> dict[str, list[str]]:
    return {
        column.title: [node.title_text for node in column.nodes] for column in app.session.columns
    }


def test_board_app_navigation_help_and_separators() -> None:
    """Board app should support navigation, help forwarding, and footer separators."""

    async def _run() -> None:
        first, second = node_from_org("* TODO First\n* TODO Second\n")
        session = _make_session(
            make_board_args([]),
            [first, second],
            columns=[
                _col("Backlog", []),
                _col("TODO", [first]),
                _col("WAITING", []),
                _col("INPROGRESS", [second]),
            ],
            selected_column_index=1,
        )
        app = _make_app(session)

        async with app.run_test() as pilot:
            assert app.screen.query_one("#board-footer-rule", Static) is not None

            await pilot.press("down")
            assert app.session.selected_row_index == 0

            await pilot.press("right")
            assert app.session.selected_column_index == 3

            await pilot.press("left")
            assert app.session.selected_column_index == 1
            app.action_show_help()
            await pilot.pause()

            assert app.screen.query_one("#help-content", Static) is not None
            await pilot.press("right")
            await pilot.pause()

            assert app.session.selected_column_index == 3
            assert app.screen.query_one("#board-body", BoardViewport) is not None

    asyncio.run(_run())


def test_board_app_search_prompt_filters_columns_live_and_escape_restores() -> None:
    """Search modal should live-filter each column and escape should restore the previous search."""

    async def _run() -> None:
        alpha, beta, beta_done = node_from_org("* TODO Alpha\n* TODO Beta\n* DONE Beta done\n")
        all_columns = [
            _col("Backlog", []),
            _col("TODO", [alpha, beta]),
            _col("DONE", [beta_done]),
        ]
        session = _make_session(
            make_board_args([]),
            [alpha, beta, beta_done],
            columns=all_columns,
            all_columns=all_columns,
            selected_column_index=1,
        )
        app = _make_app(session)

        async with app.run_test() as pilot:
            app.action_prompt_search()
            await pilot.pause()

            prompt_input = app.screen.query_one(Input)
            prompt_input.value = "beta"
            prompt_screen = cast("Any", app.screen_stack[-1])
            prompt_screen.on_input_changed(Input.Changed(prompt_input, "beta"))

            assert app.session.search_text == "beta"
            assert _visible_board_titles_by_column(app) == {
                "Backlog": [],
                "TODO": ["Beta"],
                "DONE": ["Beta done"],
            }

            await pilot.press("escape")
            await pilot.pause()

            assert app.session.search_text == ""
            assert app.session.status_message == "Search cancelled"
            assert _visible_board_titles_by_column(app) == {
                "Backlog": [],
                "TODO": ["Alpha", "Beta"],
                "DONE": ["Beta done"],
            }

    asyncio.run(_run())


def test_board_app_enter_edits_selected_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enter should trigger external-editor handling on the selected task card."""

    async def _run() -> None:
        nodes = node_from_org("* TODO Task\n")
        monkeypatch.setattr(
            board_events,
            "edit_heading_subtree_in_external_editor",
            lambda _heading: editor_command.DocumentEditResult(changed=False),
        )
        app = _make_app(_make_session(make_board_args([]), nodes))

        async with app.run_test() as pilot:
            await pilot.press("enter")
            assert app.session.status_message == "No changes."

    asyncio.run(_run())


def test_board_app_capture_prompt_submits_and_reloads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Capture prompt submission should create a task and reload board state."""

    async def _run() -> None:
        nodes = node_from_org("* TODO Existing\n")
        captured_node = node_from_org("* TODO Captured\n")[0]
        reloaded: dict[str, object] = {}
        monkeypatch.setattr(
            config_module,
            "CONFIG_CAPTURE_TEMPLATES",
            {"quick": {"file": "tasks.org", "content": "* TODO Captured"}},
        )
        monkeypatch.setattr(
            board_events,
            "capture_task",
            lambda _args: capture_command.TasksCaptureResult(
                template_name="quick",
                heading=captured_node,
                document=captured_node.document,
            ),
        )
        monkeypatch.setattr(
            board_events,
            "reload_session",
            lambda _session, preserve_identity: reloaded.update(identity=preserve_identity),
        )

        app = _make_app(_make_session(make_board_args([]), nodes))

        async with app.run_test() as pilot:
            app.action_prompt_capture()
            await pilot.pause()
            app.screen_stack[-1].dismiss("1")
            await pilot.pause()

            assert reloaded["identity"] == heading_locator(captured_node)
            assert app.session.status_message == "Task captured"

    asyncio.run(_run())


def test_board_app_capture_without_templates_sets_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Capture should report a clear status when no templates are configured."""

    async def _run() -> None:
        monkeypatch.setattr(config_module, "CONFIG_CAPTURE_TEMPLATES", {})
        app = _make_app(_make_session(make_board_args([]), node_from_org("* TODO Existing\n")))

        async with app.run_test():
            app.action_prompt_capture()
            assert app.session.status_message == "No capture templates configured"

    asyncio.run(_run())


def test_board_app_shift_bindings_trigger_state_and_priority_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shift actions should dispatch state and priority mutations."""

    async def _run() -> None:
        calls: list[str] = []
        monkeypatch.setattr(
            board_events,
            "apply_state_move",
            lambda _session, *, direction: calls.append(f"state:{direction}"),
        )
        monkeypatch.setattr(
            board_events,
            "apply_priority_shift",
            lambda _session, *, increase: calls.append(f"priority:{increase}"),
        )
        app = _make_app(_make_session(make_board_args([]), node_from_org("* TODO Existing\n")))

        async with app.run_test():
            app.action_move_state_left()
            app.action_move_state_right()
            app.action_increase_priority()
            app.action_decrease_priority()

            assert calls == ["state:-1", "state:1", "priority:True", "priority:False"]

    asyncio.run(_run())


def test_run_flow_board_interactive_uses_app_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Interactive board path should delegate to the Textual app runner."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], days=100000)
    called = {"value": False}

    def _fake_run(
        passed_args: board_command.BoardArgs,
        nodes: list[Heading],
        todo_states: list[str],
        done_states: list[str],
        color_enabled: bool,
    ) -> None:
        called["value"] = True
        assert passed_args.files == [fixture_path]
        assert nodes
        assert todo_states
        assert done_states
        assert color_enabled is False

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("org.commands.board.command.run_board_app", _fake_run)

    board_command.run_flow_board(args)

    assert called["value"] is True
