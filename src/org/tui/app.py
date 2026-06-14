"""Shared Textual app helpers for interactive command UIs."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import App, SuspendNotSupported


if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager


class CommandApp(App[None]):
    """Shared helpers for Textual-backed interactive command apps."""

    def suspend_for_external(self, callback: Callable[[], None]) -> None:
        """Suspend the app when possible around one blocking callback."""
        suspend = getattr(self, "suspend", None)
        if callable(suspend):
            try:
                with cast("AbstractContextManager[object]", suspend()):
                    callback()
            except SuspendNotSupported:
                callback()
        else:
            callback()

    def run_external_and_refresh(
        self,
        callback: Callable[[], None],
        *,
        refresh: Callable[[], None],
    ) -> None:
        """Suspend around one external action and refresh afterwards."""
        self.suspend_for_external(callback)
        refresh()
