"""Parsing utilities for org-mode files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import typer
from org_parser import loads


if TYPE_CHECKING:
    from org_parser.document import Document, Heading


class FilterSpec(Protocol):
    """Protocol for filtering node lists."""

    def filter(self, nodes: list[Heading]) -> list[Heading]:
        """Filter nodes and return the filtered list."""
        raise NotImplementedError


logger = logging.getLogger("org")


def _read_org_file(name: str) -> str:
    """Read one org file and normalize unsupported time values."""
    path = Path(name)
    try:
        with path.open(encoding="utf-8") as f:
            logger.info("Processing %s...", name)
            return f.read().replace("24:00", "00:00")
    except FileNotFoundError as err:
        raise typer.BadParameter(f"File '{name}' not found") from err
    except PermissionError as err:
        raise typer.BadParameter(f"Permission denied for '{name}'") from err


def _prepend_todo_config(contents: str, todo_states: list[str], done_states: list[str]) -> str:
    """Prepend TODO keyword configuration to file contents."""
    todo_config = f"#+TODO: {' '.join(todo_states)} | {' '.join(done_states)}\n\n"
    return todo_config + contents


def load_root_nodes(
    filenames: list[str],
    todo_states: list[str],
    done_states: list[str],
) -> tuple[list[Document], list[str], list[str]]:
    """Load org-mode files and return root nodes with merged todo/done keys."""
    roots: list[Document] = []
    all_todo_states: set[str] = set(todo_states)
    all_done_states: set[str] = set(done_states)

    for name in filenames:
        contents = _read_org_file(name)
        contents = _prepend_todo_config(contents, todo_states, done_states)
        root = loads(contents, filename=name)
        all_todo_states = all_todo_states.union(set(root.todo_states))
        all_done_states = all_done_states.union(set(root.done_states))
        roots.append(root)

    return roots, list(all_todo_states), list(all_done_states)
