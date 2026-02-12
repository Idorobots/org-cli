"""Tests for the AnalysisResult dataclass."""

from orgstats.core import AnalysisResult, Frequency


def test_analysis_result_initialization() -> None:
    """Test that AnalysisResult can be initialized with all fields."""
    from orgstats.core import Relations

    result = AnalysisResult(
        total_tasks=10,
        done_tasks=5,
        tag_frequencies={"python": Frequency(3)},
        tag_relations={"python": Relations(name="python", relations={})},
        tag_time_ranges={},
        tag_groups=[],
    )

    assert result.total_tasks == 10
    assert result.done_tasks == 5
    assert result.tag_frequencies == {"python": Frequency(3)}
    assert "python" in result.tag_relations
    assert result.tag_time_ranges == {}
    assert result.tag_groups == []


def test_analysis_result_empty_initialization() -> None:
    """Test AnalysisResult with empty data."""
    result = AnalysisResult(
        total_tasks=0,
        done_tasks=0,
        tag_frequencies={},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    assert result.total_tasks == 0
    assert result.done_tasks == 0
    assert result.tag_frequencies == {}
    assert result.tag_relations == {}
    assert result.tag_time_ranges == {}
    assert result.tag_groups == []


def test_analysis_result_attributes() -> None:
    """Test that AnalysisResult has all expected attributes."""
    result = AnalysisResult(
        total_tasks=1,
        done_tasks=1,
        tag_frequencies={},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    assert result.total_tasks == 1
    assert result.done_tasks == 1
    assert result.tag_frequencies == {}
    assert result.tag_relations == {}
    assert result.tag_time_ranges == {}
    assert result.tag_groups == []


def test_analysis_result_is_dataclass() -> None:
    """Test that AnalysisResult is a dataclass."""
    from dataclasses import is_dataclass

    assert is_dataclass(AnalysisResult)


def test_analysis_result_repr() -> None:
    """Test the string representation of AnalysisResult."""
    result = AnalysisResult(
        total_tasks=2,
        done_tasks=1,
        tag_frequencies={"test": Frequency(1)},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    repr_str = repr(result)
    assert "AnalysisResult" in repr_str
    assert "total_tasks=2" in repr_str
    assert "done_tasks=1" in repr_str


def test_analysis_result_equality() -> None:
    """Test equality comparison of AnalysisResult objects."""
    result1 = AnalysisResult(
        total_tasks=5,
        done_tasks=3,
        tag_frequencies={"python": Frequency(2)},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    result2 = AnalysisResult(
        total_tasks=5,
        done_tasks=3,
        tag_frequencies={"python": Frequency(2)},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    result3 = AnalysisResult(
        total_tasks=10,
        done_tasks=5,
        tag_frequencies={},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    assert result1 == result2
    assert result1 != result3


def test_analysis_result_mutable_fields() -> None:
    """Test that AnalysisResult fields can be modified."""
    from orgstats.core import Group, Relations, TimeRange

    result = AnalysisResult(
        total_tasks=0,
        done_tasks=0,
        tag_frequencies={},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    result.total_tasks = 10
    result.done_tasks = 5
    result.tag_frequencies["new"] = Frequency(1)
    result.tag_relations["test"] = Relations(name="test", relations={})
    result.tag_time_ranges["python"] = TimeRange()
    result.tag_groups.append(Group(tags=["python", "testing"]))

    assert result.total_tasks == 10
    assert result.done_tasks == 5
    assert "new" in result.tag_frequencies
    assert "test" in result.tag_relations
    assert "python" in result.tag_time_ranges
    assert len(result.tag_groups) == 1


def test_analysis_result_dict_operations() -> None:
    """Test that dictionary operations work on frequency fields."""
    result = AnalysisResult(
        total_tasks=3,
        done_tasks=2,
        tag_frequencies={"python": Frequency(3), "testing": Frequency(2)},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    assert len(result.tag_frequencies) == 2
    assert "python" in result.tag_frequencies
    assert list(result.tag_frequencies.keys()) == ["python", "testing"]
    assert result.tag_frequencies["python"].total == 3
