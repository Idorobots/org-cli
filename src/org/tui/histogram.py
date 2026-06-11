"""Histogram rendering functions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from org.tui.bits import apply_indent, section_header_lines, visual_len
from org.tui.color import bright_blue, colorize, dim_white, get_state_color


if TYPE_CHECKING:
    from org.analyze import Distribution


@dataclass
class RenderConfig:
    """Configuration for histogram rendering."""

    color_enabled: bool = False
    histogram_type: str = "other"
    done_states: list[str] = field(default_factory=list)
    todo_states: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HistogramRenderConfig:
    """Configuration for histogram layout and style."""

    plot_width: int
    category_order: list[str] | None
    style: RenderConfig = field(default_factory=RenderConfig)


@dataclass(frozen=True)
class HistogramSectionConfig:
    """Configuration for rendering histogram sections."""

    plot_width: int
    order: list[str]
    render_config: RenderConfig
    indent: str


def _resolve_render_config(
    config: HistogramRenderConfig | int,
    category_order: list[str] | None,
    style: RenderConfig | None,
) -> tuple[HistogramRenderConfig, int | None]:
    """Resolve legacy and current render configuration arguments."""
    if isinstance(config, HistogramRenderConfig):
        return config, None

    return (
        HistogramRenderConfig(
            plot_width=config,
            category_order=category_order,
            style=style or RenderConfig(),
        ),
        config,
    )


def _resolve_categories(distribution: Distribution, category_order: list[str] | None) -> list[str]:
    """Resolve final category sequence for rendering."""
    occurring_categories = set(distribution.values.keys())
    if category_order is None:
        return sorted(occurring_categories)

    seen: set[str] = set()
    ordered_categories = []
    for category in category_order:
        if category not in seen:
            seen.add(category)
            ordered_categories.append(category)

    remaining_categories = sorted(
        category for category in occurring_categories if category not in seen
    )
    return ordered_categories + remaining_categories


def render_histogram(
    distribution: Distribution,
    config: HistogramRenderConfig | int,
    category_order: list[str] | None = None,
    style: RenderConfig | None = None,
) -> list[str]:
    """Render histogram as visual bar chart."""
    render_config_input, legacy_total_blocks = _resolve_render_config(config, category_order, style)

    render_config = render_config_input.style

    total_sum = sum(distribution.values.values())
    categories = _resolve_categories(distribution, render_config_input.category_order)

    lines = []
    for category in categories:
        value = distribution.values.get(category, 0)
        display_name = category[:8] + "." if len(category) > 9 else category
        if render_config.histogram_type == "task_states":
            state_style = get_state_color(
                category,
                render_config.done_states,
                render_config.todo_states,
                render_config.color_enabled,
            )
            if render_config.color_enabled and state_style:
                colored_name = colorize(display_name, state_style, render_config.color_enabled)
            else:
                colored_name = display_name
        else:
            colored_name = dim_white(display_name, render_config.color_enabled)

        delimiter = dim_white("┊", render_config.color_enabled)
        value_text = f" {value}"

        if render_config.color_enabled:
            visual_width = visual_len(colored_name)
            padding = " " * (9 - visual_width)
            prefix = f"{colored_name}{padding}{delimiter}"
        else:
            prefix = f"{colored_name:9s}{delimiter}"

        if legacy_total_blocks is not None:
            available_blocks = legacy_total_blocks
        else:
            available_blocks = max(
                0,
                render_config_input.plot_width - visual_len(prefix) - len(value_text),
            )
        bar_length = int((value / total_sum) * available_blocks) if total_sum > 0 else 0
        bars = "█" * bar_length
        colored_bars = bright_blue(bars, render_config.color_enabled)

        line = f"{prefix}{colored_bars}{value_text}"

        lines.append(line)

    return lines


def format_histogram_section(
    title: str,
    distribution: Distribution,
    config: HistogramSectionConfig,
) -> list[str]:
    """Render one histogram section as indented output lines."""
    lines = section_header_lines(title, config.render_config.color_enabled)
    histogram_plot_width = max(3, config.plot_width - 2)
    histogram_lines = render_histogram(
        distribution,
        HistogramRenderConfig(
            plot_width=histogram_plot_width,
            category_order=config.order,
            style=config.render_config,
        ),
    )
    lines.extend([f"  {line}" for line in histogram_lines])
    return apply_indent(lines, config.indent)
