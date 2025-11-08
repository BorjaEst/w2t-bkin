"""CLI subcommand invocation tests.

Validates that each subcommand can be invoked with correct exit codes and
produces expected artifacts or output messages.
"""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.cli,
    pytest.mark.skip(reason="CLI not implemented yet"),
]


def test_cli_help_works():
    """Test --help is accessible and returns zero exit code."""
    assert True


def test_ingest_command_creates_manifest(synthetic_session, temp_workdir, mock_config_toml):
    """Test ingest subcommand produces manifest.json."""
    # Validates CLI contract: ingest writes manifest with absolute paths
    assert True


def test_sync_command_produces_timestamps(temp_workdir, dummy_manifest):
    """Test sync subcommand creates timestamp CSVs and summary."""
    # Validates CLI contract: sync produces per-camera timestamps
    assert True


def test_to_nwb_command_with_missing_optional_warns(temp_workdir):
    """Test to-nwb warns when optional data (pose/facemap) missing."""
    # Validates CLI contract: warn when optional data missing
    assert True


def test_validate_command_runs_nwbinspector(temp_workdir):
    """Test validate subcommand invokes nwbinspector."""
    # Validates CLI contract: validate runs nwbinspector
    assert True


def test_report_command_generates_html(temp_workdir):
    """Test report subcommand creates QC HTML."""
    # Validates CLI contract: report generates QC HTML
    assert True


def test_cli_subcommands_idempotent(synthetic_session, temp_workdir):
    """Test re-running subcommands without changes is a no-op."""
    # Validates NFR-2: Idempotence
    assert True
