"""Tasks create command."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import org_parser
import typer
from org_parser.document import Document, Heading

from org import config as config_module
from org.cli_common import resolve_input_paths


_TASK_TEMPLATE = "{heading}\n{planning}{properties}{body}"


@dataclass
class CreateArgs:
    """Arguments for the tasks create command."""

    files: list[str] | None
    config: str
    level: int | None
    todo: str | None
    priority: str | None
    is_comment: bool
    title: str | None
    counter: str | None
    tags: list[str] | None
    heading: str | None
    deadline: str | None
    scheduled: str | None
    closed: str | None
    properties: list[str] | None
    category: str | None
    id_value: str | None
    body: str | None
    parent: str | None
    file: str | None


def _validate_heading_option_exclusivity(args: CreateArgs) -> None:
    """Reject combinations where --heading is mixed with incompatible switches."""
    if args.heading is None:
        return

    conflicts: list[str] = []
    if args.tags is not None:
        conflicts.append("--tag")
    if args.counter is not None:
        conflicts.append("--counter")
    if args.title is not None:
        conflicts.append("--title")
    if args.is_comment:
        conflicts.append("--is-comment")
    if args.priority is not None:
        conflicts.append("--priority")
    if args.todo is not None:
        conflicts.append("--todo")
    if args.level is not None:
        conflicts.append("--level")

    if conflicts:
        conflicts_text = ", ".join(conflicts)
        raise typer.BadParameter(f"--heading cannot be combined with: {conflicts_text}")


def _validate_required_heading_components(args: CreateArgs) -> None:
    """Require at least one heading source component to be specified."""
    has_structured_heading_component = (
        args.todo is not None or args.is_comment or args.title is not None
    )
    if args.heading is not None or has_structured_heading_component:
        return
    raise typer.BadParameter(
        "Task heading is empty. Provide --heading or at least one of: --todo, --is-comment, --title"
    )


def _parse_property_option(value: str) -> tuple[str, str]:
    """Parse one --property value in KEY=VALUE format."""
    if "=" not in value:
        raise typer.BadParameter(f"--property must be in KEY=VALUE format, got '{value}'")

    key, property_value = value.split("=", 1)
    normalized_key = key.strip()
    if not normalized_key:
        raise typer.BadParameter("--property key cannot be empty")
    return normalized_key, property_value


def _resolve_target_file(file_option: str | None, files: list[str] | None) -> str:
    """Resolve the file that should receive the new heading."""
    if file_option is not None:
        file_path = Path(file_option)
        if not file_path.exists():
            raise typer.BadParameter(f"File '{file_option}' not found")
        if not file_path.is_file():
            raise typer.BadParameter(f"Path '{file_option}' is not a file")
        return str(file_path)

    resolved_files = resolve_input_paths(files)
    return resolved_files[0]


def _resolve_parent_heading(document: Document, parent_value: str) -> Heading:
    """Resolve one parent heading by id first, then title."""
    selector = parent_value.strip()
    if not selector:
        raise typer.BadParameter("--parent cannot be empty")

    id_match = document.heading_by_id(selector)
    if id_match is not None:
        return id_match

    nodes = list(document)
    title_matches = [node for node in nodes if node.title_text.strip() == selector]
    if len(title_matches) > 1:
        raise typer.BadParameter(
            f"--parent is ambiguous, multiple headings with title '{selector}'"
        )
    if len(title_matches) == 1:
        return title_matches[0]

    raise typer.BadParameter(f"--parent '{selector}' was not found")


def _load_document(path: str) -> Document:
    """Load org document from file for mutation."""
    try:
        return org_parser.load(path)
    except FileNotFoundError as err:
        raise typer.BadParameter(f"File '{path}' not found") from err
    except PermissionError as err:
        raise typer.BadParameter(f"Permission denied for '{path}'") from err
    except ValueError as err:
        raise typer.BadParameter(f"Unable to parse '{path}': {err}") from err


def _save_document(document: Document, path: str) -> None:
    """Persist updated org document back to disk."""
    try:
        org_parser.dump(document, path)
    except PermissionError as err:
        raise typer.BadParameter(f"Permission denied for '{path}'") from err


def _resolve_level(level: int | None, parent_level: int | None) -> int:
    """Resolve effective heading level from CLI options and parent context."""
    if level is not None:
        if level < 1:
            raise typer.BadParameter("--level must be greater than or equal to 1")
        if parent_level is not None and level <= parent_level:
            raise typer.BadParameter(
                "--level must be greater than parent level when --parent is used"
            )
        return level

    if parent_level is not None:
        return parent_level + 1
    return 1


def _build_heading_line_from_fields(args: CreateArgs, level: int) -> str:
    """Build a heading line from structured heading switches."""
    marker = "*" * level
    metadata_tokens: list[str] = []
    if args.todo is not None:
        metadata_tokens.append(args.todo)
    if args.priority is not None:
        metadata_tokens.append(f"[#{args.priority}]")
    if args.is_comment:
        metadata_tokens.append("COMMENT")

    title_parts = [part for part in (args.title, args.counter) if part is not None]
    title_text = " ".join(title_parts)

    heading_line = marker
    if metadata_tokens:
        heading_line = f"{heading_line} {' '.join(metadata_tokens)}"
    if title_text:
        heading_line = f"{heading_line} {title_text}"

    if args.tags:
        heading_line = f"{heading_line} :{':'.join(args.tags)}:"
    elif metadata_tokens and not title_text:
        heading_line = f"{heading_line} "

    return heading_line


def _resolve_heading_line(args: CreateArgs, level: int) -> str:
    """Resolve heading line either from --heading or structured switches."""
    if args.heading is None:
        return _build_heading_line_from_fields(args, level)

    heading_value = args.heading.strip()
    if not heading_value:
        raise typer.BadParameter("--heading cannot be empty")
    if "\n" in heading_value or "\r" in heading_value:
        raise typer.BadParameter("--heading must be exactly one line")
    return heading_value


def _planning_line(args: CreateArgs) -> str:
    """Build one org planning line from timestamp switches."""
    planning_tokens: list[str] = []
    if args.scheduled is not None:
        planning_tokens.append(f"SCHEDULED: {args.scheduled}")
    if args.deadline is not None:
        planning_tokens.append(f"DEADLINE: {args.deadline}")
    if args.closed is not None:
        planning_tokens.append(f"CLOSED: {args.closed}")
    if not planning_tokens:
        return ""
    return f"{' '.join(planning_tokens)}\n"


def _build_properties(args: CreateArgs) -> dict[str, str]:
    """Build final property map from --property, --category, and --id."""
    properties: dict[str, str] = {}
    for value in args.properties or []:
        key, property_value = _parse_property_option(value)
        properties[key] = property_value

    if args.category is not None:
        properties["CATEGORY"] = args.category
    if args.id_value is not None:
        properties["ID"] = args.id_value

    return properties


def _properties_block(args: CreateArgs) -> str:
    """Build an org properties drawer block."""
    properties = _build_properties(args)
    if not properties:
        return ""

    lines = [":PROPERTIES:"]
    for key, value in properties.items():
        lines.append(f":{key}: {value}")
    lines.append(":END:")
    return "\n".join(lines) + "\n"


def _body_block(body: str | None) -> str:
    """Build body block from --body value."""
    if body is None:
        return ""
    return f"{body}\n"


def _build_task_source(args: CreateArgs, parent_level: int | None) -> str:
    """Build task source from CLI options and hardcoded template."""
    level = _resolve_level(args.level, parent_level)
    heading_line = _resolve_heading_line(args, level)
    planning = _planning_line(args)
    properties = _properties_block(args)
    body = _body_block(args.body)
    return _TASK_TEMPLATE.format(
        heading=heading_line,
        planning=planning,
        properties=properties,
        body=body,
    )


def _validate_task_source(task_source: str) -> Heading:
    """Validate the generated task source by parsing it as exactly one heading."""
    try:
        return Heading.from_source(task_source)
    except ValueError as err:
        raise typer.BadParameter(f"Invalid task template: {err}") from err


def _validate_parent_level(parent_level: int | None, heading: Heading) -> None:
    """Ensure explicit --heading level is valid when attached to a parent."""
    if parent_level is None:
        return
    if heading.level <= parent_level:
        raise typer.BadParameter("Heading level must be greater than parent level")


def _attach_heading(document: Document, parent_heading: Heading | None, heading: Heading) -> None:
    """Attach heading to the document root or parent heading."""
    if parent_heading is None:
        document.children.append(heading)
        return
    parent_heading.children.append(heading)


def run_tasks_create(args: CreateArgs) -> None:
    """Run the tasks create command."""
    _validate_heading_option_exclusivity(args)
    _validate_required_heading_components(args)

    filename = _resolve_target_file(args.file, args.files)
    document = _load_document(filename)
    parent_heading: Heading | None = None
    if args.parent is not None:
        parent_heading = _resolve_parent_heading(document, args.parent)

    parent_level = parent_heading.level if parent_heading is not None else None
    task_source = _build_task_source(args, parent_level)
    heading = _validate_task_source(task_source)
    _validate_parent_level(parent_level, heading)

    _attach_heading(document, parent_heading, heading)
    _save_document(document, filename)


def register(app: typer.Typer) -> None:
    """Register the tasks create command."""

    @app.command("create")
    def tasks_create(  # noqa: PLR0913
        files: list[str] | None = typer.Argument(  # noqa: B008
            None,
            metavar="FILE",
            help="Org-mode archive files or directories used to resolve default target file",
        ),
        config: str = typer.Option(
            ".org-cli.json",
            "--config",
            metavar="FILE",
            help="Config file name to load from current directory",
        ),
        level: int | None = typer.Option(
            None,
            "--level",
            metavar="N",
            help="Heading level for the new task",
        ),
        todo: str | None = typer.Option(
            None,
            "--todo",
            metavar="KEY",
            help="TODO state for the new task",
        ),
        priority: str | None = typer.Option(
            None,
            "--priority",
            metavar="P",
            help="Priority marker for the new task",
        ),
        is_comment: bool = typer.Option(
            False,
            "--is-comment",
            help="Mark the heading as COMMENT",
        ),
        title: str | None = typer.Option(
            None,
            "--title",
            metavar="TEXT",
            help="Heading title text for the new task",
        ),
        counter: str | None = typer.Option(
            None,
            "--counter",
            metavar="COUNTER",
            help="Completion counter content for the new task",
        ),
        tags: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--tag",
            metavar="TAG",
            help="Tag to attach to the task (repeatable)",
        ),
        heading: str | None = typer.Option(
            None,
            "--heading",
            metavar="HEADING",
            help=(
                "Entire heading line for the task. Cannot be combined with --level, --todo, "
                "--priority, --is-comment, --title, --counter, or --tag"
            ),
        ),
        deadline: str | None = typer.Option(
            None,
            "--deadline",
            metavar="TIMESTAMP",
            help="Deadline timestamp for the new task",
        ),
        scheduled: str | None = typer.Option(
            None,
            "--scheduled",
            metavar="TIMESTAMP",
            help="Scheduled timestamp for the new task",
        ),
        closed: str | None = typer.Option(
            None,
            "--closed",
            metavar="TIMESTAMP",
            help="Closed timestamp for the new task",
        ),
        properties: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--property",
            metavar="KEY=VALUE",
            help="Property to attach to the task (repeatable)",
        ),
        category: str | None = typer.Option(
            None,
            "--category",
            metavar="TEXT",
            help="CATEGORY property value",
        ),
        id_value: str | None = typer.Option(
            None,
            "--id",
            metavar="TEXT",
            help="ID property value",
        ),
        body: str | None = typer.Option(
            None,
            "--body",
            metavar="TEXT",
            help="Task body text",
        ),
        parent: str | None = typer.Option(
            None,
            "--parent",
            metavar="ID_OR_TITLE",
            help="Parent heading id or title for inserting task as a child",
        ),
        file: str | None = typer.Option(
            None,
            "--file",
            metavar="FILE",
            help="Specific org file to update (overrides default file selection)",
        ),
    ) -> None:
        """Create a new task heading and append it to a selected org document."""
        args = CreateArgs(
            files=files,
            config=config,
            level=level,
            todo=todo,
            priority=priority,
            is_comment=is_comment,
            title=title,
            counter=counter,
            tags=tags,
            heading=heading,
            deadline=deadline,
            scheduled=scheduled,
            closed=closed,
            properties=properties,
            category=category,
            id_value=id_value,
            body=body,
            parent=parent,
            file=file,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "tasks create")
        config_module.log_command_arguments(args, "tasks create")
        run_tasks_create(args)
