"""Agenda view configuration and section spec compilation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer

import org.config.app
from org.pipeline.query import compile_filter_order_query


if TYPE_CHECKING:
    from org.query_language.compiler import CompiledQuery

    from .command import AgendaArgs


@dataclass(frozen=True)
class AgendaSectionSpec:
    """Compiled agenda section specification."""

    name: str
    query: CompiledQuery
    style: str
    timeline: bool


@dataclass(frozen=True)
class AgendaViewContext:
    """Resolved view context for agenda rendering."""

    section_specs: list[AgendaSectionSpec]
    name: str


def _compile_section_query(filter_query: str, order_by: str | None) -> CompiledQuery:
    """Compile one agenda section filter/order query text."""
    return compile_filter_order_query(filter_query, order_by)


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
            query = _compile_section_query(section.filter, section.order_by)
        except Exception as err:
            raise typer.BadParameter(
                f"Invalid agenda filter/order-by (view={view.name}, section={section.name}): {err}",
            ) from err
        section_specs.append(
            AgendaSectionSpec(
                name=section.name,
                query=query,
                style=section.style,
                timeline=section.timeline,
            ),
        )
    return section_specs


def resolve_view_context(args: AgendaArgs) -> AgendaViewContext:
    """Resolve configured or fallback view context for agenda rendering."""
    selected_view = args.view.strip() if args.view else None
    configured_views = org.config.app.CONFIG_AGENDA_VIEWS

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
