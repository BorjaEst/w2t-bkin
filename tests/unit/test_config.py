"""Unit tests for config module.

Requirements: FR-10 (Configuration-driven), NFR-10 (Type safety)
Design: requirements.md (Configuration keys), design.md §21.1 (Layer 1)
"""

import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from w2t_bkin.config import (
    ENV_PREFIX,
    Settings,
    load_settings,
)


# ============================================================================
# Test: Settings Creation and Defaults
# ============================================================================


def test_settings_creation_with_defaults():
    """WHEN creating Settings with no arguments, THE SYSTEM SHALL use default values."""
    settings = Settings()

    assert settings.project.name == "w2t-bkin-pipeline"
    assert settings.project.n_cameras == 5
    assert settings.paths.raw_root == Path("data/raw")
    assert settings.video.fps == 30.0
    assert settings.logging.level == "INFO"


def test_settings_creation_with_partial_config():
    """WHEN creating Settings with partial config, THE SYSTEM SHALL merge with defaults."""
    settings = Settings(project={"name": "custom"})

    assert settings.project.name == "custom"
    assert settings.project.n_cameras == 5  # Default


def test_settings_rejects_extra_keys():
    """WHEN creating Settings with unknown keys, THE SYSTEM SHALL raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(unknown_key="value")

    assert "extra_forbidden" in str(exc_info.value).lower()


# ============================================================================
# Test: ProjectConfig Validation
# ============================================================================


def test_project_n_cameras_valid_range():
    """WHEN n_cameras is in range [1-10], THE SYSTEM SHALL accept the value."""
    settings = Settings(project={"n_cameras": 1})
    assert settings.project.n_cameras == 1

    settings = Settings(project={"n_cameras": 10})
    assert settings.project.n_cameras == 10


def test_project_n_cameras_below_minimum():
    """WHEN n_cameras is less than 1, THE SYSTEM SHALL raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(project={"n_cameras": 0})

    assert "greater_than_equal" in str(exc_info.value).lower()


def test_project_n_cameras_above_maximum():
    """WHEN n_cameras is greater than 10, THE SYSTEM SHALL raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(project={"n_cameras": 11})

    assert "less_than_equal" in str(exc_info.value).lower()


# ============================================================================
# Test: PathsConfig Expansion
# ============================================================================


def test_paths_expand_home_directory():
    """WHEN paths contain ~, THE SYSTEM SHALL expand to user home directory."""
    settings = Settings(paths={"raw_root": "~/data"})

    assert "~" not in str(settings.paths.raw_root)
    assert str(settings.paths.raw_root).startswith(str(Path.home()))


def test_paths_expand_environment_variables():
    """WHEN paths contain env vars, THE SYSTEM SHALL expand them."""
    os.environ["TEST_VAR"] = "/test/path"
    try:
        settings = Settings(paths={"raw_root": "$TEST_VAR/data"})
        assert str(settings.paths.raw_root) == "/test/path/data"
    finally:
        del os.environ["TEST_VAR"]


def test_paths_are_path_objects():
    """WHEN accessing paths, THE SYSTEM SHALL provide Path objects."""
    settings = Settings()

    assert isinstance(settings.paths.raw_root, Path)
    assert isinstance(settings.paths.intermediate_root, Path)
    assert isinstance(settings.paths.output_root, Path)
    assert isinstance(settings.paths.models_root, Path)


# ============================================================================
# Test: VideoConfig Validation
# ============================================================================


def test_video_fps_positive():
    """WHEN video.fps is positive, THE SYSTEM SHALL accept the value."""
    settings = Settings(video={"fps": 60.0})
    assert settings.video.fps == 60.0


def test_video_fps_zero():
    """WHEN video.fps is zero, THE SYSTEM SHALL raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(video={"fps": 0.0})

    assert "greater_than" in str(exc_info.value).lower()


