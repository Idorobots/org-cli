"""Timeline chart rendering functions."""

from datetime import date, timedelta


def expand_timeline(timeline: dict[date, int], earliest: date, latest: date) -> dict[date, int]:
    """Fill in missing dates with 0 activity to create a complete timeline.

    Args:
        timeline: Sparse timeline with only days that have activity
        earliest: First date in the range
        latest: Last date in the range

    Returns:
        Complete timeline with all dates from earliest to latest, missing dates set to 0
    """
    expanded: dict[date, int] = {}
    current = earliest

    while current <= latest:
        expanded[current] = timeline.get(current, 0)
        current = current + timedelta(days=1)

    return expanded


def bucket_timeline(timeline: dict[date, int], num_buckets: int) -> list[int]:
    """Group timeline into N equal-sized time buckets and sum activity per bucket.

    Args:
        timeline: Complete timeline dict mapping dates to activity counts
        num_buckets: Number of buckets to create

    Returns:
        List of bucket sums (length = num_buckets)
    """
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
    """Map a value to appropriate unicode bar character based on percentage.

    Args:
        value: Value to map
        max_value: Maximum value for percentage calculation

    Returns:
        Unicode bar character representing the percentage
    """
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
    timeline: dict[date, int], earliest: date, latest: date, num_buckets: int
) -> tuple[str, str, str]:
    """Create ASCII bar chart from timeline data.

    Args:
        timeline: Timeline dict mapping dates to activity counts
        earliest: First date in the range
        latest: Last date in the range
        num_buckets: Number of buckets (bars) in the chart

    Returns:
        Tuple of (date_line, chart_line, underline)
    """
    expanded = expand_timeline(timeline, earliest, latest)
    buckets = bucket_timeline(expanded, num_buckets)
    max_value = max(buckets) if buckets else 0

    bars = "".join(_map_value_to_bar(value, max_value) for value in buckets)

    start_date_str = earliest.isoformat()
    end_date_str = latest.isoformat()

    chart_width = len(bars) + 2
    padding_spaces = chart_width - len(start_date_str) - len(end_date_str)
    date_padding = " " * max(0, padding_spaces)
    date_line = f"{start_date_str}{date_padding}{end_date_str}"

    if timeline:
        max_count = max(timeline.values())
        top_day = min(d for d, count in timeline.items() if count == max_count)
        top_day_str = f"{max_count} ({top_day.isoformat()})"
    else:
        top_day_str = "0"

    chart_line = f"┊{bars}┊ {top_day_str}"

    underline = "‾" * chart_width

    return (date_line, chart_line, underline)
