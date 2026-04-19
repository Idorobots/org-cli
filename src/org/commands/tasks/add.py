"""Tasks add command."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import typer
from org_parser.document import Document, Heading

from org import config as config_module
from org.cli_common import resolve_input_paths
from org.commands.tasks.common import (
    apply_subtree_level,
    load_document,
    normalize_optional_value,
    normalize_selector,
    parse_comment_flag,
    parse_counter,
    parse_properties_json,
    parse_tags_csv,
    parse_timestamp,
    resolve_parent_heading,
    save_document,
)


_TASK_TEMPLATE = "{heading}\n{planning}{properties}{body}"


@dataclass
class AddArgs:
    """Arguments for the tasks add command."""

    files: list[str] | None
    config: str
    level: int | None
    todo: str | None
    priority: str | None
    comment: str | None
    title: str | None
    counter: str | None
    tags: str | None
    heading: str | None
    deadline: str | None
    scheduled: str | None
    closed: str | None
    properties: str | None
    category: str | None
    id_value: str | None
    body: str | None
    parent: str | None
    file: str | None


def _validate_heading_option_exclusivity(args: AddArgs) -> None:
    """Reject combinations where --heading is mixed with incompatible switches."""
    if args.heading is None:
        return

    conflicts: list[str] = []
    if args.tags is not None:
        conflicts.append("--tags")
    if args.counter is not None:
        conflicts.append("--counter")
    if args.title is not None:
        conflicts.append("--title")
    if args.comment is not None:
        conflicts.append("--comment")
    if args.priority is not None:
        conflicts.append("--priority")
    if args.todo is not None:
        conflicts.append("--todo")
    if args.level is not None:
        conflicts.append("--level")

    if conflicts:
        conflicts_text = ", ".join(conflicts)
        raise typer.BadParameter(f"--heading cannot be combined with: {conflicts_text}")


def _has_structured_heading_component(args: AddArgs) -> bool:
    """Return true when structured heading options provide heading source."""
    comment_enabled = parse_comment_flag(args.comment) if args.comment is not None else False
    return args.todo is not None or comment_enabled or args.title is not None


def _should_read_task_from_stdin(args: AddArgs) -> bool:
    """Return true when heading source should be read from stdin."""
    return args.heading is None and not _has_structured_heading_component(args)


def _read_task_source_from_stdin() -> str:
    """Read complete task source from stdin."""
    task_source = sys.stdin.read()
    if task_source.strip():
        return task_source
    raise typer.BadParameter(
        "Task heading is empty. Provide --heading, at least one of --todo/--comment/--title, "
        "or pass task source via stdin",
    )


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


def _resolve_level(level: int | None, parent_level: int | None) -> int:
    """Resolve effective heading level from CLI options and parent context."""
    if level is not None:
        if level < 1:
            raise typer.BadParameter("--level must be greater than or equal to 1")
        if parent_level is not None and level <= parent_level:
            raise typer.BadParameter(
                "--level must be greater than parent level when --parent is used",
            )
        return level

    if parent_level is not None:
        return parent_level + 1
    return 1


def _build_heading_line_from_fields(args: AddArgs, level: int) -> str:
    """Build a heading line from structured heading switches."""
    marker = "*" * level
    metadata_tokens: list[str] = []
    if args.todo is not None:
        metadata_tokens.append(args.todo)
    if args.priority is not None:
        metadata_tokens.append(f"[#{args.priority}]")
    if args.comment is not None and parse_comment_flag(args.comment):
        metadata_tokens.append("COMMENT")

    title_parts = [part for part in (args.title, args.counter) if part is not None]
    title_text = " ".join(title_parts)

    heading_line = marker
    if metadata_tokens:
        heading_line = f"{heading_line} {' '.join(metadata_tokens)}"
    if title_text:
        heading_line = f"{heading_line} {title_text}"

    parsed_tags = [] if args.tags is None else parse_tags_csv(args.tags)
    if parsed_tags:
        heading_line = f"{heading_line} :{':'.join(parsed_tags)}:"
    elif metadata_tokens and not title_text:
        heading_line = f"{heading_line} "

    return heading_line


def _resolve_heading_line(args: AddArgs, level: int) -> str:
    """Resolve heading line either from --heading or structured switches."""
    if args.heading is None:
        return _build_heading_line_from_fields(args, level)

    heading_value = args.heading.strip()
    if not heading_value:
        raise typer.BadParameter("--heading cannot be empty")
    if "\n" in heading_value or "\r" in heading_value:
        raise typer.BadParameter("--heading must be exactly one line")
    return heading_value


def _planning_line(args: AddArgs) -> str:
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


def _build_properties(args: AddArgs) -> dict[str, str]:
    """Build final property map from --properties, --category, and --id."""
    properties = {} if args.properties is None else parse_properties_json(args.properties)

    if args.category is not None:
        properties["CATEGORY"] = args.category

    normalized_id = normalize_selector(args.id_value, "--id")
    if normalized_id is not None:
        properties["ID"] = normalized_id
    elif "ID" not in properties:
        properties["ID"] = str(uuid4())

    return properties


def _properties_block(args: AddArgs) -> str:
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


def _build_task_source(args: AddArgs, parent_level: int | None) -> str:
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


def _apply_stdin_level_edit(args: AddArgs, parent_level: int | None, heading: Heading) -> None:
    """Apply effective level edits to stdin-provided heading."""
    if args.level is not None:
        target_level = _resolve_level(args.level, parent_level)
    else:
        target_level = _resolve_level(heading.level, parent_level)
    apply_subtree_level(heading, target_level)


def _apply_stdin_heading_metadata_edits(args: AddArgs, heading: Heading) -> None:
    """Apply heading metadata edits on stdin heading."""
    if args.priority is not None:
        heading.priority = normalize_optional_value(args.priority)
    if args.comment is not None:
        heading.is_comment = parse_comment_flag(args.comment)
    if args.counter is not None:
        heading.counter = parse_counter(args.counter)
    if args.tags is not None:
        heading.heading_tags = parse_tags_csv(args.tags)


def _apply_stdin_planning_edits(args: AddArgs, heading: Heading) -> None:
    """Apply planning timestamp edits on stdin heading."""
    if args.scheduled is not None:
        heading.scheduled = parse_timestamp(args.scheduled, "--scheduled")
    if args.deadline is not None:
        heading.deadline = parse_timestamp(args.deadline, "--deadline")
    if args.closed is not None:
        heading.closed = parse_timestamp(args.closed, "--closed")


def _apply_stdin_property_edits(args: AddArgs, heading: Heading) -> None:
    """Apply property, category, and ID edits on stdin heading."""
    if args.properties is not None:
        heading.properties = parse_properties_json(args.properties)
    if args.category is not None:
        heading.heading_category = normalize_optional_value(args.category)

    normalized_id = normalize_selector(args.id_value, "--id")
    if normalized_id is not None:
        heading.id = normalized_id
    elif heading.id is None:
        heading.id = str(uuid4())


def _apply_stdin_task_edits(args: AddArgs, parent_level: int | None, heading: Heading) -> None:
    """Apply non-source add switches as edits on stdin heading."""
    _apply_stdin_level_edit(args, parent_level, heading)
    _apply_stdin_heading_metadata_edits(args, heading)
    _apply_stdin_planning_edits(args, heading)
    _apply_stdin_property_edits(args, heading)

    if args.body is not None:
        heading.body = args.body


def _build_heading_from_stdin(args: AddArgs, parent_level: int | None) -> Heading:
    """Read task heading source from stdin and apply edit switches."""
    task_source = _read_task_source_from_stdin()
    heading = _validate_task_source(task_source)
    _apply_stdin_task_edits(args, parent_level, heading)
    return heading


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


def run_tasks_add(args: AddArgs) -> None:
    """Run the tasks add command."""
    _validate_heading_option_exclusivity(args)
    read_from_stdin = _should_read_task_from_stdin(args)

    filename = _resolve_target_file(args.file, args.files)
    document = load_document(filename)
    parent_heading: Heading | None = None
    if args.parent is not None:
        parent_heading = resolve_parent_heading(document, args.parent)

    parent_level = parent_heading.level if parent_heading is not None else None
    if read_from_stdin:
        heading = _build_heading_from_stdin(args, parent_level)
    else:
        task_source = _build_task_source(args, parent_level)
        heading = _validate_task_source(task_source)
        _validate_parent_level(parent_level, heading)

    _attach_heading(document, parent_heading, heading)
    save_document(document)


def register(app: typer.Typer) -> None:
    """Register the tasks add command."""

    @app.command("add")
    def tasks_add(  # noqa: PLR0913
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
        comment: str | None = typer.Option(
            None,
            "--comment",
            metavar="BOOL",
            help="Set COMMENT flag using true or false",
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
        tags: str | None = typer.Option(
            None,
            "--tags",
            metavar="TAG1,TAG2",
            help="Comma-separated tags to set",
        ),
        heading: str | None = typer.Option(
            None,
            "--heading",
            metavar="HEADING",
            help=(
                "Entire heading line for the task. Cannot be combined with --level, --todo, "
                "--priority, --comment, --title, --counter, or --tags"
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
        properties: str | None = typer.Option(
            None,
            "--properties",
            metavar="JSON",
            help="Properties JSON object to set (empty string clears)",
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
        args = AddArgs(
            files=files,
            config=config,
            level=level,
            todo=todo,
            priority=priority,
            comment=comment,
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
        config_module.log_applied_config_defaults(args, sys.argv[1:], "tasks add")
        config_module.log_command_arguments(args, "tasks add")
        run_tasks_add(args)
