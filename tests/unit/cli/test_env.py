"""Unit tests for environment file loading."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from w2t_bkin.cli.env import load_env_file, load_project_env


class TestLoadEnvFile:
    """Test environment file parsing and loading."""

    def test_basic_key_value(self, tmp_path):
        """Test basic KEY=VALUE parsing."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR=test_value\nANOTHER=123\n")

        result = load_env_file(env_file)

        assert result == {"TEST_VAR": "test_value", "ANOTHER": "123"}
        assert os.environ.get("TEST_VAR") == "test_value"
        assert os.environ.get("ANOTHER") == "123"

    def test_quoted_values(self, tmp_path):
        """Test quoted value handling."""
        env_file = tmp_path / ".env"
        env_file.write_text('QUOTED_DOUBLE="value with spaces"\n' "QUOTED_SINGLE='another value'\n" 'MIXED="value"\n')

        result = load_env_file(env_file)

        assert result["QUOTED_DOUBLE"] == "value with spaces"
        assert result["QUOTED_SINGLE"] == "another value"
        assert result["MIXED"] == "value"

    def test_comments_and_blank_lines(self, tmp_path):
        """Test comment and blank line handling."""
        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\n" "VAR1=value1\n" "\n" "  \n" "# Another comment\n" "VAR2=value2\n")

        result = load_env_file(env_file)

        assert result == {"VAR1": "value1", "VAR2": "value2"}

    def test_override_behavior(self, tmp_path):
        """Test override vs setdefault behavior."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR=new_value\n")

        # Set initial value
        os.environ["TEST_VAR"] = "old_value"

        # Without override (default): should NOT replace
        result = load_env_file(env_file, override=False)
        assert result["TEST_VAR"] == "new_value"  # Loaded
        assert os.environ["TEST_VAR"] == "old_value"  # Not replaced

        # With override: should replace
        result = load_env_file(env_file, override=True)
        assert result["TEST_VAR"] == "new_value"
        assert os.environ["TEST_VAR"] == "new_value"  # Replaced

    def test_missing_file_silent(self, tmp_path):
        """Test silent handling of missing file."""
        missing = tmp_path / "missing.env"

        result = load_env_file(missing, silent=True)

        assert result == {}

    def test_missing_file_warning(self, tmp_path, capsys):
        """Test warning for missing file when not silent."""
        missing = tmp_path / "missing.env"

        result = load_env_file(missing, silent=False)

        assert result == {}
        # Console output would be checked with rich console mock

    def test_malformed_lines_skipped(self, tmp_path):
        """Test malformed lines are skipped with warning."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "GOOD_VAR=value\n"
            "NO_EQUALS_SIGN\n"
            "ANOTHER_GOOD=123\n"
            "INVALID VAR=value\n"  # Space in key
            "VALID_VAR=final\n"
        )

        result = load_env_file(env_file)

        assert "GOOD_VAR" in result
        assert "ANOTHER_GOOD" in result
        assert "VALID_VAR" in result
        assert len(result) == 3

    def test_empty_value(self, tmp_path):
        """Test empty value handling."""
        env_file = tmp_path / ".env"
        env_file.write_text("EMPTY_VAR=\nWHITE_SPACE=   \n")

        result = load_env_file(env_file)

        assert result["EMPTY_VAR"] == ""
        assert result["WHITE_SPACE"] == ""

    def test_equals_in_value(self, tmp_path):
        """Test equals sign in value."""
        env_file = tmp_path / ".env"
        env_file.write_text('CONNECTION_STRING="server=localhost;user=admin"\n')

        result = load_env_file(env_file)

        assert result["CONNECTION_STRING"] == "server=localhost;user=admin"


class TestLoadProjectEnv:
    """Test project environment loading wrapper."""

    def test_default_workers_env(self, tmp_path):
        """Test loading default .workers/.env."""
        workers_dir = tmp_path / ".workers"
        workers_dir.mkdir()
        env_file = workers_dir / ".env"
        env_file.write_text("PROJECT_VAR=project_value\n")

        result = load_project_env(tmp_path)

        assert result["PROJECT_VAR"] == "project_value"
        assert os.environ.get("PROJECT_VAR") == "project_value"

    def test_custom_env_file(self, tmp_path):
        """Test loading custom env file."""
        custom_env = tmp_path / "custom.env"
        custom_env.write_text("CUSTOM_VAR=custom_value\n")

        result = load_project_env(tmp_path, env_file=custom_env)

        assert result["CUSTOM_VAR"] == "custom_value"

    def test_custom_env_file_missing(self, tmp_path):
        """Test warning when custom env file doesn't exist."""
        missing = tmp_path / "missing.env"

        result = load_project_env(tmp_path, env_file=missing)

        assert result == {}

    def test_default_missing_silent(self, tmp_path):
        """Test silent behavior when default .workers/.env doesn't exist."""
        # No .workers/.env exists
        result = load_project_env(tmp_path)

        assert result == {}  # No error, returns empty

    def test_precedence_explicit_env_wins(self, tmp_path):
        """Test that explicit process env beats env file."""
        env_file = tmp_path / ".workers" / ".env"
        env_file.parent.mkdir()
        env_file.write_text("PRECEDENCE_TEST=from_file\n")

        # Set explicit env var
        os.environ["PRECEDENCE_TEST"] = "from_process"

        result = load_project_env(tmp_path)

        # File is loaded but doesn't override
        assert result["PRECEDENCE_TEST"] == "from_file"
        assert os.environ["PRECEDENCE_TEST"] == "from_process"


@pytest.fixture(autouse=True)
def clean_env():
    """Clean environment variables before and after each test."""
    test_vars = [
        "TEST_VAR",
        "ANOTHER",
        "QUOTED_DOUBLE",
        "QUOTED_SINGLE",
        "MIXED",
        "VAR1",
        "VAR2",
        "GOOD_VAR",
        "ANOTHER_GOOD",
        "VALID_VAR",
        "EMPTY_VAR",
        "WHITE_SPACE",
        "CONNECTION_STRING",
        "PROJECT_VAR",
        "CUSTOM_VAR",
        "PRECEDENCE_TEST",
    ]

    # Clean before
    for var in test_vars:
        os.environ.pop(var, None)

    yield

    # Clean after
    for var in test_vars:
        os.environ.pop(var, None)
