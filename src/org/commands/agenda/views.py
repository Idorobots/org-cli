"""Agenda view configuration and section spec compilation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer

import org.config.app
from org.query.engine.errors import QueryParseError, QueryRuntimeError
from org.query.runner import build_filter_order_query_text, run_query


if TYPE_CHECKING:
    from .command import AgendaArgs


@dataclass(frozen=True)
class AgendaSectionSpec:
    """Agenda section query specification."""

    name: str
    query_text: str
    style: str
    timeline: bool


@dataclass(frozen=True)
class AgendaViewContext:
    """Resolved view context for agenda rendering."""

    section_specs: list[AgendaSectionSpec]
    name: str


def _fallback_agenda_view() -> org.config.app.AgendaViewConfig:
    """Return built-in fallback agenda view definition."""
    return org.config.app.AgendaViewConfig(
        name="default",
        sections=[
            org.config.app.AgendaSectionConfig(
                name="[bold dim white]Agenda[/]",
                filter="true",
                order_by=None,
                style="bold white",
                timeline=True,
            ),
        ],
    )


def _compile_view_section_specs(view: org.config.app.AgendaViewConfig) -> list[AgendaSectionSpec]:
    """Compile one agenda view's filters into renderable section specs."""
    section_specs: list[AgendaSectionSpec] = []
    for section in view.sections:
        try:
            query_text = build_filter_order_query_text(section.filter, section.order_by)
            run_query([], [query_text], {})
        except (QueryParseError, QueryRuntimeError) as err:
            raise typer.BadParameter(
                f"Invalid agenda filter/order-by (view={view.name}, section={section.name}): {err}",
            ) from err
        section_specs.append(
            AgendaSectionSpec(
                name=section.name,
                query_text=query_text,
                style=section.style,
                timeline=section.timeline,
            ),
        )
    return section_specs


def resolve_view_context(
    args: AgendaArgs,
    configured_views: dict[str, org.config.app.AgendaViewConfig],
) -> AgendaViewContext:
    """Resolve configured or fallback view context for agenda rendering."""
    selected_view = args.view.strip() if args.view else None

    if selected_view is None:
        view = _fallback_agenda_view()
        return AgendaViewContext(section_specs=_compile_view_section_specs(view), name=view.name)

    if not configured_views:
        raise typer.BadParameter("--view requested, but no agenda views are configured")

    selected_view_config = configured_views.get(selected_view)
    if selected_view_config is None:
        raise typer.BadParameter(f"Requested agenda view not found: {selected_view}")

    return AgendaViewContext(
        section_specs=_compile_view_section_specs(selected_view_config),
        name=selected_view_config.name,
    )
