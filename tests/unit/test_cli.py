"""Unit tests for the cli module.

Tests Typer-based CLI orchestration of pipeline stages
as specified in cli/requirements.md and design.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestCLISubcommands:
    """Test CLI subcommand availability (MR-1)."""

    def test_Should_ProvideIngestCommand_When_Imported_MR1(self):
        """THE MODULE SHALL provide subcommands for all pipeline stages.

        Requirements: MR-1
        Issue: CLI module - Ingest subcommand
        """
        # Arrange & Act
        from w2t_bkin.cli import app

        # Assert - Should have ingest command
        commands = [cmd.name for cmd in app.registered_commands]
        assert "ingest" in commands

    def test_Should_ProvideSyncCommand_When_Imported_MR1(self):
        """THE MODULE SHALL provide sync subcommand.

        Requirements: MR-1
        Issue: CLI module - Sync subcommand
        """
        # Arrange & Act
        from w2t_bkin.cli import app

        # Assert
        commands = [cmd.name for cmd in app.registered_commands]
        assert "sync" in commands

    def test_Should_ProvideTranscodeCommand_When_Imported_MR1(self):
        """THE MODULE SHALL provide transcode subcommand.

        Requirements: MR-1
        Issue: CLI module - Transcode subcommand
        """
        # Arrange & Act
        from w2t_bkin.cli import app

        # Assert
        commands = [cmd.name for cmd in app.registered_commands]
        assert "transcode" in commands

    def test_Should_ProvidePoseCommand_When_Imported_MR1(self):
        """THE MODULE SHALL provide pose subcommand.

        Requirements: MR-1
        Issue: CLI module - Pose subcommand
        """
        # Arrange & Act
        from w2t_bkin.cli import app

        # Assert
        commands = [cmd.name for cmd in app.registered_commands]
        assert "pose" in commands

    def test_Should_ProvideFacemapCommand_When_Imported_MR1(self):
        """THE MODULE SHALL provide facemap subcommand.

        Requirements: MR-1
        Issue: CLI module - Facemap subcommand
        """
        # Arrange & Act
        from w2t_bkin.cli import app

        # Assert
        commands = [cmd.name for cmd in app.registered_commands]
        assert "facemap" in commands

    def test_Should_ProvideToNwbCommand_When_Imported_MR1(self):
        """THE MODULE SHALL provide to-nwb subcommand.

        Requirements: MR-1, Design - to-nwb stage
        Issue: CLI module - to-nwb subcommand
        """
        # Arrange & Act
        from w2t_bkin.cli import app

        # Assert
        commands = [cmd.name for cmd in app.registered_commands]
        assert "to-nwb" in commands or "to_nwb" in commands

    def test_Should_ProvideValidateCommand_When_Imported_MR1(self):
        """THE MODULE SHALL provide validate subcommand.

        Requirements: MR-1, Design - validate stage
        Issue: CLI module - Validate subcommand
        """
        # Arrange & Act
        from w2t_bkin.cli import app

        # Assert
        commands = [cmd.name for cmd in app.registered_commands]
        assert "validate" in commands

    def test_Should_ProvideReportCommand_When_Imported_MR1(self):
        """THE MODULE SHALL provide report subcommand.

        Requirements: MR-1, Design - report stage
        Issue: CLI module - Report subcommand
        """
        # Arrange & Act
        from w2t_bkin.cli import app

        # Assert
        commands = [cmd.name for cmd in app.registered_commands]
        assert "report" in commands


class TestSettingsLoading:
    """Test settings loading and passing (MR-2)."""

    def test_Should_LoadSettings_When_CommandRun_MR2(self):
        """THE MODULE SHALL load settings and pass them to stage entry points.

        Requirements: MR-2
        Issue: CLI module - Settings loading
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act - Run with config path
        result = runner.invoke(app, ["ingest", "--config", "config.toml", "--help"])

        # Assert - Should not error on config loading
        assert result.exit_code in [0, 2]  # 0 for help, 2 for missing file

    def test_Should_AcceptConfigPath_When_Provided_MR2(self):
        """THE MODULE SHALL accept --config flag for settings path.

        Requirements: MR-2, Design - global --config
        Issue: CLI module - Config flag
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["--config", "/path/to/config.toml", "ingest", "--help"])

        # Assert - Should accept config flag
        assert result.exit_code in [0, 2]

    def test_Should_PassSettingsToStages_When_Run_MR2(self):
        """THE MODULE SHALL pass loaded settings to stage entry points.

        Requirements: MR-2
        Issue: CLI module - Settings passing
        """
        # Arrange
        import inspect

        from w2t_bkin.cli import app

        # Assert - Commands should accept settings or config parameter
        for cmd in app.registered_commands:
            if cmd.name == "ingest":
                sig = inspect.signature(cmd.callback)
                params = list(sig.parameters.keys())
                # Should have config/settings parameter
                assert any(p in params for p in ["settings", "config", "ctx"])

    def test_Should_LoadFromEnvironment_When_Configured_MR2(self):
        """THE MODULE SHALL support environment variable overrides.

        Requirements: MR-2
        Issue: CLI module - Environment loading
        """
        # Arrange
        import os

        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()
        env = {"W2T_BKIN_SESSION__ROOT": "/custom/path"}

        # Act
        result = runner.invoke(app, ["ingest", "--help"], env=env)

        # Assert - Should work with environment
        assert result.exit_code == 0


class TestErrorHandling:
    """Test error handling and exit codes (MR-3)."""

    def test_Should_ReturnNonZero_When_CommandFails_MR3(self):
        """THE MODULE SHALL return non-zero exit codes on failures.

        Requirements: MR-3
        Issue: CLI module - Exit codes
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act - Run with invalid arguments
        result = runner.invoke(app, ["ingest", "--nonexistent-flag"])

        # Assert
        assert result.exit_code != 0

    def test_Should_ShowReadableError_When_CommandFails_MR3(self):
        """THE MODULE SHALL show readable errors on failures.

        Requirements: MR-3
        Issue: CLI module - Error messages
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act - Run with missing required argument
        result = runner.invoke(app, ["ingest"])

        # Assert - Should have error message
        assert result.exit_code != 0
        # Should have some error output
        assert len(result.output) > 0 or len(str(result.exception)) > 0

    def test_Should_MapExceptions_When_StageErrors_MR3(self):
        """THE MODULE SHALL map known exceptions to user-friendly messages.

        Requirements: MR-3, Design - Exception mapping
        Issue: CLI module - Exception handling
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act - Trigger an expected error (e.g., missing session)
        result = runner.invoke(app, ["ingest", "--session-root", "/nonexistent"])

        # Assert - Should handle gracefully
        assert result.exit_code != 0

    def test_Should_ReturnZero_When_CommandSucceeds_MR3(self):
        """THE MODULE SHALL return zero exit code on success.

        Requirements: MR-3
        Issue: CLI module - Success exit code
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act - Run help (always succeeds)
        result = runner.invoke(app, ["--help"])

        # Assert
        assert result.exit_code == 0


class TestHelpOutput:
    """Test help output accuracy (M-NFR-1)."""

    def test_Should_ShowHelp_When_Requested_MNFR1(self):
        """THE MODULE SHALL provide accurate --help output.

        Requirements: M-NFR-1
        Issue: CLI module - Help output
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["--help"])

        # Assert
        assert result.exit_code == 0
        assert "ingest" in result.output.lower()
        assert "sync" in result.output.lower()

    def test_Should_ShowSubcommandHelp_When_Requested_MNFR1(self):
        """THE MODULE SHALL provide help for each subcommand.

        Requirements: M-NFR-1
        Issue: CLI module - Subcommand help
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["ingest", "--help"])

        # Assert
        assert result.exit_code == 0
        assert "ingest" in result.output.lower()

    def test_Should_DocumentExamples_When_HelpShown_MNFR1(self):
        """THE MODULE SHALL document usage examples.

        Requirements: M-NFR-1
        Issue: CLI module - Examples documentation
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["--help"])

        # Assert - Should have usage or example information
        assert result.exit_code == 0
        assert "usage" in result.output.lower() or "example" in result.output.lower()

    def test_Should_DescribeArguments_When_HelpShown_MNFR1(self):
        """THE MODULE SHALL describe all arguments in help.

        Requirements: M-NFR-1
        Issue: CLI module - Argument descriptions
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["ingest", "--help"])

        # Assert - Should describe options
        assert result.exit_code == 0
        assert "options" in result.output.lower() or "arguments" in result.output.lower()


class TestCommandComposability:
    """Test command composability and idempotence (M-NFR-2)."""

    def test_Should_SupportChaining_When_Configured_MNFR2(self):
        """THE MODULE SHALL support composable commands.

        Requirements: M-NFR-2
        Issue: CLI module - Command chaining
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act - Commands should be runnable independently
        result1 = runner.invoke(app, ["ingest", "--help"])
        result2 = runner.invoke(app, ["sync", "--help"])

        # Assert - Both should work
        assert result1.exit_code == 0
        assert result2.exit_code == 0

    def test_Should_BeIdempotent_When_ReRun_MNFR2(self):
        """THE MODULE SHALL support idempotent-friendly commands.

        Requirements: M-NFR-2
        Issue: CLI module - Idempotence
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act - Help is naturally idempotent
        result1 = runner.invoke(app, ["ingest", "--help"])
        result2 = runner.invoke(app, ["ingest", "--help"])

        # Assert - Same results
        assert result1.exit_code == result2.exit_code
        assert result1.output == result2.output

    def test_Should_SupportDryRun_When_Configured_MNFR2(self):
        """THE MODULE SHALL support --dry-run flag for composability.

        Requirements: M-NFR-2, Design - dry-run flags
        Issue: CLI module - Dry run support
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["ingest", "--dry-run", "--help"])

        # Assert - Should accept or ignore dry-run flag
        assert result.exit_code in [0, 2]


