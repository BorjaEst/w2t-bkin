"""Unit tests for pose mode configuration validation.

Tests the mode field validation in DLCConfig and SLEAPConfig,
including mode/model_path consistency checks.
"""

from pathlib import Path

from pydantic import ValidationError
import pytest

from w2t_bkin.config import DLCConfig, SLEAPConfig


class TestDLCConfigMode:
    """Test DLCConfig mode field validation."""

    def test_default_mode_is_auto(self):
        """Test that default mode is 'auto' when enabled."""
        config = DLCConfig(enabled=True)
        assert config.mode == "auto"
        assert config.enabled is True

    def test_default_mode_auto_with_enabled_false(self):
        """Test that default enabled=False auto-corrects mode to 'off'."""
        config = DLCConfig()  # enabled defaults to False
        assert config.enabled is False
        assert config.mode == "off"  # Auto-corrected by validator

    def test_mode_off_sets_enabled_false(self):
        """Test that mode='off' sets enabled=False."""
        config = DLCConfig(enabled=True, mode="off")
        assert config.enabled is False
        assert config.mode == "off"

    def test_enabled_false_sets_mode_off(self):
        """Test that enabled=False sets mode='off'."""
        config = DLCConfig(enabled=False, mode="generate")
        assert config.mode == "off"
        assert config.enabled is False

    def test_generate_mode_requires_model_path(self):
        """Test that mode='generate' requires model_path."""
        with pytest.raises(ValidationError, match="requires model_path"):
            DLCConfig(enabled=True, mode="generate", model_path=None)

    def test_generate_mode_with_model_path_valid(self):
        """Test that mode='generate' with model_path is valid."""
        config = DLCConfig(enabled=True, mode="generate", model_path=Path("models/dlc_model/config.yaml"))
        assert config.mode == "generate"
        assert config.model_path == Path("models/dlc_model/config.yaml")

    def test_discover_mode_without_model_path_valid(self):
        """Test that mode='discover' without model_path is valid."""
        config = DLCConfig(enabled=True, mode="discover")
        assert config.mode == "discover"
        assert config.model_path is None

    def test_discover_mode_with_model_path_valid(self):
        """Test that mode='discover' with model_path is valid (path ignored)."""
        config = DLCConfig(enabled=True, mode="discover", model_path=Path("models/dlc_model/config.yaml"))
        assert config.mode == "discover"
        assert config.model_path == Path("models/dlc_model/config.yaml")

    def test_auto_mode_without_model_path(self):
        """Test that mode='auto' without model_path is valid."""
        config = DLCConfig(enabled=True, mode="auto")
        assert config.mode == "auto"
        assert config.model_path is None

    def test_auto_mode_with_model_path(self):
        """Test that mode='auto' with model_path is valid."""
        config = DLCConfig(enabled=True, mode="auto", model_path=Path("models/dlc_model/config.yaml"))
        assert config.mode == "auto"
        assert config.model_path == Path("models/dlc_model/config.yaml")

    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises ValidationError."""
        with pytest.raises(ValidationError):
            DLCConfig(enabled=True, mode="invalid_mode")


class TestSLEAPConfigMode:
    """Test SLEAPConfig mode field validation."""

    def test_default_mode_is_auto(self):
        """Test that default mode is 'auto' when enabled."""
        config = SLEAPConfig(enabled=True)
        assert config.mode == "auto"
        assert config.enabled is True

    def test_default_mode_auto_with_enabled_false(self):
        """Test that default enabled=False auto-corrects mode to 'off'."""
        config = SLEAPConfig()  # enabled defaults to False
        assert config.enabled is False
        assert config.mode == "off"  # Auto-corrected by validator

    def test_mode_off_sets_enabled_false(self):
        """Test that mode='off' sets enabled=False."""
        config = SLEAPConfig(enabled=True, mode="off")
        assert config.enabled is False
        assert config.mode == "off"

    def test_enabled_false_sets_mode_off(self):
        """Test that enabled=False sets mode='off'."""
        config = SLEAPConfig(enabled=False, mode="discover")
        assert config.mode == "off"
        assert config.enabled is False

    def test_generate_mode_raises_error(self):
        """Test that mode='generate' raises error (not implemented)."""
        with pytest.raises(ValidationError, match="not yet implemented"):
            SLEAPConfig(enabled=True, mode="generate")

    def test_discover_mode_valid(self):
        """Test that mode='discover' is valid."""
        config = SLEAPConfig(enabled=True, mode="discover")
        assert config.mode == "discover"

    def test_auto_mode_valid(self):
        """Test that mode='auto' is valid."""
        config = SLEAPConfig(enabled=True, mode="auto")
        assert config.mode == "auto"

    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises ValidationError."""
        with pytest.raises(ValidationError):
            SLEAPConfig(enabled=True, mode="invalid_mode")


class TestDLCConfigModelPathResolution:
    """Test DLCConfig model_path resolution."""

    def test_resolve_model_path_none(self):
        """Test resolving None model_path."""
        config = DLCConfig(enabled=True, mode="discover")
        models_root = Path("/models")
        assert config.resolve_model_path(models_root) is None

    def test_resolve_model_path_absolute(self):
        """Test resolving absolute model_path."""
        absolute_path = Path("/absolute/models/dlc_model/config.yaml")
        config = DLCConfig(enabled=True, mode="generate", model_path=absolute_path)
        models_root = Path("/models")
        resolved = config.resolve_model_path(models_root)
        assert resolved == absolute_path

    def test_resolve_model_path_relative(self):
        """Test resolving relative model_path."""
        config = DLCConfig(enabled=True, mode="generate", model_path=Path("iteration-1/dlc_model/config.yaml"))
        models_root = Path("/models")
        resolved = config.resolve_model_path(models_root)
        assert resolved == Path("/models/iteration-1/dlc_model/config.yaml").resolve()


class TestSLEAPConfigModelPathResolution:
    """Test SLEAPConfig model_path resolution."""

    def test_resolve_model_path_none(self):
        """Test resolving None model_path."""
        config = SLEAPConfig(enabled=True, mode="discover")
        models_root = Path("/models")
        assert config.resolve_model_path(models_root) is None

    def test_resolve_model_path_absolute(self):
        """Test resolving absolute model_path."""
        absolute_path = Path("/absolute/models/sleap_model.h5")
        config = SLEAPConfig(enabled=True, mode="discover", model_path=absolute_path)
        models_root = Path("/models")
        resolved = config.resolve_model_path(models_root)
        assert resolved == absolute_path

    def test_resolve_model_path_relative(self):
        """Test resolving relative model_path."""
        config = SLEAPConfig(enabled=True, mode="discover", model_path=Path("sleap_model.h5"))
        models_root = Path("/models")
        resolved = config.resolve_model_path(models_root)
        assert resolved == Path("/models/sleap_model.h5").resolve()
