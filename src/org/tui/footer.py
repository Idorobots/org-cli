"""Footer helpers for interactive Textual UIs."""

from __future__ import annotations

from dataclasses import dataclass

from rich.table import Table
from rich.text import Text


@dataclass
class FooterPromptState:
    """Simple prompt label/value state shared by Textual prompt configs."""

    label: str
    value: str = ""
    cursor_position: int = 0
    error_message: str = ""


def footer_renderable(left_text: str, right_text: str, *, style: str) -> Table:
    """Build one footer line with a right-aligned help hint."""
    footer_line = Table.grid(expand=True)
    footer_line.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    footer_line.add_column(ratio=4, justify="right", no_wrap=True, overflow="ellipsis")
    footer_line.add_row(
        Text(left_text, style=style, no_wrap=True, overflow="ellipsis"),
        Text(right_text, style=style, no_wrap=True, overflow="ellipsis"),
    )
    return footer_line
