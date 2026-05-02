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
BRACKETED_PASTE_ENABLE = "\x1b[?2004h"
BRACKETED_PASTE_DISABLE = "\x1b[?2004l"
BRACKETED_PASTE_START = b"\x1b[200~"
BRACKETED_PASTE_END = b"\x1b[201~"


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


def read_escape_sequence(fd: int) -> bytes:
    """Read one terminal escape sequence from stdin."""
    payload = bytearray(b"\x1b")
    ready, _, _ = select.select([fd], [], [], 0.01)
    if not ready:
        return bytes(payload)

    payload.extend(os.read(fd, 1))

    second = payload[-1:]
    if second != b"[":
        return bytes(payload)

    for _ in range(32):
        ready, _, _ = select.select([fd], [], [], 0.002)
        if not ready:
            break
        next_byte = os.read(fd, 1)
        payload.extend(next_byte)
        if next_byte in {b"~", b"M", b"m"}:
            break
        if next_byte.isalpha():
            break

    return bytes(payload)


def read_bracketed_paste_payload(fd: int, initial_payload: bytes) -> bytes:
    """Read remaining bytes until bracketed-paste end marker is received."""
    payload = bytearray(initial_payload)
    while BRACKETED_PASTE_END not in payload:
        ready, _, _ = select.select([fd], [], [], 0.05)
        if not ready:
            break
        payload.extend(os.read(fd, 1024))
    return bytes(payload)


def extract_bracketed_paste_text(payload: bytes) -> str | None:
    """Extract decoded text from a bracketed-paste payload."""
    if not payload.startswith(BRACKETED_PASTE_START):
        return None
    end_index = payload.find(BRACKETED_PASTE_END)
    if end_index < 0:
        return ""

    text_bytes = payload[len(BRACKETED_PASTE_START) : end_index]
    try:
        return text_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return text_bytes.decode("utf-8", errors="ignore")


def read_available_bytes(fd: int) -> bytes:
    """Read currently available bytes from stdin with short timeout."""
    payload = bytearray()
    ready, _, _ = select.select([fd], [], [], 0.05)
    if not ready:
        return b""

    payload.extend(os.read(fd, 1024))
    while True:
        ready, _, _ = select.select([fd], [], [], 0.01)
        if not ready:
            break
        payload.extend(os.read(fd, 1024))
    return bytes(payload)


def _utf8_char_width(first_byte: int) -> int:
    """Return expected UTF-8 byte width for one first byte."""
    if first_byte & 0b1000_0000 == 0:
        return 1
    if first_byte & 0b1110_0000 == 0b1100_0000:
        return 2
    if first_byte & 0b1111_0000 == 0b1110_0000:
        return 3
    if first_byte & 0b1111_1000 == 0b1111_0000:
        return 4
    return 1


def _has_control_characters(text: str) -> bool:
    """Return whether text contains ASCII control characters."""
    return any(ord(char) < 32 or ord(char) == 127 for char in text)


def read_utf8_input_text(fd: int, first_byte: bytes) -> str | None:
    """Read one UTF-8 input text value from initial first byte."""
    utf8_bytes = bytearray(first_byte)
    expected = _utf8_char_width(first_byte[0])
    while len(utf8_bytes) < expected:
        ready, _, _ = select.select([fd], [], [], 0.01)
        if not ready:
            break
        utf8_bytes.extend(os.read(fd, 1))

    try:
        text = bytes(utf8_bytes).decode("utf-8")
    except UnicodeDecodeError:
        return None
    if _has_control_characters(text):
        return None
    return text


def _decode_bytes_payload(payload: bytes) -> str:
    """Decode byte payload as UTF-8 with lossy fallback."""
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload.decode("utf-8", errors="ignore")


def _read_ctrl_p_paste_event(fd: int) -> tuple[str, str]:
    """Read one Ctrl-P paste event payload."""
    payload = read_available_bytes(fd)
    bracketed_text = extract_bracketed_paste_text(payload)
    if bracketed_text is not None:
        return ("TEXT", bracketed_text)
    return ("TEXT", _decode_bytes_payload(payload))


def _read_escape_input_event(
    fd: int,
    token_map: dict[str, str] | None,
) -> tuple[str, str]:
    """Read one escape-sequence input event."""
    escape_sequence = read_escape_sequence(fd)
    if escape_sequence.startswith(BRACKETED_PASTE_START):
        bracketed_payload = read_bracketed_paste_payload(fd, escape_sequence)
        pasted_text = extract_bracketed_paste_text(bracketed_payload)
        return ("IGNORE", "") if pasted_text is None else ("TEXT", pasted_text)

    if escape_sequence == b"\x1b[3~":
        return ("DELETE", "")

    escape_token = decode_escape_sequence(escape_sequence)
    defaults = {
        "LEFT": "LEFT",
        "RIGHT": "RIGHT",
        "HOME": "HOME",
        "END": "END",
        "ESC": "ESC",
    }
    event_map = defaults if token_map is None else token_map
    return (event_map.get(escape_token, "IGNORE"), "")


def read_input_event(
    fd: int,
    *,
    token_map: dict[str, str] | None = None,
    ctrl_p_as_paste: bool = False,
) -> tuple[str, str]:
    """Read one input event token and optional text payload."""
    first = os.read(fd, 1)
    if first in {b"\r", b"\n"}:
        return ("ENTER", "")
    if first == b"\x03":
        raise KeyboardInterrupt
    if first in {b"\x7f", b"\x08"}:
        return ("BACKSPACE", "")

    if first == b"\x10" and ctrl_p_as_paste:
        return _read_ctrl_p_paste_event(fd)

    if first == b"\x1b":
        return _read_escape_input_event(fd, token_map)

    text = read_utf8_input_text(fd, first)
    if text is None:
        return ("IGNORE", "")
    return ("TEXT", text)


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


def set_bracketed_paste(enabled: bool) -> None:
    """Enable or disable terminal bracketed paste mode."""
    if not sys.stdout.isatty():
        return

    sequence = BRACKETED_PASTE_ENABLE if enabled else BRACKETED_PASTE_DISABLE
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
            return decode_escape_sequence(read_escape_sequence(fd))
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
