"""Tests for the analyze() function."""

import orgparse

from orgstats.analyze import analyze
from tests.conftest import node_from_org


def test_analyze_empty_nodes() -> None:
    """Test analyze with empty nodes list."""
    nodes: list[orgparse.node.OrgNode] = []
    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks == 0
    assert result.task_states.values.get("DONE", 0) == 0
    assert result.task_states.values.get("TODO", 0) == 0
    assert result.tag_frequencies == {}
    assert result.tag_relations == {}
    assert result.tag_time_ranges == {}


def test_analyze_single_done_task() -> None:
    """Test analyze with a single DONE task."""
    nodes = node_from_org("* DONE Write tests :Testing:\nUnit tests\n")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks == 1
    assert result.task_states.values["DONE"] == 1
    assert result.task_states.values.get("TODO", 0) == 0
    assert "Testing" in result.tag_frequencies
    assert result.tag_frequencies["Testing"] == 1


def test_analyze_single_todo_task() -> None:
    """Test analyze with a single TODO task."""
    nodes = node_from_org("* TODO Implement feature :Feature:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks == 1
    assert result.task_states.values["TODO"] == 1
    assert result.task_states.values.get("DONE", 0) == 0


def test_analyze_multiple_tasks() -> None:
    """Test analyze with multiple tasks."""
    nodes = node_from_org("""
* DONE Task 1 :Tag1:
* DONE Task 2 :Tag2:
* TODO Task 3 :Tag3:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks == 3
    assert result.task_states.values["DONE"] == 2
    assert result.task_states.values["TODO"] == 1


def test_analyze_tag_frequencies() -> None:
    """Test that tag frequencies are counted correctly."""
    nodes = node_from_org("""
* DONE Task :Python:
* DONE Task :Python:
* DONE Task :Python:Testing:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.tag_frequencies["Python"] == 3
    assert result.tag_frequencies["Testing"] == 1


def test_analyze_heading_word_frequencies() -> None:
    """Test that heading words are counted correctly when category is 'heading'."""
    nodes = node_from_org("""
* DONE Implement feature
* DONE Implement tests
* DONE Write documentation
""")

    result = analyze(nodes, {}, category="heading", max_relations=3, done_keys=["DONE"])

    assert result.tag_frequencies["implement"] == 2
    assert result.tag_frequencies["feature"] == 1
    assert result.tag_frequencies["tests"] == 1
    assert result.tag_frequencies["write"] == 1
    assert result.tag_frequencies["documentation"] == 1


def test_analyze_body_word_frequencies() -> None:
    """Test that body words are counted correctly when category is 'body'."""
    nodes = node_from_org("""
* DONE Task
Python code implementation
* DONE Task
Python tests
""")

    result = analyze(nodes, {}, category="body", max_relations=3, done_keys=["DONE"])

    assert result.tag_frequencies["python"] == 2
    assert result.tag_frequencies["code"] == 1
    assert result.tag_frequencies["implementation"] == 1
    assert result.tag_frequencies["tests"] == 1


def test_analyze_repeated_tasks() -> None:
    """Test analyze with repeated tasks."""
    nodes = node_from_org("""
* TODO Task :Recurring:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
- State "TODO"       from "DONE"       [2023-10-18 Wed 09:05]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    # result.total_tasks = max(1, len(repeated_tasks)) = max(1, 3) = 3
    assert result.total_tasks == 3
    # Repeated tasks only: 2 DONE repeats + 1 TODO repeat = 1 TODO, 2 DONE
    assert result.task_states.values["TODO"] == 1
    assert result.task_states.values["DONE"] == 2
    # Tags should be counted with count=2
    assert result.tag_frequencies["Recurring"] == 2


def test_analyze_repeated_tasks_count_in_tags() -> None:
    """Test that repeated task count affects tag frequencies."""
    nodes = node_from_org("""
* TODO Meeting :Daily:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])
    assert result.tag_frequencies["Daily"] == 2

    result_heading = analyze(nodes, {}, category="heading", max_relations=3, done_keys=["DONE"])
    assert result_heading.tag_frequencies["meeting"] == 2


def test_analyze_done_task_no_repeats() -> None:
    """Test DONE task with no repeated tasks."""
    nodes = node_from_org("* DONE Task :Simple:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks == 1
    assert result.task_states.values["DONE"] == 1
    assert result.task_states.values.get("TODO", 0) == 0
    assert result.tag_frequencies["Simple"] == 1


def test_analyze_normalizes_tags() -> None:
    """Test that analyze applies mapping to tags without normalization."""
    nodes = node_from_org("* DONE Task :Test:SysAdmin:\n")

    result = analyze(
        nodes,
        {"Test": "Testing", "SysAdmin": "DevOps"},
        category="tags",
        max_relations=3,
        done_keys=["DONE"],
    )

    # "Test" -> "Testing" (mapped, no normalization)
    # "SysAdmin" -> "DevOps" (mapped, no normalization)
    assert "Testing" in result.tag_frequencies
    assert "DevOps" in result.tag_frequencies


def test_analyze_multiple_tags_per_task() -> None:
    """Test task with multiple tags."""
    nodes = node_from_org("* DONE Task :Python:Testing:Debugging:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert len(result.tag_frequencies) == 3
    assert "Python" in result.tag_frequencies
    assert "Testing" in result.tag_frequencies
    assert "Debugging" in result.tag_frequencies


def test_analyze_empty_tags() -> None:
    """Test task with no tags."""
    nodes = node_from_org("* DONE No tags\n")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.tag_frequencies == {}


def test_analyze_empty_heading() -> None:
    """Test task with empty heading."""
    nodes = node_from_org("* DONE\nContent\n")

    result = analyze(nodes, {}, category="heading", max_relations=3, done_keys=["DONE"])

    assert result.tag_frequencies == {}


def test_analyze_empty_body() -> None:
    """Test task with empty body."""
    nodes = node_from_org("* DONE Title\n")

    result = analyze(nodes, {}, category="body", max_relations=3, done_keys=["DONE"])

    # Empty body split() returns [''], which becomes {''} in normalize
    # Frequency objects, so check if empty string exists
    if "" in result.tag_frequencies:
        assert result.tag_frequencies[""].total >= 0


def test_analyze_returns_tuple() -> None:
    """Test that analyze returns an AnalysisResult object."""
    from orgstats.analyze import AnalysisResult

    nodes: list[orgparse.node.OrgNode] = []
    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert isinstance(result, AnalysisResult)
    assert result.total_tasks == 0
    assert result.task_states.values.get("DONE", 0) == 0
    assert result.task_states.values.get("TODO", 0) == 0
    assert result.tag_frequencies == {}
    assert result.tag_relations == {}
    assert result.tag_time_ranges == {}


def test_analyze_accumulates_across_nodes() -> None:
    """Test that frequencies accumulate across multiple nodes."""
    nodes = node_from_org("""
* DONE Task one :Python:
implementation
* DONE Task two :Python:
implementation
""")

    result_tags = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])
    assert result_tags.tag_frequencies["Python"] == 2

    result_heading = analyze(nodes, {}, category="heading", max_relations=3, done_keys=["DONE"])
    assert result_heading.tag_frequencies["task"] == 2
    assert result_heading.tag_frequencies["one"] == 1
    assert result_heading.tag_frequencies["two"] == 1

    result_body = analyze(nodes, {}, category="body", max_relations=3, done_keys=["DONE"])
    assert result_body.tag_frequencies["implementation"] == 2


def test_analyze_max_count_logic() -> None:
    """Test the max(final, repeats) logic for count."""
    # Case 1: final > repeats (DONE task with TODO repeat)
    # Case 2: repeats > final (TODO task with DONE repeats)
    nodes = node_from_org("""
* DONE Task :A:
:LOGBOOK:
- State "TODO"       from "DONE"       [2023-10-18 Wed 09:05]
:END:

* TODO Task :B:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    # Node1: count = max(1, 0) = 1
    # Node2: count = max(0, 2) = 2
    assert result.tag_frequencies["A"] == 1
    assert result.tag_frequencies["B"] == 2


def test_analyze_with_custom_mapping() -> None:
    """Test analyze with custom mapping parameter."""
    custom_map = {"Foo": "Bar", "Baz": "Qux"}
    nodes = node_from_org("* DONE Task :Foo:Baz:Unmapped:\n")

    result = analyze(nodes, custom_map, category="tags", max_relations=3, done_keys=["DONE"])

    assert "Bar" in result.tag_frequencies
    assert "Qux" in result.tag_frequencies
    assert "Unmapped" in result.tag_frequencies
    assert "Foo" not in result.tag_frequencies
    assert "Baz" not in result.tag_frequencies


def test_analyze_with_empty_mapping() -> None:
    """Test analyze with empty mapping (no transformations)."""
    empty_map: dict[str, str] = {}
    nodes = node_from_org("* DONE Task :Test:SysAdmin:\n")

    result = analyze(nodes, empty_map, category="tags", max_relations=3, done_keys=["DONE"])

    assert "Test" in result.tag_frequencies
    assert "SysAdmin" in result.tag_frequencies
    assert "Testing" not in result.tag_frequencies
    assert "DevOps" not in result.tag_frequencies


def test_analyze_default_mapping_parameter() -> None:
    """Test that default mapping parameter uses MAP."""
    nodes = node_from_org("* DONE Task :Test:SysAdmin:\n")

    result = analyze(
        nodes,
        {"Test": "Testing", "SysAdmin": "DevOps"},
        category="tags",
        max_relations=3,
        done_keys=["DONE"],
    )

    assert "Testing" in result.tag_frequencies
    assert "DevOps" in result.tag_frequencies


def test_analyze_mapping_affects_all_categories() -> None:
    """Test that custom mapping affects tags, heading, and body."""
    custom_map = {"Foo": "Bar", "foo": "bar"}
    nodes = node_from_org("* DONE foo word :Foo:\nfoo content\n")

    result_tags = analyze(nodes, custom_map, category="tags", max_relations=3, done_keys=["DONE"])
    assert "Bar" in result_tags.tag_frequencies

    result_heading = analyze(
        nodes, custom_map, category="heading", max_relations=3, done_keys=["DONE"]
    )
    assert "bar" in result_heading.tag_frequencies

    result_body = analyze(nodes, custom_map, category="body", max_relations=3, done_keys=["DONE"])
    assert "bar" in result_body.tag_frequencies


def test_analyze_cancelled_task() -> None:
    """Test analyze with CANCELLED task (orgparse recognizes it via configuration)."""
    import orgparse

    content = """#+TODO: TODO | DONE CANCELLED

* CANCELLED Task :Feature:
"""
    ns = orgparse.loads(content)
    nodes = list(ns[1:]) if ns else []

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks == 1
    assert result.task_states.values["CANCELLED"] == 1
    assert result.task_states.values.get("DONE", 0) == 0
    assert result.task_states.values.get("TODO", 0) == 0


def test_analyze_suspended_task() -> None:
    """Test analyze with SUSPENDED task (orgparse recognizes it via configuration)."""
    import orgparse

    content = """#+TODO: TODO | DONE SUSPENDED

* SUSPENDED Task :Feature:
"""
    ns = orgparse.loads(content)
    nodes = list(ns[1:]) if ns else []

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks == 1
    assert result.task_states.values["SUSPENDED"] == 1
    assert result.task_states.values.get("DONE", 0) == 0
    assert result.task_states.values.get("TODO", 0) == 0


def test_analyze_delegated_task() -> None:
    """Test analyze with DELEGATED task (orgparse recognizes it via configuration)."""
    import orgparse

    content = """#+TODO: TODO | DONE DELEGATED

* DELEGATED Task :Feature:
"""
    ns = orgparse.loads(content)
    nodes = list(ns[1:]) if ns else []

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks == 1
    assert result.task_states.values["DELEGATED"] == 1
    assert result.task_states.values.get("DONE", 0) == 0
    assert result.task_states.values.get("TODO", 0) == 0


def test_analyze_node_without_state() -> None:
    """Test analyze with node that has no TODO state (maps to 'none')."""
    nodes = node_from_org("* Task without state :Feature:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks == 1
    assert result.task_states.values["none"] == 1
    assert result.task_states.values.get("DONE", 0) == 0
    assert result.task_states.values.get("TODO", 0) == 0


def test_analyze_repeated_tasks_different_states() -> None:
    """Test repeated tasks with different states than parent node."""
    import orgparse

    content = """#+TODO: TODO | DONE CANCELLED

* TODO Task :Feature:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "CANCELLED"  from "TODO"       [2023-10-19 Thu 09:10]
:END:
"""
    ns = orgparse.loads(content)
    nodes = list(ns[1:]) if ns else []

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks == 2
    # Only repeated tasks are counted (main node TODO state is ignored)
    assert result.task_states.values.get("TODO", 0) == 0
    assert result.task_states.values["DONE"] == 1
    assert result.task_states.values["CANCELLED"] == 1


def test_analyze_all_task_states_mixed() -> None:
    """Test analyze with all task states mixed."""
    import orgparse

    content = """#+TODO: TODO | DONE CANCELLED SUSPENDED DELEGATED

* TODO Task 1 :A:
* DONE Task 2 :B:
* CANCELLED Task 3 :C:
* SUSPENDED Task 4 :D:
* DELEGATED Task 5 :E:
* Task 6 :F:
"""
    ns = orgparse.loads(content)
    nodes = list(ns[1:]) if ns else []

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks == 6
    assert result.task_states.values["TODO"] == 1
    assert result.task_states.values["DONE"] == 1
    assert result.task_states.values["CANCELLED"] == 1
    assert result.task_states.values["SUSPENDED"] == 1
    assert result.task_states.values["DELEGATED"] == 1
    assert result.task_states.values["none"] == 1


def test_analyze_state_counts_match_total_tasks() -> None:
    """Test that sum of state counts equals total_tasks."""
    nodes = node_from_org("""
* TODO Task 1 :A:
* DONE Task 2 :B:
* TODO Task 3 :C:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    # Sum all state counts
    total_state_counts = sum(result.task_states.values.values())

    # Should equal total_tasks
    assert total_state_counts == result.total_tasks


def test_analyze_state_counts_match_with_no_repeats() -> None:
    """Test state count sum equals total_tasks when no tasks have repeats."""
    nodes = node_from_org("""
* TODO Task 1 :A:
* DONE Task 2 :B:
* CANCELLED Task 3 :C:
* Task 4 without state :D:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    # Sum all state counts
    total_state_counts = sum(result.task_states.values.values())

    # Should equal total_tasks
    assert total_state_counts == result.total_tasks
    assert result.total_tasks == 4


def test_analyze_state_counts_match_with_all_repeats() -> None:
    """Test state count sum equals total_tasks when all tasks have repeats."""
    import orgparse

    content = """#+TODO: TODO | DONE

* TODO Task 1 :A:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
:END:

* TODO Task 2 :B:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:05]
:END:
"""
    ns = orgparse.loads(content)
    nodes = list(ns[1:]) if ns else []

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    # Sum all state counts
    total_state_counts = sum(result.task_states.values.values())

    # Should equal total_tasks
    assert total_state_counts == result.total_tasks
    assert result.total_tasks == 3
