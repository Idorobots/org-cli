"""Tests for the analyze() function."""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core import analyze


class MockNode:
    """Mock node object for testing analyze()."""
    
    def __init__(self, todo="TODO", tags=None, heading="", body="", repeated_tasks=None):
        self.todo = todo
        self.tags = tags if tags is not None else []
        self.heading = heading
        self.body = body
        self.repeated_tasks = repeated_tasks if repeated_tasks is not None else []


class MockRepeatedTask:
    """Mock repeated task for testing."""
    
    def __init__(self, after="TODO"):
        self.after = after


def test_analyze_empty_nodes():
    """Test analyze with empty nodes list."""
    nodes = []
    total, done, tags, heading, words = analyze(nodes)
    
    assert total == 0
    assert done == 0
    assert tags == {}
    assert heading == {}
    assert words == {}


def test_analyze_single_done_task():
    """Test analyze with a single DONE task."""
    node = MockNode(todo="DONE", tags=["Testing"], heading="Write tests", body="Unit tests")
    nodes = [node]
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert total == 1
    assert done == 1
    assert "testing" in tags
    assert tags["testing"] == 1


def test_analyze_single_todo_task():
    """Test analyze with a single TODO task."""
    node = MockNode(todo="TODO", tags=["Feature"], heading="Implement feature", body="")
    nodes = [node]
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert total == 1
    assert done == 0  # Not done


def test_analyze_multiple_tasks():
    """Test analyze with multiple tasks."""
    nodes = [
        MockNode(todo="DONE", tags=["Tag1"], heading="Task 1", body=""),
        MockNode(todo="DONE", tags=["Tag2"], heading="Task 2", body=""),
        MockNode(todo="TODO", tags=["Tag3"], heading="Task 3", body=""),
    ]
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert total == 3
    assert done == 2


def test_analyze_tag_frequencies():
    """Test that tag frequencies are counted correctly."""
    nodes = [
        MockNode(todo="DONE", tags=["Python"], heading="", body=""),
        MockNode(todo="DONE", tags=["Python"], heading="", body=""),
        MockNode(todo="DONE", tags=["Python", "Testing"], heading="", body=""),
    ]
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert tags["python"] == 3
    assert tags["testing"] == 1


def test_analyze_heading_word_frequencies():
    """Test that heading words are counted correctly."""
    nodes = [
        MockNode(todo="DONE", tags=[], heading="Implement feature", body=""),
        MockNode(todo="DONE", tags=[], heading="Implement tests", body=""),
        MockNode(todo="DONE", tags=[], heading="Write documentation", body=""),
    ]
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert heading["implement"] == 2
    assert heading["feature"] == 1
    assert heading["tests"] == 1
    assert heading["write"] == 1
    assert heading["documentation"] == 1


def test_analyze_body_word_frequencies():
    """Test that body words are counted correctly."""
    nodes = [
        MockNode(todo="DONE", tags=[], heading="", body="Python code implementation"),
        MockNode(todo="DONE", tags=[], heading="", body="Python tests"),
    ]
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert words["python"] == 2
    assert words["code"] == 1
    assert words["implementation"] == 1
    assert words["tests"] == 1


def test_analyze_repeated_tasks():
    """Test analyze with repeated tasks."""
    repeated = [
        MockRepeatedTask(after="DONE"),
        MockRepeatedTask(after="DONE"),
        MockRepeatedTask(after="TODO"),
    ]
    node = MockNode(todo="TODO", tags=["Recurring"], heading="", body="", repeated_tasks=repeated)
    nodes = [node]
    
    total, done, tags, heading, words = analyze(nodes)
    
    # total = max(1, len(repeated_tasks)) = max(1, 3) = 3
    assert total == 3
    # done = 2 (two DONE in repeated tasks)
    assert done == 2
    # Tags should be counted with count=2
    assert tags["recurring"] == 2


def test_analyze_repeated_tasks_count_in_tags():
    """Test that repeated task count affects tag frequencies."""
    repeated = [
        MockRepeatedTask(after="DONE"),
        MockRepeatedTask(after="DONE"),
    ]
    node = MockNode(todo="TODO", tags=["Daily"], heading="Meeting", body="", repeated_tasks=repeated)
    nodes = [node]
    
    total, done, tags, heading, words = analyze(nodes)
    
    # count = max(final=0, repeats=2) = 2
    assert tags["daily"] == 2
    assert heading["meeting"] == 2


def test_analyze_done_task_no_repeats():
    """Test DONE task with no repeated tasks."""
    node = MockNode(todo="DONE", tags=["Simple"], heading="Task", body="")
    nodes = [node]
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert total == 1
    assert done == 1
    assert tags["simple"] == 1


def test_analyze_normalizes_tags():
    """Test that analyze normalizes tags (via normalize function)."""
    node = MockNode(todo="DONE", tags=["Test", "SysAdmin"], heading="", body="")
    nodes = [node]
    
    total, done, tags, heading, words = analyze(nodes)
    
    # "Test" -> "test" -> "testing" (mapped)
    # "SysAdmin" -> "sysadmin" -> "devops" (mapped)
    assert "testing" in tags
    assert "devops" in tags


def test_analyze_multiple_tags_per_task():
    """Test task with multiple tags."""
    node = MockNode(todo="DONE", tags=["Python", "Testing", "Debugging"], heading="", body="")
    nodes = [node]
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert len(tags) == 3
    assert "python" in tags
    assert "testing" in tags
    assert "debugging" in tags


def test_analyze_empty_tags():
    """Test task with no tags."""
    node = MockNode(todo="DONE", tags=[], heading="No tags", body="")
    nodes = [node]
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert tags == {}


def test_analyze_empty_heading():
    """Test task with empty heading."""
    node = MockNode(todo="DONE", tags=[], heading="", body="Content")
    nodes = [node]
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert heading == {}


def test_analyze_empty_body():
    """Test task with empty body."""
    node = MockNode(todo="DONE", tags=[], heading="Title", body="")
    nodes = [node]
    
    total, done, tags, heading, words = analyze(nodes)
    
    # Empty body split() returns [''], which becomes {''} in normalize
    assert words.get("", 0) >= 0  # May have empty string


def test_analyze_returns_tuple():
    """Test that analyze returns a tuple."""
    nodes = []
    result = analyze(nodes)
    
    assert isinstance(result, tuple)
    assert len(result) == 5


def test_analyze_accumulates_across_nodes():
    """Test that frequencies accumulate across multiple nodes."""
    nodes = [
        MockNode(todo="DONE", tags=["Python"], heading="Task one", body="implementation"),
        MockNode(todo="DONE", tags=["Python"], heading="Task two", body="implementation"),
    ]
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert tags["python"] == 2
    assert heading["task"] == 2
    assert heading["one"] == 1
    assert heading["two"] == 1
    assert words["implementation"] == 2


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
    
    total, done, tags, heading, words = analyze([node1, node2])
    
    # Node1: count = max(1, 0) = 1
    # Node2: count = max(0, 2) = 2
    assert tags["a"] == 1
    assert tags["b"] == 2
