"""Parsing utilities for org-mode files."""

from __future__ import annotations

import logging
from typing import Protocol, cast

import orgparse
import typer


class FilterSpec(Protocol):
    """Protocol for filtering node lists."""

    def filter(self, nodes: list[orgparse.node.OrgNode]) -> list[orgparse.node.OrgNode]:
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
) -> tuple[list[orgparse.node.OrgRootNode], list[str], list[str]]:
    """Load org-mode files and return root nodes with merged todo/done keys."""
    roots: list[orgparse.node.OrgRootNode] = []
    all_todo_keys: set[str] = set(todo_keys)
    all_done_keys: set[str] = set(done_keys)

    for name in filenames:
        contents = _read_org_file(name)
        contents = _prepend_todo_config(contents, todo_keys, done_keys)
        root = cast(orgparse.node.OrgRootNode, orgparse.loads(contents, filename=name))
        all_todo_keys = all_todo_keys.union(set(root.env.todo_keys))
        all_done_keys = all_done_keys.union(set(root.env.done_keys))
        roots.append(root)

    return roots, list(all_todo_keys), list(all_done_keys)


def load_nodes(
    filenames: list[str],
    todo_keys: list[str],
    done_keys: list[str],
    filters: list[FilterSpec],
) -> tuple[list[orgparse.node.OrgNode], list[str], list[str]]:
    """Load, parse, and filter org-mode files.

    Processes each file separately: preprocess -> parse -> filter -> extract keys -> combine.

    Args:
        filenames: List of file paths to load
        todo_keys: List of TODO state keywords to prepend to files
        done_keys: List of DONE state keywords to prepend to files
        filters: List of filter specs to apply to nodes from each file

    Returns:
        Tuple of (filtered nodes, all todo keys, all done keys)

    Raises:
        typer.BadParameter: If file cannot be read
    """
    roots, all_todo_keys, all_done_keys = load_root_nodes(filenames, todo_keys, done_keys)

    all_nodes: list[orgparse.node.OrgNode] = []
    for root in roots:
        file_nodes = list(root[1:])
        for filter_spec in filters:
            file_nodes = filter_spec.filter(file_nodes)
        all_nodes = all_nodes + file_nodes

    return all_nodes, all_todo_keys, all_done_keys
