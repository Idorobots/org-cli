"""Tests for time range computation in analyze()."""

from datetime import date, datetime

from orgstats.core import analyze


class MockTimestamp:
    """Mock timestamp object."""

    def __init__(self, start):
        self.start = start


class MockRepeatedTask:
    """Mock repeated task."""

    def __init__(self, after, start):
        self.after = after
        self.start = start


class MockNode:
    """Mock node object for testing analyze()."""

    def __init__(  # noqa: PLR0913
        self,
        todo="TODO",
        tags=None,
        heading="",
        body="",
        repeated_tasks=None,
        properties=None,
        closed=None,
        scheduled=None,
        deadline=None,
    ):
        self.todo = todo
        self.tags = tags if tags is not None else []
        self.heading = heading
        self.body = body
        self.repeated_tasks = repeated_tasks if repeated_tasks is not None else []
        self.properties = properties if properties is not None else {}
        self.closed = closed
        self.scheduled = scheduled
        self.deadline = deadline


def test_analyze_empty_nodes_empty_time_ranges():
    """Test empty nodes returns empty time ranges."""
    nodes = []
    result = analyze(nodes, {}, category="tags")

    assert result.tag_time_ranges == {}


def test_analyze_single_task_time_range():
    """Test single task creates TimeRange."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(todo="DONE", tags=["Python"], heading="Test", body="", closed=closed)
    nodes = [node]

    result = analyze(nodes, {}, category="tags")

    assert "python" in result.tag_time_ranges
    assert result.tag_time_ranges["python"].earliest == dt
    assert result.tag_time_ranges["python"].latest == dt


def test_analyze_multiple_tasks_time_range():
    """Test multiple tasks update TimeRange correctly."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 20, 14, 43)

    nodes = [
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt1)),
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt2)),
    ]

    result = analyze(nodes, {}, category="tags")

    assert result.tag_time_ranges["python"].earliest == dt1
    assert result.tag_time_ranges["python"].latest == dt2


def test_analyze_time_range_with_repeated_tasks():
    """Test repeated tasks update TimeRange."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)

    repeated = [MockRepeatedTask("DONE", dt1), MockRepeatedTask("DONE", dt2)]
    node = MockNode(todo="TODO", tags=["Daily"], heading="", body="", repeated_tasks=repeated)
    nodes = [node]

    result = analyze(nodes, {}, category="tags")

    assert result.tag_time_ranges["daily"].earliest == dt1
    assert result.tag_time_ranges["daily"].latest == dt2


def test_analyze_time_range_fallback_to_closed():
    """Test fallback to closed timestamp."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=closed)
    nodes = [node]

    result = analyze(nodes, {}, category="tags")

    assert result.tag_time_ranges["python"].earliest == dt
    assert result.tag_time_ranges["python"].latest == dt


def test_analyze_time_range_fallback_to_scheduled():
    """Test fallback to scheduled timestamp."""
    dt = datetime(2023, 10, 20, 0, 0)
    scheduled = MockTimestamp(dt)
    node = MockNode(todo="TODO", tags=["Python"], heading="", body="", scheduled=scheduled)
    nodes = [node]

    result = analyze(nodes, {}, category="tags")

    assert result.tag_time_ranges["python"].earliest == dt
    assert result.tag_time_ranges["python"].latest == dt


def test_analyze_time_range_fallback_to_deadline():
    """Test fallback to deadline timestamp."""
    dt = datetime(2023, 10, 25, 0, 0)
    deadline = MockTimestamp(dt)
    node = MockNode(todo="TODO", tags=["Python"], heading="", body="", deadline=deadline)
    nodes = [node]

    result = analyze(nodes, {}, category="tags")

    assert result.tag_time_ranges["python"].earliest == dt
    assert result.tag_time_ranges["python"].latest == dt


def test_analyze_time_range_no_timestamps_ignored():
    """Test tasks without timestamps are ignored for time ranges."""
    node = MockNode(todo="TODO", tags=["Python"], heading="", body="")
    nodes = [node]

    result = analyze(nodes, {}, category="tags")

    assert result.tag_time_ranges == {}


def test_analyze_time_range_normalized_tags():
    """Test time ranges use normalized tags."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(todo="DONE", tags=["Test", "SysAdmin"], heading="", body="", closed=closed)
    nodes = [node]

    result = analyze(nodes, {"test": "testing", "sysadmin": "devops"}, category="tags")

    assert "testing" in result.tag_time_ranges
    assert "devops" in result.tag_time_ranges


def test_analyze_time_range_heading_separate():
    """Test heading time ranges computed for heading category."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(todo="DONE", tags=[], heading="Implement feature", body="", closed=closed)
    nodes = [node]

    result = analyze(nodes, {}, category="heading")

    assert "implement" in result.tag_time_ranges
    assert "feature" in result.tag_time_ranges


def test_analyze_time_range_body_separate():
    """Test body time ranges computed for body category."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(todo="DONE", tags=[], heading="", body="Python code", closed=closed)
    nodes = [node]

    result = analyze(nodes, {}, category="body")

    assert "python" in result.tag_time_ranges
    assert "code" in result.tag_time_ranges


def test_analyze_time_range_earliest_latest():
    """Test earliest and latest are correctly tracked."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)

    nodes = [
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt2)),
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt1)),
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt3)),
    ]

    result = analyze(nodes, {}, category="tags")

    assert result.tag_time_ranges["python"].earliest == dt1
    assert result.tag_time_ranges["python"].latest == dt3


