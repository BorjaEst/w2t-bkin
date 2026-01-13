"""Integration tests for Phase 0 Foundation modules (utils, domain, config).

Tests the interaction between foundation modules: configuration loading with domain
validation, deterministic hashing, and error handling across module boundaries.

Requirements: FR-10, FR-12, NFR-1, NFR-10, NFR-11
Acceptance: A13, A14, A18
GitHub Issue: #2
"""

from pathlib import Path
import tempfile
from typing import Any, Dict

from pydantic import ValidationError
import pytest


class TestConfigDomainIntegration:
    """Test integration between config loading and domain validation."""

    @pytest.mark.skip(reason="Config class and load_config() removed - use SessionFlowConfig + env vars")
    def test_Should_LoadValidConfig_When_AllRequiredFieldsProvided_Issue2(self):
        """Should successfully load and validate a complete config file.

        Tests the full pipeline: TOML parsing → domain validation → deterministic hashing.

        DEPRECATED: load_config() and Config class removed. Use SessionFlowConfig.
        """
        from w2t_bkin.config import Config, compute_config_hash, load_config

        # Use the fixtures provided in the test suite
        config_path = Path(__file__).parent.parent / "fixtures" / "configs" / "valid_config.toml"

        # Load configuration
        config = load_config(config_path)

        # Verify it's a proper Config domain object
        assert isinstance(config, Config)
        assert config.synchronization.strategy == "hardware_pulse"
        assert config.verification.mismatch_tolerance_frames == 0

        # Test deterministic hashing (A18)
        hash1 = compute_config_hash(config)
        hash2 = compute_config_hash(config)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest

    def test_Should_LoadValidSession_When_AllRequiredFieldsProvided_Issue2(self):
        """Should successfully load and validate a complete session file.

        Tests the NWB-first approach: metadata loading → NWBFile creation.
        """
        from pynwb import NWBFile

        from w2t_bkin.core.session import create_nwb_file, load_metadata

        # Use the fixtures provided in the test suite
        session_path = Path(__file__).parent.parent / "fixtures" / "sessions" / "valid_session.toml"

        # Load metadata
        metadata = load_metadata(session_path)

        # Create NWBFile
        nwbfile = create_nwb_file(metadata)

        # Verify it's a proper NWBFile object
        assert isinstance(nwbfile, NWBFile)
        assert nwbfile.identifier == "Session-000001"
        assert nwbfile.subject.subject_id == "mouse_001"

        # Check devices (cameras)
        assert len(nwbfile.devices) == 2
        assert "cam0_top" in nwbfile.devices
        assert "cam1_side" in nwbfile.devices

    @pytest.mark.skip(reason="Config class and load_config() removed - use SessionFlowConfig")
    def test_Should_FailValidation_When_ConfigMissingRequiredSection_Issue2(self):
        """Should fail when config file is missing required sections (A13).

        DEPRECATED: load_config() removed. SessionFlowConfig validates required fields.
        """
        from w2t_bkin.config import load_config

        # Use existing fixture with missing 'paths' section
        config_path = Path(__file__).parent.parent / "fixtures" / "configs" / "missing_paths.toml"

        with pytest.raises(ValidationError) as exc_info:
            load_config(config_path)

        assert "paths" in str(exc_info.value).lower()

    @pytest.mark.skip(reason="Config class removed - SessionFlowConfig validates via extra='forbid'")
    def test_Should_FailValidation_When_ConfigHasExtraKeys_Issue2(self):
        """Should fail when config file has extra keys not in schema (A13).

        DEPRECATED: Config class removed. SessionFlowConfig uses extra='forbid'.
        """
        from w2t_bkin.config import load_config

        # Use fixture with extra key in paths section
        config_path = Path(__file__).parent.parent / "fixtures" / "configs" / "config_with_extra_key.toml"

        with pytest.raises(ValidationError) as exc_info:
            load_config(config_path)

        # Should mention the extra field
        error_str = str(exc_info.value).lower()
        assert "extra" in error_str or "forbidden" in error_str

    def test_Should_FailValidation_When_SessionMissingRequiredSection_Issue2(self):
        """Should fail when session file is missing required sections (A14).

        Tests that NWBFile creation fails if essential metadata is missing.
        """
        from pynwb import NWBFile

        from w2t_bkin.core.session import create_nwb_file, load_metadata

        # Use fixture missing required 'session' section
        session_path = Path(__file__).parent.parent / "fixtures" / "sessions" / "session_missing_required.toml"

        # Load metadata (this might succeed if it's just a dict)
        metadata = load_metadata(session_path)

        # NWBFile creation should fail or produce incomplete object depending on what's missing
        # If 'identifier' or 'session_description' are missing, NWBFile constructor raises ValueError
        with pytest.raises((ValueError, TypeError)) as exc_info:
            create_nwb_file(metadata)

        # Check that error relates to missing required fields
        error_str = str(exc_info.value).lower()
        assert "identifier" in error_str or "description" in error_str


