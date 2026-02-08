"""Direct tests for CLI functions (for coverage)."""

import os
import sys
from io import StringIO


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_main_function_directly():
    """Test the main() function directly for coverage."""
    from orgstats.cli import main

    # Save original argv and stdout
    original_argv = sys.argv
    original_stdout = sys.stdout

    try:
        # Redirect stdout to capture output
        sys.stdout = StringIO()

        # Set argv to test with a fixture file
        fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
        sys.argv = ["cli.py", fixture_path]

        # Call main()
        main()

        # Get output
        output = sys.stdout.getvalue()

        # Verify output
        assert "Processing" in output
        assert "Total tasks:" in output
        assert "Done tasks:" in output

    finally:
        # Restore original argv and stdout
        sys.argv = original_argv
        sys.stdout = original_stdout


def test_main_with_multiple_files_direct():
    """Test main() with multiple files."""
    from orgstats.cli import main

    original_argv = sys.argv
    original_stdout = sys.stdout

    try:
        sys.stdout = StringIO()

        fixture1 = os.path.join(FIXTURES_DIR, "simple.org")
        fixture2 = os.path.join(FIXTURES_DIR, "single_task.org")
        sys.argv = ["cli.py", fixture1, fixture2]

        main()

        output = sys.stdout.getvalue()

        assert "Processing" in output
        assert output.count("Processing") == 2

    finally:
        sys.argv = original_argv
        sys.stdout = original_stdout


def test_main_with_filter_parameter():
    """Test main function with --filter parameter."""
    from orgstats.cli import main

    original_argv = sys.argv
    original_stdout = sys.stdout

    try:
        sys.stdout = StringIO()

        fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")
        sys.argv = ["cli.py", "--filter", "hard", fixture_path]

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
