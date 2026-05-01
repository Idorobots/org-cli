"""Tasks capture command for creating tasks from named templates."""

from __future__ import annotations

import logging
import re
import sys
import termios
import tty
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

import typer
from org_parser.document import Document, Heading
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from typer.rich_utils import _get_rich_console

from org import config as config_module
from org.commands.interactive_common import read_input_event, set_bracketed_paste
from org.commands.tasks.common import load_document, save_document
from org.output_format import DEFAULT_OUTPUT_THEME
from org.query_language import (
    EvalContext,
    QueryParseError,
    QueryRuntimeError,
    Stream,
    compile_query_text,
)


_PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s*}}")
_ORG_WEEKDAY_ABBR = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_FOOTER_CONTROLS = (
    "Enter confirm | Left/Right move cursor | Backspace delete left "
    "| Delete delete right | Ctrl-C cancel"
)
logger = logging.getLogger("org")


@dataclass
class TasksCaptureArgs:
    """Arguments for the tasks capture command."""

    template_name: str | None
    config: str
    file: str | None
    parent: str | None
    set_values: list[str] | None


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


def _select_template_name(template_names: list[str]) -> str:
    """Prompt user for template selection by numeric index."""
    typer.echo("Select capture template:")
    for index, name in enumerate(template_names, start=1):
        typer.echo(f"{index}) {name}")

    selected_text = typer.prompt("Template number").strip()
    if not selected_text:
        raise typer.BadParameter("Template selection cannot be empty")
    if not selected_text.isdigit():
        raise typer.BadParameter("Template selection must be a number")

    selected_index = int(selected_text)
    if selected_index < 1 or selected_index > len(template_names):
        raise typer.BadParameter(
            f"Unknown template number {selected_index}. "
            f"Valid template numbers: 1-{len(template_names)}",
        )
    return template_names[selected_index - 1]


def _resolve_template_name(
    template_name: str | None,
    templates: dict[str, dict[str, str]],
) -> str:
    """Resolve template name from CLI argument or interactive selection."""
    template_names = _template_names(templates)
    if template_name is None:
        return _select_template_name(template_names)

    if template_name in templates:
        return template_name

    valid_names = _valid_template_names_text(template_names)
    raise typer.BadParameter(
        f"Unknown capture template '{template_name}'. Valid templates: {valid_names}",
    )


def _template_placeholders(template_content: str) -> list[str]:
    """Return unique placeholders in first-appearance order."""
    placeholders = [match.group(1) for match in _PLACEHOLDER_RE.finditer(template_content)]
    return list(dict.fromkeys(placeholders))


@dataclass(frozen=True)
class _TemplatePreview:
    """Rendered capture template preview with placeholder spans."""

    text: str
    placeholder_spans: dict[str, list[tuple[int, int]]]


@dataclass(frozen=True)
class _FooterState:
    """Footer display state for interactive capture editor."""

    current_placeholder: str | None
    current_input_value: str
    cursor_position: int
    current_field_index: int | None
    total_fields: int


@dataclass(frozen=True)
class _ActiveField:
    """Descriptor for one actively edited placeholder field."""

    placeholder: str
    field_index: int
    total_fields: int


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
    return _TemplatePreview(
        text="".join(chunks),
        placeholder_spans=placeholder_spans,
    )


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


def _build_footer_prompt(
    footer_state: _FooterState,
) -> Text:
    """Build interactive footer prompt with visible cursor position."""
    if footer_state.current_placeholder is None:
        return Text(
            "All placeholders resolved",
            style="bold",
            no_wrap=True,
            overflow="ellipsis",
        )

    input_value_length = len(footer_state.current_input_value)
    clamped_cursor = max(0, min(footer_state.cursor_position, input_value_length))
    footer = Text(
        f"Value for '{footer_state.current_placeholder}': ",
        style="bold",
    )
    footer.append(footer_state.current_input_value[:clamped_cursor])
    if clamped_cursor < len(footer_state.current_input_value):
        footer.append(footer_state.current_input_value[clamped_cursor], style="reverse")
        footer.append(footer_state.current_input_value[clamped_cursor + 1 :])
    else:
        footer.append(" ", style="reverse")
    return footer


def _value_progress_marker(footer_state: _FooterState) -> str:
    """Build footer field progress marker text."""
    if footer_state.total_fields < 1:
        return "Value 0/0"
    if footer_state.current_field_index is None:
        return f"Value {footer_state.total_fields}/{footer_state.total_fields}"
    return f"Value {footer_state.current_field_index}/{footer_state.total_fields}"


def _build_footer_status_line(footer_state: _FooterState) -> Table:
    """Build footer status line with marker and key bindings."""
    status_line = Table.grid(expand=True)
    status_line.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    status_line.add_column(ratio=4, justify="right", no_wrap=True, overflow="ellipsis")
    status_line.add_row(
        Text(_value_progress_marker(footer_state), style="dim", no_wrap=True, overflow="ellipsis"),
        Text(_FOOTER_CONTROLS, style="dim", no_wrap=True, overflow="ellipsis"),
    )
    return status_line


