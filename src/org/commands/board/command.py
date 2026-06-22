"""Board command."""

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

from . import actions, ui
from .app import run_board_app


logger = logging.getLogger("org")


@dataclass
class BoardArgs:
    """Arguments for the board command."""

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
    view: str | None
    width: int | None
    max_results: int | None
    offset: int
    days: int
    order_by_level: bool
    order_by_file_order: bool
    order_by_file_order_reversed: bool
    order_by_priority: bool
    order_by_timestamp_asc: bool
    order_by_timestamp_desc: bool
    with_tags_as_category: bool


_BOARD_HELP_ENTRIES = ui.BOARD_HELP_ENTRIES


def _resolve_tasks_limit(max_results: int | None) -> int:
    """Resolve effective tasks limit, defaulting to all available tasks."""
    if max_results is None:
        return sys.maxsize
    return max_results


def _validate_board_args(args: BoardArgs, config: org.config.app.AppConfig) -> None:
    """Validate board arguments and configured view selection."""
    actions.resolve_column_specs(args, config.board.views)


def run_board(args: BoardArgs, config: org.config.app.AppConfig) -> None:
    """Run the board command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled, args.width)
    if console.width < 80:
        raise typer.BadParameter("--width must be at least 80")
    if args.offset < 0:
        raise typer.BadParameter("--offset must be non-negative")
    if args.max_results is not None and args.max_results < 0:
        raise typer.BadParameter("--limit must be non-negative")
    if args.days < 1:
        raise typer.BadParameter("--days must be at least 1")
    args.max_results = _resolve_tasks_limit(args.max_results)
    _validate_board_args(args, config)

    with processing_status(console, color_enabled):
        nodes, discovered_todo_states, discovered_done_states = load_and_process_data(args, config)
        nodes = actions.filter_recent_completed_nodes(nodes, args.days)
        todo_states, done_states = actions.resolved_states(
            args,
            discovered_todo_states,
            discovered_done_states,
        )

    if not nodes:
        console.print("No results", markup=False)
        return

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise click.UsageError("org board requires a TTY")

    run_board_app(args, config, nodes, (todo_states, done_states), color_enabled)


def register(app: typer.Typer, app_config: org.config.app.AppConfig) -> None:
    """Register the board command."""

    @app.command(
        "board",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
        help=interactive_help_command_text(
            "Display tasks as an interactive flow board.",
            _BOARD_HELP_ENTRIES,
        ),
    )
    def board(  # noqa: PLR0913
        ctx: typer.Context,
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
            app_config.exclude,
            "--exclude",
            metavar="FILE",
            help="File containing words to exclude (one per line)",
        ),
        mapping: str | None = typer.Option(
            app_config.mapping,
            "--mapping",
            metavar="FILE",
            help="JSON file containing tag mappings (dict[str, str])",
        ),
        todo_states: str = typer.Option(
            ",".join(app_config.todo_states),
            "--todo-states",
            metavar="KEYS",
            help="Comma-separated list of incomplete task states",
        ),
        done_states: str = typer.Option(
            ",".join(app_config.done_states),
            "--done-states",
            metavar="KEYS",
            help="Comma-separated list of completed task states",
        ),
        filter_priority: str | None = typer.Option(
            app_config.filter_priority,
            "--filter-priority",
            metavar="P",
            help="Filter tasks where priority equals P",
        ),
        filter_level: int | None = typer.Option(
            app_config.filter_level,
            "--filter-level",
            metavar="N",
            help="Filter tasks where heading level equals N",
        ),
        filter_repeats_above: int | None = typer.Option(
            app_config.filter_repeats_above,
            "--filter-repeats-above",
            metavar="N",
            help="Filter tasks where repeat count > N (non-inclusive)",
        ),
        filter_repeats_below: int | None = typer.Option(
            app_config.filter_repeats_below,
            "--filter-repeats-below",
            metavar="N",
            help="Filter tasks where repeat count < N (non-inclusive)",
        ),
        filter_date_from: str | None = typer.Option(
            app_config.filter_date_from,
            "--filter-date-from",
            metavar="TIMESTAMP",
            help=(
                "Filter tasks with timestamps after date (inclusive). "
                "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
                "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
            ),
        ),
        filter_date_until: str | None = typer.Option(
            app_config.filter_date_until,
            "--filter-date-until",
            metavar="TIMESTAMP",
            help=(
                "Filter tasks with timestamps before date (inclusive). "
                "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
                "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
            ),
        ),
        filter_properties: list[str] | None = typer.Option(  # noqa: B008
            app_config.filter_properties,
            "--filter-property",
            metavar="KEY=VALUE",
            help="Filter tasks with exact property match (case-sensitive, can specify multiple)",
        ),
        filter_tags: list[str] | None = typer.Option(  # noqa: B008
            app_config.filter_tags,
            "--filter-tag",
            metavar="REGEX",
            help="Filter tasks where any tag matches regex (case-sensitive, can specify multiple)",
        ),
        filter_headings: list[str] | None = typer.Option(  # noqa: B008
            app_config.filter_headings,
            "--filter-heading",
            metavar="REGEX",
            help="Filter tasks where heading matches regex (case-sensitive, can specify multiple)",
        ),
        filter_bodies: list[str] | None = typer.Option(  # noqa: B008
            app_config.filter_bodies,
            "--filter-body",
            metavar="REGEX",
            help=(
                "Filter tasks where body matches regex (case-sensitive, multiline, "
                "can specify multiple)"
            ),
        ),
        filter_completed: bool = typer.Option(
            app_config.filter_completed,
            "--filter-completed",
            help="Filter tasks with todo state in done keys",
        ),
        filter_not_completed: bool = typer.Option(
            app_config.filter_not_completed,
            "--filter-not-completed",
            help="Filter tasks with todo state in todo keys or without a todo state",
        ),
        color_flag: bool | None = typer.Option(
            app_config.color_flag,
            "--color/--no-color",
            help="Force colored output",
        ),
        view: str | None = typer.Option(
            app_config.board.view,
            "--view",
            metavar="NAME",
            help="Configured board view name",
        ),
        width: int | None = typer.Option(
            app_config.board.width,
            "--width",
            metavar="N",
            min=80,
            help="Override auto-derived console width (minimum: 80)",
        ),
        max_results: int | None = typer.Option(
            app_config.board.max_results,
            "--limit",
            "-n",
            metavar="N",
            help="Maximum number of results to display (defaults to all results)",
        ),
        offset: int = typer.Option(
            0 if app_config.board.offset is None else app_config.board.offset,
            "--offset",
            metavar="N",
            help="Number of results to skip before displaying",
        ),
        days: int = typer.Option(
            7 if app_config.board.days is None else app_config.board.days,
            "--days",
            metavar="N",
            min=1,
            help="Show completed tasks modified in last N days",
        ),
        order_by_level: bool = typer.Option(
            app_config.order_by_level,
            "--order-by-level",
            help="Order tasks by heading level (repeatable)",
        ),
        order_by_file_order: bool = typer.Option(
            app_config.order_by_file_order,
            "--order-by-file-order",
            help="Keep tasks in source file order (repeatable)",
        ),
        order_by_file_order_reversed: bool = typer.Option(
            app_config.order_by_file_order_reversed,
            "--order-by-file-order-reversed",
            help="Reverse source file order (repeatable)",
        ),
        order_by_priority: bool = typer.Option(
            app_config.order_by_priority,
            "--order-by-priority",
            help="Order by priority (repeatable)",
        ),
        order_by_timestamp_asc: bool = typer.Option(
            app_config.order_by_timestamp_asc,
            "--order-by-timestamp-asc",
            help="Order by oldest timestamp first (repeatable)",
        ),
        order_by_timestamp_desc: bool = typer.Option(
            app_config.order_by_timestamp_desc,
            "--order-by-timestamp-desc",
            help="Order by newest timestamp first (repeatable)",
        ),
        with_tags_as_category: bool = typer.Option(
            app_config.with_tags_as_category,
            "--with-tags-as-category",
            help="Preprocess nodes to set category from first tag",
        ),
    ) -> None:
        """Display tasks as an interactive board."""
        app_config = org.config.app.require_app_config(ctx)
        args = BoardArgs(
            files=files,
            config=config,
            exclude=exclude,
            mapping=mapping,
            mapping_inline=app_config.mapping_inline,
            exclude_inline=app_config.exclude_inline,
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
            view=view,
            width=width,
            max_results=max_results,
            offset=offset,
            days=days,
            order_by_level=order_by_level,
            order_by_file_order=order_by_file_order,
            order_by_file_order_reversed=order_by_file_order_reversed,
            order_by_priority=order_by_priority,
            order_by_timestamp_asc=order_by_timestamp_asc,
            order_by_timestamp_desc=order_by_timestamp_desc,
            with_tags_as_category=with_tags_as_category,
        )
        org.logging.log_command_config(app_config, "board")
        org.logging.log_command_arguments(args, "board")
        run_board(args, app_config)
