"""Shared helpers for external editor workflows."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import click
import typer

from org.db.errors import DocumentParseError
from org.db.repository import load_document_from_text


if TYPE_CHECKING:
    from org_parser.document import Heading


def _editor_program() -> str:
    """Return external editor program from $EDITOR."""
    editor = os.environ.get("EDITOR")
    if editor is None or not editor.strip():
        raise typer.BadParameter("$EDITOR is not defined")
    return editor


def edit_text_in_external_editor(initial_text: str, *, suffix: str = ".org") -> str:
    """Open initial text in configured external editor and return edited result."""
    editor = _editor_program()
    try:
        edited_text = click.edit(initial_text, editor=editor, extension=suffix)
    except click.ClickException as err:
        raise typer.BadParameter(str(err)) from err

    if edited_text is None:
        return initial_text
    if isinstance(edited_text, str):
        return edited_text
    raise typer.BadParameter("Editor returned non-text content")


@dataclass(frozen=True)
class DocumentEditResult:
    """Result of editing a task's source document."""

    changed: bool


def _run_editor_at_line(filename: str, line: int) -> int:
    """Open one file in the configured editor at a given line."""
    editor = _editor_program()
    try:
        click.edit(editor=f"{editor} +{line}", filename=filename)
    except click.ClickException:
        return 1
    return 0


def _read_document_text(path: Path, filename: str) -> str:
    """Read one document file from disk."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as err:
        raise typer.BadParameter(f"File '{filename}' not found") from err
    except PermissionError as err:
        raise typer.BadParameter(f"Permission denied for '{filename}'") from err


def _write_document_text(path: Path, filename: str, document_text: str) -> None:
    """Write one full document file to disk."""
    try:
        path.write_text(document_text, encoding="utf-8")
    except PermissionError as err:
        raise typer.BadParameter(f"Permission denied for '{filename}'") from err


def edit_heading_subtree_in_external_editor(heading: Heading) -> DocumentEditResult:
    """Edit one file-backed task subtree in the configured external editor."""
    filename = heading.document.filename or None
    if filename is None:
        raise typer.BadParameter(
            "This task is not associated with a file and cannot be edited.",
        )

    path = Path(filename)
    original_text = _read_document_text(path, filename)
    return_code = _run_editor_at_line(filename, 0 if heading.line is None else heading.line)
    if return_code == 0:
        edited_text = _read_document_text(path, filename)
        if edited_text == original_text:
            return DocumentEditResult(changed=False)
        try:
            load_document_from_text(edited_text, filename)
        except DocumentParseError as err:
            raise typer.BadParameter(f"Edited document content is invalid: {err.detail}") from err
        return DocumentEditResult(changed=True)

    raise typer.BadParameter("Editor failed to open")
