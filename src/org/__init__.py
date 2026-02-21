"""org - Analyze Emacs Org-mode archive files for task statistics."""

from org.analyze import AnalysisResult, Frequency, Relations, Tag, TimeRange, analyze
from org.cli import main
from org.filters import (
    filter_completed,
    filter_date_from,
    filter_date_until,
    filter_gamify_exp_above,
    filter_gamify_exp_below,
    filter_not_completed,
    filter_property,
    filter_repeats_above,
    filter_repeats_below,
    filter_tag,
    get_repeat_count,
)


__version__ = "0.1.0"

__all__ = [
    "AnalysisResult",
    "Frequency",
    "Relations",
    "Tag",
    "TimeRange",
    "__version__",
    "analyze",
    "filter_completed",
    "filter_date_from",
    "filter_date_until",
    "filter_gamify_exp_above",
    "filter_gamify_exp_below",
    "filter_not_completed",
    "filter_property",
    "filter_repeats_above",
    "filter_repeats_below",
    "filter_tag",
    "get_repeat_count",
    "main",
]
