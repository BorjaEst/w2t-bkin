"""Pipeline orchestration integration tests (Phase 2).

Tests the high-level pipeline orchestration API that owns Config/Session
and coordinates all stages with primitive-based low-level tool calls.

Requirements: Phase 2 orchestration, FR-1..17
"""

from pathlib import Path

import pytest

from w2t_bkin.pipeline import run_session, run_validation


class TestPipelineOrchestration:
    """Test high-level pipeline orchestration API."""

    def test_Should_RunPipeline_When_ValidConfigAndSession(self, tmp_path):
        """Should orchestrate complete pipeline from config and session_id."""
        from synthetic.scenarios import happy_path

        # Generate synthetic session
        session = happy_path.make_session(root=tmp_path, n_frames=64, seed=42)

        # Run orchestration (skip NWB for now - not yet implemented)
        result = run_session(
            config_path=str(session.config_path),
            session_id="Session-Happy-Path",
            options={"skip_nwb": True},
        )

        # Verify manifest
        assert result["manifest"].session_id == "Session-Happy-Path"
        assert len(result["manifest"].cameras) == 1
        assert result["manifest"].cameras[0].camera_id == "cam0"

        # Verify provenance
        assert "provenance" in result
        assert result["provenance"]["config_hash"]
        assert result["provenance"]["session_hash"]

    def test_Should_ParseEvents_When_BpodFilesPresent(self, tmp_path):
        """Should parse Bpod events when files are discovered."""
        from synthetic.scenarios import happy_path

        # Generate synthetic session with Bpod
        session = happy_path.make_session(root=tmp_path, n_frames=64, seed=42)

        # Run orchestration (skip NWB)
        result = run_session(
            config_path=str(session.config_path),
            session_id="Session-Happy-Path",
            options={"skip_nwb": True},
        )

        # Verify events parsed (should have events_summary)
        assert "events_summary" in result
        if result["events_summary"]:  # Only if Bpod files exist
            assert "n_trials" in result["events_summary"]

    def test_Should_HandleMissingSession_When_InvalidSessionId(self, tmp_path):
        """Should raise error when session_id doesn't match or doesn't exist."""
        from synthetic.scenarios import happy_path

        # Generate synthetic session
        session = happy_path.make_session(root=tmp_path, n_frames=64, seed=42)

        # Try to run with invalid session_id
        with pytest.raises(FileNotFoundError):
            run_session(
                config_path=str(session.config_path),
                session_id="Session-Nonexistent",
                options={"skip_nwb": True},
            )

    @pytest.mark.skip(reason="NWB assembly not yet implemented in pipeline")
    def test_Should_SkipNWB_When_OptionSet(self, tmp_path):
        """Should skip NWB assembly when skip_nwb option is True."""
        # This will be implemented when NWB assembly is complete
        pass

    def test_Should_CreateProvenance_When_PipelineExecutes(self, tmp_path):
        """Should include provenance metadata in result."""
        from synthetic.scenarios import happy_path

        # Generate synthetic session
        session = happy_path.make_session(root=tmp_path, n_frames=64, seed=42)

        # Run orchestration
        result = run_session(
            config_path=str(session.config_path),
            session_id="Session-Happy-Path",
            options={"skip_nwb": True},
        )

        # Verify provenance structure
        assert "provenance" in result
        prov = result["provenance"]
        assert "config_hash" in prov
        assert "session_hash" in prov
        assert "pipeline_version" in prov
        assert "execution_time" in prov  # ISO 8601 timestamp


class TestValidationOrchestration:
    """Test NWB validation orchestration."""

    def test_Should_RaiseError_When_NWBFileMissing(self, tmp_path):
        """Should raise FileNotFoundError when NWB file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.nwb"

        with pytest.raises(FileNotFoundError):
            run_validation(nonexistent)

    @pytest.mark.skip(reason="Placeholder: NWB assembly not yet implemented")
    def test_Should_ValidateNWB_When_FileExists(self, tmp_path):
        """Should validate NWB file when it exists."""
        # This will be implemented when NWB assembly is complete
        pass
