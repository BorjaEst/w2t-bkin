"""
Unit tests for CLI modules.

Tests the modular CLI structure including pipeline, validation, and data commands.
"""

import sys

import pytest
from typer.testing import CliRunner

from w2t_bkin.cli import app

runner = CliRunner()


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_cli_help(self):
        """Test that CLI help works."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "w2t-bkin" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_version_command(self):
        """Test version command."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        # Should output version information
        assert len(result.stdout) > 0


class TestPipelineCommands:
    """Test pipeline command group."""

    def test_run_help(self):
        """Test run command help."""
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "config" in result.stdout.lower()

    def test_batch_help(self):
        """Test batch command help."""
        result = runner.invoke(app, ["batch", "--help"])
        assert result.exit_code == 0
        assert "config" in result.stdout.lower()

    def test_discover_help(self):
        """Test discover command help."""
        result = runner.invoke(app, ["discover", "--help"])
        assert result.exit_code == 0
        assert "config" in result.stdout.lower()


class TestValidationCommands:
    """Test validation command group."""

    def test_validate_help(self):
        """Test validate command help."""
        result = runner.invoke(app, ["validate", "--help"])
        assert result.exit_code == 0
        assert "nwb" in result.stdout.lower()

    def test_inspect_help(self):
        """Test inspect command help."""
        result = runner.invoke(app, ["inspect", "--help"])
        assert result.exit_code == 0
        assert "nwb" in result.stdout.lower()


class TestDataCommands:
    """Test data management command group."""

    def test_data_help(self):
        """Test data group help."""
        result = runner.invoke(app, ["data", "--help"])
        assert result.exit_code == 0
        assert "init" in result.stdout.lower()

    def test_data_init_help(self):
        """Test data init command help."""
        result = runner.invoke(app, ["data", "init", "--help"])
        assert result.exit_code == 0
        assert "root" in result.stdout.lower()

    def test_data_add_subject_help(self):
        """Test data add-subject command help."""
        result = runner.invoke(app, ["data", "add-subject", "--help"])
        assert result.exit_code == 0
        assert "subject" in result.stdout.lower()

    def test_data_add_session_help(self):
        """Test data add-session command help."""
        result = runner.invoke(app, ["data", "add-session", "--help"])
        assert result.exit_code == 0
        assert "session" in result.stdout.lower()

    def test_data_import_raw_help(self):
        """Test data import-raw command help."""
        result = runner.invoke(app, ["data", "import-raw", "--help"])
        assert result.exit_code == 0
        assert "source" in result.stdout.lower()

    def test_data_validate_help(self):
        """Test data validate command help."""
        result = runner.invoke(app, ["data", "validate", "--help"])
        assert result.exit_code == 0
        assert "experiment" in result.stdout.lower()


class TestCLIUtils:
    """Test CLI utilities module."""

    def test_console_import(self):
        """Test that console can be imported."""
        from w2t_bkin.cli.utils import console

        assert console is not None

    def test_display_functions_import(self):
        """Test that display functions can be imported."""
        from w2t_bkin.cli.utils import display_batch_result, display_session_result, format_discoveries

        assert display_session_result is not None
        assert display_batch_result is not None


class TestImportIsolation:
    """Test that base CLI doesn't import worker dependencies."""

    def test_cli_import_no_worker_deps(self):
        """Test that importing CLI doesn't load worker extras."""
        # Clear any prior imports
        worker_deps = ["torch", "tensorflow", "deeplabcut", "facemap"]
        for dep in worker_deps:
            if dep in sys.modules:
                del sys.modules[dep]

        # Import CLI
        import w2t_bkin.cli
        import w2t_bkin.cli.worker

        # Verify worker deps are NOT imported
        for dep in worker_deps:
            assert dep not in sys.modules, f"{dep} should not be imported by base CLI"

    def test_worker_help_no_heavy_imports(self):
        """Test that worker --help doesn't trigger heavy imports."""
        result = runner.invoke(app, ["worker", "--help"])
        assert result.exit_code == 0
        assert "worker" in result.stdout.lower()

        # Verify heavy deps not imported
        worker_deps = ["torch", "tensorflow", "deeplabcut", "facemap"]
        for dep in worker_deps:
            assert dep not in sys.modules, f"{dep} should not be imported for worker --help"

    def test_worker_start_help_no_heavy_imports(self):
        """Test that worker start --help doesn't trigger heavy imports."""
        result = runner.invoke(app, ["worker", "start", "--help"])
        assert result.exit_code == 0
        assert "pool" in result.stdout.lower()

        # Verify heavy deps not imported
        worker_deps = ["torch", "tensorflow", "deeplabcut", "facemap"]
        for dep in worker_deps:
            assert dep not in sys.modules, f"{dep} should not be imported for worker start --help"
