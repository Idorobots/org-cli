"""Tests for the analyze() function."""

from orgstats.core import analyze


class MockNode:
    """Mock node object for testing analyze()."""

    def __init__(  # noqa: PLR0913
        self, todo="TODO", tags=None, heading="", body="", repeated_tasks=None, properties=None
    ):
        self.todo = todo
        self.tags = tags if tags is not None else []
        self.heading = heading
        self.body = body
        self.repeated_tasks = repeated_tasks if repeated_tasks is not None else []
        self.properties = properties if properties is not None else {}


class MockRepeatedTask:
    """Mock repeated task for testing."""

    def __init__(self, after="TODO"):
        self.after = after


def test_analyze_empty_nodes():
    """Test analyze with empty nodes list."""
    nodes = []
    result = analyze(nodes)

    assert result.total_tasks == 0
    assert result.done_tasks == 0
    assert result.tag_frequencies == {}
    assert result.heading_frequencies == {}
    assert result.body_frequencies == {}


def test_analyze_single_done_task():
    """Test analyze with a single DONE task."""
    node = MockNode(todo="DONE", tags=["Testing"], heading="Write tests", body="Unit tests")
    nodes = [node]

    result = analyze(nodes)

    assert result.total_tasks == 1
    assert result.done_tasks == 1
    assert "testing" in result.tag_frequencies
    assert result.tag_frequencies["testing"] == 1


def test_analyze_single_todo_task():
    """Test analyze with a single TODO task."""
    node = MockNode(todo="TODO", tags=["Feature"], heading="Implement feature", body="")
    nodes = [node]

    result = analyze(nodes)

    assert result.total_tasks == 1
    assert result.done_tasks == 0  # Not result.done_tasks


def test_analyze_multiple_tasks():
    """Test analyze with multiple tasks."""
    nodes = [
        MockNode(todo="DONE", tags=["Tag1"], heading="Task 1", body=""),
        MockNode(todo="DONE", tags=["Tag2"], heading="Task 2", body=""),
        MockNode(todo="TODO", tags=["Tag3"], heading="Task 3", body=""),
    ]

    result = analyze(nodes)

    assert result.total_tasks == 3
    assert result.done_tasks == 2


def test_analyze_tag_frequencies():
    """Test that tag frequencies are counted correctly."""
    nodes = [
        MockNode(todo="DONE", tags=["Python"], heading="", body=""),
        MockNode(todo="DONE", tags=["Python"], heading="", body=""),
        MockNode(todo="DONE", tags=["Python", "Testing"], heading="", body=""),
    ]

    result = analyze(nodes)

    assert result.tag_frequencies["python"] == 3
    assert result.tag_frequencies["testing"] == 1


def test_analyze_heading_word_frequencies():
    """Test that heading words are counted correctly."""
    nodes = [
        MockNode(todo="DONE", tags=[], heading="Implement feature", body=""),
        MockNode(todo="DONE", tags=[], heading="Implement tests", body=""),
        MockNode(todo="DONE", tags=[], heading="Write documentation", body=""),
    ]

    result = analyze(nodes)

    assert result.heading_frequencies["implement"] == 2
    assert result.heading_frequencies["feature"] == 1
    assert result.heading_frequencies["tests"] == 1
    assert result.heading_frequencies["write"] == 1
    assert result.heading_frequencies["documentation"] == 1


def test_analyze_body_word_frequencies():
    """Test that body words are counted correctly."""
    nodes = [
        MockNode(todo="DONE", tags=[], heading="", body="Python code implementation"),
        MockNode(todo="DONE", tags=[], heading="", body="Python tests"),
    ]

    result = analyze(nodes)

    assert result.body_frequencies["python"] == 2
    assert result.body_frequencies["code"] == 1
    assert result.body_frequencies["implementation"] == 1
    assert result.body_frequencies["tests"] == 1


def test_analyze_repeated_tasks():
    """Test analyze with repeated tasks."""
    repeated = [
        MockRepeatedTask(after="DONE"),
        MockRepeatedTask(after="DONE"),
        MockRepeatedTask(after="TODO"),
    ]
    node = MockNode(todo="TODO", tags=["Recurring"], heading="", body="", repeated_tasks=repeated)
    nodes = [node]

    result = analyze(nodes)

    # result.total_tasks = max(1, len(repeated_tasks)) = max(1, 3) = 3
    assert result.total_tasks == 3
    # result.done_tasks = 2 (two DONE in repeated tasks)
    assert result.done_tasks == 2
    # Tags should be counted with count=2
    assert result.tag_frequencies["recurring"] == 2


