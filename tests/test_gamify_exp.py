"""Tests for gamify_exp parsing and difficulty tracking."""

from orgstats.core import Frequency, analyze, parse_gamify_exp


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

    def __init__(self, after="TODO", start=None):
        self.after = after
        self.start = start


def test_parse_gamify_exp_integer():
    """Test parsing integer gamify_exp values."""
    assert parse_gamify_exp("5") == 5
    assert parse_gamify_exp("10") == 10
    assert parse_gamify_exp("20") == 20
    assert parse_gamify_exp("25") == 25
    assert parse_gamify_exp("100") == 100


def test_parse_gamify_exp_tuple_format():
    """Test parsing (X Y) tuple format."""
    assert parse_gamify_exp("(5 10)") == 5
    assert parse_gamify_exp("(25 30)") == 25
    assert parse_gamify_exp("(15 20)") == 15
    assert parse_gamify_exp("(100 200)") == 100


def test_parse_gamify_exp_tuple_with_whitespace():
    """Test parsing (X Y) format with various whitespace."""
    assert parse_gamify_exp("( 5 10 )") == 5
    assert parse_gamify_exp("(  15   20  )") == 15
    assert parse_gamify_exp("(25  30)") == 25


def test_parse_gamify_exp_none():
    """Test parsing None returns None."""
    assert parse_gamify_exp(None) is None


def test_parse_gamify_exp_empty_string():
    """Test parsing empty string returns None."""
    assert parse_gamify_exp("") is None
    assert parse_gamify_exp("   ") is None


def test_parse_gamify_exp_invalid_format():
    """Test parsing invalid formats returns None."""
    assert parse_gamify_exp("invalid") is None
    assert parse_gamify_exp("abc") is None
    assert parse_gamify_exp("not a number") is None


def test_parse_gamify_exp_invalid_tuple():
    """Test parsing invalid tuple format returns None."""
    assert parse_gamify_exp("(abc 10)") is None
    assert parse_gamify_exp("(abc def)") is None
    assert parse_gamify_exp("(10)") is None
    assert parse_gamify_exp("()") is None


def test_parse_gamify_exp_tuple_with_invalid_second():
    """Test that (X Y) format extracts X even if Y is invalid."""
    assert parse_gamify_exp("(10 abc)") == 10
    assert parse_gamify_exp("(15 invalid)") == 15


def test_parse_gamify_exp_with_extra_spaces():
    """Test parsing values with leading/trailing spaces."""
    assert parse_gamify_exp("  5  ") == 5
    assert parse_gamify_exp("  15  ") == 15


def test_difficulty_simple_tasks():
    """Test that tasks with gamify_exp < 10 are classified as simple."""
    node = MockNode(
        todo="DONE", tags=["Python"], heading="Task", body="", properties={"gamify_exp": "5"}
    )
    result = analyze([node])

    assert result.tag_frequencies["python"].total == 1
    assert result.tag_frequencies["python"].simple == 1
    assert result.tag_frequencies["python"].regular == 0
    assert result.tag_frequencies["python"].hard == 0


def test_difficulty_simple_edge_case():
    """Test that gamify_exp = 9 is simple (< 10)."""
    node = MockNode(
        todo="DONE", tags=["Testing"], heading="", body="", properties={"gamify_exp": "9"}
    )
    result = analyze([node])

    assert result.tag_frequencies["testing"].simple == 1
    assert result.tag_frequencies["testing"].regular == 0
    assert result.tag_frequencies["testing"].hard == 0


def test_difficulty_regular_tasks():
    """Test that tasks with 10 <= gamify_exp < 20 are classified as regular."""
    nodes = [
        MockNode(todo="DONE", tags=["Tag1"], heading="", body="", properties={"gamify_exp": "10"}),
        MockNode(todo="DONE", tags=["Tag2"], heading="", body="", properties={"gamify_exp": "15"}),
        MockNode(todo="DONE", tags=["Tag3"], heading="", body="", properties={"gamify_exp": "19"}),
    ]
    result = analyze(nodes)

    assert result.tag_frequencies["tag1"].regular == 1
    assert result.tag_frequencies["tag2"].regular == 1
    assert result.tag_frequencies["tag3"].regular == 1


