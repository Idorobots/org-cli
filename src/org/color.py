"""Color support for CLI output using colorama."""

import sys

from colorama import Fore, Style


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


def colorize(text: str, color_code: str, enabled: bool) -> str:
    """Apply color to text if enabled.

    Args:
        text: Text to colorize
        color_code: Colorama color code (e.g., Fore.GREEN, Style.BRIGHT)
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    if not enabled:
        return text
    return f"{color_code}{text}{Style.RESET_ALL}"


def bright_white(text: str, enabled: bool) -> str:
    """Apply bright white color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, Style.BRIGHT + Fore.WHITE, enabled)


def white(text: str, enabled: bool) -> str:
    """Apply white color to text (default, usually no-op).

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, Fore.WHITE, enabled)


def dim_white(text: str, enabled: bool) -> str:
    """Apply dim white color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, Style.DIM + Fore.WHITE, enabled)


def magenta(text: str, enabled: bool) -> str:
    """Apply magenta color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, Fore.MAGENTA, enabled)


def green(text: str, enabled: bool) -> str:
    """Apply green color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, Fore.GREEN, enabled)


def bright_green(text: str, enabled: bool) -> str:
    """Apply bright green color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, Style.BRIGHT + Fore.GREEN, enabled)


def bright_red(text: str, enabled: bool) -> str:
    """Apply bright red color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, Style.BRIGHT + Fore.RED, enabled)


def bright_yellow(text: str, enabled: bool) -> str:
    """Apply bright yellow color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, Style.BRIGHT + Fore.YELLOW, enabled)


def bright_blue(text: str, enabled: bool) -> str:
    """Apply bright blue color to text.

    Args:
        text: Text to colorize
        enabled: Whether coloring is enabled

    Returns:
        Colored text if enabled, original text otherwise
    """
    return colorize(text, Style.BRIGHT + Fore.BLUE, enabled)


def get_state_color(state: str, done_keys: list[str], todo_keys: list[str], enabled: bool) -> str:
    """Get appropriate color for a task state.

    Args:
        state: Task state (e.g., "DONE", "TODO", "CANCELLED")
        done_keys: List of done state keywords
        todo_keys: List of todo state keywords
        enabled: Whether coloring is enabled

    Returns:
        Color code for the state
    """
    if not enabled:
        return ""

    if state in done_keys:
        if state == "CANCELLED":
            return str(Style.BRIGHT + Fore.RED)
        return str(Style.BRIGHT + Fore.GREEN)

    if state in todo_keys or state == "" or state.lower() == "none":
        return str(Style.DIM + Fore.WHITE)

    return str(Style.BRIGHT + Fore.YELLOW)
