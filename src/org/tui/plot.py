"""Timeline chart rendering functions."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from org.tui.color import bright_blue, dim_white, magenta


if TYPE_CHECKING:
    from datetime import datetime

    from org.logic.stats import TimeRange


@dataclass(frozen=True)
class TimelineFormatConfig:
    """Configuration for rendering timeline charts."""

    color_enabled: bool
    indent: str
    plot_width: int


@dataclass(frozen=True)
class TimelineRenderConfig:
    """Configuration for timeline chart rendering."""

    plot_width: int
    color_enabled: bool = False


def select_earliest_date(
    date_from: datetime | None,
    global_timerange: TimeRange,
    local_timerange: TimeRange,
) -> date | None:
    """Select earliest date using priority: user filter > global > local."""
    if date_from:
        return date_from.date()
    if global_timerange.earliest:
        return global_timerange.earliest.date()
    if local_timerange.earliest:
        return local_timerange.earliest.date()
    return None


def select_latest_date(
    date_until: datetime | None,
    global_timerange: TimeRange,
    local_timerange: TimeRange,
) -> date | None:
    """Select latest date using priority: user filter > global > local."""
    if date_until:
        return date_until.date()
    if global_timerange.latest:
        return global_timerange.latest.date()
    if local_timerange.latest:
        return local_timerange.latest.date()
    if local_timerange.earliest:
        return local_timerange.earliest.date()
    return None


def resolve_timeline_plot_width(config: TimelineFormatConfig) -> int:
    """Resolve visual timeline plot width from config."""
    return max(3, config.plot_width)


def expand_timeline(timeline: dict[date, int], earliest: date, latest: date) -> dict[date, int]:
    """Fill in missing dates with 0 activity to create a complete timeline."""
    expanded: dict[date, int] = {}
    current = earliest

    while current <= latest:
        expanded[current] = timeline.get(current, 0)
        current = current + timedelta(days=1)

    return expanded


def bucket_timeline(timeline: dict[date, int], num_buckets: int) -> list[int]:
    """Group timeline into N equal-sized time buckets and sum activity per bucket."""
    if not timeline:
        return [0] * num_buckets

    sorted_dates = sorted(timeline.keys())
    total_days = len(sorted_dates)

    if total_days == 0:
        return [0] * num_buckets

    buckets = [0] * num_buckets

    for i, current_date in enumerate(sorted_dates):
        bucket_index = (i * num_buckets) // total_days
        if bucket_index >= num_buckets:
            bucket_index = num_buckets - 1
        buckets[bucket_index] += timeline[current_date]

    return buckets


def _map_value_to_bar(value: int, max_value: int) -> str:
    """Map a value to appropriate unicode bar character based on percentage."""
    if max_value == 0 or value == 0:
        return " "

    percentage = (value / max_value) * 100
    thresholds = [
        (100, "█"),
        (87.5, "▇"),
        (75, "▆"),
        (62.5, "▅"),
        (50, "▄"),
        (37.5, "▃"),
        (25, "▂"),
    ]

    for threshold, char in thresholds:
        if percentage >= threshold:
            return char
    return "▁"


def render_timeline_chart(
    timeline: dict[date, int],
    earliest: date,
    latest: date,
    config: TimelineRenderConfig,
) -> tuple[str, str, str]:
    """Create ASCII bar chart from timeline data."""
    expanded = expand_timeline(timeline, earliest, latest)
    num_buckets = max(1, config.plot_width - 2)
    buckets = bucket_timeline(expanded, num_buckets)
    max_value = max(buckets) if buckets else 0

    bars = "".join(_map_value_to_bar(value, max_value) for value in buckets)
    colored_bars = bright_blue(bars, config.color_enabled)

    start_date_str = earliest.isoformat()
    end_date_str = latest.isoformat()

    chart_width = config.plot_width
    padding_spaces = chart_width - len(start_date_str) - len(end_date_str)
    date_padding = " " * max(0, padding_spaces)
    date_line = f"{start_date_str}{date_padding}{end_date_str}"

    if timeline:
        max_count = max(timeline.values())
        top_day = min(d for d, count in timeline.items() if count == max_count)
        top_day_str = f"{max_count} ({top_day.isoformat()})"
    else:
        top_day_str = "0"

    delimiter = dim_white("┊", config.color_enabled)

    top_day_start = (chart_width - len(top_day_str)) // 2
    top_day_end = top_day_start + len(top_day_str)
    end_date_start = chart_width - len(end_date_str)
    has_left_gap = top_day_start > len(start_date_str)
    has_right_gap = top_day_end < end_date_start
    if has_left_gap and has_right_gap:
        left_padding = " " * (top_day_start - len(start_date_str))
        middle_padding = " " * (end_date_start - top_day_end)
        centered_top = magenta(top_day_str, config.color_enabled)
        date_line = f"{start_date_str}{left_padding}{centered_top}{middle_padding}{end_date_str}"

    chart_line = f"{delimiter}{colored_bars}{delimiter}"

    underline = dim_white("‾" * chart_width, config.color_enabled)

    return (date_line, chart_line, underline)


def format_timeline_lines(
    timeline: dict[date, int],
    earliest_date: date,
    latest_date: date,
    config: TimelineFormatConfig,
) -> list[str]:
    """Render timeline chart lines and apply configured indentation."""
    plot_width = resolve_timeline_plot_width(config)
    date_line, chart_line, underline = render_timeline_chart(
        timeline,
        earliest_date,
        latest_date,
        TimelineRenderConfig(
            plot_width=plot_width,
            color_enabled=config.color_enabled,
        ),
    )
    return [
        f"{config.indent}{line}" if config.indent and line else line
        for line in [date_line, chart_line, underline]
    ]