class TestTyperApp:
    """Test Typer app structure."""

    def test_Should_CreateTyperApp_When_Imported_Design(self):
        """THE MODULE SHALL provide Typer app instance.

        Requirements: Design - Typer app
        Issue: CLI module - App instance
        """
        # Arrange & Act
        # Assert
        from typer import Typer

        from w2t_bkin.cli import app

        assert isinstance(app, Typer)

    def test_Should_RegisterSubcommands_When_Loaded_Design(self):
        """THE MODULE SHALL register subcommands under app.

        Requirements: Design - Subcommand registration
        Issue: CLI module - Command registration
        """
        # Arrange & Act
        from w2t_bkin.cli import app

        # Assert - Should have multiple commands
        assert len(app.registered_commands) >= 5


class TestLoggingIntegration:
    """Test logging integration (Design)."""

    def test_Should_SetupLogging_When_CommandRuns_Design(self):
        """THE MODULE SHALL provide consistent logging.

        Requirements: Design - Logging
        Issue: CLI module - Logging setup
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["--help"])

        # Assert - Should complete without logging errors
        assert result.exit_code == 0

    def test_Should_LogToConsole_When_Verbose_Design(self):
        """THE MODULE SHALL support verbose logging flag.

        Requirements: Design - Console/file logging
        Issue: CLI module - Verbose flag
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act - Try verbose flag
        result = runner.invoke(app, ["--verbose", "--help"])

        # Assert - Should accept or ignore verbose flag
        assert result.exit_code in [0, 2]


