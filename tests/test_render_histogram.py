"""Tests for the render_histogram() function."""

from orgstats.core import Histogram, render_histogram


def test_render_histogram_empty() -> None:
    """Test empty histogram with no values."""
    histogram = Histogram(values={})
    category_order = ["Some", "Value", "unknown"]

    lines = render_histogram(histogram, 40, category_order)

    assert len(lines) == 3
    assert lines[0] == "Some     ┊ 0"
    assert lines[1] == "Value    ┊ 0"
    assert lines[2] == "unknown  ┊ 0"


def test_render_histogram_single_value_100_percent() -> None:
    """Test one category with all the count."""
    histogram = Histogram(values={"Value": 100})
    category_order = ["Some", "Value"]

    lines = render_histogram(histogram, 40, category_order)

    assert len(lines) == 2
    assert lines[0] == "Some     ┊ 0"
    assert lines[1] == "Value    ┊" + "█" * 40 + " 100"


def test_render_histogram_all_equal_values() -> None:
    """Test multiple categories with equal counts."""
    histogram = Histogram(values={"Some": 50, "Value": 50})
    category_order = ["Some", "Value"]

    lines = render_histogram(histogram, 40, category_order)

    assert len(lines) == 2
    assert lines[0] == "Some     ┊" + "█" * 20 + " 50"
    assert lines[1] == "Value    ┊" + "█" * 20 + " 50"


def test_render_histogram_normal_distribution() -> None:
    """Test realistic distribution."""
    histogram = Histogram(
        values={
            "Monday": 3526,
            "Tuesday": 3273,
            "Wednesday": 3129,
            "Thursday": 2936,
            "Friday": 2694,
            "Saturday": 3452,
            "Sunday": 4165,
            "unknown": 54,
        }
    )
    category_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "unknown",
    ]

    lines = render_histogram(histogram, 50, category_order)

    total = sum(histogram.values.values())
    assert len(lines) == 8

    monday_expected_bars = int((3526 / total) * 50)
    assert lines[0] == f"Monday   ┊{'█' * monday_expected_bars} 3526"

    unknown_expected_bars = int((54 / total) * 50)
    assert lines[7] == f"unknown  ┊{'█' * unknown_expected_bars} 54"


def test_render_histogram_zero_values_shown() -> None:
    """Test categories in order with 0 counts."""
    histogram = Histogram(values={"DONE": 30})
    category_order = ["DONE", "TODO", "CANCELLED"]

    lines = render_histogram(histogram, 40, category_order)

    assert len(lines) == 3
    assert lines[0] == "DONE     ┊" + "█" * 40 + " 30"
    assert lines[1] == "TODO     ┊ 0"
    assert lines[2] == "CANCELLED┊ 0"


def test_render_histogram_category_truncation() -> None:
    """Test long category names truncated."""
    histogram = Histogram(values={"verylongname": 50, "short": 50})
    category_order = ["verylongname", "short"]

    lines = render_histogram(histogram, 40, category_order)

    assert len(lines) == 2
    assert lines[0].startswith("verylong.")
    assert lines[1].startswith("short    ")


def test_render_histogram_category_padding() -> None:
    """Test short names padded."""
    histogram = Histogram(values={"a": 50, "ab": 25, "abc": 25})
    category_order = ["a", "ab", "abc"]

    lines = render_histogram(histogram, 40, category_order)

    assert len(lines) == 3
    assert lines[0][0:10] == "a        ┊"
    assert lines[1][0:10] == "ab       ┊"
    assert lines[2][0:10] == "abc      ┊"


def test_render_histogram_custom_order() -> None:
    """Test respects category_order parameter."""
    histogram = Histogram(values={"DONE": 30, "TODO": 10, "CANCELLED": 5})
    category_order = ["TODO", "DONE", "CANCELLED"]

    lines = render_histogram(histogram, 40, category_order)

    assert len(lines) == 3
    assert lines[0].startswith("TODO     ")
    assert lines[1].startswith("DONE     ")
    assert lines[2].startswith("CANCELLED")


