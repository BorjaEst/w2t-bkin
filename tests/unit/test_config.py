"""Unit tests for the config module.

Tests configuration loading, validation, environment overrides, and error handling
as specified in config/requirements.md and config/design.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestConfigLoading:
    """Test configuration loading from TOML files (MR-1)."""

    def test_Should_LoadValidTOML_When_FileExists_MR1(self, tmp_path: Path):
        """THE MODULE SHALL load configuration from TOML.

        Requirements: MR-1
        Issue: Config module - TOML loading
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test-project"
n_cameras = 5

[paths]
raw_root = "/data/raw"
intermediate_root = "/data/interim"
output_root = "/data/processed"
models_root = "/models"
"""
        )

        # Act
        settings = load_settings(config_path)

        # Assert
        assert settings.project.name == "test-project"
        assert settings.project.n_cameras == 5
        assert settings.paths.raw_root == Path("/data/raw")

    def test_Should_LoadFromString_When_PathIsString_MR1(self, tmp_path: Path):
        """THE MODULE SHALL accept path as string or Path object.

        Requirements: MR-1, Design - Inputs/Outputs
        Issue: Config module - Path flexibility
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test-project"
n_cameras = 5
"""
        )

        # Act
        settings = load_settings(str(config_path))

        # Assert
        assert settings.project.name == "test-project"

    def test_Should_LoadCompleteSchema_When_AllSectionsPresent_MR1(self, tmp_path: Path):
        """THE MODULE SHALL load all configuration sections from requirements.

        Requirements: MR-1, Requirements - Configuration keys
        Issue: Config module - Complete schema loading
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test-project"
n_cameras = 5

[paths]
raw_root = "/data/raw"
intermediate_root = "/data/interim"
output_root = "/data/processed"
models_root = "/models"

[session]
id = "session_001"
subject_id = "mouse_001"
date = "2025-11-08"
experimenter = "John Doe"
description = "Test session"
sex = "M"
age = "P90"
genotype = "wildtype"

[video]
pattern = "cam*.mp4"
fps = 30.0

[video.transcode]
enabled = true
codec = "h264"
crf = 23
preset = "medium"
keyint = 30

[sync]
tolerance_ms = 2.0
drop_frame_max_gap_ms = 100.0
primary_clock = "cam0"

[[sync.ttl_channels]]
path = "/data/sync/cam0.csv"
name = "cam0"
polarity = "rising"

[labels.dlc]
model = "/models/dlc_model.pb"
run_inference = false

[labels.sleap]
model = "/models/sleap_model.h5"
run_inference = false

[facemap]
run = false
roi = [0, 0, 640, 480]

[nwb]
link_external_video = true
file_name = "session.nwb"
session_description = "Multi-camera behavioral session"
lab = "Larkum Lab"
institution = "Humboldt University"

[qc]
generate_report = true
out = "/data/qc"

[logging]
level = "INFO"

[events]
patterns = ["**/*_training.ndjson", "**/*_trial_stats.ndjson"]
format = "ndjson"
"""
        )

        # Act
        settings = load_settings(config_path)

        # Assert - Verify all sections loaded
        assert settings.project.name == "test-project"
        assert settings.paths.raw_root == Path("/data/raw")
        assert settings.session.id == "session_001"
        assert settings.video.fps == 30.0
        assert settings.video.transcode.enabled is True
        assert settings.sync.tolerance_ms == 2.0
        assert len(settings.sync.ttl_channels) == 1
        assert settings.labels.dlc.model == Path("/models/dlc_model.pb")
        assert settings.facemap.run is False
        assert settings.nwb.link_external_video is True
        assert settings.qc.generate_report is True
        assert settings.logging.level == "INFO"
        assert len(settings.events.patterns) == 2


class TestConfigValidation:
    """Test Pydantic validation of configuration (MR-2)."""

    def test_Should_ValidateTypes_When_LoadingConfig_MR2(self, tmp_path: Path):
        """THE MODULE SHALL validate all keys and types using Pydantic models.

        Requirements: MR-2
        Issue: Config module - Type validation
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test-project"
n_cameras = 5