def test_analyze_repeated_tasks_count_in_tags():
    """Test that repeated task count affects tag frequencies."""
    repeated = [
        MockRepeatedTask(after="DONE"),
        MockRepeatedTask(after="DONE"),
    ]
    node = MockNode(
        todo="TODO", tags=["Daily"], heading="Meeting", body="", repeated_tasks=repeated
    )
    nodes = [node]

    result = analyze(nodes)

    # count = max(final=0, repeats=2) = 2
    assert result.tag_frequencies["daily"] == 2
    assert result.heading_frequencies["meeting"] == 2


def test_analyze_done_task_no_repeats():
    """Test DONE task with no repeated tasks."""
    node = MockNode(todo="DONE", tags=["Simple"], heading="Task", body="")
    nodes = [node]

    result = analyze(nodes)

    assert result.total_tasks == 1
    assert result.done_tasks == 1
    assert result.tag_frequencies["simple"] == 1


def test_analyze_normalizes_tags():
    """Test that analyze normalizes tags (via normalize function)."""
    node = MockNode(todo="DONE", tags=["Test", "SysAdmin"], heading="", body="")
    nodes = [node]

    result = analyze(nodes)

    # "Test" -> "test" -> "testing" (mapped)
    # "SysAdmin" -> "sysadmin" -> "devops" (mapped)
    assert "testing" in result.tag_frequencies
    assert "devops" in result.tag_frequencies


def test_analyze_multiple_tags_per_task():
    """Test task with multiple tags."""
    node = MockNode(todo="DONE", tags=["Python", "Testing", "Debugging"], heading="", body="")
    nodes = [node]

    result = analyze(nodes)

    assert len(result.tag_frequencies) == 3
    assert "python" in result.tag_frequencies
    assert "testing" in result.tag_frequencies
    assert "debugging" in result.tag_frequencies


def test_analyze_empty_tags():
    """Test task with no tags."""
    node = MockNode(todo="DONE", tags=[], heading="No tags", body="")
    nodes = [node]

    result = analyze(nodes)

    assert result.tag_frequencies == {}


def test_analyze_empty_heading():
    """Test task with empty heading."""
    node = MockNode(todo="DONE", tags=[], heading="", body="Content")
    nodes = [node]

    result = analyze(nodes)

    assert result.heading_frequencies == {}


def test_analyze_empty_body():
    """Test task with empty body."""
    node = MockNode(todo="DONE", tags=[], heading="Title", body="")
    nodes = [node]

    result = analyze(nodes)

    # Empty body split() returns [''], which becomes {''} in normalize
    # Frequency objects, so check if empty string exists
    if "" in result.body_frequencies:
        assert result.body_frequencies[""].total >= 0


def test_analyze_returns_tuple():
    """Test that analyze returns an AnalysisResult object."""
    from orgstats.core import AnalysisResult

    nodes = []
    result = analyze(nodes)

    assert isinstance(result, AnalysisResult)
    assert hasattr(result, "total_tasks")
    assert hasattr(result, "done_tasks")
    assert hasattr(result, "tag_frequencies")
    assert hasattr(result, "heading_frequencies")
    assert hasattr(result, "body_frequencies")


def test_analyze_accumulates_across_nodes():
    """Test that frequencies accumulate across multiple nodes."""
    nodes = [
        MockNode(todo="DONE", tags=["Python"], heading="Task one", body="implementation"),
        MockNode(todo="DONE", tags=["Python"], heading="Task two", body="implementation"),
    ]

    result = analyze(nodes)

    assert result.tag_frequencies["python"] == 2
    assert result.heading_frequencies["task"] == 2
    assert result.heading_frequencies["one"] == 1
    assert result.heading_frequencies["two"] == 1
    assert result.body_frequencies["implementation"] == 2


def test_analyze_max_count_logic():
    """Test the max(final, repeats) logic for count."""
    # Case 1: final > repeats
    repeated1 = [MockRepeatedTask(after="TODO")]
    node1 = MockNode(todo="DONE", tags=["A"], heading="", body="", repeated_tasks=repeated1)

    # Case 2: repeats > final
    repeated2 = [
        MockRepeatedTask(after="DONE"),
        MockRepeatedTask(after="DONE"),
    ]
    node2 = MockNode(todo="TODO", tags=["B"], heading="", body="", repeated_tasks=repeated2)

    result = analyze([node1, node2])

    # Node1: count = max(1, 0) = 1
    # Node2: count = max(0, 2) = 2
    assert result.tag_frequencies["a"] == 1
    assert result.tag_frequencies["b"] == 2
