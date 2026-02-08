"""Tests for time range computation in analyze()."""

from datetime import datetime

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
    result = analyze(nodes)

    assert result.tag_time_ranges == {}
    assert result.heading_time_ranges == {}
    assert result.body_time_ranges == {}


def test_analyze_single_task_time_range():
    """Test single task creates TimeRange."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(todo="DONE", tags=["Python"], heading="Test", body="", closed=closed)
    nodes = [node]

    result = analyze(nodes)

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

    result = analyze(nodes)

    assert result.tag_time_ranges["python"].earliest == dt1
    assert result.tag_time_ranges["python"].latest == dt2


def test_analyze_time_range_with_repeated_tasks():
    """Test repeated tasks update TimeRange."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)

    repeated = [MockRepeatedTask("DONE", dt1), MockRepeatedTask("DONE", dt2)]
    node = MockNode(todo="TODO", tags=["Daily"], heading="", body="", repeated_tasks=repeated)
    nodes = [node]

    result = analyze(nodes)

    assert result.tag_time_ranges["daily"].earliest == dt1
    assert result.tag_time_ranges["daily"].latest == dt2


def test_analyze_time_range_fallback_to_closed():
    """Test fallback to closed timestamp."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=closed)
    nodes = [node]

    result = analyze(nodes)

    assert result.tag_time_ranges["python"].earliest == dt
    assert result.tag_time_ranges["python"].latest == dt


def test_analyze_time_range_fallback_to_scheduled():
    """Test fallback to scheduled timestamp."""
    dt = datetime(2023, 10, 20, 0, 0)
    scheduled = MockTimestamp(dt)
    node = MockNode(todo="TODO", tags=["Python"], heading="", body="", scheduled=scheduled)
    nodes = [node]

    result = analyze(nodes)

    assert result.tag_time_ranges["python"].earliest == dt
    assert result.tag_time_ranges["python"].latest == dt


def test_analyze_time_range_fallback_to_deadline():
    """Test fallback to deadline timestamp."""
    dt = datetime(2023, 10, 25, 0, 0)
    deadline = MockTimestamp(dt)
    node = MockNode(todo="TODO", tags=["Python"], heading="", body="", deadline=deadline)
    nodes = [node]

    result = analyze(nodes)

    assert result.tag_time_ranges["python"].earliest == dt
    assert result.tag_time_ranges["python"].latest == dt


def test_analyze_time_range_no_timestamps_ignored():
    """Test tasks without timestamps are ignored for time ranges."""
    node = MockNode(todo="TODO", tags=["Python"], heading="", body="")
    nodes = [node]

    result = analyze(nodes)

    assert result.tag_time_ranges == {}


def test_analyze_time_range_normalized_tags():
    """Test time ranges use normalized tags."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(todo="DONE", tags=["Test", "SysAdmin"], heading="", body="", closed=closed)
    nodes = [node]

    result = analyze(nodes)

    assert "testing" in result.tag_time_ranges
    assert "devops" in result.tag_time_ranges


def test_analyze_time_range_heading_separate():
    """Test heading time ranges computed separately."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(todo="DONE", tags=[], heading="Implement feature", body="", closed=closed)
    nodes = [node]

    result = analyze(nodes)

    assert "implement" in result.heading_time_ranges
    assert "feature" in result.heading_time_ranges


def test_analyze_time_range_body_separate():
    """Test body time ranges computed separately."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(todo="DONE", tags=[], heading="", body="Python code", closed=closed)
    nodes = [node]

    result = analyze(nodes)

    assert "python" in result.body_time_ranges
    assert "code" in result.body_time_ranges


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

    result = analyze(nodes)

    assert result.tag_time_ranges["python"].earliest == dt1
    assert result.tag_time_ranges["python"].latest == dt3


def test_analyze_time_range_same_timestamp():
    """Test multiple tasks with same timestamp."""
    dt = datetime(2023, 10, 20, 14, 43)

    nodes = [
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt)),
        MockNode(todo="DONE", tags=["Python"], heading="", body="", closed=MockTimestamp(dt)),
    ]

    result = analyze(nodes)

    assert result.tag_time_ranges["python"].earliest == dt
    assert result.tag_time_ranges["python"].latest == dt


def test_analyze_result_has_time_range_fields():
    """Test AnalysisResult includes time range fields."""
    from orgstats.core import AnalysisResult

    nodes = []
    result = analyze(nodes)

    assert isinstance(result, AnalysisResult)
    assert hasattr(result, "tag_time_ranges")
    assert hasattr(result, "heading_time_ranges")
    assert hasattr(result, "body_time_ranges")


def test_analyze_time_range_multiple_tags():
    """Test multiple tags in single task update separately."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(todo="DONE", tags=["Python", "Testing"], heading="", body="", closed=closed)
    nodes = [node]

    result = analyze(nodes)

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

    result = analyze(nodes)

    assert result.tag_time_ranges["daily"].earliest == dt1
    assert result.tag_time_ranges["daily"].latest == dt3
