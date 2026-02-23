"""Text utility functions for formatting and display."""

from rich.text import Text


def visual_len(text: str) -> int:
    """Get visual length of text (excluding Rich markup).

    Args:
        text: Text that may contain Rich markup or ANSI codes

    Returns:
        Visual length of the text
    """
    return len(Text.from_markup(text).plain)