def _count_wrapped_prompt_lines(
    footer_prompt: Text,
    *,
    console_width: int,
) -> int:
    """Count wrapped footer prompt lines for the current terminal width."""
    wrap_width = max(1, console_width)
    measure_console = Console(width=wrap_width, force_terminal=True)
    wrapped_lines = footer_prompt.wrap(
        measure_console,
        width=wrap_width,
        overflow="fold",
        no_wrap=False,
    )
    return max(1, len(wrapped_lines))


def _resolve_terminal_width() -> int:
    """Resolve interactive terminal width from Typer's Rich console."""
    return max(1, _get_rich_console(stderr=False).size.width)


def _build_fullscreen_capture_renderable(
    template_content: str,
    values: dict[str, str],
    footer_state: _FooterState,
    console_width: int,
) -> Layout:
    """Build full-screen capture renderable with template body and footer prompt."""
    footer_prompt = _build_footer_prompt(footer_state)
    footer_prompt_height = _count_wrapped_prompt_lines(footer_prompt, console_width=console_width)
    footer_height = max(2, 1 + footer_prompt_height)
    layout = Layout(name="capture")
    layout.split_column(
        Layout(name="body", ratio=1),
        Layout(name="separator", size=1),
        Layout(name="footer", size=footer_height),
    )
    layout["body"].update(
        _build_template_body(
            template_content,
            values,
            footer_state.current_placeholder,
            footer_state.current_input_value,
        ),
    )
    layout["separator"].update(Rule(style="dim"))
    layout["footer"].update(
        Group(
            _build_footer_status_line(footer_state),
            footer_prompt,
        ),
    )
    return layout