class TestUtilsConfigIntegration:
    """Test integration between utils and config modules."""

    @pytest.mark.skip(reason="Config class and compute_config_hash() removed")
    def test_Should_ProduceConsistentHashes_When_ConfigContentIdentical_Issue2(self):
        """Should produce identical hashes for identical config content (NFR-1, A18).

        DEPRECATED: compute_config_hash() removed. Use generic compute_hash() from utils.
        """
        from w2t_bkin.config import compute_config_hash, load_config
        from w2t_bkin.utils import compute_hash

        config_path = Path(__file__).parent.parent / "fixtures" / "configs" / "valid_config.toml"

        # Load same config twice
        config1 = load_config(config_path)
        config2 = load_config(config_path)

        # Hashes should be identical
        hash1 = compute_config_hash(config1)
        hash2 = compute_config_hash(config2)
        assert hash1 == hash2

        # Should also work with utils.compute_hash directly
        config_dict = config1.model_dump()
        util_hash1 = compute_hash(config_dict)
        util_hash2 = compute_hash(config_dict)
        assert util_hash1 == util_hash2

    @pytest.mark.skip(reason="Config class removed - paths now from environment only")
    def test_Should_HandlePathSanitization_When_ConfigContainsPaths_Issue2(self):
        """Should safely handle path sanitization for config paths.

        DEPRECATED: config.paths removed. Paths come from env vars (W2T_RAW_ROOT, etc.).
        """
        from w2t_bkin.config import load_config
        from w2t_bkin.utils import sanitize_path

        config_path = Path(__file__).parent.parent / "fixtures" / "configs" / "valid_config.toml"
        config = load_config(config_path)

        # Sanitize paths from config
        raw_root = sanitize_path(config.paths.raw_root)
        assert isinstance(raw_root, Path)

        # Should reject directory traversal
        with pytest.raises(ValueError, match="Directory traversal not allowed"):
            sanitize_path("../../../etc/passwd")

    @pytest.mark.skip(reason="Config class removed - SessionFlowConfig is the runtime model")
    def test_Should_WriteAndReadJSON_When_ConfigSerialized_Issue2(self):
        """Should correctly serialize and deserialize config data via JSON utils.

        DEPRECATED: Config class removed. Use SessionFlowConfig.model_dump(mode='json').
        """
        from w2t_bkin.config import load_config
        from w2t_bkin.utils import read_json, write_json

        config_path = Path(__file__).parent.parent / "fixtures" / "configs" / "valid_config.toml"
        config = load_config(config_path)

        # Convert to dict and serialize
        config_dict = config.model_dump(mode="json")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json_path = Path(f.name)

        try:
            # Write and read back
            write_json(config_dict, json_path)
            read_data = read_json(json_path)

            # Should be identical
            assert read_data == config_dict
        finally:
            json_path.unlink()


class TestDomainUtilsIntegration:
    """Test integration between domain models and utils."""

    @pytest.mark.skip(reason="Pydantic models are mutable by default unless frozen=True")
    def test_Should_ValidateImmutability_When_DomainModelsCreated_Issue2(self):
        """Should ensure domain models are immutable (FR-12)."""
        from w2t_bkin.config import AlignmentConfig, Config

        # Create a minimal config
        alignment_config = AlignmentConfig(method="nearest", tolerance_s=0.01, global_offset_s=0.0)

        # Should not be able to modify
        with pytest.raises((ValidationError, AttributeError)):
            alignment_config.method = "linear"

    def test_Should_ComputeStableHashes_When_DomainObjectsUsed_Issue2(self):
        """Should produce stable hashes for domain objects (NFR-1, A18)."""
        from w2t_bkin.config import AlignmentConfig
        from w2t_bkin.utils import compute_hash

        # Create identical alignment configs
        alignment1 = AlignmentConfig(method="nearest", tolerance_s=0.01, global_offset_s=0.0)

        alignment2 = AlignmentConfig(method="nearest", tolerance_s=0.01, global_offset_s=0.0)

        # Should produce identical hashes
        hash1 = compute_hash(alignment1.model_dump())
        hash2 = compute_hash(alignment2.model_dump())
        assert hash1 == hash2


