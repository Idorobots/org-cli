"""CLI tests for new filter arguments."""

import os
import subprocess
import sys


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_cli_filter_gamify_exp_above() -> None:
    """Test --filter-gamify-exp-above CLI argument."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--filter-gamify-exp-above",
            "20",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "Total tasks:" in result.stdout


def test_cli_filter_gamify_exp_below() -> None:
    """Test --filter-gamify-exp-below CLI argument."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--filter-gamify-exp-below",
            "10",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_repeats_above() -> None:
    """Test --filter-repeats-above CLI argument."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--filter-repeats-above",
            "2",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_repeats_below() -> None:
    """Test --filter-repeats-below CLI argument."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--filter-repeats-below",
            "3",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_date_from() -> None:
    """Test --filter-date-from CLI argument."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-from",
            "2025-01-01",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_date_until() -> None:
    """Test --filter-date-until CLI argument."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-until",
            "2025-12-31",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_date_range() -> None:
    """Test combining --filter-date-from and --filter-date-until."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-from",
            "2025-01-01",
            "--filter-date-until",
            "2025-03-01",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_property() -> None:
    """Test --filter-property CLI argument."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-property",
            "custom_prop=value1",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_property_with_equals() -> None:
    """Test --filter-property with value containing equals sign."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-property",
            "equation=E=mc^2",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_filter_multiple_properties() -> None:
    """Test multiple --filter-property arguments."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-property",
            "custom_prop=value1",
            "--filter-property",
            "gamify_exp=15",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_filter_tag() -> None:
    """Test --filter-tag CLI argument."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-tag", "tag1", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_multiple_tags() -> None:
    """Test multiple --filter-tag arguments (AND logic)."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-tag",
            "tag1",
            "--filter-tag",
            "tag2",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_filter_completed() -> None:
    """Test --filter-completed CLI argument."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-completed", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_not_completed() -> None:
    """Test --filter-not-completed CLI argument."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-not-completed", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_preset_simple_still_works() -> None:
    """Test that old --filter-category simple preset still works."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--filter-category",
            "simple",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_preset_regular_still_works() -> None:
    """Test that old --filter-category regular preset still works."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--filter-category",
            "regular",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_preset_hard_still_works() -> None:
    """Test that old --filter-category hard preset still works."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-category", "hard", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_preset_combined_with_explicit_filter() -> None:
    """Test combining preset with explicit filter."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-category",
            "simple",
            "--filter-tag",
            "tag1",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_complex_filter_combination() -> None:
    """Test complex combination of multiple filters."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-gamify-exp-above",
            "10",
            "--filter-gamify-exp-below",
            "30",
            "--filter-completed",
            "--filter-tag",
            "tag1",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_no_results() -> None:
    """Test that 'No results' is displayed when filters match nothing."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-gamify-exp-above",
            "100",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "No results" in result.stdout


def test_cli_invalid_date_format() -> None:
    """Test error handling for invalid date format."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-from",
            "01/01/2025",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "YYYY-MM-DD" in result.stderr


def test_cli_invalid_property_format() -> None:
    """Test error handling for invalid property format (no equals)."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-property",
            "noequals",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "KEY=VALUE" in result.stderr


def test_cli_help_shows_new_options() -> None:
    """Test that --help displays new filter options."""
    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--filter-gamify-exp-above" in result.stdout
    assert "--filter-gamify-exp-below" in result.stdout
    assert "--filter-repeats-above" in result.stdout
    assert "--filter-repeats-below" in result.stdout
    assert "--filter-date-from" in result.stdout
    assert "--filter-date-until" in result.stdout
    assert "--filter-property" in result.stdout
    assert "--filter-tag" in result.stdout
    assert "--filter-completed" in result.stdout
    assert "--filter-not-completed" in result.stdout


def test_cli_filter_date_from_with_time() -> None:
    """Test --filter-date-from with time component (YYYY-MM-DDThh:mm)."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-from",
            "2025-01-01T12:00",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_date_from_with_seconds() -> None:
    """Test --filter-date-from with seconds (YYYY-MM-DDThh:mm:ss)."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-from",
            "2025-01-01T12:30:45",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_date_from_space_separator() -> None:
    """Test --filter-date-from with space separator (YYYY-MM-DD hh:mm)."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-from",
            "2025-01-01 12:00",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_date_from_space_with_seconds() -> None:
    """Test --filter-date-from with space and seconds (YYYY-MM-DD hh:mm:ss)."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-from",
            "2025-01-01 12:30:45",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_date_until_with_time() -> None:
    """Test --filter-date-until with time component (YYYY-MM-DDThh:mm)."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-until",
            "2025-12-31T23:59",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_date_until_with_seconds() -> None:
    """Test --filter-date-until with seconds (YYYY-MM-DDThh:mm:ss)."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-until",
            "2025-12-31T23:59:59",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_date_until_space_separator() -> None:
    """Test --filter-date-until with space separator (YYYY-MM-DD hh:mm)."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-until",
            "2025-12-31 23:59",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_date_range_mixed_formats() -> None:
    """Test date range with different formats for from and until."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-from",
            "2025-01-01T00:00:00",
            "--filter-date-until",
            "2025-03-01 12:30",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_date_from_midnight() -> None:
    """Test --filter-date-from with midnight time."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-from",
            "2025-01-01T00:00:00",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_date_invalid_format() -> None:
    """Test --filter-date-from with invalid format shows helpful error."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-date-from",
            "01/15/2025",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "must be in one of these formats" in result.stderr
    assert "YYYY-MM-DD" in result.stderr
    assert "YYYY-MM-DDThh:mm" in result.stderr
    assert "YYYY-MM-DD hh:mm" in result.stderr


def test_cli_filter_date_help_shows_formats() -> None:
    """Test that --help shows the new timestamp formats."""
    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "YYYY-MM-DDThh:mm" in result.stdout
    assert "YYYY-MM-DD hh:mm" in result.stdout
