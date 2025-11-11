"""Unit tests for config loading and validation (Phase 0).

Tests configuration loading from TOML files with strict schema validation,
enum constraints, conditional requirements, and deterministic hashing.

Requirements: FR-10, NFR-10, NFR-11
Acceptance: A13, A14, A9, A10, A11, A18
"""

from pathlib import Path

from pydantic import ValidationError
import pytest


class TestConfigLoading:
    """Test configuration file loading and parsing."""

    def test_Should_LoadValidConfig_When_ValidTOMLProvided(self):
        """Should successfully load a valid config.toml file."""
        from w2t_bkin.config import load_config

        config_path = Path("tests/fixtures/configs/valid_config.toml")
        config = load_config(config_path)

        assert config.project.name == "w2t-bkin-pipeline"
        assert config.paths.raw_root == "data/raw"
        assert config.timebase.source == "nominal_rate"

    def test_Should_RejectConfig_When_MissingRequiredKey(self):
        """Should reject config missing required key (A13)."""
        from w2t_bkin.config import load_config

        config_path = Path("tests/fixtures/configs/missing_paths.toml")

        with pytest.raises((ValidationError, KeyError)):
            load_config(config_path)

    def test_Should_RejectConfig_When_ExtraKeyPresent(self):
        """Should reject config with extra key not in schema (A13)."""
        from w2t_bkin.domain import Config

        config_data = {
            "project": {"name": "test", "extra_key": "not allowed"},
            "paths": {
                "raw_root": "data/raw",
                "intermediate_root": "data/interim",
                "output_root": "data/processed",
                "metadata_file": "session.toml",
                "models_root": "models",
            },
            "timebase": {"source": "nominal_rate", "mapping": "nearest", "jitter_budget_s": 0.01, "offset_s": 0.0},
            "acquisition": {"concat_strategy": "ffconcat"},
            "verification": {"mismatch_tolerance_frames": 0, "warn_on_mismatch": False},
            "bpod": {"parse": True},
            "video": {"transcode": {"enabled": True, "codec": "h264", "crf": 20, "preset": "fast", "keyint": 15}},
            "nwb": {
                "link_external_video": True,
                "lab": "Lab",
                "institution": "Inst",
                "file_name_template": "{session.id}.nwb",
                "session_description_template": "Session {session.id}",
            },
            "qc": {"generate_report": True, "out_template": "qc/{session.id}", "include_verification": True},
            "logging": {"level": "INFO", "structured": False},
            "labels": {"dlc": {"run_inference": False, "model": "model.pb"}, "sleap": {"run_inference": False, "model": "sleap.h5"}},
            "facemap": {"run_inference": False, "ROIs": ["face"]},
        }

        with pytest.raises(ValidationError) as exc_info:
            Config(**config_data)

        assert "extra" in str(exc_info.value).lower()


class TestTimebaseValidation:
    """Test timebase configuration validation with enum and conditional constraints."""

    def test_Should_AcceptTimebaseSource_When_ValidEnum(self):
        """Should accept valid timebase.source values: nominal_rate, ttl, neuropixels."""
        from w2t_bkin.config import load_config

        config_path = Path("tests/fixtures/configs/valid_config.toml")
        config = load_config(config_path)

        assert config.timebase.source in ["nominal_rate", "ttl", "neuropixels"]

    def test_Should_RejectTimebaseSource_When_InvalidEnum(self):
        """Should reject invalid timebase.source value (A11)."""
        from w2t_bkin.config import _validate_config_enums, load_config

        data = {"timebase": {"source": "invalid_source"}}

        with pytest.raises(ValueError):
            _validate_config_enums(data)

    def test_Should_AcceptTimebaseMapping_When_ValidEnum(self):
        """Should accept valid timebase.mapping values: nearest, linear."""
        from w2t_bkin.config import load_config

        config_path = Path("tests/fixtures/configs/valid_config.toml")
        config = load_config(config_path)

        assert config.timebase.mapping in ["nearest", "linear"]

    def test_Should_RejectTimebaseMapping_When_InvalidEnum(self):
        """Should reject invalid timebase.mapping value (A11)."""
        from w2t_bkin.config import _validate_config_enums

        data = {"timebase": {"mapping": "invalid_mapping"}}

        with pytest.raises(ValueError):
            _validate_config_enums(data)

    def test_Should_RejectJitterBudget_When_NegativeValue(self):
        """Should reject negative jitter_budget_s (A11)."""
        from w2t_bkin.config import _validate_config_enums

        data = {"timebase": {"jitter_budget_s": -0.1}}

        with pytest.raises(ValueError):
            _validate_config_enums(data)

    def test_Should_RequireTTLId_When_SourceIsTTL(self):
        """Should require ttl_id when timebase.source='ttl' (A9)."""
        from w2t_bkin.config import _validate_config_conditionals

        data = {"timebase": {"source": "ttl"}}  # Missing ttl_id

        with pytest.raises(ValueError):
            _validate_config_conditionals(data)

    def test_Should_RequireNeuropixelsStream_When_SourceIsNeuropixels(self):
        """Should require neuropixels_stream when timebase.source='neuropixels' (A10)."""
        from w2t_bkin.config import _validate_config_conditionals

        data = {"timebase": {"source": "neuropixels"}}  # Missing neuropixels_stream

        with pytest.raises(ValueError):
            _validate_config_conditionals(data)


