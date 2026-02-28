"""Query command for jq-style data queries."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Protocol

import click
import orgparse
import typer
from orgparse.date import OrgDate
from orgparse.node import OrgRootNode
from rich.console import Console
from rich.syntax import Syntax

from org import config as config_module
from org.cli_common import load_root_data
from org.output_format import (
    DEFAULT_OUTPUT_THEME,
    OutputFormat,
    OutputFormatError,
    OutputOperation,
    PreparedOutput,
    _build_org_document,
    _json_output_payload,
    _normalize_syntax_theme,
    _org_to_pandoc_format,
    _parse_pandoc_args,
    _prepare_output,
    print_prepared_output,
)
from org.query_language import (
    EvalContext,
    QueryParseError,
    QueryRuntimeError,
    Stream,
    compile_query_text,
)
from org.tui import build_console, processing_status, setup_output


class QueryOutputFormatter(Protocol):
    """Formatter interface for the query command."""

    include_filenames: bool

    def prepare(
        self, values: list[object], console: Console, color_enabled: bool, out_theme: str
    ) -> PreparedOutput:
        """Prepare query output values for rendering."""
        ...


def _is_org_object(value: object) -> bool:
    """Return whether value is an org node or org date object."""
    return isinstance(value, orgparse.node.OrgNode | OrgRootNode | OrgDate)


def _format_org_block(value: object) -> str:
    """Build org-formatted text block for one value."""
    if isinstance(value, orgparse.node.OrgNode | OrgRootNode):
        filename = value.env.filename if value.env.filename else "unknown"
        node_text = str(value).rstrip()
        return f"# {filename}\n{node_text}" if node_text else f"# {filename}"
    if isinstance(value, OrgDate) and not bool(value):
        return "none"
    return str(value)


def _format_query_value(value: object) -> str:
    """Format one query result value for output."""
    if isinstance(value, orgparse.node.OrgNode):
        return str(value).rstrip()
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class OrgQueryOutputFormatter:
    """Org output formatter for query command."""

    include_filenames = True

    def prepare(
        self, values: list[object], console: Console, color_enabled: bool, out_theme: str
    ) -> PreparedOutput:
        del console
        del color_enabled
        if values and all(_is_org_object(value) for value in values):
            return self._prepare_org_values(values, out_theme)

        lines = [_format_query_value(value) for value in values]
        if not lines:
            return PreparedOutput(
                operations=(OutputOperation(kind="console_print", text="No results", markup=False),)
            )

        return PreparedOutput(
            operations=tuple(
                OutputOperation(kind="console_print", text=line, markup=False) for line in lines
            )
        )

    def _prepare_org_values(self, values: list[object], out_theme: str) -> PreparedOutput:
        """Prepare org values using org-mode syntax highlighting."""
        theme = _normalize_syntax_theme(out_theme)
        operations: list[OutputOperation] = []
        for idx, value in enumerate(values):
            if idx > 0:
                operations.append(OutputOperation(kind="console_print", text="", markup=False))
            operations.append(
                OutputOperation(
                    kind="console_print",
                    renderable=Syntax(
                        _format_org_block(value),
                        "org",
                        theme=theme,
                        line_numbers=False,
                        word_wrap=True,
                    ),
                )
            )
        return PreparedOutput(operations=tuple(operations))


class PandocQueryOutputFormatter:
    """Pandoc-based output formatter for query command."""

    include_filenames = False

    def __init__(self, output_format: str, pandoc_args: str | None) -> None:
        self.output_format = output_format
        self.pandoc_args = _parse_pandoc_args(pandoc_args)

    def prepare(
        self, values: list[object], console: Console, color_enabled: bool, out_theme: str
    ) -> PreparedOutput:
        del console
        if not values:
            return PreparedOutput(
                operations=(OutputOperation(kind="console_print", text="No results", markup=False),)
            )
        formatted_text = _org_to_pandoc_format(
            _build_org_document(values),
            self.output_format,
            self.pandoc_args,
        )
        return _prepare_output(formatted_text, color_enabled, self.output_format, out_theme)


class JsonQueryOutputFormatter:
    """JSON output formatter for query command."""

    include_filenames = False

    def prepare(
        self, values: list[object], console: Console, color_enabled: bool, out_theme: str
    ) -> PreparedOutput:
        del console
        return _prepare_output(
            json.dumps(_json_output_payload(values), ensure_ascii=True),
            color_enabled,
            OutputFormat.JSON,
            out_theme,
        )


_ORG_QUERY_FORMATTER = OrgQueryOutputFormatter()
_JSON_QUERY_FORMATTER = JsonQueryOutputFormatter()


def get_query_formatter(output_format: str, pandoc_args: str | None) -> QueryOutputFormatter:
    """Return query formatter for selected output format."""
    normalized_output = output_format.strip().lower()
    if normalized_output == OutputFormat.ORG:
        return _ORG_QUERY_FORMATTER
    if normalized_output == OutputFormat.JSON:
        return _JSON_QUERY_FORMATTER
    return PandocQueryOutputFormatter(normalized_output, pandoc_args)


@dataclass
class QueryArgs:
    """Arguments for the query command."""

    query: str
    files: list[str] | None
    config: str
    exclude: str | None
    mapping: str | None
    mapping_inline: dict[str, str] | None
    exclude_inline: list[str] | None
    todo_keys: str
    done_keys: str
    color_flag: bool | None
    max_results: int
    offset: int
    out: str
    out_theme: str
    pandoc_args: str | None


def run_query(args: QueryArgs) -> None:
    """Run the query command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled)
    if args.offset < 0:
        raise typer.BadParameter("--offset must be non-negative")
    if args.max_results < 0:
        raise typer.BadParameter("--max-results must be non-negative")
    try:
        formatter = get_query_formatter(args.out, args.pandoc_args)
    except OutputFormatError as exc:
        raise click.UsageError(str(exc)) from exc

    with processing_status(console, color_enabled):
        try:
            compiled_query = compile_query_text(args.query)
        except QueryParseError as exc:
            raise click.UsageError(str(exc)) from exc

        roots, todo_keys, done_keys = load_root_data(args)

        context = EvalContext(
            {
                "offset": args.offset,
                "limit": args.max_results,
                "todo_keys": todo_keys,
                "done_keys": done_keys,
            }
        )
        try:
            stream_nodes = Stream([roots])
            results = compiled_query(stream_nodes, context)
        except QueryRuntimeError as exc:
            raise click.UsageError(str(exc)) from exc

        first_result = results[0] if results else None
        if len(results) == 1 and isinstance(first_result, list | tuple | set):
            output_values = list(first_result)
        else:
            output_values = list(results)

        try:
            prepared_output = formatter.prepare(
                output_values, console, color_enabled, args.out_theme
            )
        except OutputFormatError as exc:
            raise click.UsageError(str(exc)) from exc

    print_prepared_output(console, prepared_output)


