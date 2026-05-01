"""Shared helpers for interactive command-mode UIs."""

from __future__ import annotations

import os
import select
import sys
import termios
import tty
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from org_parser.element import Repeat
from org_parser.time import Timestamp
from rich.syntax import Syntax

from org.output_format import DEFAULT_OUTPUT_THEME


if TYPE_CHECKING:
    from collections.abc import Mapping

    from org_parser.document import Heading
    from rich.console import Console


class _KeyHandler(Protocol):
    """Type protocol for interactive key handler callbacks."""

    def __call__(self) -> bool | None:
        """Run key handler callback and return optional continue-loop flag."""


MOUSE_REPORTING_ENABLE = "\x1b[?1000h\x1b[?1006h"
MOUSE_REPORTING_DISABLE = "\x1b[?1000l\x1b[?1006l"


@dataclass(frozen=True)
class HeadingIdentity:
    """Stable identity used to restore selected heading across reloads."""

    filename: str
    heading_id: str | None
    title: str
    todo: str | None
    priority: str | None
    scheduled: str | None
    deadline: str | None


@dataclass(frozen=True)
class KeyBinding:
    """One interactive key binding and optional live-pause requirement."""

    handler: _KeyHandler
    requires_live_pause: bool = False


@dataclass(frozen=True)
class KeyDispatchResult:
    """Result of dispatching one keypress against key bindings."""

    handled: bool
    continue_loop: bool
    requires_live_pause: bool


def key_binding_for_action(
    action: _KeyHandler,
    *,
    requires_live_pause: bool = False,
) -> KeyBinding:
    """Build one key binding from a void action callback."""

    def _handler() -> bool:
        action()
        return True

    return KeyBinding(_handler, requires_live_pause=requires_live_pause)


def dispatch_key_binding(
    key: str,
    bindings: Mapping[str, KeyBinding],
) -> KeyDispatchResult:
    """Dispatch one keypress to a key-binding map."""
    binding = bindings.get(key)
    if binding is None:
        return KeyDispatchResult(handled=False, continue_loop=True, requires_live_pause=False)

    outcome = binding.handler()
    continue_loop = True if outcome is None else outcome
    return KeyDispatchResult(
        handled=True,
        continue_loop=continue_loop,
        requires_live_pause=binding.requires_live_pause,
    )


def key_binding_requires_live_pause(
    key: str,
    bindings: Mapping[str, KeyBinding],
) -> bool:
    """Return whether one key binding requires temporarily stopping Live."""
    binding = bindings.get(key)
    if binding is None:
        return False
    return binding.requires_live_pause


def local_now() -> datetime:
    """Return local timezone-aware current datetime."""
    return datetime.now(tz=UTC).astimezone()


def shift_priority(priority: str | None, *, increase: bool) -> str | None:
    """Shift priority one step across A/B/C/none."""
    order: list[str | None] = ["A", "B", "C", None]
    normalized = priority if priority in {"A", "B", "C"} else None
    index = order.index(normalized)
    if increase:
        return order[max(0, index - 1)]
    return order[min(len(order) - 1, index + 1)]


def heading_identity(node: Heading) -> HeadingIdentity:
    """Build stable heading identity for selection restoration."""
    return HeadingIdentity(
        filename=node.document.filename or "",
        heading_id=node.id,
        title=node.title_text,
        todo=node.todo,
        priority=node.priority,
        scheduled=str(node.scheduled) if node.scheduled is not None else None,
        deadline=str(node.deadline) if node.deadline is not None else None,
    )


def heading_identity_matches(node: Heading, identity: HeadingIdentity) -> bool:
    """Return whether node matches preserved heading identity."""
    same_file = (node.document.filename or "") == identity.filename
    if not same_file:
        return False

    if identity.heading_id is not None:
        return node.id == identity.heading_id

    return (
        node.title_text == identity.title
        and node.todo == identity.todo
        and node.priority == identity.priority
        and (str(node.scheduled) if node.scheduled is not None else None) == identity.scheduled
        and (str(node.deadline) if node.deadline is not None else None) == identity.deadline
    )


