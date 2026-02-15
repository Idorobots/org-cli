"""Histogram data structure and rendering functions."""

from dataclasses import dataclass, field


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


def render_histogram(
    histogram: Histogram, total_blocks: int, category_order: list[str] | None
) -> list[str]:
    """Render histogram as visual bar chart.

    Args:
        histogram: Histogram object to render
        total_blocks: Number of blocks for 100% width (e.g., args.buckets)
        category_order: Optional list specifying display order of categories

    Returns:
        List of formatted strings, one per category
    """
    total_sum = sum(histogram.values.values())
    categories = category_order if category_order is not None else sorted(histogram.values.keys())

    lines = []
    for category in categories:
        value = histogram.values.get(category, 0)
        display_name = category[:8] + "." if len(category) > 9 else category
        bar_length = int((value / total_sum) * total_blocks) if total_sum > 0 else 0
        bars = "█" * bar_length
        line = f"{display_name:9s}┊{bars} {value}"
        lines.append(line)

    return lines
