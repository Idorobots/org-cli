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
    """Apply bright white color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, "bold white", enabled)


def white(text: str, enabled: bool) -> str:
    """Apply white color to text (default, usually no-op).

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, "white", enabled)


def dim_white(text: str, enabled: bool) -> str:
    """Apply dim white color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, "dim white", enabled)


def magenta(text: str, enabled: bool) -> str:
    """Apply magenta color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, "magenta", enabled)


def green(text: str, enabled: bool) -> str:
    """Apply green color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, "green", enabled)


def bright_green(text: str, enabled: bool) -> str:
    """Apply bright green color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, "bold green", enabled)


def bright_red(text: str, enabled: bool) -> str:
    """Apply bright red color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, "bold red", enabled)


def bright_yellow(text: str, enabled: bool) -> str:
    """Apply bright yellow color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, "bold yellow", enabled)


def bright_blue(text: str, enabled: bool) -> str:
    """Apply bright blue color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, "bold blue", enabled)


def get_state_color(state: str, done_keys: list[str], todo_keys: list[str], enabled: bool) -> str:
    """Get appropriate style for a task state.

    Args:
        state: Task state (e.g., "DONE", "TODO", "CANCELLED")
        done_keys: List of done state keywords
        todo_keys: List of todo state keywords
        enabled: Whether coloring is enabled

    Returns:
        Rich style string for the state
    """
    if not enabled:
        return ""

    if state in done_keys:
        if state == "CANCELLED":
            return "bold red"
        return "bold green"

    if state in todo_keys or state == "" or state.lower() == "none":
        return "dim white"

    return "bold yellow"