def append_repeat_transition(
    heading: Heading,
    before: str | None,
    after: str | None,
    now: datetime,
) -> None:
    """Append one repeat transition entry at current time."""
    transition_time = now.replace(second=0, microsecond=0)
    repeat = Repeat(
        before=before,
        after=after,
        timestamp=Timestamp.from_datetime(transition_time, is_active=False),
    )
    heading.repeats.append(repeat)


def decode_mouse_sequence(sequence: bytes) -> str | None:
    """Decode xterm SGR mouse sequence into command token."""
    if not sequence.startswith(b"\x1b[<"):
        return None
    if sequence[-1:] not in {b"M", b"m"}:
        return None

    try:
        body = sequence[3:-1].decode("ascii")
        cb_text, _col_text, _row_text = body.split(";", 2)
        cb = int(cb_text)
    except UnicodeDecodeError, ValueError:
        return "UNSUPPORTED-MOUSE"

    if cb & 64 == 0:
        result = "UNSUPPORTED-MOUSE"
    elif cb & 4:
        result = "UNSUPPORTED-SHIFT-WHEEL"
    else:
        button = cb & 0b11
        result = {0: "WHEEL-UP", 1: "WHEEL-DOWN"}.get(button, "UNSUPPORTED-MOUSE")

    return result


def decode_escape_sequence(sequence: bytes) -> str:
    """Decode terminal escape sequence into one key token."""
    mapping = {
        b"\x1b[A": "UP",
        b"\x1b[B": "DOWN",
        b"\x1b[1;2A": "S-UP",
        b"\x1b[1;2B": "S-DOWN",
        b"\x1b[1;2C": "S-RIGHT",
        b"\x1b[1;2D": "S-LEFT",
        b"\x1b[;2A": "S-UP",
        b"\x1b[;2B": "S-DOWN",
        b"\x1b[;2C": "S-RIGHT",
        b"\x1b[;2D": "S-LEFT",
        b"\x1b[C": "RIGHT",
        b"\x1b[D": "LEFT",
    }
    mapped = mapping.get(sequence)
    if mapped is not None:
        return mapped

    if sequence == b"\x1b":
        return "ESC"

    mouse_token = decode_mouse_sequence(sequence)
    if mouse_token is not None:
        return mouse_token

    return f"UNSUPPORTED-ESC:{sequence.hex()}"


def set_mouse_reporting(enabled: bool) -> None:
    """Enable or disable terminal mouse reporting."""
    if not sys.stdout.isatty():
        return

    sequence = MOUSE_REPORTING_ENABLE if enabled else MOUSE_REPORTING_DISABLE
    try:
        sys.stdout.write(sequence)
        sys.stdout.flush()
    except OSError:
        return


def read_keypress(timeout_seconds: float | None = None) -> str:
    """Read one keypress and normalize to a command token."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        if timeout_seconds is not None:
            ready, _, _ = select.select([fd], [], [], timeout_seconds)
            if not ready:
                return ""
        first = os.read(fd, 1)
        if first == b"\x03":
            return "q"
        if first in {b"\r", b"\n"}:
            return "ENTER"
        if first == b"\x1b":
            payload = bytearray(first)
            while True:
                ready, _, _ = select.select([fd], [], [], 0.01)
                if not ready:
                    break
                payload.extend(os.read(fd, 1))
            return decode_escape_sequence(bytes(payload))
        try:
            return first.decode("utf-8").lower()
        except UnicodeDecodeError:
            return ""
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def detail_org_block(node: Heading) -> str:
    """Build detailed org block text for one heading subtree."""
    filename = node.document.filename or "unknown"
    node_text = node.render().rstrip()
    return f"# {filename}\n{node_text}" if node_text else f"# {filename}"


def open_task_detail_in_pager(console: Console, node: Heading, *, color_enabled: bool) -> None:
    """Open task detail in pager with Org syntax highlighting."""
    detail = Syntax(
        detail_org_block(node),
        "org",
        theme=DEFAULT_OUTPUT_THEME,
        line_numbers=False,
        word_wrap=True,
    )
    with console.pager(styles=color_enabled):
        console.print(detail)