[sync]
tolerance_ms = 2.0
"""
        )

        # Act
        settings = load_settings(config_path)

        # Assert - Types should be correct
        assert isinstance(settings.project.name, str)
        assert isinstance(settings.project.n_cameras, int)
        assert isinstance(settings.sync.tolerance_ms, float)

    def test_Should_RaiseError_When_InvalidType_MR2_MR4(self, tmp_path: Path):
        """THE MODULE SHALL raise ConfigValidationError on invalid types.

        Requirements: MR-2, MR-4
        Issue: Config module - Type validation error
        """
        # Arrange
        from w2t_bkin.config import ConfigValidationError, load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test-project"
n_cameras = "five"
"""
        )

        # Act & Assert
        with pytest.raises(ConfigValidationError) as exc_info:
            load_settings(config_path)

        # Should include offending key
        assert "n_cameras" in str(exc_info.value).lower() or "cameras" in str(exc_info.value).lower()

    def test_Should_RaiseError_When_RequiredFieldMissing_MR2_MR4(self, tmp_path: Path):
        """THE MODULE SHALL raise ConfigValidationError when required fields missing.

        Requirements: MR-2, MR-4
        Issue: Config module - Required field validation
        """
        # Arrange
        from w2t_bkin.config import ConfigValidationError, load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
# Missing required 'name' field
n_cameras = 5
"""
        )

        # Act & Assert
        with pytest.raises(ConfigValidationError) as exc_info:
            load_settings(config_path)

        # Should mention missing field
        assert "name" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()

    def test_Should_ValidatePathFields_When_LoadingConfig_MR2(self, tmp_path: Path):
        """THE MODULE SHALL convert path strings to Path objects.

        Requirements: MR-2, Design - Immutable settings
        Issue: Config module - Path type conversion
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test"
n_cameras = 5

[paths]
raw_root = "/data/raw"
intermediate_root = "/data/interim"
output_root = "/data/processed"
models_root = "/models"
"""
        )

        # Act
        settings = load_settings(config_path)

        # Assert - Paths should be Path objects
        assert isinstance(settings.paths.raw_root, Path)
        assert isinstance(settings.paths.intermediate_root, Path)
        assert isinstance(settings.paths.output_root, Path)

    def test_Should_ValidateEnumFields_When_Present_MR2(self, tmp_path: Path):
        """THE MODULE SHALL validate enum/choice fields.

        Requirements: MR-2
        Issue: Config module - Enum validation
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test"
n_cameras = 5

[logging]
level = "DEBUG"
"""
        )

        # Act
        settings = load_settings(config_path)

        # Assert - Valid enum value accepted
        assert settings.logging.level in ["DEBUG", "INFO", "WARNING", "ERROR"]

    def test_Should_RaiseError_When_InvalidEnumValue_MR2_MR4(self, tmp_path: Path):
        """THE MODULE SHALL reject invalid enum values.

        Requirements: MR-2, MR-4
        Issue: Config module - Enum validation error
        """
        # Arrange
        from w2t_bkin.config import ConfigValidationError, load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test"
n_cameras = 5

[logging]
level = "INVALID_LEVEL"
"""
        )

        # Act & Assert
        with pytest.raises(ConfigValidationError) as exc_info:
            load_settings(config_path)

        assert "level" in str(exc_info.value).lower()


class TestEnvironmentOverrides:
    """Test environment variable configuration overrides (MR-1, NFR-10)."""

    def test_Should_OverrideWithEnv_When_EnvVarSet_MR1_NFR10(self, tmp_path: Path, monkeypatch):
        """THE MODULE SHALL merge environment overrides.

        Requirements: MR-1, NFR-10 (pydantic-settings)
        Issue: Config module - Environment override
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test-project"
n_cameras = 5

[sync]
tolerance_ms = 2.0
"""
        )

        # Set environment override
        monkeypatch.setenv("W2T_BKIN_SYNC__TOLERANCE_MS", "5.0")
        monkeypatch.setenv("W2T_BKIN_PROJECT__NAME", "overridden-project")

        # Act
        settings = load_settings(config_path)

        # Assert - Environment should override TOML
        assert settings.sync.tolerance_ms == 5.0
        assert settings.project.name == "overridden-project"

    def test_Should_UseTOMLWhenNoEnv_When_EnvNotSet_MR1_MNFR1(self, tmp_path: Path, monkeypatch):
        """THE MODULE SHALL use TOML values when environment not set.

        Requirements: MR-1, M-NFR-1 (Deterministic merging)
        Issue: Config module - Precedence order
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test-project"
n_cameras = 5

[sync]
tolerance_ms = 2.0
"""
        )

        # Ensure no relevant env vars set
        for key in list(monkeypatch._setitem):
            if "W2T_BKIN" in key:
                monkeypatch.delenv(key, raising=False)

        # Act
        settings = load_settings(config_path)

        # Assert - Should use TOML values
        assert settings.sync.tolerance_ms == 2.0
        assert settings.project.name == "test-project"

    def test_Should_OverrideNestedFields_When_EnvVarSet_MR1(self, tmp_path: Path, monkeypatch):
        """THE MODULE SHALL support overrides for nested configuration fields.

        Requirements: MR-1
        Issue: Config module - Nested field overrides
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test"
n_cameras = 5

[video.transcode]
enabled = false
codec = "h264"
crf = 23
"""
        )

        # Override nested field
        monkeypatch.setenv("W2T_BKIN_VIDEO__TRANSCODE__ENABLED", "true")
        monkeypatch.setenv("W2T_BKIN_VIDEO__TRANSCODE__CRF", "18")

        # Act
        settings = load_settings(config_path)

        # Assert
        assert settings.video.transcode.enabled is True
        assert settings.video.transcode.crf == 18