def test_video_fps_negative():
    """WHEN video.fps is negative, THE SYSTEM SHALL raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(video={"fps": -30.0})

    assert "greater_than" in str(exc_info.value).lower()


def test_video_transcode_crf_valid_range():
    """WHEN transcode.crf is in range [0-51], THE SYSTEM SHALL accept the value."""
    settings = Settings(video={"transcode": {"crf": 0}})
    assert settings.video.transcode.crf == 0

    settings = Settings(video={"transcode": {"crf": 51}})
    assert settings.video.transcode.crf == 51


def test_video_transcode_crf_out_of_range():
    """WHEN transcode.crf is outside [0-51], THE SYSTEM SHALL raise ValidationError."""
    with pytest.raises(ValidationError):
        Settings(video={"transcode": {"crf": -1}})

    with pytest.raises(ValidationError):
        Settings(video={"transcode": {"crf": 52}})


def test_video_transcode_keyint_positive():
    """WHEN transcode.keyint is >= 1, THE SYSTEM SHALL accept the value."""
    settings = Settings(video={"transcode": {"keyint": 1}})
    assert settings.video.transcode.keyint == 1


def test_video_transcode_keyint_zero():
    """WHEN transcode.keyint is zero, THE SYSTEM SHALL raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(video={"transcode": {"keyint": 0}})

    assert "greater_than_equal" in str(exc_info.value).lower()


# ============================================================================
# Test: SyncConfig Validation
# ============================================================================


def test_sync_tolerance_ms_non_negative():
    """WHEN sync.tolerance_ms is >= 0, THE SYSTEM SHALL accept the value."""
    settings = Settings(sync={"tolerance_ms": 0.0})
    assert settings.sync.tolerance_ms == 0.0

    settings = Settings(sync={"tolerance_ms": 5.0})
    assert settings.sync.tolerance_ms == 5.0


def test_sync_tolerance_ms_negative():
    """WHEN sync.tolerance_ms is negative, THE SYSTEM SHALL raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(sync={"tolerance_ms": -1.0})

    assert "greater_than_equal" in str(exc_info.value).lower()


def test_sync_ttl_channel_polarity_valid():
    """WHEN ttl_channel.polarity is 'rising' or 'falling', THE SYSTEM SHALL accept."""
    settings = Settings(
        sync={"ttl_channels": [{"path": "test", "name": "test", "polarity": "rising"}]}
    )
    assert settings.sync.ttl_channels[0].polarity == "rising"

    settings = Settings(
        sync={"ttl_channels": [{"path": "test", "name": "test", "polarity": "falling"}]}
    )
    assert settings.sync.ttl_channels[0].polarity == "falling"


def test_sync_ttl_channel_polarity_invalid():
    """WHEN ttl_channel.polarity is invalid, THE SYSTEM SHALL raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            sync={
                "ttl_channels": [
                    {"path": "test", "name": "test", "polarity": "invalid"}
                ]
            }
        )

    assert "polarity must be" in str(exc_info.value).lower()


# ============================================================================
# Test: LoggingConfig Validation
# ============================================================================


@pytest.mark.parametrize(
    "level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "debug", "info"]
)
def test_logging_level_valid(level: str):
    """WHEN logging.level is valid, THE SYSTEM SHALL accept and normalize to uppercase."""
    settings = Settings(logging={"level": level})
    assert settings.logging.level == level.upper()


def test_logging_level_invalid():
    """WHEN logging.level is invalid, THE SYSTEM SHALL raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(logging={"level": "INVALID"})

    assert "level must be one of" in str(exc_info.value).lower()


# ============================================================================
# Test: TOML Loading
# ============================================================================


def test_load_settings_from_valid_toml(tmp_path: Path):
    """WHEN loading valid TOML file, THE SYSTEM SHALL parse and validate successfully."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[project]
name = "test-project"
n_cameras = 3

[video]
fps = 60.0

[logging]
level = "DEBUG"
"""
    )

    settings = load_settings(config_file)

    assert settings.project.name == "test-project"
    assert settings.project.n_cameras == 3
    assert settings.video.fps == 60.0
    assert settings.logging.level == "DEBUG"


def test_load_settings_from_nonexistent_file():
    """WHEN loading nonexistent TOML file, THE SYSTEM SHALL raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError) as exc_info:
        load_settings("/nonexistent/config.toml")

    assert "not found" in str(exc_info.value).lower()


def test_load_settings_with_invalid_toml(tmp_path: Path):
    """WHEN loading invalid TOML file, THE SYSTEM SHALL raise appropriate error."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("[project]\nname = ")  # Invalid TOML

    with pytest.raises(Exception):  # tomllib.TOMLDecodeError or similar
        load_settings(config_file)


def test_load_settings_with_validation_error(tmp_path: Path):
    """WHEN TOML contains invalid config, THE SYSTEM SHALL raise ValidationError."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[project]
