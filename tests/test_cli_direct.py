"""Direct tests for CLI functions (for coverage)."""

import os
import sys
from io import StringIO


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_main_function_directly() -> None:
    """Test the main() function directly for coverage."""
    from org.cli import main

    # Save original argv and stdout
    original_argv = sys.argv
    original_stdout = sys.stdout

    try:
        # Redirect stdout to capture output
        sys.stdout = StringIO()

        # Set argv to test with a fixture file
        fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
        sys.argv = ["cli.py", "stats", "summary", fixture_path]

        # Call main()
        main()

        # Get output
        output = sys.stdout.getvalue()

        # Verify output
        assert "Processing" in output
        assert "Total tasks:" in output
        assert "Task states:" in output

    finally:
        # Restore original argv and stdout
        sys.argv = original_argv
        sys.stdout = original_stdout


def test_main_with_multiple_files_direct() -> None:
    """Test main() with multiple files."""
    from org.cli import main

    original_argv = sys.argv
    original_stdout = sys.stdout

    try:
        sys.stdout = StringIO()

        fixture1 = os.path.join(FIXTURES_DIR, "simple.org")
        fixture2 = os.path.join(FIXTURES_DIR, "single_task.org")
        sys.argv = ["cli.py", "stats", "summary", fixture1, fixture2]

        main()

        output = sys.stdout.getvalue()

        assert "Processing" in output
        assert output.count("Processing") == 2

    finally:
        sys.argv = original_argv
        sys.stdout = original_stdout


def test_main_with_filter_parameter() -> None:
    """Test main function with --filter parameter."""
    from org.cli import main

    original_argv = sys.argv
    original_stdout = sys.stdout

    try:
        sys.stdout = StringIO()

        fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")
        sys.argv = [
            "cli.py",
            "stats",
            "summary",
            "--config",
            "missing.json",
            "--with-gamify-category",
            "--filter-category",
            "hard",
            fixture_path,
        ]

        main()

        output = sys.stdout.getvalue()

        # Verify output
        assert "Processing" in output
        assert "Total tasks:" in output
        # Should show integer tuples, not Frequency objects
        assert "Frequency(" not in output

    finally:
        sys.argv = original_argv
        sys.stdout = original_stdout


def test_main_with_custom_todo_keys() -> None:
    """Test main function with --todo-keys parameter."""
    from org.cli import main

    original_argv = sys.argv
    original_stdout = sys.stdout

    try:
        sys.stdout = StringIO()

        fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
        sys.argv = [
            "cli.py",
            "stats",
            "summary",
            "--todo-keys",
            "TODO,WAITING,IN-PROGRESS",
            fixture_path,
        ]

        main()

        output = sys.stdout.getvalue()

        assert "Processing" in output
        assert "Total tasks:" in output
        assert "Task states:" in output

    finally:
        sys.argv = original_argv
        sys.stdout = original_stdout


def test_main_with_custom_done_keys() -> None:
    """Test main function with --done-keys parameter."""
    from org.cli import main

    original_argv = sys.argv
    original_stdout = sys.stdout

    try:
        sys.stdout = StringIO()

        fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
        sys.argv = [
            "cli.py",
            "stats",
            "summary",
            "--done-keys",
            "DONE,CANCELLED,ARCHIVED",
            fixture_path,
        ]

        main()

        output = sys.stdout.getvalue()

        assert "Processing" in output
        assert "Total tasks:" in output
        assert "Task states:" in output

    finally:
        sys.argv = original_argv
        sys.stdout = original_stdout


def test_main_with_both_todo_and_done_keys() -> None:
    """Test main function with both --todo-keys and --done-keys."""
    from org.cli import main

    original_argv = sys.argv
    original_stdout = sys.stdout

    try:
        sys.stdout = StringIO()

        fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
        sys.argv = [
            "cli.py",
            "stats",
            "summary",
            "--todo-keys",
            "TODO,WAITING",
            "--done-keys",
            "DONE,CANCELLED",
            fixture_path,
        ]

        main()

        output = sys.stdout.getvalue()

        assert "Processing" in output
        assert "Total tasks:" in output
        assert "Task states:" in output

    finally:
        sys.argv = original_argv
        sys.stdout = original_stdout


def test_main_displays_none_state() -> None:
    """Test that tasks without state show as 'none' in output."""
    from org.cli import main

    original_argv = sys.argv
    original_stdout = sys.stdout

    try:
        sys.stdout = StringIO()

        fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
        sys.argv = ["cli.py", "stats", "summary", fixture_path]

        main()

        output = sys.stdout.getvalue()

        assert "Processing" in output
        assert "none     ┊" in output

    finally:
        sys.argv = original_argv
        sys.stdout = original_stdout