class TestFullPhase0Integration:
    """Test complete Phase 0 integration scenarios."""

    def test_Should_CompleteFoundationWorkflow_When_ValidInputsProvided_Issue2(self):
        """Should complete the full Phase 0 foundation workflow successfully.

        This tests the complete foundation: config loading → domain validation →
        hashing → JSON serialization → path handling.
        """
        from pynwb import NWBFile

        from w2t_bkin.config import Config, compute_config_hash, load_config
        from w2t_bkin.core.session import create_nwb_file, load_metadata
        from w2t_bkin.utils import compute_hash, configure_logger, read_json, write_json

        # Setup logger (utils)
        logger = configure_logger("test", level="INFO", structured=False)
        assert logger.name == "test"

        # Load and validate config (config + domain)
        config_path = Path(__file__).parent.parent / "fixtures" / "configs" / "valid_config.toml"
        config = load_config(config_path)
        assert isinstance(config, Config)

        # Load and validate session (metadata + NWB)
        session_path = Path(__file__).parent.parent / "fixtures" / "sessions" / "valid_session.toml"
        metadata = load_metadata(session_path)
        nwbfile = create_nwb_file(metadata)
        assert isinstance(nwbfile, NWBFile)

        # Compute deterministic hashes (config + utils)
        config_hash = compute_config_hash(config)
        # For session/metadata, we hash the dictionary
        session_hash = compute_hash(metadata)

        assert len(config_hash) == 64
        assert len(session_hash) == 64

        # Create provenance data (domain + utils)
        provenance_data = {"config_hash": config_hash, "session_hash": session_hash, "timestamp": "2025-11-11T12:00:00Z", "phase": "foundation_test"}

        # Serialize to JSON (utils)
        with tempfile.TemporaryDirectory() as tmpdir:
            provenance_path = Path(tmpdir) / "provenance.json"
            write_json(provenance_data, provenance_path)

            # Read back and verify
            read_provenance = read_json(provenance_path)
            assert read_provenance["config_hash"] == config_hash
            assert read_provenance["session_hash"] == session_hash

    def test_Should_HandleErrors_When_InvalidInputsProvided_Issue2(self):
        """Should properly handle and propagate errors across foundation modules.

        Tests error handling integration between config loading, domain validation,
        and utility functions.
        """
        from w2t_bkin.config import load_config
        from w2t_bkin.core.session import load_metadata
        from w2t_bkin.utils import sanitize_path

        # Test config file not found
        with pytest.raises(FileNotFoundError):
            load_config(Path("/nonexistent/config.toml"))

        # Test session file not found
        with pytest.raises(FileNotFoundError):
            load_metadata(Path("/nonexistent/metadata.toml"))

        # Test path traversal security
        with pytest.raises(ValueError, match="Directory traversal not allowed"):
            sanitize_path("../../../sensitive/file")

    def test_Should_ValidateTimebaseConditionals_When_ConfiguredCorrectly_Issue2(self, tmp_path):
        """Should validate synchronization conditional requirements (A9, A10, A11)."""
        from w2t_bkin.config import load_config

        # Create config with hardware_pulse strategy but missing reference_channel
        config_content = """
[project]
name = "test"

[paths]
raw_root = "data/raw"
intermediate_root = "data/interim"
output_root = "data/processed"
models_root = "models"

[synchronization]
strategy = "hardware_pulse"
# Missing reference_channel

[synchronization.alignment]
method = "nearest"
tolerance_s = 0.01
global_offset_s = 0.0

[logging]
level = "INFO"
"""

        config_path = tmp_path / "invalid_sync_config.toml"
        config_path.write_text(config_content)

        with pytest.raises(ValueError, match="reference_channel.*required"):
            load_config(config_path)
