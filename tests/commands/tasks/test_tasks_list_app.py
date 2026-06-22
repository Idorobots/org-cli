"""App tests for the tasks list command."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

from textual.widgets import Input, OptionList, Static

import org.config.app
from org.commands.tasks.list import command as tasks_list
from org.commands.tasks.list.app import TasksListApp
from tests.commands.tasks.test_tasks_list import make_list_args
from tests.conftest import node_from_org


if TYPE_CHECKING:
    import pytest
    from org_parser.document import Heading


def _make_session_data(nodes: list[Heading]) -> tasks_list._TasksListSessionData:
    return tasks_list._TasksListSessionData(
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        color_enabled=False,
    )


def _default_config() -> org.config.app.AppConfig:
    return org.config.app.AppConfig(config_path=".org-cli.yaml")


def test_tasks_list_app_navigation_and_help_forwarding() -> None:
    """Tasks list app should support navigation and help key forwarding."""

    async def _run() -> None:
        nodes = node_from_org("* TODO A\n* TODO B\n")
        app = TasksListApp(make_list_args([]), _default_config(), _make_session_data(nodes))

        async with app.run_test() as pilot:
            await pilot.press("down")
            assert app.session.selected_index == 1

            await pilot.press("up")
            assert app.session.selected_index == 0

            app.action_show_help()
            await pilot.pause()

            help_title = app.screen.query_one("#help-title", Static)
            help_content = app.screen.query_one("#help-content", Static)
            title_rendered = cast("Any", help_title).render()
            rendered = cast("Any", help_content).render()
            title_text = getattr(title_rendered, "plain", str(title_rendered))
            plain_text = getattr(rendered, "plain", str(rendered))
            assert title_text == "Key bindings"
            assert "Key bindings:" not in plain_text
            assert "Esc/q" in plain_text

            await pilot.press("down")
            await pilot.pause()

            assert app.session.selected_index == 1
            assert app.screen.query_one("#tasks-body", Static) is not None

    asyncio.run(_run())


def test_tasks_list_app_search_prompt_filters_results_live() -> None:
    """Search prompt should update visible tasks through Textual input flow."""

    async def _run() -> None:
        nodes = node_from_org("* TODO Alpha\nBody\n* TODO Beta\nOther\n")
        app = TasksListApp(make_list_args([]), _default_config(), _make_session_data(nodes))

        async with app.run_test() as pilot:
            app.action_prompt_search()
            await pilot.pause()

            prompt_input = app.screen.query_one(Input)
            assert prompt_input.value == ""

            prompt_input.value = "alpha"
            prompt_screen = cast("Any", app.screen_stack[-1])
            prompt_screen.on_input_changed(Input.Changed(prompt_input, "alpha"))
            assert app.session.search_text == "alpha"
            assert [node.title_text for node in app.session.visible_nodes] == ["Alpha"]

            app.screen_stack[-1].dismiss("alpha")
            await pilot.pause()
            assert app.session.search_text == "alpha"
            assert [node.title_text for node in app.session.visible_nodes] == ["Alpha"]

    asyncio.run(_run())


def test_tasks_list_app_help_prompt_and_separator_widgets() -> None:
    """Search prompt label and footer separators should render correctly."""

    async def _run() -> None:
        nodes = node_from_org("* TODO Alpha\n")
        app = TasksListApp(make_list_args([]), _default_config(), _make_session_data(nodes))

        async with app.run_test() as pilot:
            assert app.screen.query_one("#tasks-footer-rule", Static) is not None

            app.action_prompt_search()
            await pilot.pause()

            prompt_label = app.screen.query_one("#prompt-label", Static)
            rendered = cast("Any", prompt_label).render()
            plain_text = getattr(rendered, "plain", str(rendered))
            assert "Search text" in plain_text

    asyncio.run(_run())


def test_tasks_list_app_escape_cancels_prompt_without_exiting() -> None:
    """Escape should dismiss the prompt modal without triggering app quit."""

    async def _run() -> None:
        nodes = node_from_org("* TODO Alpha\n* TODO Beta\n")
        app = TasksListApp(make_list_args([]), _default_config(), _make_session_data(nodes))

        async with app.run_test() as pilot:
            app.action_prompt_search()
            await pilot.pause()
            assert app.screen.query_one("#prompt-label", Static) is not None

            await pilot.press("escape")
            await pilot.pause()

            assert app.is_running
            assert app.session.status_message == "Search cancelled"
            assert app.screen.query_one("#tasks-body", Static) is not None

    asyncio.run(_run())


def test_tasks_list_app_capture_selection_uses_keyboard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Capture selection should be fully keyboard navigable."""

    async def _run() -> None:
        nodes = node_from_org("* TODO Alpha\n")
        config = _default_config()
        config.capture.templates = {"quick": {}, "later": {}}
        app = TasksListApp(make_list_args([]), config, _make_session_data(nodes))
        called: list[str] = []
        monkeypatch.setattr(
            "org.commands.tasks.list.actions.apply_capture_task",
            lambda _session, template_name: called.append(template_name),
        )

        async with app.run_test() as pilot:
            app.action_prompt_capture()
            await pilot.pause()

            option_list = app.screen.query_one(OptionList)
            assert option_list.has_focus

            await pilot.press("down", "enter")
            await pilot.pause()

            assert called == ["quick"]

    asyncio.run(_run())


def test_tasks_list_app_state_selection_uses_keyboard() -> None:
    """State selection should be fully keyboard navigable."""

    async def _run() -> None:
        nodes = node_from_org("* TODO Alpha\n")
        app = TasksListApp(make_list_args([]), _default_config(), _make_session_data(nodes))

        async with app.run_test() as pilot:
            app.action_prompt_state()
            await pilot.pause()

            option_list = app.screen.query_one(OptionList)
            assert option_list.has_focus

            await pilot.press("enter")
            await pilot.pause()

            assert nodes[0].todo == "TODO"

    asyncio.run(_run())


def test_run_tasks_list_interactive_uses_app_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Interactive tasks list path should delegate to the Textual app runner."""
    nodes = node_from_org("* TODO Alpha\n")
    data = _make_session_data(nodes)
    called = {"value": False}

    def _fake_run(
        args: tasks_list.ListArgs,
        _config: org.config.app.AppConfig,
        session_data: tasks_list._TasksListSessionData,
    ) -> None:
        called["value"] = True
        assert args.files == []
        assert session_data.nodes == nodes

    monkeypatch.setattr("org.commands.tasks.list.command.run_tasks_list_app", _fake_run)

    tasks_list._run_tasks_list_interactive(
        make_list_args([]),
        _default_config(),
        data,
    )

    assert called["value"] is True
