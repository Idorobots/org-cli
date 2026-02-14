"""Tests for argparse functionality in CLI."""

import os
import subprocess
import sys


# Path to project root
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_argparse_help() -> None:
    """Test --help output."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "orgstats" in result.stdout


def test_parse_date_argument_basic_date() -> None:
    """Test parse_date_argument with basic YYYY-MM-DD format."""
    from datetime import datetime

    from orgstats.cli import parse_date_argument

    result = parse_date_argument("2025-01-15", "--test-arg")
    assert result == datetime(2025, 1, 15, 0, 0, 0)


def test_parse_date_argument_iso_with_time() -> None:
    """Test parse_date_argument with YYYY-MM-DDThh:mm format."""
    from datetime import datetime

    from orgstats.cli import parse_date_argument

    result = parse_date_argument("2025-01-15T14:30", "--test-arg")
    assert result == datetime(2025, 1, 15, 14, 30, 0)


def test_parse_date_argument_iso_with_seconds() -> None:
    """Test parse_date_argument with YYYY-MM-DDThh:mm:ss format."""
    from datetime import datetime

    from orgstats.cli import parse_date_argument

    result = parse_date_argument("2025-01-15T14:30:45", "--test-arg")
    assert result == datetime(2025, 1, 15, 14, 30, 45)


def test_parse_date_argument_space_with_time() -> None:
    """Test parse_date_argument with YYYY-MM-DD hh:mm format."""
    from datetime import datetime

    from orgstats.cli import parse_date_argument

    result = parse_date_argument("2025-01-15 14:30", "--test-arg")
    assert result == datetime(2025, 1, 15, 14, 30, 0)


def test_parse_date_argument_space_with_seconds() -> None:
    """Test parse_date_argument with YYYY-MM-DD hh:mm:ss format."""
    from datetime import datetime

    from orgstats.cli import parse_date_argument

    result = parse_date_argument("2025-01-15 14:30:45", "--test-arg")
    assert result == datetime(2025, 1, 15, 14, 30, 45)


def test_parse_date_argument_midnight() -> None:
    """Test parse_date_argument with midnight time."""
    from datetime import datetime

    from orgstats.cli import parse_date_argument

    result = parse_date_argument("2025-01-15T00:00:00", "--test-arg")
    assert result == datetime(2025, 1, 15, 0, 0, 0)


def test_parse_date_argument_end_of_day() -> None:
    """Test parse_date_argument with end of day time."""
    from datetime import datetime

    from orgstats.cli import parse_date_argument

    result = parse_date_argument("2025-01-15T23:59:59", "--test-arg")
    assert result == datetime(2025, 1, 15, 23, 59, 59)


def test_parse_date_argument_invalid_format() -> None:
    """Test parse_date_argument with invalid format exits with error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--filter-date-from",
            "2025/01/15",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "must be in one of these formats" in result.stderr
    assert "YYYY-MM-DD" in result.stderr


def test_parse_date_argument_invalid_date_values() -> None:
    """Test parse_date_argument with invalid date values."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--filter-date-from",
            "2025-13-45",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "must be in one of these formats" in result.stderr


def test_parse_date_argument_invalid_time_values() -> None:
    """Test parse_date_argument with invalid time values."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--filter-date-from",
            "2025-01-15T25:70:99",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "must be in one of these formats" in result.stderr


def test_parse_date_argument_partial_time() -> None:
    """Test parse_date_argument with partial time (only hour) is accepted."""
    from datetime import datetime

    from orgstats.cli import parse_date_argument

    result = parse_date_argument("2025-01-15T14", "--test-arg")
    assert result == datetime(2025, 1, 15, 14, 0, 0)


def test_parse_date_argument_empty_string() -> None:
    """Test parse_date_argument with empty string."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter-date-from", "", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "must be in one of these formats" in result.stderr


def test_argparse_max_results_short() -> None:
    """Test -n short flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "-n", "10", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_exclude() -> None:
    """Test --exclude with custom file."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    exclude_list_path = os.path.join(FIXTURES_DIR, "exclude_list_tags.txt")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--exclude", exclude_list_path, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "Total tasks:" in result.stdout


def test_argparse_all_options() -> None:
    """Test using all options together."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    exclude_path = os.path.join(FIXTURES_DIR, "exclude_list_tags.txt")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--max-results",
            "20",
            "--exclude",
            exclude_path,
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_invalid_max_results() -> None:
    """Test invalid max-results value."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-results", "not-a-number", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    # argparse will exit with error
    assert result.returncode != 0
    assert "invalid int value" in result.stderr or "error" in result.stderr.lower()


def test_argparse_missing_exclude_list_file() -> None:
    """Test non-existent exclude_list file."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    nonexistent_file = os.path.join(FIXTURES_DIR, "does_not_exist.txt")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--exclude", nonexistent_file, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "not found" in result.stderr


