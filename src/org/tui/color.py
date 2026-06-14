"""Color support for CLI output using Rich markup."""

import sys

from rich.markup import escape


def should_use_color(color_flag: bool | None) -> bool:
    """Determine if color should be used based on flag and TTY detection.

    Args:
        color_flag: Explicit color preference (True/False) or None for auto-detect

    Returns:
        True if colors should be used, False otherwise
    """
    if color_flag is None:
        return sys.stdout.isatty()
    return color_flag


def escape_text(text: str, enabled: bool) -> str:
    """Escape markup characters when color output is enabled.

    Args:
        text: Text to escape
        enabled: Whether coloring is enabled

    Returns:
        Escaped text when enabled, original text otherwise
    """
    if not enabled:
        return text
    return escape(text)


def colorize(text: str, style: str, enabled: bool) -> str:
    """Apply Rich markup style to text if enabled.

    Args:
        text: Text to colorize
        style: Rich style string (e.g., "green", "bold white")
        enabled: Whether coloring is enabled

    Returns:
        Styled text if enabled, original text otherwise
    """
    if not enabled:
        return text
    return f"[{style}]{escape(text)}[/]"


def bright_white(text: str, enabled: bool) -> str:
    """Apply bright white color to text."""
    return colorize(text, "bold white", enabled)


def dim_white(text: str, enabled: bool) -> str:
    """Apply dim white color to text."""
    return colorize(text, "dim white", enabled)


def magenta(text: str, enabled: bool) -> str:
    """Apply magenta color to text."""
    return colorize(text, "magenta", enabled)


def bright_blue(text: str, enabled: bool) -> str:
    """Apply bright blue color to text."""
    return colorize(text, "bold blue", enabled)


def get_state_color(
    state: str,
    done_states: list[str],
    todo_states: list[str],
    enabled: bool,
) -> str:
    """Get appropriate style for a task state."""
    if not enabled:
        return ""

    normalized_state = state.strip().upper()

    if normalized_state == "CANCELLED":
        return "bold red"

    if normalized_state == "SUSPENDED":
        return "bold yellow"

    if state in done_states:
        return "bold green"

    if state in todo_states or state == "" or state.lower() == "null":
        return "bold bright_black"

    return "bold yellow"
