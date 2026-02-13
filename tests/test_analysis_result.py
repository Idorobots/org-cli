"""Tests for the AnalysisResult dataclass."""

from orgstats.core import AnalysisResult, Frequency, Histogram, TimeRange


def test_analysis_result_initialization() -> None:
    """Test that AnalysisResult can be initialized with all fields."""
    from orgstats.core import Relations

    result = AnalysisResult(
        total_tasks=10,
        task_states=Histogram(values={"DONE": 5, "TODO": 5}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tag_frequencies={"python": Frequency(3)},
        tag_relations={"python": Relations(name="python", relations={})},
        tag_time_ranges={},
        tag_groups=[],
    )

    assert result.total_tasks == 10
    assert result.task_states.values["DONE"] == 5
    assert result.task_states.values["TODO"] == 5
    assert result.task_days.values == {}
    assert result.timerange.earliest is None
    assert result.avg_tasks_per_day == 0.0
    assert result.max_single_day_count == 0
    assert result.max_repeat_count == 0
    assert result.tag_frequencies == {"python": Frequency(3)}
    assert "python" in result.tag_relations
    assert result.tag_time_ranges == {}
    assert result.tag_groups == []


def test_analysis_result_empty_initialization() -> None:
    """Test AnalysisResult with empty data."""
    result = AnalysisResult(
        total_tasks=0,
        task_states=Histogram(values={"DONE": 0, "TODO": 0}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tag_frequencies={},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    assert result.total_tasks == 0
    assert result.task_states.values["DONE"] == 0
    assert result.task_states.values["TODO"] == 0
    assert result.task_days.values == {}
    assert result.timerange.earliest is None
    assert result.avg_tasks_per_day == 0.0
    assert result.max_single_day_count == 0
    assert result.max_repeat_count == 0
    assert result.tag_frequencies == {}
    assert result.tag_relations == {}
    assert result.tag_time_ranges == {}
    assert result.tag_groups == []


def test_analysis_result_attributes() -> None:
    """Test that AnalysisResult has all expected attributes."""
    result = AnalysisResult(
        total_tasks=1,
        task_states=Histogram(values={"DONE": 1, "TODO": 0}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tag_frequencies={},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    assert result.total_tasks == 1
    assert result.task_states.values["DONE"] == 1
    assert result.task_days.values == {}
    assert result.timerange.earliest is None
    assert result.avg_tasks_per_day == 0.0
    assert result.max_single_day_count == 0
    assert result.max_repeat_count == 0
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
        task_states=Histogram(values={"DONE": 1, "TODO": 1}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tag_frequencies={"test": Frequency(1)},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    repr_str = repr(result)
    assert "AnalysisResult" in repr_str
    assert "total_tasks=2" in repr_str
    assert "task_states" in repr_str


def test_analysis_result_equality() -> None:
    """Test equality comparison of AnalysisResult objects."""
    result1 = AnalysisResult(
        total_tasks=5,
        task_states=Histogram(values={"DONE": 3, "TODO": 2}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tag_frequencies={"python": Frequency(2)},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    result2 = AnalysisResult(
        total_tasks=5,
        task_states=Histogram(values={"DONE": 3, "TODO": 2}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tag_frequencies={"python": Frequency(2)},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    result3 = AnalysisResult(
        total_tasks=10,
        task_states=Histogram(values={"DONE": 5, "TODO": 5}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tag_frequencies={},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    assert result1 == result2
    assert result1 != result3


def test_analysis_result_mutable_fields() -> None:
    """Test that AnalysisResult fields can be modified."""
    from datetime import datetime

    from orgstats.core import Group, Relations

    result = AnalysisResult(
        total_tasks=0,
        task_states=Histogram(values={"DONE": 0, "TODO": 0}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tag_frequencies={},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    result.total_tasks = 10
    result.task_states.values["DONE"] = 5
    result.task_states.values["TODO"] = 5
    result.task_days.values["Monday"] = 3
    result.timerange.update(datetime(2024, 1, 1))
    result.avg_tasks_per_day = 1.5
    result.max_single_day_count = 5
    result.max_repeat_count = 3
    result.tag_frequencies["new"] = Frequency(1)
    result.tag_relations["test"] = Relations(name="test", relations={})
    result.tag_time_ranges["python"] = TimeRange()
    result.tag_groups.append(Group(tags=["python", "testing"]))

    assert result.total_tasks == 10
    assert result.task_states.values["DONE"] == 5
    assert result.task_states.values["TODO"] == 5
    assert result.task_days.values["Monday"] == 3
    assert result.timerange.earliest is not None
    assert result.avg_tasks_per_day == 1.5
    assert result.max_single_day_count == 5
    assert result.max_repeat_count == 3
    assert "new" in result.tag_frequencies
    assert "test" in result.tag_relations
    assert "python" in result.tag_time_ranges
    assert len(result.tag_groups) == 1


def test_analysis_result_dict_operations() -> None:
    """Test that dictionary operations work on frequency fields."""
    result = AnalysisResult(
        total_tasks=3,
        task_states=Histogram(values={"DONE": 2, "TODO": 1}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tag_frequencies={"python": Frequency(3), "testing": Frequency(2)},
        tag_relations={},
        tag_time_ranges={},
        tag_groups=[],
    )

    assert len(result.tag_frequencies) == 2
    assert "python" in result.tag_frequencies
    assert list(result.tag_frequencies.keys()) == ["python", "testing"]
    assert result.tag_frequencies["python"].total == 3
