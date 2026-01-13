"""Unit tests for template generation and data init."""

from pathlib import Path

import pytest
import tomli

from w2t_bkin.data.manager import init_experiment


class TestDataInitTemplates:
    """Test that data init creates correct templates."""

    def test_configuration_toml_no_paths(self, tmp_path):
        """Verify generated configuration.toml has no [paths] section."""
        result = init_experiment(
            root_path=tmp_path,
            lab="Test Lab",
            institution="Test Institution",
            experimenters=["Tester"],
            interactive=False,
        )

        assert result is True

        config_path = tmp_path / "configuration.toml"
        assert config_path.exists()

        # Parse TOML
        config = tomli.loads(config_path.read_text())

        # Verify NO [paths] section
        assert "paths" not in config, "configuration.toml should not contain [paths] section"

        # Verify NO [project] section (identity comes from metadata.toml)
        assert "project" not in config, "configuration.toml should not contain [project] section"

        # Verify expected sections exist
        assert "synchronization" in config
        assert "verification" in config

    def test_workers_env_created(self, tmp_path):
        """Verify .workers/.env template is valid (CLI layer creates it).

        Note: The actual .workers/.env creation happens in cli/data.py,
        not in the pure init_experiment() function. This test verifies
        the template exists and is valid.
        """
        # Just verify the template exists and is readable
        from w2t_bkin.cli.utils import _load_template

        try:
            env_template = _load_template(".env.template")
            assert "W2T_DOCKER_IMAGE" in env_template
            assert "ghcr.io/borjaest/w2t-bkin" in env_template
        except FileNotFoundError:
            pytest.fail(".env.template not found in package")

    def test_workers_env_skip(self, tmp_path):
        """Verify --skip-docker-env prevents .workers/.env creation.

        This is tested via CLI integration test since the skip_docker_env
        flag is in CLI, not in the pure manager function.
        """
        # Placeholder - actual test would be integration test
        pass

    def test_standard_toml_no_paths(self):
        """Verify base config has no [paths] section."""
        package_root = Path(__file__).parent.parent.parent.parent
        standard_config = package_root / "configs" / "standard.toml"

        assert standard_config.exists(), "configs/standard.toml not found"

        config = tomli.loads(standard_config.read_text())

        assert "paths" not in config, "configs/standard.toml should not contain [paths] section"

    def test_configuration_template_no_paths(self):
        """Verify user-facing template has no [paths] section."""
        package_root = Path(__file__).parent.parent.parent.parent
        template_config = package_root / "templates" / "configuration.toml"

        assert template_config.exists(), "templates/configuration.toml not found"

        config = tomli.loads(template_config.read_text())

        assert "paths" not in config, "templates/configuration.toml should not contain [paths] section"

    def test_data_directory_structure(self, tmp_path):
        """Verify correct directory structure is created."""
        result = init_experiment(
            root_path=tmp_path,
            lab="Test Lab",
            institution="Test Institution",
            experimenters=["Tester"],
            interactive=False,
        )

        assert result is True

        # Verify directories
        assert (tmp_path / "data" / "raw").is_dir()
        assert (tmp_path / "data" / "interim").is_dir()
        assert (tmp_path / "data" / "processed").is_dir()
        assert (tmp_path / "data" / "external").is_dir()
        assert (tmp_path / "models").is_dir()

        # Verify metadata
        assert (tmp_path / "data" / "raw" / "metadata.toml").is_file()

    def test_env_template_content(self):
        """Verify .env template has updated documentation."""
        from w2t_bkin.cli.utils import _load_template

        try:
            env_template = _load_template(".env.template")
        except FileNotFoundError:
            pytest.fail(".env.template not found in package")

        # Should mention deployment mode
        assert "Production" in env_template or "Development" in env_template

        # Should document path configuration
        assert "W2T_RAW_ROOT" in env_template or "path" in env_template.lower()
