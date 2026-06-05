"""App tests for tasks capture."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

from textual.widgets import Static, TextArea

from org import config as config_module
from org.commands.tasks import capture
from org.commands.tasks.capture.app import CaptureApp


if TYPE_CHECKING:
    from pathlib import Path


def _make_plan(tmp_path: Path) -> capture.CapturePlan:
    target = tmp_path / "tasks.org"
    config_path = tmp_path / "config.yaml"
    target.write_text("* TODO Existing\n", encoding="utf-8")
    config_path.write_text("", encoding="utf-8")
    previous = {
        "quick": {
            "file": str(target),
            "content": "* TODO {{title}} @{{owner}}",
        },
    }
    original = dict(config_module.CONFIG_CAPTURE_TEMPLATES)
    config_module.CONFIG_CAPTURE_TEMPLATES.clear()
    config_module.CONFIG_CAPTURE_TEMPLATES.update(previous)
    try:
        return capture.prepare_capture_plan(
            capture.TasksCaptureArgs(
                template_name="quick",
                config=str(config_path),
                file=None,
                parent=None,
                set_values=None,
            ),
            "quick",
        )
    finally:
        config_module.CONFIG_CAPTURE_TEMPLATES.clear()
        config_module.CONFIG_CAPTURE_TEMPLATES.update(original)


def test_capture_app_preview_updates_from_field_input(tmp_path: Path) -> None:
    """Editing a field should update the rendered preview."""

    async def _run() -> None:
        app = CaptureApp(_make_plan(tmp_path))
        async with app.run_test() as pilot:
            title_input = app.screen.query_one("#field-title", TextArea)
            owner_input = app.screen.query_one("#field-owner", TextArea)
            assert title_input.text == ""
            assert owner_input.text == ""

            await pilot.press("W", "r", "i", "t", "e")
            await pilot.pause()
            owner_input.focus()
            await pilot.pause()
            await pilot.press("J", "a", "n", "e")
            await pilot.pause()

            assert app.field_values["title"] == "Write"
            assert app.field_values["owner"] == "Jane"
            assert app._preview_values()["title"] == "Write"
            assert app._preview_values()["owner"] == "Jane"

    asyncio.run(_run())


def test_capture_app_textarea_keeps_newlines(tmp_path: Path) -> None:
    """Multiline field edits should be preserved in preview values."""

    async def _run() -> None:
        app = CaptureApp(_make_plan(tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("L", "i", "n", "e", "1", "enter", "L", "i", "n", "e", "2")
            await pilot.pause()

            assert app.field_values["title"] == "Line1\nLine2"
            assert app._preview_values()["title"] == "Line1\nLine2"

    asyncio.run(_run())


def test_capture_app_help_modal_shows_key_bindings(tmp_path: Path) -> None:
    """Question mark should open the shared help modal."""

    async def _run() -> None:
        app = CaptureApp(_make_plan(tmp_path))
        async with app.run_test() as pilot:
            app.action_show_help()
            await pilot.pause()
            title_widget = app.screen_stack[-1].query_one("#help-title", Static)
            rendered = cast("Any", title_widget).render()
            assert getattr(rendered, "plain", str(rendered)) == "Key bindings"

    asyncio.run(_run())


def test_capture_app_save_collects_form_values(tmp_path: Path) -> None:
    """Saving the form should return the current field values."""

    async def _run() -> None:
        app = CaptureApp(_make_plan(tmp_path))
        async with app.run_test() as pilot:
            owner_input = app.screen.query_one("#field-owner", TextArea)
            await pilot.press("W", "o", "r", "k")
            await pilot.pause()
            owner_input.focus()
            await pilot.pause()
            await pilot.press("S", "a", "m")
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()

        assert app.result_values is not None
        assert app.result_values["title"] == "Work"
        assert app.result_values["owner"] == "Sam"

    asyncio.run(_run())
