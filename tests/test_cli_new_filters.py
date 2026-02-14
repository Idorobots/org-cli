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
        [sys.executable, "-m", "orgstats", "--filter-gamify-exp-above", "20", fixture_path],
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
        [sys.executable, "-m", "orgstats", "--filter-gamify-exp-below", "10", fixture_path],
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
        [sys.executable, "-m", "orgstats", "--filter-repeats-above", "2", fixture_path],
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
        [sys.executable, "-m", "orgstats", "--filter-repeats-below", "3", fixture_path],
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
            "orgstats",
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
            "orgstats",
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
            "orgstats",
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
            "orgstats",
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
            "orgstats",
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
            "orgstats",
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
        [sys.executable, "-m", "orgstats", "--filter-tag", "tag1", fixture_path],
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
            "orgstats",
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
        [sys.executable, "-m", "orgstats", "--filter-completed", fixture_path],
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
        [sys.executable, "-m", "orgstats", "--filter-not-completed", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_preset_simple_still_works() -> None:
    """Test that old --filter simple preset still works."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "simple", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_preset_regular_still_works() -> None:
    """Test that old --filter regular preset still works."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "regular", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_preset_hard_still_works() -> None:
    """Test that old --filter hard preset still works."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "hard", fixture_path],
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
            "orgstats",
            "--filter",
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
            "orgstats",
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
            "orgstats",
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
            "orgstats",
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
            "orgstats",
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
        [sys.executable, "-m", "orgstats", "--help"],
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