def test_analyze_time_range_same_timestamp():
    """Test multiple tasks with same timestamp."""
    dt = datetime(2023, 10, 20, 14, 43)

    nodes = [
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt)),
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt)),
    ]

    result = analyze(nodes, {}, category="tags")

    assert result.tag_time_ranges["python"].earliest == dt
    assert result.tag_time_ranges["python"].latest == dt


def test_analyze_result_has_time_range_fields():
    """Test AnalysisResult includes time range fields."""
    from orgstats.core import AnalysisResult

    nodes = []
    result = analyze(nodes, {}, category="tags")

    assert isinstance(result, AnalysisResult)
    assert hasattr(result, "tag_time_ranges")


def test_analyze_time_range_multiple_tags():
    """Test multiple tags in single task update separately."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(todo="DONE", tags=["Python", "Testing"], heading="", body="", closed=closed)
    nodes = [node]

    result = analyze(nodes, {}, category="tags")

    assert result.tag_time_ranges["python"].earliest == dt
    assert result.tag_time_ranges["testing"].earliest == dt


def test_analyze_time_range_repeated_all_done():
    """Test all DONE repeated tasks contribute to time range."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)

    repeated = [
        MockRepeatedTask("DONE", dt1),
        MockRepeatedTask("DONE", dt2),
        MockRepeatedTask("DONE", dt3),
    ]
    node = MockNode(todo="TODO", tags=["Daily"], heading="", body="", repeated_tasks=repeated)
    nodes = [node]

    result = analyze(nodes, {}, category="tags")

    assert result.tag_time_ranges["daily"].earliest == dt1
    assert result.tag_time_ranges["daily"].latest == dt3


def test_analyze_timeline_single_task():
    """Test single task creates timeline with one entry."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=closed)
    nodes = [node]

    result = analyze(nodes, {}, category="tags")

    assert "python" in result.tag_time_ranges
    timeline = result.tag_time_ranges["python"].timeline
    assert len(timeline) == 1
    assert timeline[date(2023, 10, 20)] == 1


def test_analyze_timeline_multiple_tasks_different_days():
    """Test multiple tasks on different days create multiple timeline entries."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)

    nodes = [
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt1)),
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt2)),
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt3)),
    ]

    result = analyze(nodes, {}, category="tags")

    timeline = result.tag_time_ranges["python"].timeline
    assert len(timeline) == 3
    assert timeline[date(2023, 10, 18)] == 1
    assert timeline[date(2023, 10, 19)] == 1
    assert timeline[date(2023, 10, 20)] == 1


def test_analyze_timeline_multiple_tasks_same_day():
    """Test multiple tasks on same day increment same timeline entry."""
    dt1 = datetime(2023, 10, 20, 9, 15)
    dt2 = datetime(2023, 10, 20, 14, 43)

    nodes = [
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt1)),
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt2)),
    ]

    result = analyze(nodes, {}, category="tags")

    timeline = result.tag_time_ranges["python"].timeline
    assert len(timeline) == 1
    assert timeline[date(2023, 10, 20)] == 2


def test_analyze_timeline_repeated_tasks():
    """Test repeated tasks all appear in timeline."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)

    repeated = [
        MockRepeatedTask("DONE", dt1),
        MockRepeatedTask("DONE", dt2),
        MockRepeatedTask("DONE", dt3),
    ]
    node = MockNode(todo="TODO", tags=["Daily"], heading="", body="", repeated_tasks=repeated)
    nodes = [node]

    result = analyze(nodes, {}, category="tags")

    timeline = result.tag_time_ranges["daily"].timeline
    assert len(timeline) == 3
    assert timeline[date(2023, 10, 18)] == 1
    assert timeline[date(2023, 10, 19)] == 1
    assert timeline[date(2023, 10, 20)] == 1


def test_analyze_timeline_repeated_tasks_same_day():
    """Test repeated tasks on same day increment counter."""
    dt1 = datetime(2023, 10, 20, 9, 15)
    dt2 = datetime(2023, 10, 20, 14, 30)
    dt3 = datetime(2023, 10, 20, 18, 0)

    repeated = [
        MockRepeatedTask("DONE", dt1),
        MockRepeatedTask("DONE", dt2),
        MockRepeatedTask("DONE", dt3),
    ]
    node = MockNode(todo="TODO", tags=["Daily"], heading="", body="", repeated_tasks=repeated)
    nodes = [node]

    result = analyze(nodes, {}, category="tags")

    timeline = result.tag_time_ranges["daily"].timeline
    assert len(timeline) == 1
    assert timeline[date(2023, 10, 20)] == 3


def test_analyze_timeline_mixed_repeats_and_regular():
    """Test mix of repeated and regular tasks."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 19, 15, 0)

    repeated = [MockRepeatedTask("DONE", dt1), MockRepeatedTask("DONE", dt2)]
    nodes = [
        MockNode(todo="TODO", tags=["Python"], heading="", body="", repeated_tasks=repeated),
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt3)),
    ]

    result = analyze(nodes, {}, category="tags")

    timeline = result.tag_time_ranges["python"].timeline
    assert len(timeline) == 2
    assert timeline[date(2023, 10, 18)] == 1
    assert timeline[date(2023, 10, 19)] == 2
