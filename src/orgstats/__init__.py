"""orgstats - Analyze Emacs Org-mode archive files for task statistics."""

from orgstats.cli import main
from orgstats.core import AnalysisResult, Frequency, analyze


__version__ = "0.1.0"

__all__ = [
    "AnalysisResult",
    "Frequency",
    "__version__",
    "analyze",
    "main",
]
