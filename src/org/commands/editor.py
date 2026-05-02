"""Shared helpers for external editor workflows."""

from __future__ import annotations

import os
from dataclasses import dataclass

import click
import typer
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
class HeadingEditResult:
    """Result of editing one heading subtree."""

    heading: Heading
    changed: bool


def _replace_heading_in_parent(heading: Heading, updated_heading: Heading) -> None:
    """Replace one heading subtree inside parent children."""
    parent = heading.parent
    if parent is None:
        raise typer.BadParameter("Unable to edit heading without a parent node")

    updated_children = list(parent.children)
    for index, child in enumerate(updated_children):
        if child is heading:
            updated_children[index] = updated_heading
            parent.children = updated_children
            return

    raise typer.BadParameter("Unable to locate selected task in parent children")


def edit_heading_subtree_in_external_editor(heading: Heading) -> HeadingEditResult:
    """Edit one heading subtree in external editor and apply replacement."""
    original_source = heading.render()
    edited_source = edit_text_in_external_editor(original_source)
    if edited_source == original_source:
        return HeadingEditResult(heading=heading, changed=False)

    try:
        updated_heading = Heading.from_source(edited_source)
    except (TypeError, ValueError) as err:
        raise typer.BadParameter(f"Edited task content is invalid: {err}") from err

    _replace_heading_in_parent(heading, updated_heading)
    return HeadingEditResult(heading=updated_heading, changed=True)
