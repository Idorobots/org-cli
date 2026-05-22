"""Shared helpers for interactive command-mode UIs."""

from __future__ import annotations

import calendar
import os
import select
import sys
import termios
import tty
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from org_parser.element import Repeat
from org_parser.time import Timestamp
from rich.console import Console, Group, RenderableType
from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from org.output_format import DEFAULT_OUTPUT_THEME


if TYPE_CHECKING:
    from collections.abc import Mapping

    from org_parser.document import Heading


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
INTERACTIVE_HELP_FOOTER_HINT = "Type ? for help"
INTERACTIVE_HELP_CLOSE_HINT = "Press any key to return"
INTERACTIVE_HELP_CLI_NOTE = (
    "In interactive mode, press ? to open key bindings help (press any key to close)."
)


@dataclass(frozen=True)
class InteractiveHelpEntry:
    """One key binding entry for interactive help rendering."""

    key: str
    description: str


@dataclass(frozen=True)
class HeadingLocator:
    """Stable heading locator used to restore selection across reloads."""

    filename: str
    heading_id: str | None
    title: str


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


@dataclass
class FooterPromptState:
    """Editable footer prompt state shared by interactive TUIs."""

    label: str
    value: str = ""
    cursor_position: int = 0
    error_message: str = ""


def render_interactive_help_panel_text(entries: list[InteractiveHelpEntry]) -> str:
    """Render key bindings as plain help text lines."""
    key_width = max(12, max((len(entry.key) for entry in entries), default=0) + 1)
    lines = ["[white not dim]Key bindings:[/]"]
    for entry in entries:
        key_text = escape(f"{entry.key:<{key_width}}")
        description_text = escape(entry.description)
        lines.append(f"  [bold white not dim]{key_text}[/][white not dim]{description_text}[/]")
    return "\n".join(lines)


def interactive_help_command_text(base_text: str, entries: list[InteractiveHelpEntry]) -> str:
    """Append shared interactive-help note and key-bindings panel to help text."""
    normalized = " ".join(base_text.split())
    panel_text = render_interactive_help_panel_text(entries)
    return f"{normalized} {INTERACTIVE_HELP_CLI_NOTE}\n\n{panel_text}"


def apply_help_modal_key(
    key: str,
    *,
    show_help_modal: bool,
) -> tuple[bool, bool]:
    """Apply one key to help-modal state and return (consumed, next_state)."""
    if show_help_modal:
        return True, False
    if key == "?":
        return True, True
    return False, show_help_modal


def render_interactive_help_modal(
    entries: list[InteractiveHelpEntry],
    *,
    color_enabled: bool,
    title: str = "Key bindings",
    close_hint: str = INTERACTIVE_HELP_CLOSE_HINT,
) -> RenderableType:
    """Render a generic interactive key bindings modal panel."""
    key_column_width = max(18, max((len(entry.key) for entry in entries), default=0) + 1)
    content = Table.grid(expand=True, padding=(0, 2))
    content.add_column(width=key_column_width, no_wrap=True, overflow="fold")
    content.add_column(ratio=1, no_wrap=False, overflow="fold")
    for entry in entries:
        content.add_row(
            Text(entry.key, style="bold", no_wrap=True),
            Text(entry.description),
        )

    border_style = "grey50" if color_enabled else ""
    panel_content: RenderableType = content
    if close_hint:
        panel_content = Group(content, Text(close_hint, style="dim"))

    return Panel(
        panel_content,
        title=title,
        title_align="left",
        border_style=border_style,
        padding=(0, 1),
        expand=True,
    )


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


def heading_locator(node: Heading) -> HeadingLocator:
    """Build a stable heading locator for selection restoration."""
    return HeadingLocator(
        filename=node.document.filename or "",
        heading_id=node.id,
        title=node.title_text,
    )


def resolve_heading_locator(
    candidates: list[Heading],
    locator: HeadingLocator | None,
) -> Heading | None:
    """Resolve a preserved heading locator against a candidate heading list."""
    if locator is None or not candidates:
        return None

    document = None
    for candidate in candidates:
        if (candidate.document.filename or "") == locator.filename:
            document = candidate.document
            break

    if document is None:
        return None

    resolved = (
        document.heading_by_id(locator.heading_id)
        if locator.heading_id is not None
        else document.heading_by_title(locator.title)
    )
    if resolved is None:
        return None

    for candidate in candidates:
        if candidate is resolved:
            return candidate
    return None


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


def set_timestamp_fields(timestamp: Timestamp, start: datetime, end: datetime | None) -> None:
    """Set timestamp date/time fields while preserving active/repeater metadata."""
    timestamp.start_year = start.year
    timestamp.start_month = start.month
    timestamp.start_day = start.day
    timestamp.start_dayname = start.strftime("%a")
    if timestamp.start_hour is not None:
        timestamp.start_hour = start.hour
        timestamp.start_minute = start.minute

    if end is None or timestamp.end is None:
        return

    timestamp.end_year = end.year
    timestamp.end_month = end.month
    timestamp.end_day = end.day
    timestamp.end_dayname = end.strftime("%a")
    if timestamp.end_hour is not None:
        timestamp.end_hour = end.hour
        timestamp.end_minute = end.minute


