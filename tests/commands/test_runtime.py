"""Tests for shared interactive runtime helpers."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.widgets import OptionList, Static

import org.tui.app
import org.tui.selection


if TYPE_CHECKING:
    from textual.app import ComposeResult


class _SelectionHarnessApp(org.tui.app.CommandApp):
    """Minimal app for exercising the shared selection modal."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "quit_app", show=False)]

    def __init__(self) -> None:
        super().__init__()
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        yield Vertical(Static("body"))

    def on_mount(self) -> None:
        self.push_screen(
            org.tui.selection.SelectionModalScreen(
                "Choose value",
                [
                    org.tui.selection.SelectionOption(value="alpha", label="alpha"),
                    org.tui.selection.SelectionOption(value="beta", label="beta"),
                ],
            ),
            callback=self._store_result,
        )

    def _store_result(self, value: str | None) -> None:
        self.result = value

    def action_quit_app(self) -> None:
        """Exit the harness app."""
        self.exit()


def test_selection_modal_supports_keyboard_navigation_and_submit() -> None:
    """Selection modal should support keyboard-only navigation and submit."""

    async def _run() -> None:
        app = _SelectionHarnessApp()

        async with app.run_test() as pilot:
            await pilot.pause()

            option_list = app.screen.query_one(OptionList)
            assert option_list.has_focus

            await pilot.press("down", "enter")
            await pilot.pause()

            assert app.result == "beta"

    asyncio.run(_run())


def test_selection_modal_escape_cancels_without_exiting_parent_app() -> None:
    """Escape should cancel the modal without triggering parent app bindings."""

    async def _run() -> None:
        app = _SelectionHarnessApp()

        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.screen.query_one("#selection-label", Static) is not None

            await pilot.press("escape")
            await pilot.pause()

            assert app.result is None
            assert app.is_running

    asyncio.run(_run())
