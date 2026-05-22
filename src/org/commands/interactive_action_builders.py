"""Reusable builders for interactive command action maps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from org.commands.interactive_actions import (
    ActionResult,
    ExternalInteractiveAction,
    NoninteractiveAction,
    ViewAction,
)
from org.commands.tasks.common import configured_capture_template_names


if TYPE_CHECKING:
    from collections.abc import Callable


class _StatusSession(Protocol):
    """Session carrying a status message field."""

    status_message: str


def quit_view_action[SessionT]() -> ViewAction[SessionT]:
    """Build standard quit action for interactive keymaps."""
    return ViewAction(run=lambda _session: ActionResult(continue_loop=False))


def view_action[SessionT](run: Callable[[SessionT], None]) -> ViewAction[SessionT]:
    """Build view action from mutating function."""
    return ViewAction(run=_wrap_no_status(run))


def status_view_action[SessionT: _StatusSession](
    run: Callable[[SessionT], None],
) -> ViewAction[SessionT]:
    """Build view action that reports session status message."""
    return ViewAction(run=_wrap_with_status(run))


def status_noninteractive_action[SessionT: _StatusSession](
    run: Callable[[SessionT], None],
) -> NoninteractiveAction[SessionT]:
    """Build noninteractive action that reports session status message."""
    return NoninteractiveAction(run=_wrap_with_status(run))


def status_external_action[SessionT: _StatusSession](
    run: Callable[[SessionT], None],
) -> ExternalInteractiveAction[SessionT]:
    """Build external interactive action that reports session status message."""
    return ExternalInteractiveAction(run=_wrap_with_status(run))


def can_activate_configured_capture_templates[SessionT](_session: SessionT) -> ActionResult | None:
    """Validate that at least one capture template is configured."""
    if not configured_capture_template_names():
        return ActionResult(success=False, status_message="No capture templates configured")
    return None


def _wrap_no_status[SessionT](
    run: Callable[[SessionT], None],
) -> Callable[[SessionT], ActionResult]:
    """Wrap mutating callable returning no result into ActionResult."""

    def _wrapped(session: SessionT) -> ActionResult:
        run(session)
        return ActionResult()

    return _wrapped


def _wrap_with_status[SessionT: _StatusSession](
    run: Callable[[SessionT], None],
) -> Callable[[SessionT], ActionResult]:
    """Wrap mutating callable and map session status to ActionResult."""

    def _wrapped(session: SessionT) -> ActionResult:
        run(session)
        return ActionResult(status_message=session.status_message)

    return _wrapped
