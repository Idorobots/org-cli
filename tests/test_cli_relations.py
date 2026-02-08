"""Tests for CLI relations display functionality."""

import os
import subprocess
import sys


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_cli_accepts_max_relations_parameter():
    """Test that --max-relations parameter is accepted."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-relations", "5", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_max_relations_default_is_3():
    """Test that default max_relations is 3."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "default: 3" in result.stdout
    assert "--max-relations" in result.stdout


def test_cli_max_relations_displays_relations():
    """Test that relations are displayed with proper format."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-relations", "3", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # Check for indented relation lines with format "    tag (count)"
    lines = result.stdout.split("\n")
    indented_lines = [line for line in lines if line.startswith("    ") and "(" in line]
    assert len(indented_lines) > 0

    # Check format of indented lines
    for line in indented_lines:
        assert line.startswith("    ")
        assert "(" in line and ")" in line


def test_cli_max_relations_limits_display():
    """Test that only max_relations items are shown per tag."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-relations", "2", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Parse output and count relations per tag
    lines = result.stdout.split("\n")
    relations_count = 0
    max_relations_for_any_tag = 0

    for i, line in enumerate(lines):
        # Check if this is a main tag line (starts with 2 spaces, has count=)
        if line.startswith("  ") and "count=" in line and not line.startswith("    "):
            # Count relations for this tag (following indented lines)
            current_tag_relations = 0
            j = i + 1
            while j < len(lines) and lines[j].startswith("    "):
                current_tag_relations += 1
                j += 1

            if current_tag_relations > 0:
                relations_count += current_tag_relations
                max_relations_for_any_tag = max(max_relations_for_any_tag, current_tag_relations)

    # With --max-relations 2, no tag should have more than 2 relations displayed
    assert max_relations_for_any_tag <= 2


def test_cli_max_relations_zero_rejected():
    """Test that --max-relations 0 is rejected."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-relations", "0", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error" in result.stderr
    assert "max-relations" in result.stderr


def test_cli_max_relations_negative_rejected():
    """Test that negative values are rejected."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-relations", "-1", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error" in result.stderr


def test_cli_max_relations_sorted_by_frequency():
    """Test that relations are sorted by frequency (descending)."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-relations", "5", "-n", "5", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Parse output and check that for each tag, relations are in descending order
    lines = result.stdout.split("\n")

    for i, line in enumerate(lines):
        # Find main tag lines
        if line.startswith("  ") and "count=" in line and not line.startswith("    "):
            # Extract relations for this tag
            relations = []
            j = i + 1
            while j < len(lines) and lines[j].startswith("    "):
                # Extract count from format "    tag (count)"
                rel_line = lines[j].strip()
                if "(" in rel_line and ")" in rel_line:
                    count_str = rel_line.split("(")[1].split(")")[0]
                    relations.append(int(count_str))
                j += 1

            # Check that relations are in descending order
            if len(relations) > 1:
                for k in range(len(relations) - 1):
                    assert relations[k] >= relations[k + 1]


def test_cli_relations_omitted_when_none():
    """Test that no relations are shown when item has none."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-relations", "3", "-n", "20", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # The "isolated" tag should appear but have no relations shown after it
    lines = result.stdout.split("\n")
    for i, line in enumerate(lines):
        if "isolated:" in line and "count=" in line:
            # Check that the next line is either not indented or is a new main item
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                # Next line should NOT be a relation (4 spaces + tag + count)
                if next_line.strip():
                    assert not next_line.startswith("    ")
            break


def test_cli_max_relations_with_other_options():
    """Test --max-relations combined with --tasks, -n, etc."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--max-relations",
            "2",
            "--tasks",
            "total",
            "-n",
            "5",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "count=" in result.stdout


def test_cli_max_relations_value_1():
    """Test that --max-relations 1 shows only one relation per tag."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-relations", "1", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Count relations per tag, should be at most 1
    lines = result.stdout.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("  ") and "count=" in line and not line.startswith("    "):
            # Count relations for this tag
            relations_count = 0
            j = i + 1
            while j < len(lines) and lines[j].startswith("    "):
                relations_count += 1
                j += 1

            if relations_count > 0:
                assert relations_count <= 1


def test_cli_relations_with_show_heading():
    """Test that relations work with --show heading."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--max-relations",
            "2",
            "--show",
            "heading",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Top heading words:" in result.stdout


def test_cli_relations_with_show_body():
    """Test that relations work with --show body."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-relations", "2", "--show", "body", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Top body words:" in result.stdout
