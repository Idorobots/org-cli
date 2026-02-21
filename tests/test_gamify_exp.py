"""Tests for gamify_exp parsing."""

from org.filters import get_gamify_exp, parse_gamify_exp
from tests.conftest import node_from_org


def test_parse_gamify_exp_integer() -> None:
    """Test parsing integer gamify_exp values."""
    assert parse_gamify_exp("5") == 5
    assert parse_gamify_exp("10") == 10
    assert parse_gamify_exp("20") == 20
    assert parse_gamify_exp("25") == 25
    assert parse_gamify_exp("100") == 100


def test_parse_gamify_exp_tuple_format() -> None:
    """Test parsing (X Y) tuple format."""
    assert parse_gamify_exp("(5 10)") == 5
    assert parse_gamify_exp("(25 30)") == 25
    assert parse_gamify_exp("(15 20)") == 15
    assert parse_gamify_exp("(100 200)") == 100


def test_parse_gamify_exp_tuple_with_whitespace() -> None:
    """Test parsing (X Y) format with various whitespace."""
    assert parse_gamify_exp("( 5 10 )") == 5
    assert parse_gamify_exp("(  15   20  )") == 15
    assert parse_gamify_exp("(25  30)") == 25


def test_parse_gamify_exp_none() -> None:
    """Test parsing None returns None."""
    assert parse_gamify_exp(None) is None


def test_parse_gamify_exp_empty_string() -> None:
    """Test parsing empty string returns None."""
    assert parse_gamify_exp("") is None
    assert parse_gamify_exp("   ") is None


def test_parse_gamify_exp_invalid_format() -> None:
    """Test parsing invalid formats returns None."""
    assert parse_gamify_exp("invalid") is None
    assert parse_gamify_exp("abc") is None
    assert parse_gamify_exp("not a number") is None


def test_parse_gamify_exp_invalid_tuple() -> None:
    """Test parsing invalid tuple format returns None."""
    assert parse_gamify_exp("(abc 10)") is None
    assert parse_gamify_exp("(abc def)") is None
    assert parse_gamify_exp("(10)") is None
    assert parse_gamify_exp("()") is None


def test_parse_gamify_exp_tuple_with_invalid_second() -> None:
    """Test that (X Y) format extracts X even if Y is invalid."""
    assert parse_gamify_exp("(10 abc)") == 10
    assert parse_gamify_exp("(15 invalid)") == 15


def test_parse_gamify_exp_with_extra_spaces() -> None:
    """Test parsing values with leading/trailing spaces."""
    assert parse_gamify_exp("  5  ") == 5
    assert parse_gamify_exp("  15  ") == 15


def test_gamify_exp_with_integer() -> None:
    """Test get_gamify_exp() extracts integer values."""
    node = node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")[0]
    assert get_gamify_exp(node) == 15


def test_gamify_exp_with_none() -> None:
    """Test get_gamify_exp() returns None when property missing."""
    node = node_from_org("* DONE Task\n")[0]
    assert get_gamify_exp(node) is None


def test_gamify_exp_with_tuple() -> None:
    """Test get_gamify_exp() extracts from tuple format."""
    node = node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: (20 25)\n:END:\n")[0]
    assert get_gamify_exp(node) == 20


def test_gamify_exp_with_invalid() -> None:
    """Test get_gamify_exp() returns None for invalid values."""
    node = node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: invalid\n:END:\n")[0]
    assert get_gamify_exp(node) is None


def test_gamify_exp_with_empty_string() -> None:
    """Test get_gamify_exp() returns None for empty string."""
    node = node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: \n:END:\n")[0]
    assert get_gamify_exp(node) is None


def test_gamify_exp_with_various_values() -> None:
    """Test get_gamify_exp() with various integer values."""
    assert (
        get_gamify_exp(node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")[0]) == 5
    )
    assert (
        get_gamify_exp(node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 10\n:END:\n")[0])
        == 10
    )
    assert (
        get_gamify_exp(node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 20\n:END:\n")[0])
        == 20
    )
    assert (
        get_gamify_exp(node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 100\n:END:\n")[0])
        == 100
    )


def test_gamify_exp_with_tuple_formats() -> None:
    """Test get_gamify_exp() with various tuple formats."""
    assert (
        get_gamify_exp(node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: (5 10)\n:END:\n")[0])
        == 5
    )
    assert (
        get_gamify_exp(node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: (25 30)\n:END:\n")[0])
        == 25
    )
    assert (
        get_gamify_exp(
            node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: ( 15 20 )\n:END:\n")[0]
        )
        == 15
    )
