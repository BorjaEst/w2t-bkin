"""Pytest configuration and shared fixtures for the w2t_bkin project.

Fixtures here are intentionally minimal during the design phase; they will
expand as modules gain implementation. The goal now is to provide a stable
scaffold for future unit and integration tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def pytest_configure(config):
    """Register custom markers for test categorization."""
    config.addinivalue_line("markers", "unit: Unit tests for pure function logic")
    config.addinivalue_line("markers", "integration: End-to-end pipeline tests with multiple stages")
    config.addinivalue_line("markers", "cli: CLI command invocation and subcommand tests")
    config.addinivalue_line("markers", "validation: Quality gate tests (lint, type, nwb)")
    config.addinivalue_line("markers", "property: Property-based tests for invariants")
    config.addinivalue_line("markers", "slow: Tests taking longer than 1 second")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return repository root path."""
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def src_root(repo_root: Path) -> Path:
    return repo_root / "src" / "w2t_bkin"


@pytest.fixture()
def temp_workdir(tmp_path: Path) -> Path:
    """Provide an isolated temporary working directory for tests."""
    return tmp_path


@pytest.fixture()
def dummy_manifest(tmp_path: Path) -> Path:
    """Create a minimal dummy manifest file for tests that need one.

    This is a placeholder; real fields will appear once ingest implementation exists.
    """
    manifest = {
        "session_id": "test_session",
        "videos": [],
        "sync": [],
        "config_snapshot": {},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


@pytest.fixture()
def synthetic_session(tmp_path: Path) -> Path:
    """Create a minimal synthetic session directory with stub files.

    Provides structure for integration tests without actual video data.
    Files contain metadata only; video frames and sync signals are mocked.
    """
    session_dir = tmp_path / "session_synthetic_001"
    session_dir.mkdir()

    # Create 5 stub video metadata files (no actual frames)
    for cam_id in range(5):
        video_stub = session_dir / f"cam{cam_id}.mp4.meta"
        video_stub.write_text(
            json.dumps(
                {
                    "camera_id": cam_id,
                    "codec": "h264",
                    "fps": 30.0,
                    "duration": 10.0,
                    "frame_count": 300,
                    "resolution": [640, 480],
                }
            )
        )

    # Create stub TTL sync log (10 pulses, 30 Hz)
    sync_log = session_dir / "sync_ttl.csv"
    sync_log.write_text("timestamp_s,camera_id,pulse\n" + "\n".join([f"{i/30.0},{i%5},1" for i in range(50)]))

    # Create stub NDJSON event logs
    training_log = session_dir / "behavior_training.ndjson"
    training_log.write_text("\n".join([json.dumps({"t": i * 0.5, "trial": i // 10, "phase": "baseline", "valid": True}) for i in range(20)]))

    trial_stats = session_dir / "behavior_trial_stats.ndjson"
    trial_stats.write_text("\n".join([json.dumps({"trial_id": i, "duration": 5.0, "outcome": "success"}) for i in range(2)]))

    return session_dir


@pytest.fixture()
def mock_config_toml(tmp_path: Path) -> Path:
    """Create a minimal TOML configuration file for CLI and config tests."""
    config = tmp_path / "config.toml"
    config.write_text(
        """
[project]
name = "test-project"
n_cameras = 5

[paths]
raw_root = "data/raw"
intermediate_root = "data/interim"
output_root = "data/processed"
models_root = "models"

[sync]
primary_clock = "cam0"
tolerance_ms = 2.0

[nwb]
link_external_video = true
"""
    )
    return config
