"""Shared helpers for interactive command-mode UIs."""

from __future__ import annotations

import os
import select
import sys
import termios
import tty
from typing import TYPE_CHECKING

from org_parser.element import Repeat
from org_parser.time import Timestamp
from rich.syntax import Syntax

from org.output_format import DEFAULT_OUTPUT_THEME


if TYPE_CHECKING:
    from datetime import datetime

    from org_parser.document import Heading
    from rich.console import Console


MOUSE_REPORTING_ENABLE = "\x1b[?1000h\x1b[?1006h"
MOUSE_REPORTING_DISABLE = "\x1b[?1000l\x1b[?1006l"


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