def register(app: typer.Typer) -> None:
    """Register the query command."""

    @app.command("query")
    def query_command(  # noqa: PLR0913
        query: str = typer.Argument(..., metavar="QUERY", help="jq-style query expression"),
        files: list[str] | None = typer.Argument(  # noqa: B008
            None, metavar="FILE", help="Org-mode archive files or directories to analyze"
        ),
        config: str = typer.Option(
            ".org-cli.json",
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
        todo_keys: str = typer.Option(
            "TODO",
            "--todo-keys",
            metavar="KEYS",
            help="Comma-separated list of incomplete task states",
        ),
        done_keys: str = typer.Option(
            "DONE",
            "--done-keys",
            metavar="KEYS",
            help="Comma-separated list of completed task states",
        ),
        color_flag: bool | None = typer.Option(
            None,
            "--color/--no-color",
            help="Force colored output",
        ),
        max_results: int = typer.Option(
            10,
            "--max-results",
            "-n",
            metavar="N",
            help="Maximum number of results to display",
        ),
        offset: int = typer.Option(
            0,
            "--offset",
            metavar="N",
            help="Number of results to skip before displaying",
        ),
        out: str = typer.Option(
            OutputFormat.ORG,
            "--out",
            help="Output format: org, json, or any pandoc writer format",
        ),
        out_theme: str = typer.Option(
            DEFAULT_OUTPUT_THEME,
            "--out-theme",
            help="Syntax theme for highlighted output blocks",
        ),
        pandoc_args: str | None = typer.Option(
            None,
            "--pandoc-args",
            metavar="ARGS",
            help="Additional arguments forwarded to pandoc export",
        ),
    ) -> None:
        """Query tasks using jq-style expressions."""
        args = QueryArgs(
            query=query,
            files=files,
            config=config,
            exclude=exclude,
            mapping=mapping,
            mapping_inline=None,
            exclude_inline=None,
            todo_keys=todo_keys,
            done_keys=done_keys,
            color_flag=color_flag,
            max_results=max_results,
            offset=offset,
            out=out,
            out_theme=out_theme,
            pandoc_args=pandoc_args,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "query")
        config_module.log_command_arguments(args, "query")
        run_query(args)