def test_argparse_empty_exclude_list_file() -> None:
    """Test empty exclude_list file."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    empty_file = os.path.join(FIXTURES_DIR, "exclude_list_empty.txt")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--exclude", empty_file, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    # Empty exclude file means no filtering (returns empty set, so defaults are used)
    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_backward_compatibility() -> None:
    """Test that old-style invocation still works."""
    fixture1 = os.path.join(FIXTURES_DIR, "simple.org")
    fixture2 = os.path.join(FIXTURES_DIR, "single_task.org")

    # Old style: just filenames as positional arguments
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture1, fixture2],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert result.stdout.count("Processing") == 2
    assert "Total tasks:" in result.stdout


def test_argparse_no_files_provided() -> None:
    """Test behavior when no files are provided."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    # It should complain than at least one FILE is required.
    assert result.returncode == 2
    assert "the following arguments are required:" in result.stderr


def test_argparse_options_before_files() -> None:
    """Test that options can come before filenames."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "-n", "50", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_options_after_files() -> None:
    """Test that options can come after filenames."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path, "-n", "50"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_load_exclude_list_function() -> None:
    """Test load_exclude_list helper function directly."""
    from orgstats.cli import load_exclude_list

    # Test with None
    result = load_exclude_list(None)
    assert result == set()

    # Test with actual file
    exclude_list_path = os.path.join(FIXTURES_DIR, "exclude_list_tags.txt")
    result = load_exclude_list(exclude_list_path)
    assert "python" in result
    assert "testing" in result
    assert "debugging" in result

    # Test with empty file
    empty_path = os.path.join(FIXTURES_DIR, "exclude_list_empty.txt")
    result = load_exclude_list(empty_path)
    assert result == set()


def test_argparse_filter_default() -> None:
    """Test default --filter behavior (should be all)."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    # Should show integer tuples, not Frequency objects
    assert "Frequency(" not in result.stdout


def test_argparse_filter_simple() -> None:
    """Test --filter simple flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "simple", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "Frequency(" not in result.stdout


def test_argparse_filter_regular() -> None:
    """Test --filter regular flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "regular", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_filter_hard() -> None:
    """Test --filter hard flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "hard", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_filter_all() -> None:
    """Test explicit --filter all flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "all", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_filter_invalid() -> None:
    """Test invalid --filter value."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "invalid", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def test_argparse_filter_with_max_results() -> None:
    """Test combining --filter with -n flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "hard", "-n", "3", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_filter_in_help() -> None:
    """Test that --filter appears in help output."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--filter" in result.stdout
    assert "simple" in result.stdout
    assert "regular" in result.stdout
    assert "hard" in result.stdout
    assert "all" in result.stdout


def test_argparse_todo_keys_single() -> None:
    """Test --todo-keys with single value."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--todo-keys", "TODO", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_todo_keys_multiple() -> None:
    """Test --todo-keys with comma-separated values."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--todo-keys",
            "TODO,WAITING,IN-PROGRESS",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "TODO     ┊" in result.stdout or "WAITING  ┊" in result.stdout


def test_argparse_done_keys_single() -> None:
    """Test --done-keys with single value."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--done-keys", "DONE", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_done_keys_multiple() -> None:
    """Test --done-keys with comma-separated values."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--done-keys",
            "DONE,CANCELLED,ARCHIVED",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_todo_done_keys_together() -> None:
    """Test both --todo-keys and --done-keys together."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--todo-keys",
            "TODO,WAITING",
            "--done-keys",
            "DONE,CANCELLED",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_todo_keys_empty() -> None:
    """Test --todo-keys with empty string fails."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--todo-keys", "", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "cannot be empty" in result.stderr


def test_argparse_todo_keys_whitespace_only() -> None:
    """Test --todo-keys with whitespace-only string fails."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--todo-keys", "   ", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "cannot be empty" in result.stderr


def test_argparse_todo_keys_with_commas_only() -> None:
    """Test --todo-keys with commas only fails."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--todo-keys", ",,,", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "cannot be empty" in result.stderr


def test_argparse_done_keys_empty() -> None:
    """Test --done-keys with empty string fails."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--done-keys", "", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "cannot be empty" in result.stderr


def test_argparse_done_keys_whitespace_only() -> None:
    """Test --done-keys with whitespace-only string fails."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--done-keys", "   ", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "cannot be empty" in result.stderr


def test_argparse_todo_keys_with_pipe() -> None:
    """Test --todo-keys with pipe character fails."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--todo-keys", "TODO|WAITING", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "pipe character" in result.stderr


def test_argparse_done_keys_with_pipe() -> None:
    """Test --done-keys with pipe character fails."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--done-keys", "DONE|CANCELLED", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "pipe character" in result.stderr


def test_argparse_todo_done_keys_in_help() -> None:
    """Test that --todo-keys and --done-keys appear in help output."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--todo-keys" in result.stdout
    assert "--done-keys" in result.stdout
    assert "incomplete task states" in result.stdout
    assert "completed task states" in result.stdout


def test_argparse_todo_keys_with_spaces() -> None:
    """Test --todo-keys with spaces in values (should be stripped)."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--todo-keys",
            "TODO , WAITING , IN-PROGRESS",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