n_cameras = 100  # Invalid: > 10
"""
    )

    with pytest.raises(ValidationError):
        load_settings(config_file)


def test_load_settings_without_toml():
    """WHEN loading without TOML file, THE SYSTEM SHALL use defaults."""
    settings = load_settings(None)

    assert settings.project.name == "w2t-bkin-pipeline"
    assert settings.project.n_cameras == 5


# ============================================================================
# Test: Environment Variable Overrides
# ============================================================================


def test_env_override_simple_value(tmp_path: Path):
    """WHEN env var overrides simple value, THE SYSTEM SHALL apply override."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[project]
name = "original"
"""
    )

    os.environ[f"{ENV_PREFIX}PROJECT__NAME"] = "overridden"
    try:
        settings = load_settings(config_file)
        assert settings.project.name == "overridden"
    finally:
        del os.environ[f"{ENV_PREFIX}PROJECT__NAME"]


def test_env_override_nested_value(tmp_path: Path):
    """WHEN env var overrides nested value, THE SYSTEM SHALL apply override."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[video.transcode]
enabled = false
"""
    )

    os.environ[f"{ENV_PREFIX}VIDEO__TRANSCODE__ENABLED"] = "true"
    try:
        settings = load_settings(config_file)
        assert settings.video.transcode.enabled is True
    finally:
        del os.environ[f"{ENV_PREFIX}VIDEO__TRANSCODE__ENABLED"]


def test_env_override_numeric_values(tmp_path: Path):
    """WHEN env var contains numeric string, THE SYSTEM SHALL parse correctly."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("")

    os.environ[f"{ENV_PREFIX}PROJECT__N_CAMERAS"] = "7"
    os.environ[f"{ENV_PREFIX}VIDEO__FPS"] = "120.0"
    try:
        settings = load_settings(config_file)
        assert settings.project.n_cameras == 7
        assert settings.video.fps == 120.0
    finally:
        del os.environ[f"{ENV_PREFIX}PROJECT__N_CAMERAS"]
        del os.environ[f"{ENV_PREFIX}VIDEO__FPS"]


def test_env_override_boolean_values():
    """WHEN env var contains boolean string, THE SYSTEM SHALL parse correctly."""
    test_cases = [
        ("true", True),
        ("True", True),
        ("yes", True),
        ("1", True),
        ("false", False),
        ("False", False),
        ("no", False),
        ("0", False),
    ]

    for env_value, expected in test_cases:
        os.environ[f"{ENV_PREFIX}VIDEO__TRANSCODE__ENABLED"] = env_value
        try:
            settings = load_settings(None)
            assert settings.video.transcode.enabled == expected
        finally:
            del os.environ[f"{ENV_PREFIX}VIDEO__TRANSCODE__ENABLED"]


def test_env_override_without_toml():
    """WHEN env vars set without TOML, THE SYSTEM SHALL apply to defaults."""
    os.environ[f"{ENV_PREFIX}PROJECT__NAME"] = "env-only"
    try:
        settings = load_settings(None)
        assert settings.project.name == "env-only"
    finally:
        del os.environ[f"{ENV_PREFIX}PROJECT__NAME"]


def test_env_override_precedence(tmp_path: Path):
    """WHEN both TOML and env var set, THE SYSTEM SHALL prefer env var."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[project]
name = "toml-value"
"""
    )

    os.environ[f"{ENV_PREFIX}PROJECT__NAME"] = "env-value"
    try:
        settings = load_settings(config_file)
        assert settings.project.name == "env-value"
    finally:
        del os.environ[f"{ENV_PREFIX}PROJECT__NAME"]


# ============================================================================
# Test: Complex TOML Structures
# ============================================================================


def test_load_settings_with_ttl_channels(tmp_path: Path):
    """WHEN TOML contains TTL channel array, THE SYSTEM SHALL parse correctly."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[[sync.ttl_channels]]
path = "nidaq/sync.bin"
name = "frame_trigger"
polarity = "rising"

[[sync.ttl_channels]]
path = "nidaq/sync2.bin"
name = "trial_trigger"
polarity = "falling"
"""
    )

    settings = load_settings(config_file)

    assert len(settings.sync.ttl_channels) == 2
    assert settings.sync.ttl_channels[0].name == "frame_trigger"
    assert settings.sync.ttl_channels[0].polarity == "rising"
    assert settings.sync.ttl_channels[1].name == "trial_trigger"
    assert settings.sync.ttl_channels[1].polarity == "falling"


