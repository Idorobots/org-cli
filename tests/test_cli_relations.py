"""Tests for CLI relations display functionality."""

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_cli_accepts_max_relations_parameter() -> None:
    """Test that --max-relations parameter is accepted."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--max-relations", "5", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_max_relations_default_is_5() -> None:
    """Test that default max_relations is 5."""
    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "default: 5" in result.stdout
    assert "--max-relations" in result.stdout


def test_cli_max_relations_displays_relations() -> None:
    """Test that relations are displayed with proper format."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--max-relations", "3", fixture_path],
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


def test_cli_max_relations_limits_display() -> None:
    """Test that only max_relations items are shown per tag."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--max-relations", "2", fixture_path],
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


def test_cli_max_relations_zero_omits_sections() -> None:
    """Test that --max-relations 0 omits all relation sections."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--max-relations", "0", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Top relations:" not in result.stdout


def test_cli_max_relations_negative_rejected() -> None:
    """Test that negative values are rejected."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--max-relations", "-1", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error" in result.stderr


def test_cli_max_relations_sorted_by_frequency() -> None:
    """Test that relations are sorted by frequency (descending)."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--max-relations",
            "5",
            "-n",
            "5",
            fixture_path,
        ],
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


def test_cli_relations_omitted_when_none() -> None:
    """Test that no relations are shown when item has none."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--max-relations",
            "3",
            "-n",
            "20",
            fixture_path,
        ],
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


def test_cli_max_relations_with_other_options() -> None:
    """Test --max-relations combined with --filter, -n, etc."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--max-relations",
            "2",
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
    assert "(" in result.stdout and ")" in result.stdout


def test_cli_max_relations_value_1() -> None:
    """Test that --max-relations 1 shows only one relation per tag."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--max-relations", "1", fixture_path],
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


def test_cli_relations_with_show_heading() -> None:
    """Test that relations work with --use heading."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--max-relations",
            "2",
            "--use",
            "heading",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "HEADING WORDS" in result.stdout


def test_cli_relations_with_show_body() -> None:
    """Test that relations work with --use body."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--max-relations",
            "2",
            "--use",
            "body",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "BODY WORDS" in result.stdout


def test_cli_relations_filtered_by_exclude() -> None:
    """Test that relations exclude words from the default exclude list."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--max-relations",
            "5",
            "-n",
            "10",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    lines = result.stdout.split("\n")

    for i, line in enumerate(lines):
        if line.startswith("  python:") and "count=" in line:
            j = i + 1
            while j < len(lines) and lines[j].startswith("    "):
                rel_line = lines[j].strip()
                assert "comp" not in rel_line.lower()
                assert "home" not in rel_line.lower()
                j += 1
            break


def test_cli_relations_filtered_with_custom_exclude_file() -> None:
    """Test that relations are filtered when using custom exclude file."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_filter_test.org")
    exclude_file = os.path.join(FIXTURES_DIR, "custom_exclude_tags.txt")

    with open(exclude_file, "w", encoding="utf-8") as f:
        f.write("comp\n")
        f.write("home\n")
        f.write("testing\n")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "org",
                "--max-relations",
                "5",
                "-n",
                "10",
                "--exclude",
                exclude_file,
                fixture_path,
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        lines = result.stdout.split("\n")

        for i, line in enumerate(lines):
            if line.startswith("  python:") and "count=" in line:
                j = i + 1
                relations_found = []
                while j < len(lines) and lines[j].startswith("    "):
                    rel_line = lines[j].strip()
                    if "(" in rel_line and ")" in rel_line:
                        tag_name = rel_line.split("(")[0].strip()
                        relations_found.append(tag_name)
                    j += 1

                for rel_tag in relations_found:
                    assert rel_tag not in ["comp", "home", "testing"]
                    assert rel_tag in ["debugging"]
                break

    finally:
        if Path(exclude_file).exists():
            Path(exclude_file).unlink()


def test_cli_relations_max_applied_after_filtering() -> None:
    """Test that max_relations limit is applied after filtering excluded words."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_filter_test.org")
    exclude_file = os.path.join(FIXTURES_DIR, "custom_exclude_for_limit.txt")

    with open(exclude_file, "w", encoding="utf-8") as f:
        f.write("comp\n")
        f.write("home\n")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "org",
                "--max-relations",
                "2",
                "-n",
                "10",
                "--exclude",
                exclude_file,
                fixture_path,
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        lines = result.stdout.split("\n")

        for i, line in enumerate(lines):
            if line.startswith("  python:") and "count=" in line:
                j = i + 1
                relations_count = 0
                while j < len(lines) and lines[j].startswith("    "):
                    relations_count += 1
                    j += 1

                assert relations_count <= 2
                break

    finally:
        if Path(exclude_file).exists():
            Path(exclude_file).unlink()


def test_cli_max_relations_shows_no_results() -> None:
    """Test that relations is omitted when max_relations > 0 but all relations filtered."""
    from io import StringIO

    from org.analyze import Tag, TimeRange
    from org.cli import display_category

    tags = {
        "python": Tag(
            name="python",
            total_tasks=10,
            time_range=TimeRange(),
            relations={"django": 5, "flask": 3},
            avg_tasks_per_day=0,
            max_single_day_count=0,
        ),
    }
    exclude_set = {"django", "flask"}

    original_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        display_category(
            "test tags",
            tags,
            (10, 3, 50, None, None, TimeRange(), 5, exclude_set, False),
            lambda item: -item[1].total_tasks,
        )

        output = sys.stdout.getvalue()

        assert "TEST TAGS" in output
        assert "Top relations:" not in output

    finally:
        sys.stdout = original_stdout


def test_cli_max_relations_zero_skips_relations() -> None:
    """Test that max_relations=0 completely skips relation display."""
    from io import StringIO

    from org.analyze import Tag, TimeRange
    from org.cli import display_category

    tags = {
        "python": Tag(
            name="python",
            total_tasks=10,
            time_range=TimeRange(),
            relations={"django": 5},
            avg_tasks_per_day=0,
            max_single_day_count=0,
        ),
    }

    original_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        display_category(
            "test tags",
            tags,
            (10, 0, 50, None, None, TimeRange(), 5, set(), False),
            lambda item: -item[1].total_tasks,
        )

        output = sys.stdout.getvalue()

        assert "Top relations:" not in output
        assert "django" not in output

    finally:
        sys.stdout = original_stdout
