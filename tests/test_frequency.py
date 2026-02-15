"""Tests for the Frequency class."""

from orgstats.analyze import Frequency


def test_frequency_default_initialization() -> None:
    """Test Frequency initializes with default value of 0."""
    freq = Frequency()
    assert freq.total == 0


def test_frequency_initialization_with_value() -> None:
    """Test Frequency initializes with provided value."""
    freq = Frequency(42)
    assert freq.total == 42


def test_frequency_repr() -> None:
    """Test Frequency.__repr__ returns correct format."""
    freq = Frequency(5)
    assert repr(freq) == "Frequency(total=5)"


def test_frequency_eq_with_int() -> None:
    """Test Frequency.__eq__ with integer."""
    freq = Frequency(10)
    assert freq == 10
    assert freq != 5


def test_frequency_eq_with_frequency() -> None:
    """Test Frequency.__eq__ with another Frequency."""
    freq1 = Frequency(10)
    freq2 = Frequency(10)
    freq3 = Frequency(5)
    assert freq1 == freq2
    assert freq1 != freq3


def test_frequency_eq_with_other_type() -> None:
    """Test Frequency.__eq__ with unsupported type returns NotImplemented."""
    freq = Frequency(10)
    result = freq.__eq__("not a number")
    assert result is NotImplemented


def test_frequency_int_conversion() -> None:
    """Test Frequency.__int__ converts to integer."""
    freq = Frequency(42)
    assert int(freq) == 42


def test_frequency_mutable() -> None:
    """Test that Frequency.total field is mutable."""
    freq = Frequency(5)
    freq.total += 10
    assert freq.total == 15
    assert freq == 15


def test_frequency_zero() -> None:
    """Test Frequency with zero value."""
    freq = Frequency(0)
    assert freq.total == 0
    assert freq == 0


def test_frequency_negative() -> None:
    """Test Frequency with negative value."""
    freq = Frequency(-5)
    assert freq.total == -5
    assert freq == -5
