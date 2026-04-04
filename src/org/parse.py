"""Parsing utilities for org-mode files."""

from __future__ import annotations

import logging
from typing import Protocol

import typer
from org_parser import loads
from org_parser.document import Document, Heading


class FilterSpec(Protocol):
    """Protocol for filtering node lists."""

    def filter(self, nodes: list[Heading]) -> list[Heading]:
        """Filter nodes and return the filtered list."""
        raise NotImplementedError


logger = logging.getLogger("org")


def _read_org_file(name: str) -> str:
    """Read one org file and normalize unsupported time values."""
    try:
        with open(name, encoding="utf-8") as f:
            logger.info("Processing %s...", name)
            return f.read().replace("24:00", "00:00")
    except FileNotFoundError as err:
        raise typer.BadParameter(f"File '{name}' not found") from err
    except PermissionError as err:
        raise typer.BadParameter(f"Permission denied for '{name}'") from err


def _prepend_todo_config(contents: str, todo_keys: list[str], done_keys: list[str]) -> str:
    """Prepend TODO keyword configuration to file contents."""
    todo_config = f"#+TODO: {' '.join(todo_keys)} | {' '.join(done_keys)}\n\n"
    return todo_config + contents


def load_root_nodes(
    filenames: list[str],
    todo_keys: list[str],
    done_keys: list[str],
) -> tuple[list[Document], list[str], list[str]]:
    """Load org-mode files and return root nodes with merged todo/done keys."""
    roots: list[Document] = []
    all_todo_keys: set[str] = set(todo_keys)
    all_done_keys: set[str] = set(done_keys)

    for name in filenames:
        contents = _read_org_file(name)
        contents = _prepend_todo_config(contents, todo_keys, done_keys)
        root = loads(contents, filename=name)
        all_todo_keys = all_todo_keys.union(set(root.todo_states))
        all_done_keys = all_done_keys.union(set(root.done_states))
        roots.append(root)

    return roots, list(all_todo_keys), list(all_done_keys)