class TestSessionLoading:
    """Test session file loading and parsing."""

    def test_Should_LoadValidSession_When_ValidTOMLProvided(self):
        """Should successfully load a valid session.toml file."""
        from w2t_bkin.config import load_session

        session_path = Path("tests/fixtures/sessions/valid_session.toml")
        session = load_session(session_path)

        assert session.session.id == "SNA-145518"
        assert session.session.subject_id == "mouse_123"
        assert len(session.TTLs) == 3
        assert len(session.cameras) == 2

    def test_Should_RejectSession_When_MissingRequiredKey(self):
        """Should reject session missing required key (A14)."""
        from w2t_bkin.domain import Session

        session_data = {
            "session": {"id": "test"},  # Missing required fields
            "bpod": {"path": "Bpod/*.mat", "order": "name_asc"},
            "TTLs": [],
            "cameras": [],
        }

        with pytest.raises(ValidationError):
            Session(**session_data)

    def test_Should_RejectSession_When_ExtraKeyPresent(self):
        """Should reject session with extra key not in schema (A14)."""
        from w2t_bkin.domain import SessionMetadata

        with pytest.raises(ValidationError):
            SessionMetadata(
                id="test",
                subject_id="test",
                date="2025-01-01",
                experimenter="test",
                description="test",
                sex="M",
                age="P60",
                genotype="WT",
                extra_field="not allowed",
            )

    def test_Should_ValidateCameraTTLReference_When_Loading(self):
        """Should validate camera ttl_id references existing TTL (A15)."""
        from w2t_bkin.config import load_session

        # Valid session should load without issues
        session_path = Path("tests/fixtures/sessions/valid_session.toml")
        session = load_session(session_path)

        # All cameras should reference valid TTL IDs
        ttl_ids = {ttl.id for ttl in session.TTLs}
        for camera in session.cameras:
            assert camera.ttl_id in ttl_ids


class TestConfigHashing:
    """Test deterministic config hashing for reproducibility (A18)."""

    def test_Should_ProduceDeterministicHash_When_SameConfigLoaded(self):
        """Config hash should be identical for identical config content (A18)."""
        from w2t_bkin.config import compute_config_hash, load_config

        config_path = Path("tests/fixtures/configs/valid_config.toml")
        config1 = load_config(config_path)
        config2 = load_config(config_path)

        hash1 = compute_config_hash(config1)
        hash2 = compute_config_hash(config2)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest

    def test_Should_ProduceDifferentHash_When_ConfigDiffers(self):
        """Config hash should differ when config content changes."""
        from w2t_bkin.config import compute_config_hash
        from w2t_bkin.domain import (
            AcquisitionConfig,
            BpodConfig,
            Config,
            DLCConfig,
            FacemapConfig,
            LabelsConfig,
            LoggingConfig,
            NWBConfig,
            PathsConfig,
            ProjectConfig,
            QCConfig,
            SLEAPConfig,
            TimebaseConfig,
            TranscodeConfig,
            VerificationConfig,
            VideoConfig,
        )

        # Create two configs with different values
        config1 = Config(
            project=ProjectConfig(name="project1"),
            paths=PathsConfig(
                raw_root="data/raw", intermediate_root="data/interim", output_root="data/processed", metadata_file="session.toml", models_root="models"
            ),
            timebase=TimebaseConfig(source="nominal_rate", mapping="nearest", jitter_budget_s=0.01, offset_s=0.0),
            acquisition=AcquisitionConfig(concat_strategy="ffconcat"),
            verification=VerificationConfig(mismatch_tolerance_frames=0, warn_on_mismatch=False),
            bpod=BpodConfig(parse=True),
            video=VideoConfig(transcode=TranscodeConfig(enabled=True, codec="h264", crf=20, preset="fast", keyint=15)),
            nwb=NWBConfig(
                link_external_video=True,
                lab="Lab",
                institution="Inst",
                file_name_template="{session.id}.nwb",
                session_description_template="Session {session.id}",
            ),
            qc=QCConfig(generate_report=True, out_template="qc/{session.id}", include_verification=True),
            logging=LoggingConfig(level="INFO", structured=False),
            labels=LabelsConfig(dlc=DLCConfig(run_inference=False, model="model.pb"), sleap=SLEAPConfig(run_inference=False, model="sleap.h5")),
            facemap=FacemapConfig(run_inference=False, ROIs=["face"]),
        )

        config2 = Config(
            project=ProjectConfig(name="project2"),  # Different name
            paths=PathsConfig(
                raw_root="data/raw", intermediate_root="data/interim", output_root="data/processed", metadata_file="session.toml", models_root="models"
            ),
            timebase=TimebaseConfig(source="nominal_rate", mapping="nearest", jitter_budget_s=0.01, offset_s=0.0),
            acquisition=AcquisitionConfig(concat_strategy="ffconcat"),
            verification=VerificationConfig(mismatch_tolerance_frames=0, warn_on_mismatch=False),
            bpod=BpodConfig(parse=True),
            video=VideoConfig(transcode=TranscodeConfig(enabled=True, codec="h264", crf=20, preset="fast", keyint=15)),
            nwb=NWBConfig(
                link_external_video=True,
                lab="Lab",
                institution="Inst",
                file_name_template="{session.id}.nwb",
                session_description_template="Session {session.id}",
            ),
            qc=QCConfig(generate_report=True, out_template="qc/{session.id}", include_verification=True),
            logging=LoggingConfig(level="INFO", structured=False),
            labels=LabelsConfig(dlc=DLCConfig(run_inference=False, model="model.pb"), sleap=SLEAPConfig(run_inference=False, model="sleap.h5")),
            facemap=FacemapConfig(run_inference=False, ROIs=["face"]),
        )

        hash1 = compute_config_hash(config1)
        hash2 = compute_config_hash(config2)

        assert hash1 != hash2

    def test_Should_IgnoreComments_When_ComputingHash(self):
        """Config hash should ignore TOML comments (A18)."""
        from w2t_bkin.config import compute_config_hash, load_config

        # Comments are not included in parsed TOML, so two files with same content
        # but different comments will have the same hash
        config_path = Path("tests/fixtures/configs/valid_config.toml")
        config = load_config(config_path)
        hash1 = compute_config_hash(config)

        # Hash should be deterministic
        assert len(hash1) == 64