class TestImmutability:
    """Test that settings objects are immutable (MR-3)."""

    def test_Should_BeImmutable_When_SettingsLoaded_MR3(self, tmp_path: Path):
        """THE MODULE SHALL provide an immutable settings object.

        Requirements: MR-3
        Issue: Config module - Immutability enforcement
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test-project"
n_cameras = 5
"""
        )

        # Act
        settings = load_settings(config_path)

        # Assert - Should not allow modification
        with pytest.raises((AttributeError, TypeError, ValueError)):
            settings.project.name = "modified"

    def test_Should_PreventNestedMutation_When_SettingsLoaded_MR3(self, tmp_path: Path):
        """THE MODULE SHALL enforce immutability on nested objects.

        Requirements: MR-3
        Issue: Config module - Nested immutability
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test"
n_cameras = 5

[video.transcode]
enabled = false
codec = "h264"
"""
        )

        # Act
        settings = load_settings(config_path)

        # Assert - Nested objects should be immutable
        with pytest.raises((AttributeError, TypeError, ValueError)):
            settings.video.transcode.enabled = True


class TestDefaultValues:
    """Test default value handling (MR-2, M-NFR-2)."""

    def test_Should_ApplyDefaults_When_OptionalFieldsMissing_MR2(self, tmp_path: Path):
        """THE MODULE SHALL provide sensible defaults for optional fields.

        Requirements: MR-2, M-NFR-2
        Issue: Config module - Default values
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "minimal-config"
n_cameras = 5
"""
        )

        # Act
        settings = load_settings(config_path)

        # Assert - Defaults should be applied
        assert hasattr(settings, "logging")
        assert settings.logging.level in ["INFO", "DEBUG", "WARNING", "ERROR"]

    def test_Should_UseDefaultForSync_When_NotSpecified_MR2(self, tmp_path: Path):
        """THE MODULE SHALL provide default sync configuration.

        Requirements: MR-2
        Issue: Config module - Sync defaults
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test"
n_cameras = 5
"""
        )

        # Act
        settings = load_settings(config_path)

        # Assert - Sync defaults should exist
        assert hasattr(settings, "sync")
        assert settings.sync.tolerance_ms > 0
        assert settings.sync.primary_clock is not None

    def test_Should_UseDefaultForTranscode_When_NotSpecified_MR2(self, tmp_path: Path):
        """THE MODULE SHALL provide default transcode configuration.

        Requirements: MR-2
        Issue: Config module - Transcode defaults
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test"
n_cameras = 5
"""
        )

        # Act
        settings = load_settings(config_path)

        # Assert - Transcode defaults should exist
        assert hasattr(settings, "video")
        assert hasattr(settings.video, "transcode")
        assert isinstance(settings.video.transcode.enabled, bool)


class TestErrorHandling:
    """Test error handling and descriptive messages (MR-4)."""

    def test_Should_RaiseDescriptiveError_When_FileNotFound_MR4(self, tmp_path: Path):
        """THE MODULE SHALL raise ConfigValidationError with descriptive message.

        Requirements: MR-4
        Issue: Config module - File not found error
        """
        # Arrange
        from w2t_bkin.config import ConfigValidationError, load_settings

        non_existent_path = tmp_path / "does_not_exist.toml"

        # Act & Assert
        with pytest.raises(ConfigValidationError) as exc_info:
            load_settings(non_existent_path)

        # Should include path in error message
        assert str(non_existent_path) in str(exc_info.value) or "not found" in str(exc_info.value).lower()

    def test_Should_RaiseDescriptiveError_When_InvalidTOML_MR4(self, tmp_path: Path):
        """THE MODULE SHALL raise ConfigValidationError on TOML parse errors.

        Requirements: MR-4
        Issue: Config module - TOML syntax error
        """
        # Arrange
        from w2t_bkin.config import ConfigValidationError, load_settings

        config_path = tmp_path / "invalid.toml"
        config_path.write_text(
            """
[project
name = "unclosed-section"
"""
        )

        # Act & Assert
        with pytest.raises(ConfigValidationError) as exc_info:
            load_settings(config_path)

        # Should indicate TOML parsing issue
        assert "toml" in str(exc_info.value).lower() or "parse" in str(exc_info.value).lower()

    def test_Should_IncludeOffendingKey_When_ValidationFails_MR4(self, tmp_path: Path):
        """THE MODULE SHALL include offending key in error message.

        Requirements: MR-4
        Issue: Config module - Error message clarity
        """
        # Arrange
        from w2t_bkin.config import ConfigValidationError, load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test"