def test_difficulty_hard_tasks():
    """Test that tasks with gamify_exp >= 20 are classified as hard."""
    nodes = [
        MockNode(todo="DONE", tags=["Hard1"], heading="", body="", properties={"gamify_exp": "20"}),
        MockNode(todo="DONE", tags=["Hard2"], heading="", body="", properties={"gamify_exp": "25"}),
        MockNode(
            todo="DONE", tags=["Hard3"], heading="", body="", properties={"gamify_exp": "100"}
        ),
    ]
    result = analyze(nodes)

    assert result.tag_frequencies["hard1"].hard == 1
    assert result.tag_frequencies["hard2"].hard == 1
    assert result.tag_frequencies["hard3"].hard == 1


def test_difficulty_missing_gamify_exp():
    """Test that tasks without gamify_exp default to regular."""
    node = MockNode(todo="DONE", tags=["Default"], heading="", body="", properties={})
    result = analyze([node])

    assert result.tag_frequencies["default"].total == 1
    assert result.tag_frequencies["default"].simple == 0
    assert result.tag_frequencies["default"].regular == 1
    assert result.tag_frequencies["default"].hard == 0


def test_difficulty_invalid_gamify_exp():
    """Test that tasks with invalid gamify_exp default to regular."""
    node = MockNode(
        todo="DONE", tags=["Invalid"], heading="", body="", properties={"gamify_exp": "invalid"}
    )
    result = analyze([node])

    assert result.tag_frequencies["invalid"].regular == 1
    assert result.tag_frequencies["invalid"].simple == 0
    assert result.tag_frequencies["invalid"].hard == 0


def test_difficulty_tuple_format():
    """Test that (X Y) format uses X for difficulty classification."""
    nodes = [
        MockNode(
            todo="DONE", tags=["Simple"], heading="", body="", properties={"gamify_exp": "(5 10)"}
        ),
        MockNode(
            todo="DONE",
            tags=["Regular"],
            heading="",
            body="",
            properties={"gamify_exp": "(15 20)"},
        ),
        MockNode(
            todo="DONE", tags=["Hard"], heading="", body="", properties={"gamify_exp": "(25 30)"}
        ),
    ]
    result = analyze(nodes)

    assert result.tag_frequencies["simple"].simple == 1
    assert result.tag_frequencies["regular"].regular == 1
    assert result.tag_frequencies["hard"].hard == 1


def test_difficulty_repeated_tasks():
    """Test that repeated tasks use the same difficulty for all repetitions."""
    repeated = [
        MockRepeatedTask(after="DONE"),
        MockRepeatedTask(after="DONE"),
        MockRepeatedTask(after="DONE"),
    ]
    node = MockNode(
        todo="TODO",
        tags=["Recurring"],
        heading="",
        body="",
        repeated_tasks=repeated,
        properties={"gamify_exp": "5"},
    )
    result = analyze([node])

    assert result.tag_frequencies["recurring"].total == 3
    assert result.tag_frequencies["recurring"].simple == 3
    assert result.tag_frequencies["recurring"].regular == 0
    assert result.tag_frequencies["recurring"].hard == 0


def test_difficulty_applies_to_heading_words():
    """Test that difficulty tracking applies to heading words."""
    node = MockNode(
        todo="DONE",
        tags=[],
        heading="Implement feature",
        body="",
        properties={"gamify_exp": "5"},
    )
    result = analyze([node])

    assert result.heading_frequencies["implement"].simple == 1
    assert result.heading_frequencies["feature"].simple == 1


