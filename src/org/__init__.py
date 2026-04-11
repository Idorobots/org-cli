"""org - Analyze Emacs Org-mode archive files for task statistics."""

from org.analyze import AnalysisResult, Frequency, Relations, Tag, TimeRange, analyze
from org.cli import main


__version__ = "0.1.0"

__all__ = [
    "AnalysisResult",
    "Frequency",
    "Relations",
    "Tag",
    "TimeRange",
    "__version__",
    "analyze",
    "main",
]
