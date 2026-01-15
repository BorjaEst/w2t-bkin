"""Unit tests for pose mode configuration validation.

Tests the mode field validation in DLCConfig and SLEAPConfig,
including backward compatibility with the old 'enabled' field.
"""

from pathlib import Path

from pydantic import ValidationError
import pytest

from w2t_bkin.config import DLCConfig, SLEAPConfig


class TestDLCConfigMode:
    """Test DLCConfig mode field validation."""

    def test_default_mode_is_auto(self):
        """Test that default mode is 'auto'."""
        config = DLCConfig()
        assert config.mode == "auto"

    def test_mode_off_valid(self):
        """Test that mode='off' is valid."""
        config = DLCConfig(mode="off")
        assert config.mode == "off"

    def test_mode_discover_valid(self):
        """Test that mode='discover' is valid."""
        config = DLCConfig(mode="discover")
        assert config.mode == "discover"

    def test_mode_generate_valid(self):
        """Test that mode='generate' is valid."""
        config = DLCConfig(mode="generate")
        assert config.mode == "generate"

    def test_mode_auto_valid(self):
        """Test that mode='auto' is valid."""
        config = DLCConfig(mode="auto")
        assert config.mode == "auto"

    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises ValidationError."""
        with pytest.raises(ValidationError):
            DLCConfig(mode="invalid_mode")


class TestDLCConfigBackwardCompatibility:
    """Test DLCConfig backward compatibility with 'enabled' field."""

    def test_enabled_false_becomes_mode_off(self):
        """Test that enabled=False migrates to mode='off'."""
        config = DLCConfig(enabled=False)
        assert config.mode == "off"
        # enabled field should not exist after migration
        assert not hasattr(config, "enabled")

    def test_enabled_false_overrides_mode(self):
        """Test that enabled=False overrides contradictory mode."""
        config = DLCConfig(enabled=False, mode="discover")
        assert config.mode == "off"

    def test_enabled_true_keeps_mode(self):
        """Test that enabled=True preserves explicit mode."""
        config = DLCConfig(enabled=True, mode="discover")
        assert config.mode == "discover"

    def test_enabled_true_mode_off_becomes_auto(self):
        """Test that enabled=True + mode='off' contradiction resolves to auto."""
        config = DLCConfig(enabled=True, mode="off")
        assert config.mode == "auto"

    def test_enabled_true_without_mode_defaults_auto(self):
        """Test that enabled=True without mode defaults to auto."""
        config = DLCConfig(enabled=True)
        assert config.mode == "auto"


class TestSLEAPConfigMode:
    """Test SLEAPConfig mode field validation."""

    def test_default_mode_is_auto(self):
        """Test that default mode is 'auto'."""
        config = SLEAPConfig()
        assert config.mode == "auto"

    def test_mode_off_valid(self):
        """Test that mode='off' is valid."""
        config = SLEAPConfig(mode="off")
        assert config.mode == "off"

    def test_mode_discover_valid(self):
        """Test that mode='discover' is valid."""
        config = SLEAPConfig(mode="discover")
        assert config.mode == "discover"

    def test_mode_auto_valid(self):
        """Test that mode='auto' is valid."""
        config = SLEAPConfig(mode="auto")
        assert config.mode == "auto"

    def test_generate_mode_raises_error(self):
        """Test that mode='generate' raises error (not implemented)."""
        with pytest.raises(ValidationError, match="not yet implemented"):
            SLEAPConfig(mode="generate")

    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises ValidationError."""
        with pytest.raises(ValidationError):
            SLEAPConfig(mode="invalid_mode")


class TestSLEAPConfigBackwardCompatibility:
    """Test SLEAPConfig backward compatibility with 'enabled' field."""

    def test_enabled_false_becomes_mode_off(self):
        """Test that enabled=False migrates to mode='off'."""
        config = SLEAPConfig(enabled=False)
        assert config.mode == "off"
        # enabled field should not exist after migration
        assert not hasattr(config, "enabled")

    def test_enabled_false_overrides_mode(self):
        """Test that enabled=False overrides contradictory mode."""
        config = SLEAPConfig(enabled=False, mode="discover")
        assert config.mode == "off"

    def test_enabled_true_keeps_mode(self):
        """Test that enabled=True preserves explicit mode."""
        config = SLEAPConfig(enabled=True, mode="discover")
        assert config.mode == "discover"

    def test_enabled_true_mode_off_becomes_auto(self):
        """Test that enabled=True + mode='off' contradiction resolves to auto."""
        config = SLEAPConfig(enabled=True, mode="off")
        assert config.mode == "auto"
