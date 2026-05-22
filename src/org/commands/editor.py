"""Shared helpers for external editor workflows."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import click
import org_parser
import typer


if TYPE_CHECKING:
    from org_parser.document import Document, Heading


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


def _load_document_from_text(document_text: str, filename: str | None) -> Document:
    """Parse full document text and preserve original filename when present."""
    try:
        document = org_parser.loads(document_text)
    except (TypeError, ValueError) as err:
        raise typer.BadParameter(f"Edited document content is invalid: {err}") from err

    document.filename = "" if filename is None else filename
    return document


def _run_editor_at_line(filename: str, line: int) -> int:
    """Open one file in the configured editor at a given line."""
    editor = _editor_program()
    try:
        click.edit(editor=f"{editor} +{line}", filename=filename)
    except click.ClickException:
        return 1
    return 0


def _confirm_temporary_file_edit(prompt: str) -> bool:
    """Ask whether a temporary-file fallback edit should be opened."""
    return typer.confirm(prompt, default=False)


def _edit_via_temporary_file(document_text: str, prompt: str) -> str | None:
    """Prompt for and run the temporary-file fallback editor flow."""
    if not _confirm_temporary_file_edit(prompt):
        return None
    return edit_text_in_external_editor(document_text)


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


def _edit_document_without_filename(heading: Heading) -> DocumentEditResult:
    """Edit a document that does not have a backing filename."""
    original_text = heading.document.render()
    edited_text = _edit_via_temporary_file(
        original_text,
        "This task is not associated with a file. Edit a temporary copy instead?",
    )
    if edited_text is None or edited_text == original_text:
        return DocumentEditResult(changed=False)

    return DocumentEditResult(changed=True)


def _edit_document_with_filename(heading: Heading, filename: str) -> DocumentEditResult:
    """Edit a document backed by a filename, preferring in-place file edits."""
    path = Path(filename)
    original_text = _read_document_text(path, filename)

    return_code = _run_editor_at_line(filename, 0 if heading.line is None else heading.line)
    if return_code == 0:
        edited_text = _read_document_text(path, filename)
        if edited_text == original_text:
            return DocumentEditResult(changed=False)
        _load_document_from_text(edited_text, filename)
        return DocumentEditResult(changed=True)

    fallback_text = _edit_via_temporary_file(
        original_text,
        "Opening the original file at the task line failed. Edit a temporary copy instead?",
    )
    if fallback_text is None or fallback_text == original_text:
        return DocumentEditResult(changed=False)

    _write_document_text(path, filename, fallback_text)
    _load_document_from_text(fallback_text, filename)
    return DocumentEditResult(changed=True)


def edit_heading_subtree_in_external_editor(heading: Heading) -> DocumentEditResult:
    """Edit the original task document, preferring in-place file editing at task line."""
    filename = heading.document.filename or None
    if filename is None:
        return _edit_document_without_filename(heading)
    return _edit_document_with_filename(heading, filename)