def _supports_live_template_prompt() -> bool:
    """Return whether interactive terminal supports live capture preview."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _prompt_unresolved_placeholders(
    placeholders: list[str],
    values: dict[str, str],
) -> dict[str, str]:
    """Prompt unresolved placeholders using standard CLI prompt fallback."""
    resolved_values = dict(values)
    for placeholder in placeholders:
        resolved_values[placeholder] = typer.prompt(
            f"Value for '{placeholder}'",
            default="",
            show_default=False,
        )
    return resolved_values


def _apply_input_event(
    value: str,
    cursor_position: int,
    event_name: str,
    event_text: str,
) -> tuple[str, int, bool]:
    """Apply one input event to editable text and cursor state."""
    if event_name == "ENTER":
        return (value, cursor_position, True)

    cursor_targets = {
        "LEFT": max(0, cursor_position - 1),
        "RIGHT": min(len(value), cursor_position + 1),
        "HOME": 0,
        "END": len(value),
    }
    target_cursor = cursor_targets.get(event_name)
    if target_cursor is not None:
        return (value, target_cursor, False)

    if event_name == "BACKSPACE" and cursor_position > 0:
        return (
            f"{value[: cursor_position - 1]}{value[cursor_position:]}",
            cursor_position - 1,
            False,
        )
    if event_name == "DELETE" and cursor_position < len(value):
        return (f"{value[:cursor_position]}{value[cursor_position + 1 :]}", cursor_position, False)
    if event_name == "TEXT":
        return (
            f"{value[:cursor_position]}{event_text}{value[cursor_position:]}",
            cursor_position + len(event_text),
            False,
        )
    return (value, cursor_position, False)


def _read_input_event_from_tty(fd: int) -> tuple[str, str]:
    """Read one input event while temporarily enabling raw mode."""
    previous_mode = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return read_input_event(fd, ctrl_p_as_paste=True)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous_mode)


def _read_live_placeholder_value(
    live: Live,
    template_content: str,
    resolved_values: dict[str, str],
    active_field: _ActiveField,
) -> str:
    """Read one placeholder value from raw keyboard events in live mode."""
    current_value = ""
    cursor_position = 0
    fd = sys.stdin.fileno()
    while True:
        live.update(
            _build_fullscreen_capture_renderable(
                template_content,
                resolved_values,
                _FooterState(
                    current_placeholder=active_field.placeholder,
                    current_input_value=current_value,
                    cursor_position=cursor_position,
                    current_field_index=active_field.field_index,
                    total_fields=active_field.total_fields,
                ),
                console_width=live.console.size.width,
            ),
            refresh=True,
        )
        event_name, event_text = _read_input_event_from_tty(fd)
        if event_name == "ESC":
            raise KeyboardInterrupt
        current_value, cursor_position, done = _apply_input_event(
            current_value,
            cursor_position,
            event_name,
            event_text,
        )
        if done:
            return current_value


def _prompt_with_live_preview(
    template_content: str,
    placeholders: list[str],
    values: dict[str, str],
) -> dict[str, str]:
    """Prompt unresolved placeholders in a full-screen interactive editor."""
    resolved_values = dict(values)
    total_fields = len(placeholders)
    try:
        fd = sys.stdin.fileno()
        termios.tcgetattr(fd)
    except OSError, ValueError, termios.error:
        return _prompt_unresolved_placeholders(placeholders, resolved_values)

    with Live(
        _build_fullscreen_capture_renderable(
            template_content,
            resolved_values,
            _FooterState(
                current_placeholder=placeholders[0],
                current_input_value="",
                cursor_position=0,
                current_field_index=1,
                total_fields=total_fields,
            ),
            console_width=_resolve_terminal_width(),
        ),
        screen=True,
        refresh_per_second=12,
        auto_refresh=False,
        transient=False,
    ) as live:
        set_bracketed_paste(True)
        try:
            for field_index, placeholder in enumerate(placeholders, start=1):
                resolved_values[placeholder] = _read_live_placeholder_value(
                    live,
                    template_content,
                    resolved_values,
                    _ActiveField(
                        placeholder=placeholder,
                        field_index=field_index,
                        total_fields=total_fields,
                    ),
                )

            live.update(
                _build_fullscreen_capture_renderable(
                    template_content,
                    resolved_values,
                    _FooterState(
                        current_placeholder=None,
                        current_input_value="",
                        cursor_position=0,
                        current_field_index=None,
                        total_fields=total_fields,
                    ),
                    console_width=live.console.size.width,
                ),
                refresh=True,
            )
        finally:
            set_bracketed_paste(False)

    return resolved_values


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


def _resolve_placeholder_values(
    template_content: str,
    placeholders: list[str],
    set_values: dict[str, str],
    static_values: dict[str, str],
    document_values: dict[str, str],
) -> dict[str, str]:
    """Resolve placeholder values from static values, --set, and prompts."""
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

    if _supports_live_template_prompt() and unresolved_placeholders:
        return _prompt_with_live_preview(template_content, unresolved_placeholders, values)

    for placeholder in unresolved_placeholders:
        values[placeholder] = typer.prompt(
            f"Value for '{placeholder}'",
            default="",
            show_default=False,
        )
    return values


def _render_capture_content(
    template_content: str,
    set_values: list[str] | None,
    static_values: dict[str, str],
    document: Document,
) -> str:
    """Render capture template content by replacing handlebars placeholders."""
    placeholders = _template_placeholders(template_content)
    provided_values = _parse_set_values(set_values)
    unknown_names = sorted(set(provided_values) - set(placeholders))
    if unknown_names:
        unknown_list = ", ".join(unknown_names)
        logger.warning("Ignoring unknown capture --set parameter(s): %s", unknown_list)

    values = _resolve_placeholder_values(
        template_content,
        placeholders,
        provided_values,
        static_values,
        _document_placeholder_values(document),
    )

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


def run_tasks_capture(args: TasksCaptureArgs) -> None:
    """Run tasks capture command using configured templates."""
    templates = config_module.CONFIG_CAPTURE_TEMPLATES
    _require_templates(templates)

    template_key = _resolve_template_name(args.template_name, templates)
    template = templates[template_key]
    target_file = template["file"] if args.file is None else args.file
    parent_selector = template.get("parent") if args.parent is None else args.parent
    document = load_document(target_file)

    parent_heading = None
    if parent_selector is not None:
        parent_heading = _resolve_parent_from_selector(document, parent_selector)

    static_values = _build_static_placeholder_values(document, parent_heading)
    rendered_content = _render_capture_content(
        template["content"],
        args.set_values,
        static_values,
        document,
    )
    heading = _validate_rendered_heading(rendered_content)

    _attach_heading(document, parent_heading, heading)
    save_document(document)


def register(app: typer.Typer) -> None:
    """Register the tasks capture command."""

    @app.command("capture")
    def capture(
        template_name: str | None = typer.Argument(
            None,
            metavar="TEMPLATE_NAME",
            help="Capture template name. If omitted, interactive selection is shown",
        ),
        config: str = typer.Option(
            ".org-cli.yaml",
            "--config",
            metavar="FILE",
            help="Config file name to load from current directory",
        ),
        file: str | None = typer.Option(
            None,
            "--file",
            metavar="FILE",
            help="Override template target file path",
        ),
        parent: str | None = typer.Option(
            None,
            "--parent",
            metavar="SELECTOR",
            help="Override template parent selector expression",
        ),
        set_values: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--set",
            metavar="KEY=VALUE",
            help="Set template parameter values without prompting",
        ),
    ) -> None:
        """Create a task from a configured capture template."""
        args = TasksCaptureArgs(
            template_name=template_name,
            config=config,
            file=file,
            parent=parent,
            set_values=set_values,
        )
        config_module.log_command_arguments(args, "tasks capture")
        run_tasks_capture(args)
