"""Agenda command for day-based task planning views."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

import click
import typer

import org.config.app
import org.logging
from org.pipeline.load import load_and_process_data
from org.tui.bits import build_console, processing_status, setup_output
from org.tui.help import interactive_help_command_text

from . import ui
from .app import run_agenda_app
from .views import resolve_view_context


logger = logging.getLogger("org")


@dataclass
class AgendaArgs:
    """Arguments for the agenda command."""

    files: list[str] | None
    config: str
    exclude: str | None
    mapping: str | None
    mapping_inline: dict[str, str] | None
    exclude_inline: list[str] | None
    todo_states: str
    done_states: str
    filter_priority: str | None
    filter_level: int | None
    filter_repeats_above: int | None
    filter_repeats_below: int | None
    filter_date_from: str | None
    filter_date_until: str | None
    filter_properties: list[str] | None
    filter_tags: list[str] | None
    filter_headings: list[str] | None
    filter_bodies: list[str] | None
    filter_completed: bool
    filter_not_completed: bool
    color_flag: bool | None
    width: int | None
    max_results: int | None
    offset: int
    order_by_level: bool
    order_by_file_order: bool
    order_by_file_order_reversed: bool
    order_by_priority: bool
    order_by_timestamp_asc: bool
    order_by_timestamp_desc: bool
    with_tags_as_category: bool
    date: str | None
    days: int
    no_completed: bool
    no_overdue: bool
    no_upcoming: bool
    future_repeats: bool
    view: str | None


def _resolve_tasks_limit(max_results: int | None) -> int:
    """Resolve effective tasks limit, defaulting to all available tasks."""
    if max_results is None:
        return sys.maxsize
    return max_results


def _validate_agenda_args(args: AgendaArgs) -> None:
    """Validate agenda arguments, including date parsing."""
    ui.resolve_agenda_start_date(args.date)


def run_agenda(args: AgendaArgs) -> None:
    """Run the agenda command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled, args.width)

    if args.offset < 0:
        raise typer.BadParameter("--offset must be non-negative")
    if args.max_results is not None and args.max_results < 0:
        raise typer.BadParameter("--limit must be non-negative")
    if args.days < 1:
        raise typer.BadParameter("--days must be at least 1")

    args.max_results = _resolve_tasks_limit(args.max_results)
    _validate_agenda_args(args)

    view_ctx = resolve_view_context(args)

    with processing_status(console, color_enabled):
        nodes, todo_states, done_states = load_and_process_data(args)

    if not nodes:
        console.print("No results", markup=False)
        return

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise click.UsageError("org agenda requires a TTY")

    run_agenda_app(
        args,
        nodes,
        ui.RenderContext(
            color_enabled=color_enabled,
            done_states=done_states,
            todo_states=todo_states,
        ),
        view_ctx,
    )


