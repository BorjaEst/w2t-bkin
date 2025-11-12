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

    def test_Should_LoadValidConfig_When_AllRequiredFieldsProvided_Issue2(self):
        """Should successfully load and validate a complete config file.

        Tests the full pipeline: TOML parsing → domain validation → deterministic hashing.
        """
        from w2t_bkin.config import compute_config_hash, load_config
        from w2t_bkin.domain import Config

        # Use the fixtures provided in the test suite
        config_path = Path(__file__).parent.parent / "fixtures" / "configs" / "valid_config.toml"

        # Load configuration
        config = load_config(config_path)

        # Verify it's a proper Config domain object
        assert isinstance(config, Config)
        assert config.project.name == "w2t-bkin-pipeline"
        assert config.timebase.source == "nominal_rate"
        assert config.verification.mismatch_tolerance_frames == 0

        # Test deterministic hashing (A18)
        hash1 = compute_config_hash(config)
        hash2 = compute_config_hash(config)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest

    def test_Should_LoadValidSession_When_AllRequiredFieldsProvided_Issue2(self):
        """Should successfully load and validate a complete session file."""
        from w2t_bkin.config import compute_session_hash, load_session
        from w2t_bkin.domain import Session

        # Use the fixtures provided in the test suite
        session_path = Path(__file__).parent.parent / "fixtures" / "sessions" / "valid_session.toml"

        # Load session
        session = load_session(session_path)

        # Verify it's a proper Session domain object
        assert isinstance(session, Session)
        assert session.session.id == "Session-000001"
        assert session.session.subject_id == "mouse_001"
        assert len(session.cameras) == 2
        assert len(session.TTLs) == 3

        # Test deterministic hashing (A18)
        hash1 = compute_session_hash(session)
        hash2 = compute_session_hash(session)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest

    def test_Should_FailValidation_When_ConfigMissingRequiredSection_Issue2(self):
        """Should fail when config file is missing required sections (A13)."""
        from w2t_bkin.config import load_config

        # Use existing fixture with missing 'paths' section
        config_path = Path(__file__).parent.parent / "fixtures" / "configs" / "missing_paths.toml"

        with pytest.raises(ValidationError) as exc_info:
            load_config(config_path)

        assert "paths" in str(exc_info.value).lower()

    def test_Should_FailValidation_When_ConfigHasExtraKeys_Issue2(self):
        """Should fail when config file has extra keys not in schema (A13)."""
        from w2t_bkin.config import load_config

        # Use fixture with extra key in project section
        config_path = Path(__file__).parent.parent / "fixtures" / "configs" / "config_with_extra_key.toml"

        with pytest.raises(ValidationError) as exc_info:
            load_config(config_path)

        # Should mention the extra field
        error_str = str(exc_info.value).lower()
        assert "extra" in error_str or "forbidden" in error_str

    def test_Should_FailValidation_When_SessionMissingRequiredSection_Issue2(self):
        """Should fail when session file is missing required sections (A14)."""
        from w2t_bkin.config import load_session

        # Use fixture missing required 'session' section
        session_path = Path(__file__).parent.parent / "fixtures" / "sessions" / "session_missing_required.toml"

        with pytest.raises(ValidationError) as exc_info:
            load_session(session_path)

        assert "session" in str(exc_info.value).lower()


class TestUtilsConfigIntegration:
    """Test integration between utils and config modules."""

    def test_Should_ProduceConsistentHashes_When_ConfigContentIdentical_Issue2(self):
        """Should produce identical hashes for identical config content (NFR-1, A18)."""
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

    def test_Should_HandlePathSanitization_When_ConfigContainsPaths_Issue2(self):
        """Should safely handle path sanitization for config paths."""
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

    def test_Should_WriteAndReadJSON_When_ConfigSerialized_Issue2(self):
        """Should correctly serialize and deserialize config data via JSON utils."""
        from w2t_bkin.config import load_config
        from w2t_bkin.utils import read_json, write_json

        config_path = Path(__file__).parent.parent / "fixtures" / "configs" / "valid_config.toml"
        config = load_config(config_path)

        # Convert to dict and serialize
        config_dict = config.model_dump()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json_path = Path(f.name)

        try:
            # Write and read back
            write_json(config_dict, json_path)
            read_data = read_json(json_path)

            # Should be identical
            assert read_data == config_dict
            assert read_data["project"]["name"] == config.project.name
        finally:
            json_path.unlink()


