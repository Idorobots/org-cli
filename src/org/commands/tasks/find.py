"""Tasks find command for selector-based task search."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import cast

import click
import typer
from org_parser.document import Heading

import org.config.app
import org.logging
from org.commands.tasks.common import normalize_selector
from org.commands.tasks.query import get_query_formatter
from org.db.format import (
    DEFAULT_OUTPUT_THEME,
    OutputFormat,
    OutputFormatError,
    print_prepared_output,
)
from org.db.load import load_root_data
from org.query.engine.errors import QueryParseError, QueryRuntimeError
from org.query.runner import run_query
from org.tui.bits import build_console, processing_status, setup_output


@dataclass
class TasksFindArgs:
    """Arguments for the tasks find command."""

    files: list[str] | None
    config: str
    exclude: str | None
    mapping: str | None
    mapping_inline: dict[str, str] | None
    exclude_inline: list[str] | None
    todo_states: str
    done_states: str
    query_title: str | None
    query_id: str | None
    query: str | None
    search_text: str | None
    search_pattern: str | None
    include_context: int
    color_flag: bool | None
    width: int | None
    out: str
    out_theme: str
    pandoc_args: str | None


def _search_stage_text(query_text: str) -> str:
    """Return query-language stage for full-text substring search."""
    return f"select({json.dumps(query_text)} in str(.))"


def _search_stage_pattern(pattern: str) -> str:
    """Return query-language stage for regex full-text search."""
    return f"select(str(.) matches {json.dumps(pattern)})"


def _title_match_stage(title: str) -> str:
    """Return query-language stage for exact title match ignoring trailing whitespace."""
    escaped_title = re.escape(title)
    pattern = rf"^{escaped_title}\s*$"
    return f"select(str(.title_text) matches {json.dumps(pattern)})"


def _build_find_query(args: TasksFindArgs) -> str:
    """Build query expression that combines all enabled selectors."""
    stages: list[str] = []

    normalized_query_title = normalize_selector(args.query_title, "--query-title")
    normalized_query_id = normalize_selector(args.query_id, "--query-id")
    normalized_query = normalize_selector(args.query, "--query")
    normalized_search_text = normalize_selector(args.search_text, "--search-text")
    normalized_search_pattern = normalize_selector(args.search_pattern, "--search-pattern")

    if normalized_query_title is not None:
        stages.append(_title_match_stage(normalized_query_title))
    if normalized_query_id is not None:
        stages.append(f"select(str(.id) == {json.dumps(normalized_query_id)})")
    if normalized_query is not None:
        stages.append(f"select({normalized_query})")
    if normalized_search_text is not None:
        stages.append(_search_stage_text(normalized_search_text))
    if normalized_search_pattern is not None:
        try:
            re.compile(normalized_search_pattern)
        except re.error as exc:
            raise typer.BadParameter(f"Invalid regex for --search-pattern: {exc}") from exc
        stages.append(_search_stage_pattern(normalized_search_pattern))

    if not stages:
        return ".[]"
    return ".[] | " + " | ".join(stages)


def _nodes_with_context(nodes: list[Heading], include_context: int) -> list[Heading]:
    """Expand each matched node with ancestors up to include_context levels."""
    if include_context == 0:
        return list(nodes)

    ordered_nodes: list[Heading] = []
    seen: set[int] = set()
    for node in nodes:
        lineage: list[Heading] = [node]
        current = node
        levels_left = include_context
        while levels_left > 0:
            parent = current.parent
            if not isinstance(parent, Heading):
                break
            current = parent
            lineage.append(parent)
            levels_left -= 1
        for item in reversed(lineage):
            item_id = id(item)
            if item_id in seen:
                continue
            seen.add(item_id)
            ordered_nodes.append(item)
    return ordered_nodes


def run_tasks_find(args: TasksFindArgs, config: org.config.app.AppConfig) -> None:
    """Run the tasks find command."""
    del config
    if args.include_context < 0:
        raise typer.BadParameter("--include-context must be non-negative")

    color_enabled = setup_output(args)
    console = build_console(color_enabled, args.width)
    try:
        formatter = get_query_formatter(args.out, args.pandoc_args)
    except OutputFormatError as exc:
        raise click.UsageError(str(exc)) from exc

    with processing_status(console, color_enabled):
        query_text = _build_find_query(args)

        roots, todo_states, done_states = load_root_data(args)
        try:
            results = run_query(
                roots,
                [query_text],
                {"todo_states": todo_states, "done_states": done_states},
            )
        except (QueryParseError, QueryRuntimeError) as exc:
            raise click.UsageError(str(exc)) from exc

        matched_nodes = [value for value in results if isinstance(value, Heading)]
        output_nodes = _nodes_with_context(matched_nodes, args.include_context)

        try:
            prepared_output = formatter.prepare(
                cast("list[object]", output_nodes),
                console,
                color_enabled,
                args.out_theme,
            )
        except OutputFormatError as exc:
            raise click.UsageError(str(exc)) from exc

    print_prepared_output(console, prepared_output)


def register(app: typer.Typer, app_config: org.config.app.AppConfig) -> None:
    """Register the tasks find command."""

    @app.command("find")
    def find_command(  # noqa: PLR0913
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
        query_title: str | None = typer.Option(
            None,
            "--query-title",
            metavar="TEXT",
            help="Select tasks where title exactly matches TEXT",
        ),
        query_id: str | None = typer.Option(
            None,
            "--query-id",
            metavar="ID",
            help="Select tasks where ID exactly matches ID",
        ),
        query: str | None = typer.Option(
            None,
            "--query",
            metavar="QUERY",
            help="Select tasks by query-language predicate expression",
        ),
        search_text: str | None = typer.Option(
            None,
            "--search-text",
            metavar="TEXT",
            help=(
                "Select tasks where full text contains TEXT "
                '(equivalent to select("TEXT" in str(.)))'
            ),
        ),
        search_pattern: str | None = typer.Option(
            None,
            "--search-pattern",
            metavar="REGEX",
            help=(
                "Select tasks where full text regex-matches REGEX "
                '(equivalent to select(str(.) matches "REGEX"))'
            ),
        ),
        include_context: int = typer.Option(
            0
            if app_config.tasks.find.include_context is None
            else app_config.tasks.find.include_context,
            "--include-context",
            metavar="N",
            help="Include up to N parent levels for each matched task",
        ),
        color_flag: bool | None = typer.Option(
            app_config.color_flag,
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
        out: str = typer.Option(
            OutputFormat.ORG if app_config.tasks.find.out is None else app_config.tasks.find.out,
            "--out",
            help="Output format: org, json, or any pandoc writer format",
        ),
        out_theme: str = typer.Option(
            DEFAULT_OUTPUT_THEME
            if app_config.tasks.find.out_theme is None
            else app_config.tasks.find.out_theme,
            "--out-theme",
            help="Syntax theme for highlighted output blocks",
        ),
        pandoc_args: str | None = typer.Option(
            app_config.tasks.find.pandoc_args,
            "--pandoc-args",
            metavar="ARGS",
            help="Additional arguments forwarded to pandoc export",
        ),
    ) -> None:
        """Find tasks by selectors and full-text search."""
        app_config = org.config.app.require_app_config(ctx)
        args = TasksFindArgs(
            files=files,
            config=config,
            exclude=exclude,
            mapping=mapping,
            mapping_inline=app_config.mapping_inline,
            exclude_inline=app_config.exclude_inline,
            todo_states=todo_states,
            done_states=done_states,
            query_title=query_title,
            query_id=query_id,
            query=query,
            search_text=search_text,
            search_pattern=search_pattern,
            include_context=include_context,
            color_flag=color_flag,
            width=width,
            out=out,
            out_theme=out_theme,
            pandoc_args=pandoc_args,
        )
        org.logging.log_command_config(app_config, "tasks find")
        org.logging.log_command_arguments(args, "tasks find")
        run_tasks_find(args, app_config)
