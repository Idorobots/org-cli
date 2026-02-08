"""Tests for the Relations dataclass."""

from orgstats.core import Relations


def test_relations_initialization():
    """Test that Relations can be initialized with all fields."""
    relations = Relations(name="python", relations={"testing": 5, "debugging": 3})

    assert relations.name == "python"
    assert relations.relations == {"testing": 5, "debugging": 3}


def test_relations_empty_initialization():
    """Test Relations with empty relations dictionary."""
    relations = Relations(name="tag", relations={})

    assert relations.name == "tag"
    assert relations.relations == {}


def test_relations_attributes():
    """Test that Relations has all expected attributes."""
    relations = Relations(name="test", relations={})

    assert hasattr(relations, "name")
    assert hasattr(relations, "relations")


def test_relations_is_dataclass():
    """Test that Relations is a dataclass."""
    from dataclasses import is_dataclass

    assert is_dataclass(Relations)


def test_relations_repr():
    """Test the string representation of Relations."""
    relations = Relations(name="python", relations={"testing": 5})

    repr_str = repr(relations)
    assert "Relations" in repr_str
    assert "name='python'" in repr_str
    assert "relations=" in repr_str


def test_relations_equality():
    """Test equality comparison of Relations objects."""
    relations1 = Relations(name="python", relations={"testing": 5})
    relations2 = Relations(name="python", relations={"testing": 5})
    relations3 = Relations(name="java", relations={"testing": 5})
    relations4 = Relations(name="python", relations={"debugging": 3})

    assert relations1 == relations2
    assert relations1 != relations3
    assert relations1 != relations4


def test_relations_mutable_fields():
    """Test that Relations fields can be modified."""
    relations = Relations(name="test", relations={})

    relations.name = "updated"
    relations.relations["new"] = 10

    assert relations.name == "updated"
    assert "new" in relations.relations
    assert relations.relations["new"] == 10


def test_relations_dict_operations():
    """Test that dictionary operations work on relations field."""
    relations = Relations(name="python", relations={"testing": 5, "debugging": 3, "refactoring": 2})

    assert len(relations.relations) == 3
    assert "testing" in relations.relations
    assert relations.relations.get("testing") == 5
    assert relations.relations.get("nonexistent", 0) == 0
    assert list(relations.relations.keys()) == ["testing", "debugging", "refactoring"]
    assert list(relations.relations.values()) == [5, 3, 2]


def test_relations_increment():
    """Test incrementing relation counts."""
    relations = Relations(name="python", relations={"testing": 5})

    relations.relations["testing"] += 1
    relations.relations["debugging"] = relations.relations.get("debugging", 0) + 3

    assert relations.relations["testing"] == 6
    assert relations.relations["debugging"] == 3


def test_relations_with_single_relation():
    """Test Relations with a single relation."""
    relations = Relations(name="tagA", relations={"tagB": 10})

    assert len(relations.relations) == 1
    assert relations.relations["tagB"] == 10