def test_load_settings_with_all_sections(tmp_path: Path):
    """WHEN TOML contains all config sections, THE SYSTEM SHALL parse all correctly."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[project]
name = "full-test"
n_cameras = 4

[paths]
raw_root = "data/raw"
intermediate_root = "data/interim"
output_root = "data/processed"
models_root = "models"

[session]
id = "session_001"
subject_id = "mouse_123"
date = "2024-01-15"
experimenter = "John Doe"
description = "Test session"
sex = "M"
age = "P60"
genotype = "WT"

[video]
pattern = "**/*.avi"
fps = 25.0

[video.transcode]
enabled = true
codec = "h264"
crf = 20
preset = "fast"
keyint = 15

[sync]
tolerance_ms = 1.5
drop_frame_max_gap_ms = 50.0
primary_clock = "cam1"

[[sync.ttl_channels]]
path = "sync.bin"
name = "trigger"
polarity = "rising"

[labels.dlc]
model = "model.pb"
run_inference = true

[labels.sleap]
model = "sleap.h5"
run_inference = false

[facemap]
run = true
roi = "face"

[nwb]
link_external_video = false
file_name = "session.nwb"
session_description = "Test"
lab = "Lab Name"
institution = "Institution Name"

[qc]
generate_report = false
out = "qc_output"

[logging]
level = "WARNING"
structured = true

[events]
patterns = ["*.json", "*.ndjson"]
format = "json"
"""
    )

    settings = load_settings(config_file)

    # Spot-check all sections
    assert settings.project.name == "full-test"
    assert settings.project.n_cameras == 4
    assert settings.session.id == "session_001"
    assert settings.video.fps == 25.0
    assert settings.video.transcode.enabled is True
    assert settings.sync.tolerance_ms == 1.5
    assert len(settings.sync.ttl_channels) == 1
    assert settings.labels.dlc.run_inference is True
    assert settings.facemap.run is True
    assert settings.nwb.link_external_video is False
    assert settings.qc.generate_report is False
    assert settings.logging.level == "WARNING"
    assert settings.logging.structured is True
    assert settings.events.format == "json"


# ============================================================================
# Test: Edge Cases
# ============================================================================


def test_settings_empty_strings_allowed():
    """WHEN config contains empty strings, THE SYSTEM SHALL accept them."""
    settings = Settings(
        session={
            "id": "",
            "subject_id": "",
        }
    )

    assert settings.session.id == ""
    assert settings.session.subject_id == ""


def test_settings_default_lists_are_empty():
    """WHEN accessing default lists, THE SYSTEM SHALL provide empty lists."""
    settings = Settings()

    assert settings.sync.ttl_channels == []
    assert isinstance(settings.sync.ttl_channels, list)


def test_settings_nested_defaults():
    """WHEN accessing nested config without TOML, THE SYSTEM SHALL use nested defaults."""
    settings = Settings()

    assert settings.video.transcode.enabled is False
    assert settings.video.transcode.codec == "libx264"
    assert settings.labels.dlc.run_inference is False


def test_path_config_with_relative_paths():
    """WHEN paths are relative, THE SYSTEM SHALL preserve them as relative Paths."""
    settings = Settings(
        paths={
            "raw_root": "relative/path",
        }
    )

    assert settings.paths.raw_root == Path("relative/path")
    assert not settings.paths.raw_root.is_absolute()


def test_multiple_env_overrides_same_section():
    """WHEN multiple env vars target same section, THE SYSTEM SHALL apply all."""
    os.environ[f"{ENV_PREFIX}PROJECT__NAME"] = "env-name"
    os.environ[f"{ENV_PREFIX}PROJECT__N_CAMERAS"] = "8"
    try:
        settings = load_settings(None)
        assert settings.project.name == "env-name"
        assert settings.project.n_cameras == 8
    finally:
        del os.environ[f"{ENV_PREFIX}PROJECT__NAME"]
        del os.environ[f"{ENV_PREFIX}PROJECT__N_CAMERAS"]