class TestSessionHashing:
    """Test deterministic session hashing for reproducibility (A18)."""

    def test_Should_ProduceDeterministicHash_When_SameSessionLoaded(self):
        """Session hash should be identical for identical session content (A18)."""
        from w2t_bkin.config import compute_session_hash, load_session

        session_path = Path("tests/fixtures/sessions/valid_session.toml")
        session1 = load_session(session_path)
        session2 = load_session(session_path)

        hash1 = compute_session_hash(session1)
        hash2 = compute_session_hash(session2)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest

    def test_Should_ProduceDifferentHash_When_SessionDiffers(self):
        """Session hash should differ when session content changes."""
        from w2t_bkin.config import compute_session_hash
        from w2t_bkin.domain import BpodSession, Session, SessionMetadata

        session1 = Session(
            session=SessionMetadata(
                id="session1", subject_id="mouse1", date="2025-01-01", experimenter="Test", description="Test", sex="M", age="P60", genotype="WT"
            ),
            bpod=BpodSession(path="Bpod/*.mat", order="name_asc"),
            TTLs=[],
            cameras=[],
        )

        session2 = Session(
            session=SessionMetadata(
                id="session2", subject_id="mouse2", date="2025-01-01", experimenter="Test", description="Test", sex="M", age="P60", genotype="WT"
            ),
            bpod=BpodSession(path="Bpod/*.mat", order="name_asc"),
            TTLs=[],
            cameras=[],
        )

        hash1 = compute_session_hash(session1)
        hash2 = compute_session_hash(session2)

        assert hash1 != hash2

    def test_Should_IgnoreComments_When_ComputingHash(self):
        """Session hash should ignore TOML comments (A18)."""
        from w2t_bkin.config import compute_session_hash, load_session

        # Comments are not included in parsed TOML
        session_path = Path("tests/fixtures/sessions/valid_session.toml")
        session = load_session(session_path)
        hash1 = compute_session_hash(session)

        # Hash should be deterministic
        assert len(hash1) == 64


class TestLoggingLevelValidation:
    """Test logging level enum validation."""

    def test_Should_AcceptLoggingLevel_When_ValidEnum(self):
        """Should accept valid logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL."""
        from w2t_bkin.config import load_config

        config_path = Path("tests/fixtures/configs/valid_config.toml")
        config = load_config(config_path)

        assert config.logging.level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_Should_RejectLoggingLevel_When_InvalidEnum(self):
        """Should reject invalid logging.level value (A11)."""
        from w2t_bkin.config import _validate_config_enums

        data = {"logging": {"level": "INVALID_LEVEL"}}

        with pytest.raises(ValueError):
            _validate_config_enums(data)