class TestDomainUtilsIntegration:
    """Test integration between domain models and utils."""

    def test_Should_ValidateImmutability_When_DomainModelsCreated_Issue2(self):
        """Should ensure domain models are immutable (FR-12)."""
        from w2t_bkin.domain import Config, Session, TimebaseConfig

        # Create a minimal config
        timebase_config = TimebaseConfig(source="nominal_rate", mapping="nearest", jitter_budget_s=0.01, offset_s=0.0)

        # Should not be able to modify
        with pytest.raises((ValidationError, AttributeError)):
            timebase_config.source = "ttl"

    def test_Should_ComputeStableHashes_When_DomainObjectsUsed_Issue2(self):
        """Should produce stable hashes for domain objects (NFR-1, A18)."""
        from w2t_bkin.domain import TimebaseConfig
        from w2t_bkin.utils import compute_hash

        # Create identical timebase configs
        timebase1 = TimebaseConfig(source="nominal_rate", mapping="nearest", jitter_budget_s=0.01, offset_s=0.0)

        timebase2 = TimebaseConfig(source="nominal_rate", mapping="nearest", jitter_budget_s=0.01, offset_s=0.0)

        # Should produce identical hashes
        hash1 = compute_hash(timebase1.model_dump())
        hash2 = compute_hash(timebase2.model_dump())
        assert hash1 == hash2


class TestFullPhase0Integration:
    """Test complete Phase 0 integration scenarios."""

    def test_Should_CompleteFoundationWorkflow_When_ValidInputsProvided_Issue2(self):
        """Should complete the full Phase 0 foundation workflow successfully.

        This tests the complete foundation: config loading → domain validation →
        hashing → JSON serialization → path handling.
        """
        from w2t_bkin.config import (
            compute_config_hash,
            compute_session_hash,
            load_config,
            load_session,
        )
        from w2t_bkin.domain import Config, Session
        from w2t_bkin.utils import configure_logger, read_json, write_json

        # Setup logger (utils)
        logger = configure_logger("test", level="INFO", structured=False)
        assert logger.name == "test"

        # Load and validate config (config + domain)
        config_path = Path(__file__).parent.parent / "fixtures" / "configs" / "valid_config.toml"
        config = load_config(config_path)
        assert isinstance(config, Config)

        # Load and validate session (config + domain)
        session_path = Path(__file__).parent.parent / "fixtures" / "sessions" / "valid_session.toml"
        session = load_session(session_path)
        assert isinstance(session, Session)

        # Compute deterministic hashes (config + utils)
        config_hash = compute_config_hash(config)
        session_hash = compute_session_hash(session)
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
        from w2t_bkin.config import load_config, load_session
        from w2t_bkin.utils import sanitize_path

        # Test config file not found
        with pytest.raises(FileNotFoundError):
            load_config(Path("/nonexistent/config.toml"))

        # Test session file not found
        with pytest.raises(FileNotFoundError):
            load_session(Path("/nonexistent/session.toml"))

        # Test path traversal security
        with pytest.raises(ValueError, match="Directory traversal not allowed"):
            sanitize_path("../../../sensitive/file")

    def test_Should_ValidateTimebaseConditionals_When_ConfiguredCorrectly_Issue2(self):
        """Should validate timebase conditional requirements (A9, A10, A11)."""
        from w2t_bkin.config import load_config

        # Use fixture with ttl source but missing ttl_id
        config_path = Path(__file__).parent.parent / "fixtures" / "configs" / "config_ttl_missing_ttl_id.toml"

        with pytest.raises(ValueError, match="ttl_id.*required"):
            load_config(config_path)