def add_months(value: datetime, months: int) -> datetime:
    """Add months to a datetime while clamping day to month length."""
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def shift_datetimes_by_unit(
    start: datetime,
    end: datetime | None,
    *,
    value: int,
    unit: str,
) -> tuple[datetime, datetime | None]:
    """Shift start/end datetimes by one repeater unit."""
    if unit == "d":
        delta = timedelta(days=value)
        return start + delta, None if end is None else end + delta
    if unit == "w":
        delta = timedelta(weeks=value)
        return start + delta, None if end is None else end + delta
    if unit == "h":
        delta = timedelta(hours=value)
        return start + delta, None if end is None else end + delta
    if unit == "m":
        return add_months(start, value), None if end is None else add_months(end, value)
    if unit == "y":
        months = value * 12
        return add_months(start, months), None if end is None else add_months(end, months)
    raise ValueError(f"Unsupported repeater unit: {unit}")


def now_aligned_for_datetime(start: datetime, now: datetime) -> datetime:
    """Normalize current datetime to match timezone-awareness of start."""
    if start.tzinfo is None:
        return now.replace(tzinfo=None)
    if now.tzinfo is None:
        return now.replace(tzinfo=start.tzinfo)
    return now.astimezone(start.tzinfo)


def advance_timestamp_by_repeater(timestamp: Timestamp) -> bool:
    """Advance timestamp once by its repeater marker, when present."""
    if timestamp.repeater is None:
        return False

    mark = timestamp.repeater.mark
    value = timestamp.repeater.value
    unit = timestamp.repeater.unit
    if value <= 0:
        return False

    start = timestamp.start
    end = timestamp.end

    try:
        if mark == "+":
            shifted_start, shifted_end = shift_datetimes_by_unit(
                start,
                end,
                value=value,
                unit=unit,
            )
        elif mark == "++":
            now = now_aligned_for_datetime(start, local_now())
            shifted_start, shifted_end = shift_datetimes_by_unit(
                start,
                end,
                value=value,
                unit=unit,
            )
            while shifted_start <= now:
                shifted_start, shifted_end = shift_datetimes_by_unit(
                    shifted_start,
                    shifted_end,
                    value=value,
                    unit=unit,
                )
        elif mark == ".+":
            now = now_aligned_for_datetime(start, local_now())
            base_start = start.replace(year=now.year, month=now.month, day=now.day)
            base_end = None if end is None else base_start + (end - start)
            shifted_start, shifted_end = shift_datetimes_by_unit(
                base_start,
                base_end,
                value=value,
                unit=unit,
            )
        else:
            return False
    except ValueError:
        return False

    set_timestamp_fields(timestamp, shifted_start, shifted_end)
    return True


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


def read_input_event_with_timeout(
    timeout_seconds: float,
    *,
    token_map: dict[str, str] | None = None,
    ctrl_p_as_paste: bool = False,
) -> tuple[str, str] | None:
    """Read one input event with timeout, returning None when idle."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        ready, _, _ = select.select([fd], [], [], timeout_seconds)
        if not ready:
            return None
        return read_input_event(fd, token_map=token_map, ctrl_p_as_paste=ctrl_p_as_paste)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def apply_footer_prompt_input_event(
    prompt: FooterPromptState,
    event_name: str,
    event_text: str,
) -> bool:
    """Apply one input event to footer prompt and return submit status."""
    if event_name == "ENTER":
        return True

    cursor_targets = {
        "LEFT": max(0, prompt.cursor_position - 1),
        "RIGHT": min(len(prompt.value), prompt.cursor_position + 1),
        "HOME": 0,
        "END": len(prompt.value),
    }
    target_cursor = cursor_targets.get(event_name)
    if target_cursor is not None:
        prompt.cursor_position = target_cursor
        return False

    if event_name == "BACKSPACE" and prompt.cursor_position > 0:
        prompt.value = (
            f"{prompt.value[: prompt.cursor_position - 1]}{prompt.value[prompt.cursor_position :]}"
        )
        prompt.cursor_position -= 1
        return False

    if event_name == "DELETE" and prompt.cursor_position < len(prompt.value):
        prompt.value = (
            f"{prompt.value[: prompt.cursor_position]}{prompt.value[prompt.cursor_position + 1 :]}"
        )
        return False

    if event_name == "TEXT":
        prompt.value = (
            f"{prompt.value[: prompt.cursor_position]}"
            f"{event_text}"
            f"{prompt.value[prompt.cursor_position :]}"
        )
        prompt.cursor_position += len(event_text)
    return False


def build_footer_prompt_text(prompt: FooterPromptState) -> Text:
    """Build prompt text with visible cursor for footer rendering."""
    clamped_cursor = max(0, min(prompt.cursor_position, len(prompt.value)))
    text = Text(f"{prompt.label}: ", style="bold")
    text.append(prompt.value[:clamped_cursor])
    if clamped_cursor < len(prompt.value):
        text.append(prompt.value[clamped_cursor], style="reverse")
        text.append(prompt.value[clamped_cursor + 1 :])
    else:
        text.append(" ", style="reverse")
    return text


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
