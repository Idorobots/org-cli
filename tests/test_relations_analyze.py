"""Tests for relations computation in the analyze() function."""

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


def test_analyze_empty_nodes_has_empty_relations():
    """Test analyze with empty nodes returns empty relations."""
    nodes = []
    result = analyze(nodes)

    assert result.tag_relations == {}
    assert result.heading_relations == {}
    assert result.body_relations == {}


def test_analyze_single_tag_no_relations():
    """Test task with single tag creates no Relations objects."""
    node = MockNode(todo="DONE", tags=["Python"], heading="", body="")
    nodes = [node]

    result = analyze(nodes)

    assert result.tag_relations == {}


def test_analyze_two_tags_bidirectional_relation():
    """Test task with two tags creates bidirectional relation."""
    node = MockNode(todo="DONE", tags=["Python", "Testing"], heading="", body="")
    nodes = [node]

    result = analyze(nodes)

    assert "python" in result.tag_relations
    assert "testing" in result.tag_relations

    assert result.tag_relations["python"].relations["testing"] == 1
    assert result.tag_relations["testing"].relations["python"] == 1


def test_analyze_three_tags_all_relations():
    """Test task with three tags creates all bidirectional relations."""
    node = MockNode(todo="DONE", tags=["TagA", "TagB", "TagC"], heading="", body="")
    nodes = [node]

    result = analyze(nodes)

    assert "taga" in result.tag_relations
    assert "tagb" in result.tag_relations
    assert "tagc" in result.tag_relations

    assert result.tag_relations["taga"].relations["tagb"] == 1
    assert result.tag_relations["tagb"].relations["taga"] == 1
    assert result.tag_relations["taga"].relations["tagc"] == 1
    assert result.tag_relations["tagc"].relations["taga"] == 1
    assert result.tag_relations["tagb"].relations["tagc"] == 1
    assert result.tag_relations["tagc"].relations["tagb"] == 1

    assert len(result.tag_relations["taga"].relations) == 2
    assert len(result.tag_relations["tagb"].relations) == 2
    assert len(result.tag_relations["tagc"].relations) == 2


def test_analyze_no_self_relations():
    """Test that tags do not create relations with themselves."""
    node = MockNode(todo="DONE", tags=["Python", "Testing"], heading="", body="")
    nodes = [node]

    result = analyze(nodes)

    assert "python" not in result.tag_relations["python"].relations
    assert "testing" not in result.tag_relations["testing"].relations


def test_analyze_relations_normalized():
    """Test that tag normalization applies to relations."""
    node = MockNode(todo="DONE", tags=["Test", "SysAdmin"], heading="", body="")
    nodes = [node]

    result = analyze(nodes)

    # "Test" -> "test" -> "testing" (mapped)
    # "SysAdmin" -> "sysadmin" -> "devops" (mapped)
    assert "testing" in result.tag_relations
    assert "devops" in result.tag_relations
    assert result.tag_relations["testing"].relations["devops"] == 1
    assert result.tag_relations["devops"].relations["testing"] == 1


def test_analyze_relations_accumulate():
    """Test that relations accumulate across multiple nodes."""
    nodes = [
        MockNode(todo="DONE", tags=["Python", "Testing"], heading="", body=""),
        MockNode(todo="DONE", tags=["Python", "Testing"], heading="", body=""),
    ]

    result = analyze(nodes)

    assert result.tag_relations["python"].relations["testing"] == 2
    assert result.tag_relations["testing"].relations["python"] == 2


def test_analyze_relations_with_repeated_tasks():
    """Test that repeated tasks increment relations by count."""
    repeated = [
        MockRepeatedTask(after="DONE"),
        MockRepeatedTask(after="DONE"),
    ]
    node = MockNode(
        todo="TODO", tags=["Daily", "Meeting"], heading="", body="", repeated_tasks=repeated
    )
    nodes = [node]

    result = analyze(nodes)

    # count = max(0, 2) = 2
    assert result.tag_relations["daily"].relations["meeting"] == 2
    assert result.tag_relations["meeting"].relations["daily"] == 2


def test_analyze_heading_relations():
    """Test that heading word relations are computed separately."""
    node = MockNode(todo="DONE", tags=[], heading="Implement feature", body="")
    nodes = [node]

    result = analyze(nodes)

    assert "implement" in result.heading_relations
    assert "feature" in result.heading_relations
    assert result.heading_relations["implement"].relations["feature"] == 1
    assert result.heading_relations["feature"].relations["implement"] == 1


