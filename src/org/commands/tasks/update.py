"""Tasks update command."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import typer
from org_parser.document import Document, Heading
from org_parser.element import ListItem, Repeat
from org_parser.time import Clock
from rich.console import Console
from rich.prompt import Confirm

from org import config as config_module
from org.cli_common import resolve_input_paths
from org.color import should_use_color
from org.commands.tasks.common import (
    apply_subtree_level,
    iter_descendants,
    load_document,
    normalize_optional_value,
    normalize_selector,
    parse_comment_flag,
    parse_counter,
    parse_properties_json,
    parse_tags_csv,
    parse_timestamp,
    resolve_headings_by_query,
    resolve_parent_heading,
    resolve_task_selector_query,
    save_document,
)


logger = logging.getLogger("org")


@dataclass
class UpdateArgs:
    """Arguments for the tasks update command."""

    files: list[str] | None
    config: str
    query_title: str | None
    query_id: str | None
    query: str | None
    level: int | None
    todo: str | None
    priority: str | None
    comment: str | None
    title: str | None
    id_value: str | None
    counter: str | None
    deadline: str | None
    scheduled: str | None
    closed: str | None
    category: str | None
    body: str | None
    parent: str | None
    tags: str | None
    properties: str | None
    add_clock_entry: list[str] | None
    remove_clock_entry: list[str] | None
    add_repeat: list[str] | None
    remove_repeat: list[str] | None
    add_tag: list[str] | None
    remove_tag: list[str] | None
    add_property: list[str] | None
    remove_property: list[str] | None
    file: str | None
    yes: bool
    color_flag: bool | None


def _resolve_destination_document(
    file_value: str | None,
    source_document: Document,
    destination_cache: dict[str, Document],
) -> Document:
    """Resolve destination document for --file or return source document."""
    if file_value is None:
        return source_document

    path = Path(file_value)
    if not path.exists():
        raise typer.BadParameter(f"File '{file_value}' not found")
    if not path.is_file():
        raise typer.BadParameter(f"Path '{file_value}' is not a file")

    source_filename = source_document.filename
    if source_filename is not None:
        source_path = Path(source_filename)
        if source_path.resolve() == path.resolve():
            return source_document

    cache_key = str(path.resolve())
    cached = destination_cache.get(cache_key)
    if cached is not None:
        return cached

    loaded_document = load_document(str(path))
    destination_cache[cache_key] = loaded_document
    return loaded_document


def _parse_property_option(value: str, option_name: str) -> tuple[str, str]:
    """Parse one property value in KEY=VALUE format."""
    if "=" not in value:
        raise typer.BadParameter(f"{option_name} must be in KEY=VALUE format, got {value!r}")

    key, property_value = value.split("=", 1)
    normalized_key = key.strip()
    if not normalized_key:
        raise typer.BadParameter(f"{option_name} key cannot be empty")
    return normalized_key, property_value


def _parse_property_key(value: str, option_name: str) -> str:
    """Parse one property key from remove-property style options."""
    normalized = value.strip()
    if not normalized:
        raise typer.BadParameter(f"{option_name} key cannot be empty")
    return normalized


def _parse_tag_option(value: str, option_name: str) -> str:
    """Parse one tag value from add/remove-tag options."""
    normalized = value.strip()
    if not normalized:
        raise typer.BadParameter(f"{option_name} cannot be empty")
    return normalized


def _parse_clock_entry(value: str, option_name: str) -> Clock:
    """Parse one clock entry line into a Clock object."""
    normalized = normalize_selector(value, option_name)
    if normalized is None:
        raise typer.BadParameter(f"{option_name} cannot be empty")
    try:
        return Clock.from_source(normalized)
    except (TypeError, ValueError) as err:
        raise typer.BadParameter(f"Value {value!r} is not a valid Org clock entry") from err


def _parse_repeat_entry(value: str, option_name: str, heading: Heading) -> Repeat:
    """Parse one repeat line into a Repeat object."""
    normalized = normalize_selector(value, option_name)
    if normalized is None:
        raise typer.BadParameter(f"{option_name} cannot be empty")

    try:
        list_item = ListItem.from_source(normalized)
    except (TypeError, ValueError) as err:
        raise typer.BadParameter(f"Value {value!r} is not a valid Org repeat entry") from err

    # FIXME: Switch to ListItem.document once org_parser exposes it reliably.
    repeat = Repeat.from_list_item(list_item, heading.document)
    if repeat is None:
        raise typer.BadParameter(f"Value {value!r} is not a valid Org repeat entry")
    return Repeat(after=repeat.after, before=repeat.before, timestamp=repeat.timestamp)


def _clock_entry_key(clock_entry: Clock) -> tuple[str, str]:
    """Build a stable key for matching clock entries."""
    timestamp_text = "" if clock_entry.timestamp is None else str(clock_entry.timestamp)
    duration_text = "" if clock_entry.duration is None else clock_entry.duration
    return (timestamp_text, duration_text)


def _repeat_key(repeat: Repeat) -> tuple[str, str, str]:
    """Build a stable key for matching repeat entries."""
    before = "" if repeat.before is None else repeat.before
    after = "" if repeat.after is None else repeat.after
    return (before, after, str(repeat.timestamp))


def _validate_parent_target(heading: Heading, parent_heading: Heading | None) -> None:
    """Validate parent target does not create loops."""
    if parent_heading is None:
        return
    if parent_heading is heading:
        raise typer.BadParameter("--parent cannot point to the task being updated")
    if parent_heading in iter_descendants(heading):
        raise typer.BadParameter("--parent cannot point to a descendant of the updated task")


def _move_heading(
    heading: Heading,
    parent_heading: Heading | None,
    target_document: Document,
) -> None:
    """Move heading under a new parent or to top-level."""
    current_parent = heading.parent
    current_parent.children.remove(heading)

    if parent_heading is None:
        target_document.children.append(heading)
    else:
        parent_heading.children.append(heading)
    heading.document = target_document
    for descendant in iter_descendants(heading):
        descendant.document = target_document


def _validate_level(level: int, parent_level: int) -> None:
    """Validate requested level against parent level rules."""
    if level < 1:
        raise typer.BadParameter("--level must be greater than or equal to 1")
    if parent_level > 0 and level <= parent_level:
        raise typer.BadParameter("--level must be greater than parent level")


def _heading_parent_level(heading: Heading) -> int:
    """Return parent level for heading, using 0 for document root."""
    if isinstance(heading.parent, Heading):
        return heading.parent.level
    return 0


def _resolve_target_parent(document: Document, parent_value: str) -> Heading | None:
    """Resolve --parent option to heading or top-level target."""
    normalized = parent_value.strip()
    if not normalized:
        return None
    return resolve_parent_heading(document, normalized)


def _apply_parent_and_level_updates(args: UpdateArgs, heading: Heading) -> None:
    """Apply parent and level updates while enforcing hierarchy rules."""
    document = heading.document
    parent_value = args.parent
    target_parent: Heading | None = None

    if parent_value is not None:
        target_parent = _resolve_target_parent(document, parent_value)
        _validate_parent_target(heading, target_parent)
        _move_heading(heading, target_parent, document)

    if parent_value is None and args.level is None:
        return

    if parent_value is not None:
        parent_level = target_parent.level if target_parent is not None else 0
        if args.level is None:
            target_level = parent_level + 1 if parent_level > 0 else 1
        else:
            _validate_level(args.level, parent_level)
            target_level = args.level
    else:
        parent_level = _heading_parent_level(heading)
        if args.level is None:
            return
        _validate_level(args.level, parent_level)
        target_level = args.level

    apply_subtree_level(heading, target_level)


def _apply_heading_metadata_updates(args: UpdateArgs, heading: Heading) -> None:
    """Apply heading-line metadata updates."""
    if args.todo is not None:
        heading.todo = normalize_optional_value(args.todo)
    if args.priority is not None:
        heading.priority = normalize_optional_value(args.priority)
    if args.comment is not None:
        heading.is_comment = parse_comment_flag(args.comment)
    if args.title is not None:
        heading.title = normalize_optional_value(args.title)
    if args.counter is not None:
        heading.counter = parse_counter(args.counter)


def _apply_planning_updates(args: UpdateArgs, heading: Heading) -> None:
    """Apply planning timestamp updates."""
    if args.scheduled is not None:
        heading.scheduled = parse_timestamp(args.scheduled)
    if args.deadline is not None:
        heading.deadline = parse_timestamp(args.deadline)
    if args.closed is not None:
        heading.closed = parse_timestamp(args.closed)


def _apply_org_metadata_updates(args: UpdateArgs, heading: Heading) -> None:
    """Apply tags/properties/category/id metadata updates."""
    if args.tags is not None:
        heading.heading_tags = parse_tags_csv(args.tags)
    if args.properties is not None:
        heading.properties = parse_properties_json(args.properties)
    if args.category is not None:
        heading.heading_category = normalize_optional_value(args.category)
    if args.id_value is not None:
        heading.id = normalize_optional_value(args.id_value)


def _apply_tag_updates(args: UpdateArgs, heading: Heading) -> None:
    """Apply fine-grained tag add/remove updates."""
    if args.add_tag is not None:
        for raw_tag in args.add_tag:
            tag = _parse_tag_option(raw_tag, "--add-tag")
            if tag in heading.heading_tags:
                continue
            heading.heading_tags.append(tag)

    if args.remove_tag is not None:
        for raw_tag in args.remove_tag:
            tag = _parse_tag_option(raw_tag, "--remove-tag")
            if tag not in heading.heading_tags:
                raise typer.BadParameter(f"--remove-tag target {tag!r} is not present on the task")
            heading.heading_tags.remove(tag)


def _apply_property_updates(args: UpdateArgs, heading: Heading) -> None:
    """Apply fine-grained property add/remove updates."""
    if args.add_property is not None:
        for raw_property in args.add_property:
            key, value = _parse_property_option(raw_property, "--add-property")
            heading.properties[key] = value

    if args.remove_property is not None:
        for raw_property in args.remove_property:
            key = _parse_property_key(raw_property, "--remove-property")
            if key not in heading.properties:
                raise typer.BadParameter(
                    f"--remove-property target {key!r} is not present on the task",
                )
            del heading.properties[key]


def _apply_clock_entry_updates(args: UpdateArgs, heading: Heading) -> None:
    """Apply fine-grained clock entry add/remove updates."""
    if args.add_clock_entry is not None:
        for raw_clock_entry in args.add_clock_entry:
            clock_entry = _parse_clock_entry(raw_clock_entry, "--add-clock-entry")
            heading.clock_entries.append(clock_entry)

    if args.remove_clock_entry is not None:
        for raw_clock_entry in args.remove_clock_entry:
            target_clock_entry = _parse_clock_entry(raw_clock_entry, "--remove-clock-entry")
            target_key = _clock_entry_key(target_clock_entry)
            matching_entry = next(
                (
                    clock_entry
                    for clock_entry in heading.clock_entries
                    if _clock_entry_key(clock_entry) == target_key
                ),
                None,
            )
            if matching_entry is None:
                raise typer.BadParameter(
                    "--remove-clock-entry target is not present on the task",
                )
            heading.clock_entries.remove(matching_entry)


def _apply_repeat_updates(args: UpdateArgs, heading: Heading) -> None:
    """Apply fine-grained repeat add/remove updates."""
    if args.add_repeat is not None:
        for raw_repeat in args.add_repeat:
            repeat = _parse_repeat_entry(raw_repeat, "--add-repeat", heading)
            heading.repeats.append(repeat)

    if args.remove_repeat is not None:
        for raw_repeat in args.remove_repeat:
            target_repeat = _parse_repeat_entry(raw_repeat, "--remove-repeat", heading)
            target_key = _repeat_key(target_repeat)
            matching_entry = next(
                (repeat for repeat in heading.repeats if _repeat_key(repeat) == target_key),
                None,
            )
            if matching_entry is None:
                raise typer.BadParameter("--remove-repeat target is not present on the task")
            heading.repeats.remove(matching_entry)


def _apply_fine_grained_org_metadata_updates(args: UpdateArgs, heading: Heading) -> None:
    """Apply fine-grained Org metadata updates after bulk replacements."""
    _apply_tag_updates(args, heading)
    _apply_property_updates(args, heading)
    _apply_clock_entry_updates(args, heading)
    _apply_repeat_updates(args, heading)


def _validate_update_option_conflicts(args: UpdateArgs) -> None:
    """Reject mutually-exclusive bulk and fine-grained update switches."""
    if args.tags is not None and (args.add_tag is not None or args.remove_tag is not None):
        raise typer.BadParameter("--tags cannot be combined with --add-tag or --remove-tag")
    if args.properties is not None and (
        args.add_property is not None or args.remove_property is not None
    ):
        raise typer.BadParameter(
            "--properties cannot be combined with --add-property or --remove-property",
        )


def _apply_field_updates(args: UpdateArgs, heading: Heading) -> None:
    """Apply non-hierarchy field updates to one heading."""
    _apply_heading_metadata_updates(args, heading)
    _apply_planning_updates(args, heading)
    _apply_org_metadata_updates(args, heading)
    _apply_fine_grained_org_metadata_updates(args, heading)
    if args.body is not None:
        heading.body = args.body


def run_tasks_update(args: UpdateArgs) -> None:
    """Run the tasks update command."""
    selector_query = resolve_task_selector_query(args.query_title, args.query_id, args.query)
    _validate_update_option_conflicts(args)
    filenames = resolve_input_paths(args.files)

    headings = resolve_headings_by_query(filenames, selector_query)
    selected_count = len(headings)
    logger.info("Selected %s tasks for update", selected_count)

    if not args.yes:
        color_enabled = should_use_color(args.color_flag)
        console = Console(no_color=not color_enabled, force_terminal=color_enabled)
        confirmed = Confirm.ask(
            f"Update {selected_count} tasks?",
            console=console,
            default=False,
            show_default=True,
            show_choices=True,
        )
        if not confirmed:
            logger.info("Update operation cancelled by user")
            typer.echo("Cancelled")
            return

    destination_cache: dict[str, Document] = {}
    documents_to_save: dict[int, Document] = {}
    for heading in headings:
        logger.info(
            "Updating task: file=%s title=%s id=%s tags=%s",
            heading.document.filename,
            heading.title_text,
            heading.id,
            list(heading.heading_tags),
        )
        source_document = heading.document
        destination_document = _resolve_destination_document(
            args.file,
            source_document,
            destination_cache,
        )

        if destination_document is not source_document:
            logger.info(
                "Moving task between files: source=%s destination=%s",
                source_document.filename,
                destination_document.filename,
            )
            _move_heading(heading, None, destination_document)

        _apply_parent_and_level_updates(args, heading)
        _apply_field_updates(args, heading)

        documents_to_save[id(destination_document)] = destination_document
        if source_document is not destination_document:
            documents_to_save[id(source_document)] = source_document

    for document in documents_to_save.values():
        logger.info("Saving updated file: %s", document.filename)
        document.sync_heading_id_index()
        save_document(document)

    typer.echo(f"Updated {selected_count} tasks.")


def register(app: typer.Typer) -> None:
    """Register the tasks update command."""

    @app.command("update")
    def tasks_update(  # noqa: PLR0913
        files: list[str] | None = typer.Argument(  # noqa: B008
            None,
            metavar="FILE",
            help="Org-mode archive files or directories to search",
        ),
        config: str = typer.Option(
            ".org-cli.yaml",
            "--config",
            metavar="FILE",
            help="Config file name to load from current directory",
        ),
        query_title: str | None = typer.Option(
            None,
            "--query-title",
            metavar="TEXT",
            help="Heading title text of the task to update",
        ),
        query_id: str | None = typer.Option(
            None,
            "--query-id",
            metavar="TEXT",
            help="ID of the task to update",
        ),
        query: str | None = typer.Option(
            None,
            "--query",
            metavar="QUERY",
            help="Generic query language selector expression",
        ),
        level: int | None = typer.Option(
            None,
            "--level",
            metavar="N",
            help="New heading level",
        ),
        todo: str | None = typer.Option(
            None,
            "--todo",
            metavar="KEY",
            help="New TODO state (empty string clears)",
        ),
        priority: str | None = typer.Option(
            None,
            "--priority",
            metavar="P",
            help="New priority marker (empty string clears)",
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
            help="New heading title text (empty string clears)",
        ),
        id_value: str | None = typer.Option(
            None,
            "--id",
            metavar="TEXT",
            help="New ID property value (empty string clears)",
        ),
        counter: str | None = typer.Option(
            None,
            "--counter",
            metavar="COUNTER",
            help="New completion counter (empty string clears)",
        ),
        deadline: str | None = typer.Option(
            None,
            "--deadline",
            metavar="TIMESTAMP",
            help="New deadline timestamp (empty string clears)",
        ),
        scheduled: str | None = typer.Option(
            None,
            "--scheduled",
            metavar="TIMESTAMP",
            help="New scheduled timestamp (empty string clears)",
        ),
        closed: str | None = typer.Option(
            None,
            "--closed",
            metavar="TIMESTAMP",
            help="New closed timestamp (empty string clears)",
        ),
        category: str | None = typer.Option(
            None,
            "--category",
            metavar="TEXT",
            help="New CATEGORY property value (empty string clears)",
        ),
        body: str | None = typer.Option(
            None,
            "--body",
            metavar="TEXT",
            help="New task body text",
        ),
        parent: str | None = typer.Option(
            None,
            "--parent",
            metavar="ID_OR_TITLE",
            help="Move task under parent ID/title (empty string moves to top-level)",
        ),
        tags: str | None = typer.Option(
            None,
            "--tags",
            metavar="TAG1,TAG2",
            help="Comma-separated tags to set (empty string clears)",
        ),
        properties: str | None = typer.Option(
            None,
            "--properties",
            metavar="JSON",
            help="Properties JSON object to set (empty string clears)",
        ),
        add_clock_entry: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--add-clock-entry",
            metavar="TEXT",
            help="Clock entry to add (repeatable)",
        ),
        remove_clock_entry: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--remove-clock-entry",
            metavar="TEXT",
            help="Clock entry to remove (repeatable)",
        ),
        add_repeat: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--add-repeat",
            metavar="TEXT",
            help="Repeat entry to add (repeatable)",
        ),
        remove_repeat: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--remove-repeat",
            metavar="TEXT",
            help="Repeat entry to remove (repeatable)",
        ),
        add_tag: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--add-tag",
            metavar="TAG",
            help="Tag to add (repeatable)",
        ),
        remove_tag: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--remove-tag",
            metavar="TAG",
            help="Tag to remove (repeatable)",
        ),
        add_property: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--add-property",
            metavar="P=V",
            help="Property to add in P=V format (repeatable)",
        ),
        remove_property: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--remove-property",
            metavar="P",
            help="Property key to remove (repeatable)",
        ),
        file: str | None = typer.Option(
            None,
            "--file",
            metavar="FILE",
            help="Move task to another file",
        ),
        yes: bool = typer.Option(
            False,
            "--yes",
            help="Automatically confirm without prompting",
        ),
        color_flag: bool | None = typer.Option(
            None,
            "--color/--no-color",
            help="Force colored output",
        ),
    ) -> None:
        """Update one task heading and persist the modified org document."""
        args = UpdateArgs(
            files=files,
            config=config,
            query_title=query_title,
            query_id=query_id,
            query=query,
            level=level,
            todo=todo,
            priority=priority,
            comment=comment,
            title=title,
            id_value=id_value,
            counter=counter,
            deadline=deadline,
            scheduled=scheduled,
            closed=closed,
            category=category,
            body=body,
            parent=parent,
            tags=tags,
            properties=properties,
            add_clock_entry=add_clock_entry,
            remove_clock_entry=remove_clock_entry,
            add_repeat=add_repeat,
            remove_repeat=remove_repeat,
            add_tag=add_tag,
            remove_tag=remove_tag,
            add_property=add_property,
            remove_property=remove_property,
            file=file,
            yes=yes,
            color_flag=color_flag,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "tasks update")
        config_module.log_command_arguments(args, "tasks update")
        run_tasks_update(args)
