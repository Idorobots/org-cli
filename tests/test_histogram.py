"""Tests for the Histogram class."""

from org.histogram import Histogram


def test_histogram_initialization_empty() -> None:
    """Test Histogram can be initialized empty."""
    hist = Histogram()

    assert hist.values == {}


def test_histogram_initialization_with_values() -> None:
    """Test Histogram can be initialized with values."""
    hist = Histogram(values={"TODO": 5, "DONE": 10})

    assert hist.values["TODO"] == 5
    assert hist.values["DONE"] == 10


def test_histogram_repr() -> None:
    """Test Histogram repr."""
    hist = Histogram(values={"TODO": 5, "DONE": 10})

    assert repr(hist) == "Histogram(values={'TODO': 5, 'DONE': 10})"


def test_histogram_empty_repr() -> None:
    """Test Histogram repr when empty."""
    hist = Histogram()

    assert repr(hist) == "Histogram(values={})"


def test_histogram_values_mutable() -> None:
    """Test that histogram values can be modified."""
    hist = Histogram(values={"TODO": 5})

    hist.update("TODO", 1)
    hist.values["DONE"] = 10

    assert hist.values["TODO"] == 6
    assert hist.values["DONE"] == 10


def test_histogram_get_with_default() -> None:
    """Test getting values with default."""
    hist = Histogram(values={"TODO": 5})

    assert hist.values.get("TODO", 0) == 5
    assert hist.values.get("DONE", 0) == 0


def test_histogram_update_existing_key() -> None:
    """Test update method with existing key."""
    hist = Histogram(values={"TODO": 5})

    hist.update("TODO", 3)

    assert hist.values["TODO"] == 8


def test_histogram_update_new_key() -> None:
    """Test update method with new key."""
    hist = Histogram(values={"TODO": 5})

    hist.update("DONE", 10)

    assert hist.values["DONE"] == 10
    assert hist.values["TODO"] == 5


def test_histogram_update_negative_amount() -> None:
    """Test update method with negative amount."""
    hist = Histogram(values={"TODO": 10})

    hist.update("TODO", -3)

    assert hist.values["TODO"] == 7


def test_histogram_update_zero_amount() -> None:
    """Test update method with zero amount."""
    hist = Histogram(values={"TODO": 5})

    hist.update("TODO", 0)

    assert hist.values["TODO"] == 5