def test_analyze_body_relations():
    """Test that body word relations are computed separately."""
    node = MockNode(todo="DONE", tags=[], heading="", body="Python code implementation")
    nodes = [node]

    result = analyze(nodes)

    assert "python" in result.body_relations
    assert "code" in result.body_relations
    assert "implementation" in result.body_relations

    assert result.body_relations["python"].relations["code"] == 1
    assert result.body_relations["code"].relations["python"] == 1
    assert result.body_relations["python"].relations["implementation"] == 1
    assert result.body_relations["implementation"].relations["python"] == 1
    assert result.body_relations["code"].relations["implementation"] == 1
    assert result.body_relations["implementation"].relations["code"] == 1


def test_analyze_relations_independent():
    """Test that tag, heading, and body relations are independent."""
    node = MockNode(
        todo="DONE", tags=["Python", "Testing"], heading="Python tests", body="Python code"
    )
    nodes = [node]

    result = analyze(nodes)

    # Tag relations: Python-Testing
    assert result.tag_relations["python"].relations.get("testing") == 1
    assert "tests" not in result.tag_relations["python"].relations

    # Heading relations: Python-tests
    assert result.heading_relations["python"].relations.get("tests") == 1
    assert "testing" not in result.heading_relations.get("python", {}).relations

    # Body relations: Python-code
    assert result.body_relations["python"].relations.get("code") == 1


def test_analyze_relations_with_different_counts():
    """Test that different nodes with different counts increment correctly."""
    repeated1 = [MockRepeatedTask(after="DONE")]
    repeated2 = [
        MockRepeatedTask(after="DONE"),
        MockRepeatedTask(after="DONE"),
        MockRepeatedTask(after="DONE"),
    ]

    nodes = [
        MockNode(todo="DONE", tags=["TagA", "TagB"], heading="", body="", repeated_tasks=repeated1),
        MockNode(todo="TODO", tags=["TagA", "TagB"], heading="", body="", repeated_tasks=repeated2),
    ]

    result = analyze(nodes)

    # First node: count = max(1, 1) = 1
    # Second node: count = max(0, 3) = 3
    # Total: 1 + 3 = 4
    assert result.tag_relations["taga"].relations["tagb"] == 4
    assert result.tag_relations["tagb"].relations["taga"] == 4


def test_analyze_relations_mixed_tags():
    """Test relations with tasks that share some but not all tags."""
    nodes = [
        MockNode(todo="DONE", tags=["Python", "Testing"], heading="", body=""),
        MockNode(todo="DONE", tags=["Python", "Debugging"], heading="", body=""),
        MockNode(todo="DONE", tags=["Testing", "Debugging"], heading="", body=""),
    ]

    result = analyze(nodes)

    # Python appears with Testing (1x) and Debugging (1x)
    assert result.tag_relations["python"].relations["testing"] == 1
    assert result.tag_relations["python"].relations["debugging"] == 1

    # Testing appears with Python (1x) and Debugging (1x)
    assert result.tag_relations["testing"].relations["python"] == 1
    assert result.tag_relations["testing"].relations["debugging"] == 1

    # Debugging appears with Python (1x) and Testing (1x)
    assert result.tag_relations["debugging"].relations["python"] == 1
    assert result.tag_relations["debugging"].relations["testing"] == 1


def test_analyze_relations_empty_tags():
    """Test that tasks with no tags create no relations."""
    node = MockNode(todo="DONE", tags=[], heading="Task", body="Content")
    nodes = [node]

    result = analyze(nodes)

    assert result.tag_relations == {}


def test_analyze_four_tags_six_relations():
    """Test task with four tags creates six bidirectional relations."""
    node = MockNode(todo="DONE", tags=["A", "B", "C", "D"], heading="", body="")
    nodes = [node]

    result = analyze(nodes)

    # With 4 tags, we should have C(4,2) = 6 unique pairs
    # A-B, A-C, A-D, B-C, B-D, C-D

    assert len(result.tag_relations["a"].relations) == 3  # B, C, D
    assert len(result.tag_relations["b"].relations) == 3  # A, C, D
    assert len(result.tag_relations["c"].relations) == 3  # A, B, D
    assert len(result.tag_relations["d"].relations) == 3  # A, B, C

    assert result.tag_relations["a"].relations["b"] == 1
    assert result.tag_relations["a"].relations["c"] == 1
    assert result.tag_relations["a"].relations["d"] == 1
    assert result.tag_relations["b"].relations["c"] == 1
    assert result.tag_relations["b"].relations["d"] == 1
    assert result.tag_relations["c"].relations["d"] == 1


def test_analyze_relations_result_structure():
    """Test that analyze returns Relations objects with correct structure."""
    from orgstats.core import Relations

    node = MockNode(todo="DONE", tags=["Python", "Testing"], heading="", body="")
    nodes = [node]

    result = analyze(nodes)

    assert isinstance(result.tag_relations["python"], Relations)
    assert result.tag_relations["python"].name == "python"
    assert isinstance(result.tag_relations["python"].relations, dict)
    assert isinstance(result.tag_relations["python"].relations["testing"], int)
