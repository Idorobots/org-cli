"""Shared interactive/noninteractive/view action dispatch for TUI commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from org.commands.interactive_common import (
    apply_footer_prompt_input_event,
    read_input_event_with_timeout,
)


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from org.commands.tasks.common import PromptActionConfig


@dataclass(frozen=True)
class ActionResult:
    """Result contract for all action executions."""

    success: bool = True
    status_message: str | None = None
    keep_prompt_open: bool = False
    continue_loop: bool = True


@dataclass
class PromptInteractiveAction[SessionT, TargetT]:
    """Prompt-driven task action requiring footer input."""

    prompt_config: PromptActionConfig
    apply_with_input: Callable[[SessionT, TargetT, str, list[str] | None], ActionResult]
    resolve_target: Callable[[SessionT], TargetT | None] | None = None
    options_factory: Callable[[SessionT], list[str] | None] | None = None
    can_activate: Callable[[SessionT], ActionResult | None] | None = None
    unavailable_status: str = "Action available only on task rows"
    requires_live_pause: bool = False

    def activate(self, session: SessionT) -> ActionResult:
        """Validate and reset prompt state before input."""
        if self.can_activate is not None:
            activation_check = self.can_activate(session)
            if activation_check is not None:
                return activation_check

        if self.resolve_target is not None:
            target = self.resolve_target(session)
            if target is None:
                return ActionResult(success=False, status_message=self.unavailable_status)

        prompt = self.prompt_config.prompt
        prompt.value = ""
        prompt.cursor_position = 0
        prompt.error_message = ""
        return ActionResult()

    def submit(self, session: SessionT) -> ActionResult:
        """Submit active prompt input to action implementation."""
        if self.resolve_target is None:
            return ActionResult(success=False)

        target = self.resolve_target(session)
        if target is None:
            return ActionResult(success=False, status_message=self.unavailable_status)

        options = None if self.options_factory is None else self.options_factory(session)
        return self.apply_with_input(session, target, self.prompt_config.prompt.value, options)


@dataclass(frozen=True)
class ExternalInteractiveAction[SessionT]:
    """Interactive action delegated to external TUI flow (edit/capture)."""

    run: Callable[[SessionT], ActionResult]
    requires_live_pause: bool = True


@dataclass(frozen=True)
class NoninteractiveAction[SessionT]:
    """Task action that executes immediately without prompt."""

    run: Callable[[SessionT], ActionResult]
    requires_live_pause: bool = False


@dataclass(frozen=True)
class ViewAction[SessionT]:
    """TUI state/view action that executes immediately."""

    run: Callable[[SessionT], ActionResult]
    requires_live_pause: bool = False


@runtime_checkable
class PromptInteractiveActionContract[SessionT](Protocol):
    """Protocol for prompt-driven interactive actions bound to one session type."""

    requires_live_pause: bool
    prompt_config: PromptActionConfig

    def activate(self, session: SessionT) -> ActionResult:
        """Activate prompt state for this action."""
        ...

    def submit(self, session: SessionT) -> ActionResult:
        """Submit active prompt input for this action."""
        ...


type SessionAction[SessionT] = (
    PromptInteractiveActionContract[SessionT]
    | ExternalInteractiveAction[SessionT]
    | NoninteractiveAction[SessionT]
    | ViewAction[SessionT]
)


@dataclass(frozen=True)
class ActionDispatchResult:
    """Key dispatch outcome for generic action maps."""

    handled: bool
    continue_loop: bool
    requires_live_pause: bool


class ActionHostSession(Protocol):
    """Protocol implemented by interactive command sessions."""

    active_interactive_action: PromptInteractiveActionContract[Self] | None
    status_message: str


def dispatch_action_key[SessionT: ActionHostSession](
    key: str,
    session: SessionT,
    bindings: Mapping[str, SessionAction[SessionT]],
) -> ActionDispatchResult:
    """Dispatch one key against interactive/noninteractive/view action map."""
    action = bindings.get(key)
    if action is None:
        return ActionDispatchResult(handled=False, continue_loop=True, requires_live_pause=False)

    if isinstance(action, PromptInteractiveActionContract):
        result = action.activate(session)
        _apply_action_result(session, result)
        if result.continue_loop and result.success:
            session.active_interactive_action = action
        return ActionDispatchResult(
            handled=True,
            continue_loop=result.continue_loop,
            requires_live_pause=action.requires_live_pause,
        )

    result = action.run(session)
    _apply_action_result(session, result)
    return ActionDispatchResult(
        handled=True,
        continue_loop=result.continue_loop,
        requires_live_pause=action.requires_live_pause,
    )


def handle_active_interactive_action_input[SessionT: ActionHostSession](
    session: SessionT,
    *,
    refresh: Callable[[], None],
    timeout_seconds: float = 0.2,
) -> bool:
    """Handle one input event for the active interactive prompt action."""
    action = session.active_interactive_action
    if action is None:
        return False

    event = read_input_event_with_timeout(timeout_seconds, ctrl_p_as_paste=True)
    if event is None:
        refresh()
        return True

    event_name, event_text = event
    if event_name == "ESC":
        session.active_interactive_action = None
        session.status_message = "Input cancelled"
        refresh()
        return True

    if event_name == "IGNORE":
        refresh()
        return True

    prompt = action.prompt_config.prompt
    if apply_footer_prompt_input_event(prompt, event_name, event_text):
        result = action.submit(session)
        _apply_action_result(session, result)
        if result.keep_prompt_open:
            if result.status_message is not None:
                prompt.error_message = result.status_message
        else:
            session.active_interactive_action = None

    refresh()
    return True


def action_requires_live_pause[SessionT](
    key: str,
    bindings: Mapping[str, SessionAction[SessionT]],
) -> bool:
    """Return whether mapped action requires pausing live rendering."""
    action = bindings.get(key)
    if action is None:
        return False
    return action.requires_live_pause


def _apply_action_result(session: ActionHostSession, result: ActionResult) -> None:
    """Apply one action result to session state."""
    if result.status_message is not None:
        session.status_message = result.status_message
