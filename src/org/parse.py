"""Parsing utilities for org-mode files."""

from __future__ import annotations

import logging
import sys
from typing import Protocol

import orgparse


class FilterSpec(Protocol):
    """Protocol for filtering node lists."""

    def filter(self, nodes: list[orgparse.node.OrgNode]) -> list[orgparse.node.OrgNode]:
        """Filter nodes and return the filtered list."""
        raise NotImplementedError


logger = logging.getLogger("org")


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
        SystemExit: If file cannot be read
    """
    all_nodes: list[orgparse.node.OrgNode] = []
    all_todo_keys: set[str] = set(todo_keys)
    all_done_keys: set[str] = set(done_keys)

    for name in filenames:
        try:
            with open(name, encoding="utf-8") as f:
                logger.info("Processing %s...", name)

                contents = f.read().replace("24:00", "00:00")

                todo_config = f"#+TODO: {' '.join(todo_keys)} | {' '.join(done_keys)}\n\n"
                contents = todo_config + contents

                ns = orgparse.loads(contents, filename=name)
                if ns is not None:
                    all_todo_keys = all_todo_keys.union(set(ns.env.todo_keys))
                    all_done_keys = all_done_keys.union(set(ns.env.done_keys))

                    file_nodes = list(ns[1:])

                    for filter_spec in filters:
                        file_nodes = filter_spec.filter(file_nodes)

                    all_nodes = all_nodes + file_nodes
        except FileNotFoundError:
            print(f"Error: File '{name}' not found", file=sys.stderr)
            sys.exit(1)
        except PermissionError:
            print(f"Error: Permission denied for '{name}'", file=sys.stderr)
            sys.exit(1)

    return all_nodes, list(all_todo_keys), list(all_done_keys)
