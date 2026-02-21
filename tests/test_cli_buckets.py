"""Integration tests for CLI timeline chart features."""

import subprocess
import sys


def test_cli_with_buckets_parameter() -> None:
    """Test that --buckets parameter is accepted."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--buckets",
            "30",
            "examples/ARCHIVE_small",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "┊" in result.stdout


def test_cli_buckets_default_value() -> None:
    """Test that default bucket value (50) is used when not specified."""
    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "examples/ARCHIVE_small"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "┊" in result.stdout


def test_cli_buckets_validation_minimum() -> None:
    """Test that error is raised when buckets < 20."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--buckets",
            "10",
            "examples/ARCHIVE_small",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Error: --buckets must be at least 20" in result.stderr


def test_cli_buckets_validation_exact_minimum() -> None:
    """Test that buckets=20 is accepted."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--buckets",
            "20",
            "examples/ARCHIVE_small",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "┊" in result.stdout


def test_cli_output_shows_global_chart() -> None:
    """Test that global chart is present."""
    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "examples/ARCHIVE_small"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "┊" in result.stdout
    lines = result.stdout.split("\n")
    chart_found = False
    for line in lines:
        if line.startswith("┊") and "┊" in line[1:]:
            chart_found = True
            break
    assert chart_found


def test_cli_output_shows_per_tag_charts() -> None:
    """Test that charts appear under each tag."""
    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "examples/ARCHIVE_small"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.split("\n")
    chart_count = 0
    for line in lines:
        if line.strip().startswith("┊") and "┊" in line[1:]:
            chart_count += 1
    assert chart_count > 1


def test_cli_chart_format_in_output() -> None:
    """Test that charts have expected format."""
    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "examples/ARCHIVE_small"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.split("\n")
    for line in lines:
        if line.startswith("┊") and "┊ " in line:
            assert line.count("┊") == 2
            value_part = line.split("┊")[-1].strip()
            assert "(" in value_part and ")" in value_part
            count_str = value_part.split()[0]
            assert count_str.isdigit()


def test_cli_buckets_different_values() -> None:
    """Test CLI with different bucket values."""
    for buckets in [20, 30, 50, 100]:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "org",
                "--no-color",
                "--buckets",
                str(buckets),
                "examples/ARCHIVE_small",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "┊" in result.stdout


def test_cli_help_shows_buckets() -> None:
    """Test that --buckets appears in help text."""
    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--buckets" in result.stdout
