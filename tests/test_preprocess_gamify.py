"""Tests for gamify category preprocessing."""

from org.filters import preprocess_gamify_categories
from tests.conftest import node_from_org


def test_preprocess_sets_category_simple() -> None:
    """Test preprocessing sets CATEGORY=simple for low gamify_exp."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: 5
:END:
""")

    processed = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "simple"


def test_preprocess_sets_category_regular() -> None:
    """Test preprocessing sets CATEGORY=regular for medium gamify_exp."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: 15
:END:
""")

    processed = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "regular"


def test_preprocess_sets_category_hard() -> None:
    """Test preprocessing sets CATEGORY=hard for high gamify_exp."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: 25
:END:
""")

    processed = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "hard"


def test_preprocess_overwrites_existing_category() -> None:
    """Test preprocessing overwrites existing CATEGORY property."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:CATEGORY: custom
:gamify_exp: 5
:END:
""")

    processed = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "simple"


def test_preprocess_missing_gamify_exp_defaults_regular() -> None:
    """Test preprocessing sets regular for missing gamify_exp."""
    nodes = node_from_org("* DONE Task\n")

    processed = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "regular"


def test_preprocess_custom_category_property() -> None:
    """Test preprocessing with custom property name."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: 5
:END:
""")

    processed = preprocess_gamify_categories(nodes, "TASK_TYPE")

    assert len(processed) == 1
    assert processed[0].properties.get("TASK_TYPE") == "simple"
    assert processed[0].properties.get("CATEGORY") is None


def test_preprocess_preserves_other_properties() -> None:
    """Test preprocessing doesn't affect other properties."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: 5
:other_prop: value
:END:
""")

    processed = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "simple"
    assert processed[0].properties.get("gamify_exp") == "5"
    assert processed[0].properties.get("other_prop") == "value"


def test_preprocess_multiple_nodes() -> None:
    """Test preprocessing multiple nodes."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:gamify_exp: 5
:END:

* DONE Task 2
:PROPERTIES:
:gamify_exp: 15
:END:

* DONE Task 3
:PROPERTIES:
:gamify_exp: 25
:END:
""")

    processed = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(processed) == 3
    assert processed[0].properties.get("CATEGORY") == "simple"
    assert processed[1].properties.get("CATEGORY") == "regular"
    assert processed[2].properties.get("CATEGORY") == "hard"


def test_preprocess_boundary_values() -> None:
    """Test boundary values for categories."""
    nodes = node_from_org("""
* DONE Task at 9
:PROPERTIES:
:gamify_exp: 9
:END:

* DONE Task at 10
:PROPERTIES:
:gamify_exp: 10
:END:

* DONE Task at 19
:PROPERTIES:
:gamify_exp: 19
:END:

* DONE Task at 20
:PROPERTIES:
:gamify_exp: 20
:END:
""")

    processed = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(processed) == 4
    assert processed[0].properties.get("CATEGORY") == "simple"
    assert processed[1].properties.get("CATEGORY") == "regular"
    assert processed[2].properties.get("CATEGORY") == "regular"
    assert processed[3].properties.get("CATEGORY") == "hard"


def test_preprocess_tuple_format() -> None:
    """Test gamify_exp in tuple format (X Y)."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: (25 30)
:END:
""")

    processed = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "hard"


def test_preprocess_invalid_gamify_exp() -> None:
    """Test invalid gamify_exp defaults to regular."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: invalid
:END:
""")

    processed = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "regular"


def test_preprocess_empty_nodes() -> None:
    """Test preprocessing empty nodes list."""
    nodes = node_from_org("")

    processed = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(processed) == 0


def test_preprocess_preserves_heading() -> None:
    """Test preprocessing preserves node heading."""
    nodes = node_from_org("""
* DONE Important Task
:PROPERTIES:
:gamify_exp: 5
:END:
""")

    processed = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].heading == "Important Task"


def test_preprocess_preserves_tags() -> None:
    """Test preprocessing preserves node tags."""
    nodes = node_from_org("""
* DONE Task :tag1:tag2:
:PROPERTIES:
:gamify_exp: 5
:END:
""")

    processed = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(processed) == 1
    assert "tag1" in processed[0].tags
    assert "tag2" in processed[0].tags
