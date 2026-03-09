"""Histogram data structure and rendering functions."""

from dataclasses import dataclass, field

from rich.cells import cell_len
from rich.text import Text

from org.color import bright_blue, colorize, dim_white, get_state_color


def visual_len(text: str) -> int:
    """Get visual length of text (excluding Rich markup).

    Args:
        text: Text that may contain Rich markup or ANSI codes

    Returns:
        Visual length of the text
    """
    return cell_len(Text.from_markup(text).plain)


@dataclass
class Histogram:
    """Represents a distribution of values.

    Attributes:
        values: Dictionary mapping categories to their counts
    """

    values: dict[str, int] = field(default_factory=dict)

    def update(self, key: str, amount: int) -> None:
        """Update the count for a given key by the specified amount.

        Args:
            key: The category to update
            amount: The amount to add
        """
        self.values[key] = self.values.get(key, 0) + amount


@dataclass
class RenderConfig:
    """Configuration for histogram rendering.

    Attributes:
        color_enabled: Whether to apply colors to the output
        histogram_type: Type of histogram ("task_states" or "other")
        done_keys: List of done state keywords (for task_states coloring)
        todo_keys: List of todo state keywords (for task_states coloring)
    """

    color_enabled: bool = False
    histogram_type: str = "other"
    done_keys: list[str] = field(default_factory=list)
    todo_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HistogramRenderConfig:
    """Configuration for histogram layout and style."""

    plot_width: int
    category_order: list[str] | None
    style: RenderConfig = field(default_factory=RenderConfig)


def render_histogram(
    histogram: Histogram,
    config: HistogramRenderConfig | int,
    category_order: list[str] | None = None,
    style: RenderConfig | None = None,
) -> list[str]:
    """Render histogram as visual bar chart.

    Args:
        histogram: Histogram object to render
        config: Histogram rendering configuration
        category_order: Deprecated legacy argument
        style: Deprecated legacy argument

    Returns:
        List of formatted strings, one per category
    """
    render_config_input: HistogramRenderConfig
    legacy_total_blocks: int | None = None
    if isinstance(config, HistogramRenderConfig):
        render_config_input = config
    else:
        legacy_total_blocks = config
        render_config_input = HistogramRenderConfig(
            plot_width=config,
            category_order=category_order,
            style=style or RenderConfig(),
        )

    render_config = render_config_input.style

    total_sum = sum(histogram.values.values())
    categories = (
        render_config_input.category_order
        if render_config_input.category_order is not None
        else sorted(histogram.values.keys())
    )

    lines = []
    for category in categories:
        value = histogram.values.get(category, 0)
        display_name = category[:8] + "." if len(category) > 9 else category
        if render_config.histogram_type == "task_states":
            state_style = get_state_color(
                category,
                render_config.done_keys,
                render_config.todo_keys,
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
                0, render_config_input.plot_width - visual_len(prefix) - len(value_text)
            )
        bar_length = int((value / total_sum) * available_blocks) if total_sum > 0 else 0
        bars = "█" * bar_length
        colored_bars = bright_blue(bars, render_config.color_enabled)

        line = f"{prefix}{colored_bars}{value_text}"

        lines.append(line)

    return lines