n_cameras = -5
"""
        )

        # Act & Assert
        with pytest.raises(ConfigValidationError) as exc_info:
            load_settings(config_path)

        # Should mention the problematic field
        error_msg = str(exc_info.value).lower()
        assert "n_cameras" in error_msg or "cameras" in error_msg

    def test_Should_ProvideHint_When_CommonMistake_MR4(self, tmp_path: Path):
        """THE MODULE SHALL provide hints for common configuration mistakes.

        Requirements: MR-4
        Issue: Config module - Helpful error messages
        """
        # Arrange
        from w2t_bkin.config import ConfigValidationError, load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
# Common mistake: wrong key name
project_name = "test"
n_cameras = 5
"""
        )

        # Act & Assert
        with pytest.raises(ConfigValidationError) as exc_info:
            load_settings(config_path)

        # Should provide helpful error
        assert "name" in str(exc_info.value).lower()


class TestNoSideEffects:
    """Test that config loading has no side effects (M-NFR-3)."""

    def test_Should_NotModifyFiles_When_LoadingConfig_MNFR3(self, tmp_path: Path):
        """THE MODULE SHALL have no side-effects beyond reading files.

        Requirements: M-NFR-3
        Issue: Config module - No side effects
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_content = """
[project]
name = "test"
n_cameras = 5
"""
        config_path.write_text(config_content)
        original_mtime = config_path.stat().st_mtime

        # Act
        load_settings(config_path)

        # Assert - File should not be modified
        assert config_path.read_text() == config_content
        assert config_path.stat().st_mtime == original_mtime

    def test_Should_NotCreateFiles_When_LoadingConfig_MNFR3(self, tmp_path: Path):
        """THE MODULE SHALL not create any files during loading.

        Requirements: M-NFR-3
        Issue: Config module - Read-only operation
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test"
n_cameras = 5
"""
        )

        files_before = set(tmp_path.rglob("*"))

        # Act
        load_settings(config_path)

        # Assert - No new files created
        files_after = set(tmp_path.rglob("*"))
        assert files_before == files_after


class TestConfigSerialization:
    """Test configuration serialization for provenance (NFR-11)."""

    def test_Should_SerializeToDict_When_Requested_NFR11(self, tmp_path: Path):
        """THE MODULE SHALL support serialization to dict for provenance.

        Requirements: NFR-11 (Provenance)
        Issue: Config module - Serialization
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test-project"
n_cameras = 5

[sync]
tolerance_ms = 2.0
"""
        )

        # Act
        settings = load_settings(config_path)
        settings_dict = settings.model_dump()  # Pydantic v2 method

        # Assert
        assert isinstance(settings_dict, dict)
        assert settings_dict["project"]["name"] == "test-project"
        assert settings_dict["sync"]["tolerance_ms"] == 2.0

    def test_Should_SerializeToJSON_When_Requested_NFR11(self, tmp_path: Path):
        """THE MODULE SHALL support JSON serialization for embedding in NWB.

        Requirements: NFR-11 (Provenance)
        Issue: Config module - JSON serialization
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test-project"
n_cameras = 5
"""
        )

        # Act
        settings = load_settings(config_path)
        settings_json = settings.model_dump_json()

        # Assert
        assert isinstance(settings_json, str)
        parsed = json.loads(settings_json)
        assert parsed["project"]["name"] == "test-project"

    def test_Should_RoundTrip_When_SerializingAndDeserializing_MNFR1(self, tmp_path: Path):
        """THE MODULE SHALL support round-trip serialization.

        Requirements: M-NFR-1 (Deterministic), Design - Testing
        Issue: Config module - Round-trip stability
        """
        # Arrange
        from w2t_bkin.config import load_settings

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            """
[project]
name = "test-project"
n_cameras = 5

[sync]
tolerance_ms = 2.0
primary_clock = "cam0"
"""
        )

        # Act
        settings1 = load_settings(config_path)
        serialized = settings1.model_dump()

        # Reconstruct from dict
        from w2t_bkin.config import Settings

        settings2 = Settings(**serialized)

        # Assert - Values should be identical
        assert settings1.project.name == settings2.project.name
        assert settings1.project.n_cameras == settings2.project.n_cameras
        assert settings1.sync.tolerance_ms == settings2.sync.tolerance_ms
