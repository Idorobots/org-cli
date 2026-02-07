"""Tests for the AnalysisResult dataclass."""

import os
import sys


# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core import AnalysisResult, Frequency


def test_analysis_result_initialization():
    """Test that AnalysisResult can be initialized with all fields."""
    result = AnalysisResult(
        total_tasks=10,
        done_tasks=5,
        tag_frequencies={"python": Frequency(3)},
        heading_frequencies={"test": Frequency(2)},
        body_frequencies={"code": Frequency(1)},
    )

    assert result.total_tasks == 10
    assert result.done_tasks == 5
    assert result.tag_frequencies == {"python": Frequency(3)}
    assert result.heading_frequencies == {"test": Frequency(2)}
    assert result.body_frequencies == {"code": Frequency(1)}


def test_analysis_result_empty_initialization():
    """Test AnalysisResult with empty data."""
    result = AnalysisResult(
        total_tasks=0, done_tasks=0, tag_frequencies={}, heading_frequencies={}, body_frequencies={}
    )

    assert result.total_tasks == 0
    assert result.done_tasks == 0
    assert result.tag_frequencies == {}
    assert result.heading_frequencies == {}
    assert result.body_frequencies == {}


def test_analysis_result_attributes():
    """Test that AnalysisResult has all expected attributes."""
    result = AnalysisResult(
        total_tasks=1, done_tasks=1, tag_frequencies={}, heading_frequencies={}, body_frequencies={}
    )

    assert hasattr(result, "total_tasks")
    assert hasattr(result, "done_tasks")
    assert hasattr(result, "tag_frequencies")
    assert hasattr(result, "heading_frequencies")
    assert hasattr(result, "body_frequencies")


def test_analysis_result_is_dataclass():
    """Test that AnalysisResult is a dataclass."""
    from dataclasses import is_dataclass

    assert is_dataclass(AnalysisResult)


def test_analysis_result_repr():
    """Test the string representation of AnalysisResult."""
    result = AnalysisResult(
        total_tasks=2,
        done_tasks=1,
        tag_frequencies={"test": Frequency(1)},
        heading_frequencies={},
        body_frequencies={},
    )

    repr_str = repr(result)
    assert "AnalysisResult" in repr_str
    assert "total_tasks=2" in repr_str
    assert "done_tasks=1" in repr_str


def test_analysis_result_equality():
    """Test equality comparison of AnalysisResult objects."""
    result1 = AnalysisResult(
        total_tasks=5,
        done_tasks=3,
        tag_frequencies={"python": Frequency(2)},
        heading_frequencies={"test": Frequency(1)},
        body_frequencies={},
    )

    result2 = AnalysisResult(
        total_tasks=5,
        done_tasks=3,
        tag_frequencies={"python": Frequency(2)},
        heading_frequencies={"test": Frequency(1)},
        body_frequencies={},
    )

    result3 = AnalysisResult(
        total_tasks=10,
        done_tasks=5,
        tag_frequencies={},
        heading_frequencies={},
        body_frequencies={},
    )

    assert result1 == result2
    assert result1 != result3


def test_analysis_result_mutable_fields():
    """Test that AnalysisResult fields can be modified."""
    result = AnalysisResult(
        total_tasks=0, done_tasks=0, tag_frequencies={}, heading_frequencies={}, body_frequencies={}
    )

    result.total_tasks = 10
    result.done_tasks = 5
    result.tag_frequencies["new"] = Frequency(1)

    assert result.total_tasks == 10
    assert result.done_tasks == 5
    assert "new" in result.tag_frequencies


def test_analysis_result_dict_operations():
    """Test that dictionary operations work on frequency fields."""
    result = AnalysisResult(
        total_tasks=3,
        done_tasks=2,
        tag_frequencies={"python": Frequency(3), "testing": Frequency(2)},
        heading_frequencies={"task": Frequency(1)},
        body_frequencies={},
    )

    assert len(result.tag_frequencies) == 2
    assert "python" in result.tag_frequencies
    assert list(result.tag_frequencies.keys()) == ["python", "testing"]
    assert result.tag_frequencies["python"].total == 3
