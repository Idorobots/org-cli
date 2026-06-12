"""Tests for the Distribution class."""

from org.logic.stats import Distribution


def test_histogram_initialization_empty() -> None:
    """Test Distribution can be initialized empty."""
    hist = Distribution()

    assert hist.values == {}


def test_histogram_initialization_with_values() -> None:
    """Test Distribution can be initialized with values."""
    hist = Distribution(values={"TODO": 5, "DONE": 10})

    assert hist.values["TODO"] == 5
    assert hist.values["DONE"] == 10


def test_histogram_repr() -> None:
    """Test Distribution repr."""
    hist = Distribution(values={"TODO": 5, "DONE": 10})

    assert repr(hist) == "Distribution(values={'TODO': 5, 'DONE': 10})"


def test_histogram_empty_repr() -> None:
    """Test Distribution repr when empty."""
    hist = Distribution()

    assert repr(hist) == "Distribution(values={})"


def test_histogram_values_mutable() -> None:
    """Test that distribution values can be modified."""
    hist = Distribution(values={"TODO": 5})

    hist.update("TODO", 1)
    hist.values["DONE"] = 10

    assert hist.values["TODO"] == 6
    assert hist.values["DONE"] == 10


def test_histogram_get_with_default() -> None:
    """Test getting values with default."""
    hist = Distribution(values={"TODO": 5})

    assert hist.values.get("TODO", 0) == 5
    assert hist.values.get("DONE", 0) == 0


def test_histogram_update_existing_key() -> None:
    """Test update method with existing key."""
    hist = Distribution(values={"TODO": 5})

    hist.update("TODO", 3)

    assert hist.values["TODO"] == 8


def test_histogram_update_new_key() -> None:
    """Test update method with new key."""
    hist = Distribution(values={"TODO": 5})

    hist.update("DONE", 10)

    assert hist.values["DONE"] == 10
    assert hist.values["TODO"] == 5


def test_histogram_update_negative_amount() -> None:
    """Test update method with negative amount."""
    hist = Distribution(values={"TODO": 10})

    hist.update("TODO", -3)

    assert hist.values["TODO"] == 7


def test_histogram_update_zero_amount() -> None:
    """Test update method with zero amount."""
    hist = Distribution(values={"TODO": 5})

    hist.update("TODO", 0)

    assert hist.values["TODO"] == 5
