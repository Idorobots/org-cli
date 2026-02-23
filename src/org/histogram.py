"""Histogram data structure and rendering functions."""

from dataclasses import dataclass, field

from rich.text import Text

from org.color import bright_blue, colorize, dim_white, get_state_color


def visual_len(text: str) -> int:
    """Get visual length of text (excluding Rich markup).

    Args:
        text: Text that may contain Rich markup or ANSI codes

    Returns:
        Visual length of the text
    """
    return len(Text.from_markup(text).plain)


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


def render_histogram(
    histogram: Histogram,
    total_blocks: int,
    category_order: list[str] | None,
    config: RenderConfig | None = None,
) -> list[str]:
    """Render histogram as visual bar chart.

    Args:
        histogram: Histogram object to render
        total_blocks: Number of blocks for 100% width (e.g., args.buckets)
        category_order: Optional list specifying display order of categories
        config: Rendering configuration (color, type, done/todo keys)

    Returns:
        List of formatted strings, one per category
    """
    render_config = config or RenderConfig()

    total_sum = sum(histogram.values.values())
    categories = category_order if category_order is not None else sorted(histogram.values.keys())

    lines = []
    for category in categories:
        value = histogram.values.get(category, 0)
        display_name = category[:8] + "." if len(category) > 9 else category
        bar_length = int((value / total_sum) * total_blocks) if total_sum > 0 else 0
        bars = "█" * bar_length

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
            colored_bars = bright_blue(bars, render_config.color_enabled)
        else:
            colored_name = dim_white(display_name, render_config.color_enabled)
            colored_bars = bright_blue(bars, render_config.color_enabled)

        delimiter = dim_white("┊", render_config.color_enabled)

        if render_config.color_enabled:
            visual_width = visual_len(colored_name)
            padding = " " * (9 - visual_width)
            line = f"{colored_name}{padding}{delimiter}{colored_bars} {value}"
        else:
            line = f"{colored_name:9s}{delimiter}{colored_bars} {value}"

        lines.append(line)

    return lines