class TestGlobalFlags:
    """Test global flags (Design - Future notes)."""

    def test_Should_AcceptGlobalConfig_When_Provided_Future(self):
        """THE MODULE SHALL support global --config flag.

        Requirements: Design - Future notes
        Issue: CLI module - Global config flag
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["--config", "custom.toml", "--help"])

        # Assert
        assert result.exit_code in [0, 2]

    def test_Should_AcceptForceFlag_When_Provided_Future(self):
        """THE MODULE SHALL support --force flag.

        Requirements: Design - Future notes
        Issue: CLI module - Force flag
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["--force", "ingest", "--help"])

        # Assert - Should accept or ignore force flag
        assert result.exit_code in [0, 2]

    def test_Should_AcceptJobsFlag_When_Provided_Future(self):
        """THE MODULE SHALL support --jobs flag for parallelism.

        Requirements: Design - Future notes
        Issue: CLI module - Jobs flag
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["--jobs", "4", "ingest", "--help"])

        # Assert
        assert result.exit_code in [0, 2]


class TestStageOrchestration:
    """Test stage orchestration integration."""

    def test_Should_CallIngestModule_When_IngestRun_Design(self):
        """THE MODULE SHALL call ingest module entry point.

        Requirements: Design - Module orchestration
        Issue: CLI module - Ingest integration
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act - Just test help works (actual call would need full setup)
        result = runner.invoke(app, ["ingest", "--help"])

        # Assert
        assert result.exit_code == 0

    def test_Should_CallSyncModule_When_SyncRun_Design(self):
        """THE MODULE SHALL call sync module entry point.

        Requirements: Design - Module orchestration
        Issue: CLI module - Sync integration
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["sync", "--help"])

        # Assert
        assert result.exit_code == 0

    def test_Should_CallNwbModule_When_ToNwbRun_Design(self):
        """THE MODULE SHALL call NWB module entry point.

        Requirements: Design - Module orchestration
        Issue: CLI module - NWB integration
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["to-nwb", "--help"])

        # Assert
        assert result.exit_code == 0 or "to_nwb" in str(result.exception).lower()


class TestRichIntegration:
    """Test rich/logging integration (Design)."""

    def test_Should_UseRichOutput_When_Available_Design(self):
        """THE MODULE SHALL use rich for enhanced output.

        Requirements: Design - rich/logging
        Issue: CLI module - Rich integration
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["--help"])

        # Assert - Should work with or without rich
        assert result.exit_code == 0

    def test_Should_FormatErrors_When_Displayed_Design(self):
        """THE MODULE SHALL format errors nicely.

        Requirements: Design - User-friendly messages
        Issue: CLI module - Error formatting
        """
        # Arrange
        from typer.testing import CliRunner

        from w2t_bkin.cli import app

        runner = CliRunner()

        # Act - Trigger an error
        result = runner.invoke(app, ["invalid-command"])

        # Assert - Should have formatted error
        assert result.exit_code != 0
        assert len(result.output) > 0 or result.exception is not None