def test_difficulty_applies_to_body_words():
    """Test that difficulty tracking applies to body words."""
    node = MockNode(
        todo="DONE", tags=[], heading="", body="Python code", properties={"gamify_exp": "25"}
    )
    result = analyze([node])

    assert result.body_frequencies["python"].hard == 1
    assert result.body_frequencies["code"].hard == 1


def test_difficulty_all_fields_updated():
    """Test that all frequency dictionaries track difficulty correctly."""
    node = MockNode(
        todo="DONE",
        tags=["Testing"],
        heading="Write tests",
        body="Unit testing code",
        properties={"gamify_exp": "15"},
    )
    result = analyze([node])

    assert result.tag_frequencies["testing"].regular == 1
    assert result.heading_frequencies["write"].regular == 1
    assert result.heading_frequencies["tests"].regular == 1
    assert result.body_frequencies["unit"].regular == 1
    assert result.body_frequencies["testing"].regular == 1
    assert result.body_frequencies["code"].regular == 1


def test_difficulty_accumulation():
    """Test that difficulty counts accumulate across multiple nodes."""
    nodes = [
        MockNode(todo="DONE", tags=["Python"], heading="", body="", properties={"gamify_exp": "5"}),
        MockNode(
            todo="DONE", tags=["Python"], heading="", body="", properties={"gamify_exp": "15"}
        ),
        MockNode(
            todo="DONE", tags=["Python"], heading="", body="", properties={"gamify_exp": "25"}
        ),
    ]
    result = analyze(nodes)

    assert result.tag_frequencies["python"].total == 3
    assert result.tag_frequencies["python"].simple == 1
    assert result.tag_frequencies["python"].regular == 1
    assert result.tag_frequencies["python"].hard == 1


def test_difficulty_boundary_values():
    """Test boundary values for difficulty classification."""
    nodes = [
        MockNode(todo="DONE", tags=["A"], heading="", body="", properties={"gamify_exp": "9"}),
        MockNode(todo="DONE", tags=["B"], heading="", body="", properties={"gamify_exp": "10"}),
        MockNode(todo="DONE", tags=["C"], heading="", body="", properties={"gamify_exp": "19"}),
        MockNode(todo="DONE", tags=["D"], heading="", body="", properties={"gamify_exp": "20"}),
    ]
    result = analyze(nodes)

    assert result.tag_frequencies["a"].simple == 1
    assert result.tag_frequencies["b"].regular == 1
    assert result.tag_frequencies["c"].regular == 1
    assert result.tag_frequencies["d"].hard == 1


def test_frequency_with_all_difficulty_types():
    """Test Frequency object with all difficulty types set."""
    freq = Frequency(total=10, simple=3, regular=5, hard=2)
    assert freq.total == 10
    assert freq.simple == 3
    assert freq.regular == 5
    assert freq.hard == 2


def test_frequency_equality_with_difficulty():
    """Test Frequency equality comparison with difficulty fields."""
    freq1 = Frequency(total=5, simple=1, regular=2, hard=2)
    freq2 = Frequency(total=5, simple=1, regular=2, hard=2)
    freq3 = Frequency(total=5, simple=2, regular=2, hard=1)

    assert freq1 == freq2
    assert freq1 != freq3


def test_frequency_repr_with_difficulty():
    """Test Frequency repr includes all difficulty fields."""
    freq = Frequency(total=10, simple=3, regular=5, hard=2)
    expected = "Frequency(total=10, simple=3, regular=5, hard=2)"
    assert repr(freq) == expected


def test_difficulty_with_zero_count():
    """Test difficulty tracking when count is 0 (TODO task with no repeats)."""
    node = MockNode(
        todo="TODO", tags=["Pending"], heading="", body="", properties={"gamify_exp": "5"}
    )
    result = analyze([node])

    assert result.tag_frequencies["pending"].total == 0
    assert result.tag_frequencies["pending"].simple == 0