def register(app: typer.Typer) -> None:
    """Register the agenda command."""

    @app.command(
        "agenda",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
        help=interactive_help_command_text(
            "Show agenda for one day or a date range.",
            ui.AGENDA_HELP_ENTRIES,
        ),
    )
    def agenda(  # noqa: PLR0913
        files: list[str] | None = typer.Argument(  # noqa: B008
            None,
            metavar="FILE",
            help="Org-mode archive files or directories to analyze",
        ),
        config: str = typer.Option(
            ".org-cli.yaml",
            "--config",
            metavar="FILE",
            help="Config file name to load from current directory",
        ),
        exclude: str | None = typer.Option(
            None,
            "--exclude",
            metavar="FILE",
            help="File containing words to exclude (one per line)",
        ),
        mapping: str | None = typer.Option(
            None,
            "--mapping",
            metavar="FILE",
            help="JSON file containing tag mappings (dict[str, str])",
        ),
        todo_states: str = typer.Option(
            "TODO",
            "--todo-states",
            metavar="KEYS",
            help="Comma-separated list of incomplete task states",
        ),
        done_states: str = typer.Option(
            "DONE",
            "--done-states",
            metavar="KEYS",
            help="Comma-separated list of completed task states",
        ),
        filter_priority: str | None = typer.Option(
            None,
            "--filter-priority",
            metavar="P",
            help="Filter tasks where priority equals P",
        ),
        filter_level: int | None = typer.Option(
            None,
            "--filter-level",
            metavar="N",
            help="Filter tasks where heading level equals N",
        ),
        filter_repeats_above: int | None = typer.Option(
            None,
            "--filter-repeats-above",
            metavar="N",
            help="Filter tasks where repeat count > N (non-inclusive)",
        ),
        filter_repeats_below: int | None = typer.Option(
            None,
            "--filter-repeats-below",
            metavar="N",
            help="Filter tasks where repeat count < N (non-inclusive)",
        ),
        filter_date_from: str | None = typer.Option(
            None,
            "--filter-date-from",
            metavar="TIMESTAMP",
            help=(
                "Filter tasks with timestamps after date (inclusive). "
                "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
                "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
            ),
        ),
        filter_date_until: str | None = typer.Option(
            None,
            "--filter-date-until",
            metavar="TIMESTAMP",
            help=(
                "Filter tasks with timestamps before date (inclusive). "
                "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
                "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
            ),
        ),
        filter_properties: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--filter-property",
            metavar="KEY=VALUE",
            help="Filter tasks with exact property match (case-sensitive, can specify multiple)",
        ),
        filter_tags: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--filter-tag",
            metavar="REGEX",
            help="Filter tasks where any tag matches regex (case-sensitive, can specify multiple)",
        ),
        filter_headings: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--filter-heading",
            metavar="REGEX",
            help="Filter tasks where heading matches regex (case-sensitive, can specify multiple)",
        ),
        filter_bodies: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--filter-body",
            metavar="REGEX",
            help=(
                "Filter tasks where body matches regex (case-sensitive, multiline, "
                "can specify multiple)"
            ),
        ),
        filter_completed: bool = typer.Option(
            False,
            "--filter-completed",
            help="Filter tasks with todo state in done keys",
        ),
        filter_not_completed: bool = typer.Option(
            False,
            "--filter-not-completed",
            help="Filter tasks with todo state in todo keys or without a todo state",
        ),
        color_flag: bool | None = typer.Option(
            None,
            "--color/--no-color",
            help="Force colored output",
        ),
        width: int | None = typer.Option(
            None,
            "--width",
            metavar="N",
            min=50,
            help="Override auto-derived console width (minimum: 50)",
        ),
        max_results: int | None = typer.Option(
            None,
            "--limit",
            "-n",
            metavar="N",
            help="Maximum number of results to display (defaults to all results)",
        ),
        offset: int = typer.Option(
            0,
            "--offset",
            metavar="N",
            help="Number of results to skip before displaying",
        ),
        order_by_level: bool = typer.Option(
            False,
            "--order-by-level",
            help="Order tasks by heading level (repeatable)",
        ),
        order_by_file_order: bool = typer.Option(
            False,
            "--order-by-file-order",
            help="Keep tasks in source file order (repeatable)",
        ),
        order_by_file_order_reversed: bool = typer.Option(
            False,
            "--order-by-file-order-reversed",
            help="Reverse source file order (repeatable)",
        ),
        order_by_priority: bool = typer.Option(
            False,
            "--order-by-priority",
            help="Order by priority (repeatable)",
        ),
        order_by_timestamp_asc: bool = typer.Option(
            False,
            "--order-by-timestamp-asc",
            help="Order by oldest timestamp first (repeatable)",
        ),
        order_by_timestamp_desc: bool = typer.Option(
            False,
            "--order-by-timestamp-desc",
            help="Order by newest timestamp first (repeatable)",
        ),
        with_tags_as_category: bool = typer.Option(
            False,
            "--with-tags-as-category",
            help="Preprocess nodes to set category from first tag",
        ),
        date: str | None = typer.Option(
            None,
            "--date",
            metavar="DATE",
            help="Agenda start date (default: today). Formats: YYYY-MM-DD or ISO datetime",
        ),
        days: int = typer.Option(
            1,
            "--days",
            metavar="N",
            min=1,
            help="How many days to show starting from --date",
        ),
        no_completed: bool = typer.Option(
            False,
            "--no-completed",
            help="Omit tasks in completed states (including repeats)",
        ),
        no_overdue: bool = typer.Option(
            False,
            "--no-overdue",
            help="Omit overdue scheduled and deadline tasks",
        ),
        no_upcoming: bool = typer.Option(
            False,
            "--no-upcoming",
            help="Omit upcoming deadlines",
        ),
        future_repeats: bool = typer.Option(
            True,
            "--future-repeats/--no-future-repeats",
            help="Include potential future planning repeats in agenda days",
        ),
        view: str | None = typer.Option(
            None,
            "--view",
            metavar="NAME",
            help="Agenda view name to use from config (defaults to built-in view)",
        ),
    ) -> None:
        """Show agenda for one day or a date range."""
        args = AgendaArgs(
            files=files,
            config=config,
            exclude=exclude,
            mapping=mapping,
            mapping_inline=None,
            exclude_inline=None,
            todo_states=todo_states,
            done_states=done_states,
            filter_priority=filter_priority,
            filter_level=filter_level,
            filter_repeats_above=filter_repeats_above,
            filter_repeats_below=filter_repeats_below,
            filter_date_from=filter_date_from,
            filter_date_until=filter_date_until,
            filter_properties=filter_properties,
            filter_tags=filter_tags,
            filter_headings=filter_headings,
            filter_bodies=filter_bodies,
            filter_completed=filter_completed,
            filter_not_completed=filter_not_completed,
            color_flag=color_flag,
            width=width,
            max_results=max_results,
            offset=offset,
            order_by_level=order_by_level,
            order_by_file_order=order_by_file_order,
            order_by_file_order_reversed=order_by_file_order_reversed,
            order_by_priority=order_by_priority,
            order_by_timestamp_asc=order_by_timestamp_asc,
            order_by_timestamp_desc=order_by_timestamp_desc,
            with_tags_as_category=with_tags_as_category,
            date=date,
            days=days,
            no_completed=no_completed,
            no_overdue=no_overdue,
            no_upcoming=no_upcoming,
            future_repeats=future_repeats,
            view=view,
        )
        org.config.app.apply_config_defaults(args)
        org.logging.log_applied_config_defaults(args, sys.argv[1:], "agenda")
        org.logging.log_command_arguments(args, "agenda")
        run_agenda(args)
