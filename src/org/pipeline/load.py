"""Pipeline helpers for loading and preprocessing org-mode data."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import typer
from org_parser import loads
from org_parser.document import Heading

from org.config.cli import (
    QueryBuildArgs,
    build_pipeline_stages,
    collect_custom_context_vars,
    normalize_cli_files_for_custom_switches,
    validate_custom_switches,
)
from org.logic.validation import validate_and_parse_keys, validate_global_arguments
from org.query.engine.errors import QueryParseError
from org.query.runner import (
    build_query_from_stages,
    execute_query_or_raise,
    flatten_query_results,
)


if TYPE_CHECKING:
    from org_parser.document import Document


logger = logging.getLogger("org")


def load_document_from_text(document_text: str, filename: str | None) -> Document:
    """Parse full document text and preserve original filename when present."""
    try:
        document = loads(document_text)
    except (TypeError, ValueError) as err:
        raise typer.BadParameter(f"Edited document content is invalid: {err}") from err

    document.filename = "" if filename is None else filename
    return document


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


def _merge_state_order(existing: list[str], discovered: list[str]) -> list[str]:
    """Merge discovered states into existing list while preserving order."""
    merged = list(existing)
    seen = set(merged)
    for state in discovered:
        if state in seen:
            continue
        merged.append(state)
        seen.add(state)
    return merged


def load_root_nodes(
    filenames: list[str],
    todo_states: list[str],
    done_states: list[str],
) -> tuple[list[Document], list[str], list[str]]:
    """Load org-mode files and return root nodes with merged todo/done keys."""
    roots: list[Document] = []
    all_todo_states = list(todo_states)
    all_done_states = list(done_states)

    for name in filenames:
        contents = _read_org_file(name)
        contents = _prepend_todo_config(contents, todo_states, done_states)
        root = loads(contents, filename=name)
        all_todo_states = _merge_state_order(all_todo_states, list(root.todo_states))
        all_done_states = _merge_state_order(all_done_states, list(root.done_states))
        roots.append(root)

    return roots, all_todo_states, all_done_states


def resolve_input_paths(inputs: list[str] | None) -> list[str]:  # noqa: C901
    """Resolve CLI inputs into a list of org files to process."""
    resolved_files: list[str] = []
    searched_dirs: list[Path] = []
    missing_paths: list[str] = []

    targets = inputs or ["."]
    for raw_path in targets:
        path = Path(raw_path)
        if not path.exists():
            missing_paths.append(raw_path)
            continue

        if path.is_dir():
            searched_dirs.append(path)
            for file_path in sorted(path.glob("*.org")):
                if file_path.exists():
                    resolved_files.append(str(file_path))
                else:
                    missing_paths.append(str(file_path))
            continue

        if path.is_file():
            resolved_files.append(str(path))
            continue

        raise typer.BadParameter(f"Path '{raw_path}' is not a file or directory")

    for raw_path in missing_paths:
        logger.info("Warning: file '%s' not found", raw_path)

    if not resolved_files:
        if missing_paths:
            missing_list = ", ".join(missing_paths)
            raise typer.BadParameter(f"All input paths are missing: {missing_list}")
        if searched_dirs:
            searched_list = ", ".join(str(path) for path in searched_dirs)
            raise typer.BadParameter(f"No .org files found in: {searched_list}")
        raise typer.BadParameter("No .org files found")

    return resolved_files


class RootDataLoadArgs(Protocol):
    """Protocol for loading root nodes without filters or enrichment."""

    files: list[str] | None
    todo_states: str
    done_states: str
    width: int | None


class DataLoadArgs(QueryBuildArgs, Protocol):
    """Protocol for loading and preprocessing data."""

    files: list[str] | None
    todo_states: str
    done_states: str
    width: int | None


class SlicedDataLoadArgs(Protocol):
    """Protocol for args that support query slicing."""

    offset: int
    max_results: int


def _load_roots_for_inputs(
    files: list[str] | None,
    todo_states: list[str],
    done_states: list[str],
) -> tuple[list[Document], list[str], list[str]]:
    """Resolve file inputs and load all org root nodes."""
    return load_root_nodes(resolve_input_paths(files), todo_states, done_states)


def _resolve_and_load_roots(args: RootDataLoadArgs) -> tuple[list[Document], list[str], list[str]]:
    """Resolve inputs and load org roots after validating todo/done keys."""
    todo_states = validate_and_parse_keys(args.todo_states, "--todo-states")
    done_states = validate_and_parse_keys(args.done_states, "--done-states")
    return _load_roots_for_inputs(args.files, todo_states, done_states)


def load_root_data(args: RootDataLoadArgs) -> tuple[list[Document], list[str], list[str]]:
    """Load org root nodes without filters, enrichment, or ordering."""
    return _resolve_and_load_roots(args)


def load_and_process_data(args: DataLoadArgs) -> tuple[list[Heading], list[str], list[str]]:
    """Load nodes, preprocess, and apply query-based filters/ordering."""
    include_ordering = hasattr(args, "order_by_level")
    validate_custom_switches(sys.argv, include_ordering)

    normalized_files = normalize_cli_files_for_custom_switches(args.files)
    args.files = normalized_files

    todo_states, done_states = validate_global_arguments(args)
    roots, todo_states, done_states = _load_roots_for_inputs(
        normalized_files,
        todo_states,
        done_states,
    )
    nodes = [node for root in roots for node in list(root)]

    include_slice = include_ordering and hasattr(args, "offset") and hasattr(args, "max_results")
    try:
        query = build_query_from_stages(
            build_pipeline_stages(args, sys.argv, include_ordering),
            include_slice,
        )
    except QueryParseError as exc:
        raise typer.BadParameter(str(exc)) from exc

    context_vars: dict[str, object] = {
        "todo_states": todo_states,
        "done_states": done_states,
    }
    context_vars.update(collect_custom_context_vars(sys.argv, normalized_files, include_ordering))
    if include_slice:
        sliced_args = cast("SlicedDataLoadArgs", args)
        context_vars["offset"] = sliced_args.offset
        context_vars["limit"] = sliced_args.max_results

    logger.info("Query context: %s", context_vars)

    results = execute_query_or_raise(query, [nodes], context_vars, typer.BadParameter)

    flattened = flatten_query_results(results)
    return [value for value in flattened if isinstance(value, Heading)], todo_states, done_states