def test_render_histogram_no_order_alphabetical() -> None:
    """Test alphabetical when no order given."""
    histogram = Histogram(values={"DONE": 30, "TODO": 10, "CANCELLED": 5})

    lines = render_histogram(histogram, 40, None)

    assert len(lines) == 3
    assert lines[0].startswith("CANCELLED")
    assert lines[1].startswith("DONE     ")
    assert lines[2].startswith("TODO     ")


def test_render_histogram_different_bucket_widths() -> None:
    """Test various bucket sizes."""
    histogram = Histogram(values={"Value": 100})

    lines_20 = render_histogram(histogram, 20, ["Value"])
    lines_50 = render_histogram(histogram, 50, ["Value"])
    lines_100 = render_histogram(histogram, 100, ["Value"])

    assert "█" * 20 in lines_20[0]
    assert "█" * 50 in lines_50[0]
    assert "█" * 100 in lines_100[0]


def test_render_histogram_proper_rounding() -> None:
    """Test bar lengths round correctly."""
    histogram = Histogram(values={"A": 33, "B": 33, "C": 34})

    lines = render_histogram(histogram, 30, ["A", "B", "C"])

    total = 100
    a_bars = int((33 / total) * 30)
    b_bars = int((33 / total) * 30)
    c_bars = int((34 / total) * 30)

    assert lines[0] == f"A        ┊{'█' * a_bars} 33"
    assert lines[1] == f"B        ┊{'█' * b_bars} 33"
    assert lines[2] == f"C        ┊{'█' * c_bars} 34"


def test_render_histogram_with_unknown_category() -> None:
    """Test unknown category handling."""
    histogram = Histogram(values={"Monday": 5, "Tuesday": 5, "Wednesday": 7, "unknown": 2})
    category_order = ["Monday", "Tuesday", "Wednesday", "unknown"]

    lines = render_histogram(histogram, 40, category_order)

    assert len(lines) == 4
    assert lines[3].startswith("unknown  ")


def test_render_histogram_wednesday_no_truncation() -> None:
    """Test Wednesday (9 chars) fits exactly without truncation."""
    histogram = Histogram(values={"Wednesday": 100})

    lines = render_histogram(histogram, 40, ["Wednesday"])

    assert lines[0].startswith("Wednesday┊")


def test_render_histogram_exact_nine_chars() -> None:
    """Test category with exactly 9 characters."""
    histogram = Histogram(values={"ExactNine": 100})

    lines = render_histogram(histogram, 40, ["ExactNine"])

    assert lines[0][0:10] == "ExactNine┊"


def test_render_histogram_ten_chars_truncated() -> None:
    """Test category with 10 characters gets truncated."""
    histogram = Histogram(values={"TenCharact": 100})

    lines = render_histogram(histogram, 40, ["TenCharact"])

    assert lines[0][0:10] == "TenChara.┊"


def test_render_histogram_proportional_to_sum() -> None:
    """Test bars are proportional to sum, not max value."""
    histogram = Histogram(values={"A": 10, "B": 90})

    lines = render_histogram(histogram, 100, ["A", "B"])

    assert lines[0] == f"A        ┊{'█' * 10} 10"
    assert lines[1] == f"B        ┊{'█' * 90} 90"


def test_render_histogram_preserves_category_order_with_missing() -> None:
    """Test that missing categories from order are shown as 0."""
    histogram = Histogram(values={"B": 50})
    category_order = ["A", "B", "C"]

    lines = render_histogram(histogram, 40, category_order)

    assert len(lines) == 3
    assert lines[0] == "A        ┊ 0"
    assert lines[1] == "B        ┊" + "█" * 40 + " 50"
    assert lines[2] == "C        ┊ 0"


def test_render_histogram_empty_with_no_order() -> None:
    """Test empty histogram with no order produces empty list."""
    histogram = Histogram(values={})

    lines = render_histogram(histogram, 40, None)

    assert lines == []


def test_render_histogram_single_bar_with_small_value() -> None:
    """Test that small values still show correctly."""
    histogram = Histogram(values={"A": 1, "B": 99})

    lines = render_histogram(histogram, 100, ["A", "B"])

    assert lines[0] == f"A        ┊{'█' * 1} 1"
    assert lines[1] == f"B        ┊{'█' * 99} 99"
