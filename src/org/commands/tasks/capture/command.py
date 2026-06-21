"""CLI wiring for tasks capture."""

from __future__ import annotations

import sys
from dataclasses import replace

import click
import typer

import org.config.app
import org.logging
from org.tui.help import interactive_help_command_text

from .app import run_capture_form_app, run_template_selection_app
from .domain import (
    _CAPTURE_HELP_ENTRIES,
    TasksCaptureArgs,
    TasksCaptureResult,
    _missing_placeholder_error,
    _missing_template_name_error,
    _require_templates,
    _template_names,
    _valid_template_names_text,
    finalize_capture_plan,
    prepare_capture_plan,
)


def _is_interactive_terminal() -> bool:
    """Return whether capture can launch interactive terminal apps."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def capture_task(
    args: TasksCaptureArgs,
    templates: dict[str, dict[str, str]],
) -> TasksCaptureResult:
    """Capture one task from templates and return created heading metadata."""
    _require_templates(templates)

    interactive_used = False
    resolved_args = args
    interactive_terminal = _is_interactive_terminal()

    if args.template_name is None:
        if not interactive_terminal:
            raise _missing_template_name_error()
        selected_name = run_template_selection_app(_template_names(templates))
        if selected_name is None:
            raise KeyboardInterrupt
        resolved_args = replace(args, template_name=selected_name)
        interactive_used = True

    if resolved_args.template_name is None:
        raise _missing_template_name_error()
    if resolved_args.template_name not in templates:
        valid_names = _valid_template_names_text(_template_names(templates))
        raise typer.BadParameter(
            "Unknown capture template "
            f"'{resolved_args.template_name}'. Valid templates: {valid_names}",
        )

    plan = prepare_capture_plan(resolved_args, resolved_args.template_name, templates)
    if plan.unresolved_placeholders:
        if not interactive_terminal:
            raise _missing_placeholder_error(plan.unresolved_placeholders)
        values = run_capture_form_app(plan)
        if values is None:
            raise KeyboardInterrupt
        return finalize_capture_plan(plan, values, interactive_used=True)

    return finalize_capture_plan(plan, plan.values, interactive_used=interactive_used)


def run_tasks_capture(args: TasksCaptureArgs, templates: dict[str, dict[str, str]]) -> None:
    """Run tasks capture command using configured templates."""
    if args.template_name is None and not _is_interactive_terminal():
        raise click.UsageError(
            "org tasks capture requires a TTY unless TEMPLATE_NAME and all values are provided",
        )

    result = capture_task(args, templates)
    if not result.interactive_used:
        typer.echo(result.heading.id or result.heading.title_text)


def register(app: typer.Typer) -> None:
    """Register the tasks capture command."""

    @app.command(
        "capture",
        help=interactive_help_command_text(
            "Create a task from a configured capture template.",
            _CAPTURE_HELP_ENTRIES,
        ),
    )
    def capture(  # noqa: PLR0913
        ctx: typer.Context,
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
            metavar="ID_OR_TITLE",
            help="Override template parent by heading ID or title",
        ),
        set_values: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--set",
            metavar="KEY=VALUE",
            help="Set template parameter values without prompting",
        ),
    ) -> None:
        """Create a task from a configured capture template."""
        app_config = org.config.app.require_app_config(ctx)
        args = TasksCaptureArgs(
            template_name=template_name,
            config=config,
            file=file,
            parent=parent,
            set_values=set_values,
        )
        org.logging.log_command_arguments(args, "tasks capture")
        run_tasks_capture(args, app_config.capture.templates)


__all__ = ["TasksCaptureArgs", "TasksCaptureResult", "register", "run_tasks_capture"]
