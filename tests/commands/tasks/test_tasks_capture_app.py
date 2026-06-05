"""App tests for tasks capture."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

from textual.widgets import Static, TextArea

from org.commands.tasks import capture
from org.commands.tasks.capture.app import CaptureApp


if TYPE_CHECKING:
    from org_parser.document import Document, Heading


def _make_plan() -> capture.CapturePlan:
    return capture.CapturePlan(
        args=capture.TasksCaptureArgs(
            template_name="quick",
            config="unused.yaml",
            file=None,
            parent=None,
            set_values=None,
        ),
        template_name="quick",
        template_content="* TODO {{title}} @{{owner}}",
        document=cast("Document", object()),
        parent_heading=cast("Heading | None", None),
        placeholders=["title", "owner"],
        values={},
        unresolved_placeholders=["title", "owner"],
    )


def test_capture_app_preview_updates_from_field_input() -> None:
    """Editing a field should update the rendered preview."""

    async def _run() -> None:
        app = CaptureApp(_make_plan())
        async with app.run_test():
            title_input = app.screen.query_one("#field-title", TextArea)
            owner_input = app.screen.query_one("#field-owner", TextArea)
            assert title_input.text == ""
            assert owner_input.text == ""

            title_input.load_text("Write")
            app.on_text_area_changed(TextArea.Changed(title_input))
            owner_input.load_text("Jane")
            app.on_text_area_changed(TextArea.Changed(owner_input))

            assert app.field_values["title"] == "Write"
            assert app.field_values["owner"] == "Jane"
            assert app._preview_values()["title"] == "Write"
            assert app._preview_values()["owner"] == "Jane"

    asyncio.run(_run())


def test_capture_app_textarea_keeps_newlines() -> None:
    """Multiline field edits should be preserved in preview values."""

    async def _run() -> None:
        app = CaptureApp(_make_plan())
        async with app.run_test():
            title_input = app.screen.query_one("#field-title", TextArea)
            title_input.load_text("Line1\nLine2")
            app.on_text_area_changed(TextArea.Changed(title_input))

            assert app.field_values["title"] == "Line1\nLine2"
            assert app._preview_values()["title"] == "Line1\nLine2"

    asyncio.run(_run())


def test_capture_app_help_modal_shows_key_bindings() -> None:
    """Question mark should open the shared help modal."""

    async def _run() -> None:
        app = CaptureApp(_make_plan())
        async with app.run_test() as pilot:
            app.action_show_help()
            await pilot.pause()
            title_widget = app.screen_stack[-1].query_one("#help-title", Static)
            rendered = cast("Any", title_widget).render()
            assert getattr(rendered, "plain", str(rendered)) == "Key bindings"

    asyncio.run(_run())


def test_capture_app_save_collects_form_values() -> None:
    """Saving the form should return the current field values."""

    async def _run() -> None:
        app = CaptureApp(_make_plan())
        async with app.run_test():
            app.field_values["title"] = "Work"
            app.field_values["owner"] = "Sam"
            app.action_save_capture()

        assert app.result_values is not None
        assert app.result_values["title"] == "Work"
        assert app.result_values["owner"] == "Sam"

    asyncio.run(_run())
