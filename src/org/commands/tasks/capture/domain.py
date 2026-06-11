"""Domain logic for tasks capture."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import typer
from org_parser.document import Document, Heading
from rich.syntax import Syntax

from org import config as config_module
from org.commands.interactive_common import InteractiveHelpEntry
from org.commands.tasks.common import load_document, resolve_parent_heading, save_document
from org.query_language import (
    EvalContext,
    QueryParseError,
    QueryRuntimeError,
    Stream,
    compile_query_text,
)
from org.serde.format import DEFAULT_OUTPUT_THEME


if TYPE_CHECKING:
    from rich.text import Text


_PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s*}}")
_ORG_WEEKDAY_ABBR = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
logger = logging.getLogger("org")


_CAPTURE_HELP_ENTRIES = [
    InteractiveHelpEntry("Tab / Shift-Tab", "Move focus between form fields and controls."),
    InteractiveHelpEntry("Type text", "Edit the focused field and update the preview live."),
    InteractiveHelpEntry("Ctrl-S", "Save the rendered capture entry."),
    InteractiveHelpEntry("Esc", "Cancel capture and return to the shell."),
]


@dataclass
class TasksCaptureArgs:
    """Arguments for the tasks capture command."""

    template_name: str | None
    config: str
    file: str | None
    parent: str | None
    set_values: list[str] | None


@dataclass(frozen=True)
class TasksCaptureResult:
    """Result metadata for one successful capture operation."""

    template_name: str
    heading: Heading
    document: Document
    interactive_used: bool = False


@dataclass(frozen=True)
class CapturePlan:
    """Prepared capture plan with unresolved placeholder metadata."""

    args: TasksCaptureArgs
    template_name: str
    template_content: str
    document: Document
    parent_heading: Heading | None
    placeholders: list[str]
    values: dict[str, str]
    unresolved_placeholders: list[str]


@dataclass(frozen=True)
class _TemplatePreview:
    """Rendered capture template preview with placeholder spans."""

    text: str
    placeholder_spans: dict[str, list[tuple[int, int]]]


def _template_names(templates: dict[str, dict[str, str]]) -> list[str]:
    """Return stable template name ordering for prompts and errors."""
    return sorted(templates)


def _require_templates(templates: dict[str, dict[str, str]]) -> None:
    """Require at least one capture template before running capture."""
    if templates:
        return
    raise typer.BadParameter("No capture templates configured")


def _valid_template_names_text(template_names: list[str]) -> str:
    """Return comma-separated template names for error messages."""
    return ", ".join(template_names)


def _template_placeholders(template_content: str) -> list[str]:
    """Return unique placeholders in first-appearance order."""
    placeholders = [match.group(1) for match in _PLACEHOLDER_RE.finditer(template_content)]
    return list(dict.fromkeys(placeholders))


def _placeholder_token(placeholder: str) -> str:
    """Return canonical placeholder token for unresolved values."""
    return f"{{{{{placeholder}}}}}"


def _render_template_preview(template_content: str, values: dict[str, str]) -> _TemplatePreview:
    """Render template preview text and track placeholder output spans."""
    chunks: list[str] = []
    placeholder_spans: dict[str, list[tuple[int, int]]] = {}
    output_index = 0
    cursor = 0

    for match in _PLACEHOLDER_RE.finditer(template_content):
        leading_text = template_content[cursor : match.start()]
        chunks.append(leading_text)
        output_index += len(leading_text)

        placeholder = match.group(1)
        replacement = values.get(placeholder, _placeholder_token(placeholder))
        replacement_start = output_index
        replacement_end = replacement_start + len(replacement)
        chunks.append(replacement)
        output_index = replacement_end
        placeholder_spans.setdefault(placeholder, []).append((replacement_start, replacement_end))

        cursor = match.end()

    trailing_text = template_content[cursor:]
    chunks.append(trailing_text)
    return _TemplatePreview(text="".join(chunks), placeholder_spans=placeholder_spans)


def _build_template_body(
    template_content: str,
    values: dict[str, str],
    current_placeholder: str | None,
    current_input_value: str,
) -> Text:
    """Build syntax-highlighted template body with active placeholder emphasis."""
    preview_values = dict(values)
    if current_placeholder is not None and current_input_value:
        preview_values[current_placeholder] = current_input_value

    preview = _render_template_preview(template_content, preview_values)
    syntax = Syntax(
        preview.text,
        "org",
        theme=DEFAULT_OUTPUT_THEME,
        line_numbers=False,
        word_wrap=True,
    )
    highlighted = syntax.highlight(preview.text)
    if current_placeholder is not None:
        for start, end in preview.placeholder_spans.get(current_placeholder, []):
            if end > start:
                highlighted.stylize("bold black on bright_yellow", start, end)
    return highlighted


def _static_placeholder_values(document: Document) -> dict[str, str]:
    """Build values for static non-interactive placeholders."""
    now = datetime.now().astimezone().replace(microsecond=0)
    day_name = _ORG_WEEKDAY_ABBR[now.weekday()]
    today_org = f"<{now:%Y-%m-%d} {day_name}>"
    now_org = f"<{now:%Y-%m-%d} {day_name} {now:%H:%M}>"
    next_id = str(len(list(document)) + 1)
    return {
        "uuid": str(uuid4()),
        "today": today_org,
        "now": now_org,
        "id": next_id,
    }


def _parent_placeholder_values(parent_heading: Heading) -> dict[str, str]:
    """Build parent-based placeholders for one resolved parent heading."""

    def _to_string(value: object) -> str:
        if value is None:
            return ""
        return str(value)

    return {
        "parent_category": _to_string(parent_heading.category),
        "parent_title": _to_string(parent_heading.title_text),
        "parent_todo": _to_string(parent_heading.todo),
        "parent_id": _to_string(parent_heading.id),
    }


def _build_static_placeholder_values(
    document: Document,
    parent_heading: Heading | None,
) -> dict[str, str]:
    """Build static placeholder map, optionally including parent placeholders."""
    static_values = _static_placeholder_values(document)
    if parent_heading is not None:
        static_values.update(_parent_placeholder_values(parent_heading))
    return static_values


def _parse_set_values(set_values: list[str] | None) -> dict[str, str]:
    """Parse repeated --set KEY=VALUE options into one map."""
    if set_values is None:
        return {}

    parsed: dict[str, str] = {}
    for raw_value in set_values:
        if "=" not in raw_value:
            raise typer.BadParameter(f"--set must be KEY=VALUE, got {raw_value!r}")
        key, value = raw_value.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            raise typer.BadParameter("--set key cannot be empty")
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_-]*", normalized_key):
            raise typer.BadParameter(
                f"--set key {normalized_key!r} is not a valid template parameter name",
            )
        parsed[normalized_key] = value
    return parsed


def _document_placeholder_values(document: Document) -> dict[str, str]:
    """Return explicit document-backed placeholder values."""

    def _to_optional_string(value: object) -> str | None:
        if value is None:
            return None
        text = str(value)
        if not text:
            return None
        return text

    values = {
        "document_category": _to_optional_string(document.category),
        "document_filename": _to_optional_string(document.filename),
        "document_title": _to_optional_string(document.title),
        "document_author": _to_optional_string(document.author),
        "document_description": _to_optional_string(document.description),
    }
    return {key: value for key, value in values.items() if value is not None}


def resolve_initial_placeholder_values(
    placeholders: list[str],
    set_values: dict[str, str],
    static_values: dict[str, str],
    document_values: dict[str, str],
) -> tuple[dict[str, str], list[str]]:
    """Resolve initial placeholder values without prompting."""
    values: dict[str, str] = {}
    unresolved_placeholders: list[str] = []
    for placeholder in placeholders:
        if placeholder in set_values:
            values[placeholder] = set_values[placeholder]
            continue
        if placeholder in static_values:
            values[placeholder] = static_values[placeholder]
            continue
        if placeholder in document_values:
            values[placeholder] = document_values[placeholder]
            continue
        if placeholder in values:
            continue
        unresolved_placeholders.append(placeholder)
    return values, unresolved_placeholders


def _render_capture_content_with_values(template_content: str, values: dict[str, str]) -> str:
    """Render capture content from fully resolved placeholder values."""

    def _replace(match: re.Match[str]) -> str:
        return values[match.group(1)]

    rendered = _PLACEHOLDER_RE.sub(_replace, template_content)
    if rendered.endswith("\n"):
        return rendered
    return f"{rendered}\n"


def _validate_rendered_heading(rendered_content: str) -> Heading:
    """Parse rendered capture template as a single heading."""
    try:
        return Heading.from_source(rendered_content)
    except ValueError as err:
        raise typer.BadParameter(f"Invalid rendered capture heading: {err}") from err


def _resolve_parent_from_selector(document: Document, parent_selector: str) -> Heading:
    """Resolve one parent heading from selector expression against one target document."""
    normalized_selector = parent_selector.strip()
    if not normalized_selector:
        raise typer.BadParameter("Capture template parent selector cannot be empty")

    query_text = f".[] | select({normalized_selector})"

    try:
        compiled_query = compile_query_text(query_text)
    except QueryParseError as err:
        raise typer.BadParameter(f"Invalid parent selector: {err}") from err

    try:
        results = compiled_query(Stream([document]), EvalContext({}))
    except QueryRuntimeError as err:
        raise typer.BadParameter(f"Parent selector failed: {err}") from err

    matches_by_identity: dict[int, Heading] = {}
    for result in results:
        if not isinstance(result, Heading):
            raise typer.BadParameter("Parent selector must match task headings")
        matches_by_identity[id(result)] = result

    matches = list(matches_by_identity.values())
    if not matches:
        raise typer.BadParameter("Parent selector did not match any heading")
    if len(matches) > 1:
        raise typer.BadParameter("Parent selector matched multiple headings")
    return matches[0]


def _attach_heading(document: Document, parent_heading: Heading | None, heading: Heading) -> None:
    """Attach heading at root or under one resolved parent."""
    if parent_heading is None:
        document.children.append(heading)
        return
    parent_heading.children.append(heading)


def prepare_capture_plan(args: TasksCaptureArgs, template_name: str) -> CapturePlan:
    """Prepare capture plan from resolved template and current document state."""
    templates = config_module.CONFIG_CAPTURE_TEMPLATES
    template = templates[template_name]
    target_file = template["file"] if args.file is None else args.file
    template_parent_selector = template.get("parent")
    document = load_document(target_file)

    parent_heading = None
    if args.parent is not None:
        parent_heading = resolve_parent_heading(document, args.parent)
    elif template_parent_selector is not None:
        parent_heading = _resolve_parent_from_selector(document, template_parent_selector)

    placeholders = _template_placeholders(template["content"])
    set_values = _parse_set_values(args.set_values)
    unknown_names = sorted(set(set_values) - set(placeholders))
    if unknown_names:
        unknown_list = ", ".join(unknown_names)
        logger.warning("Ignoring unknown capture --set parameter(s): %s", unknown_list)

    static_values = _build_static_placeholder_values(document, parent_heading)
    document_values = _document_placeholder_values(document)
    values, unresolved_placeholders = resolve_initial_placeholder_values(
        placeholders,
        set_values,
        static_values,
        document_values,
    )
    return CapturePlan(
        args=args,
        template_name=template_name,
        template_content=template["content"],
        document=document,
        parent_heading=parent_heading,
        placeholders=placeholders,
        values=values,
        unresolved_placeholders=unresolved_placeholders,
    )


def _missing_template_name_error() -> typer.BadParameter:
    return typer.BadParameter("Capture template name is required in non-interactive mode")


def _missing_placeholder_error(unresolved_placeholders: list[str]) -> typer.BadParameter:
    names = ", ".join(unresolved_placeholders)
    return typer.BadParameter(f"Missing placeholder values for: {names}")


def finalize_capture_plan(
    plan: CapturePlan,
    values: dict[str, str],
    *,
    interactive_used: bool,
) -> TasksCaptureResult:
    """Render and save the prepared capture plan."""
    rendered_content = _render_capture_content_with_values(plan.template_content, values)
    heading = _validate_rendered_heading(rendered_content)
    _attach_heading(plan.document, plan.parent_heading, heading)
    save_document(plan.document)
    return TasksCaptureResult(
        template_name=plan.template_name,
        heading=heading,
        document=plan.document,
        interactive_used=interactive_used,
    )
