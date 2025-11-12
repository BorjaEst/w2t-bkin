"""Pytest configuration and shared fixtures for w2t_bkin pipeline tests.

Provides:
- Fixture data paths and session configurations
- Temporary directory management
- Mock configuration builders
- Common test utilities
"""

import json
from pathlib import Path
import shutil
from typing import Any, Dict

import pytest
import tomli

# ============================================================================
# Path Configuration
# ============================================================================


@pytest.fixture(scope="session")
def fixtures_root() -> Path:
    """Root directory containing all test fixtures."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_data_root(fixtures_root: Path) -> Path:
    """Root of the fixture data directory structure."""
    return fixtures_root / "data"


@pytest.fixture(scope="session")
def fixtures_raw_root(fixtures_data_root: Path) -> Path:
    """Raw data directory (Session-000001)."""
    return fixtures_data_root / "raw"


@pytest.fixture(scope="session")
def fixture_session_path(fixtures_raw_root: Path) -> Path:
    """Path to Session-000001 fixture."""
    return fixtures_raw_root / "Session-000001"


@pytest.fixture(scope="session")
def fixture_session_toml(fixture_session_path: Path) -> Path:
    """Path to session.toml for Session-000001."""
    return fixture_session_path / "session.toml"


# ============================================================================
# Temporary Working Directories
# ============================================================================


@pytest.fixture
def tmp_work_dir(tmp_path: Path) -> Path:
    """Temporary working directory for test outputs.

    Structure:
        tmp_path/
        ├── interim/
        ├── processed/
        └── external/
    """
    interim = tmp_path / "interim"
    processed = tmp_path / "processed"
    external = tmp_path / "external"

    interim.mkdir()
    processed.mkdir()
    external.mkdir()

    return tmp_path


@pytest.fixture
def tmp_session_copy(tmp_work_dir: Path, fixture_session_path: Path) -> Path:
    """Copy of Session-000001 in temporary raw directory for tests that modify data."""
    raw_dir = tmp_work_dir / "raw"
    raw_dir.mkdir()

    session_copy = raw_dir / "Session-000001"
    shutil.copytree(fixture_session_path, session_copy)

    return session_copy


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture
def minimal_config_dict(tmp_work_dir: Path, fixtures_raw_root: Path) -> Dict[str, Any]:
    """Minimal valid config dictionary for testing."""
    return {
        "project": {"name": "test-w2t-bkin"},
        "paths": {
            "raw_root": str(fixtures_raw_root),
            "intermediate_root": str(tmp_work_dir / "interim"),
            "output_root": str(tmp_work_dir / "processed"),
            "metadata_file": "session.toml",
            "models_root": str(tmp_work_dir / "external" / "models"),
        },
        "timebase": {"source": "nominal_rate", "mapping": "nearest", "jitter_budget_s": 0.001, "offset_s": 0.0},
        "acquisition": {"concat_strategy": "order"},
        "verification": {"mismatch_tolerance_frames": 2, "warn_on_mismatch": True},
        "bpod": {"parse": True},
        "video": {"transcode": {"enabled": False, "codec": "libx264", "crf": 23, "preset": "medium", "keyint": 300}},
        "nwb": {
            "link_external_video": True,
            "lab": "Test Lab",
            "institution": "Test Institution",
            "file_name_template": "{session_id}.nwb",
            "session_description_template": "Session {session_id}",
        },
        "qc": {"generate_report": True, "out_template": "{session_id}_qc.html", "include_verification": True},
        "logging": {"level": "INFO", "structured": True},
        "labels": {"dlc": {"run_inference": False, "model": ""}, "sleap": {"run_inference": False, "model": ""}},
        "facemap": {"run_inference": False, "ROIs": []},
    }


@pytest.fixture
def minimal_config_toml(tmp_work_dir: Path, fixtures_raw_root: Path) -> Path:
    """Minimal valid config.toml file."""
    config_path = tmp_work_dir / "config.toml"
    config_content = f"""
[project]
name = "test-w2t-bkin"

[paths]
raw_root = "{fixtures_raw_root}"
intermediate_root = "{tmp_work_dir / "interim"}"
output_root = "{tmp_work_dir / "processed"}"
metadata_file = "session.toml"
models_root = "{tmp_work_dir / "external" / "models"}"

[timebase]
source = "nominal_rate"
mapping = "nearest"
jitter_budget_s = 0.001
offset_s = 0.0

[acquisition]
concat_strategy = "order"

[verification]
mismatch_tolerance_frames = 2
warn_on_mismatch = true

[bpod]
parse = true

[video.transcode]
enabled = false
codec = "libx264"
crf = 23
preset = "medium"
keyint = 300

[nwb]
link_external_video = true
lab = "Test Lab"
institution = "Test Institution"
file_name_template = "{{session_id}}.nwb"
session_description_template = "Session {{session_id}}"

[qc]
generate_report = true
out_template = "{{session_id}}_qc.html"
include_verification = true

[logging]
level = "INFO"
structured = true

[labels.dlc]
run_inference = false
model = ""

[labels.sleap]
run_inference = false
model = ""

[facemap]
run_inference = false
ROIs = []
"""
    with open(config_path, "w") as f:
        f.write(config_content)
    return config_path


@pytest.fixture
def ttl_timebase_config_dict(minimal_config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Config with TTL timebase source."""
    config = minimal_config_dict.copy()
    config["timebase"] = {"source": "ttl", "mapping": "linear", "jitter_budget_s": 0.002, "offset_s": 0.0, "ttl_id": "ttl_camera"}
    return config


@pytest.fixture
def neuropixels_timebase_config_dict(minimal_config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Config with Neuropixels timebase source."""
    config = minimal_config_dict.copy()
    config["timebase"] = {"source": "neuropixels", "mapping": "linear", "jitter_budget_s": 0.001, "offset_s": 0.0, "neuropixels_stream": "imec0.ap"}
    return config


# ============================================================================
# Session Metadata Fixtures
# ============================================================================


@pytest.fixture
def fixture_session_dict(fixture_session_toml: Path) -> Dict[str, Any]:
    """Parsed session.toml as dictionary."""
    with open(fixture_session_toml, "rb") as f:
        return tomli.load(f)


@pytest.fixture
def expected_camera_count() -> int:
    """Expected number of cameras in Session-000001."""
    return 2


@pytest.fixture
def expected_ttl_count() -> int:
    """Expected number of TTL channels in Session-000001."""
    return 3


@pytest.fixture
def expected_bpod_file_count() -> int:
    """Expected number of Bpod files in Session-000001."""
    return 1


# ============================================================================
# Verification & Validation Fixtures
# ============================================================================


@pytest.fixture
def mock_verification_summary() -> Dict[str, Any]:
    """Mock verification summary for testing."""
    return {
        "session_id": "Session-000001",
        "cameras": [
            {"camera_id": "cam0_top", "ttl_id": "ttl_camera", "frame_count": 100, "ttl_pulse_count": 100, "mismatch": 0, "verifiable": True, "status": "OK"},
            {
                "camera_id": "cam1_pupil_left",
                "ttl_id": "ttl_camera",
                "frame_count": 98,
                "ttl_pulse_count": 100,
                "mismatch": 2,
                "verifiable": True,
                "status": "WARNING",
            },
        ],
        "generated_at": "2025-01-01T12:00:00Z",
    }


@pytest.fixture
def mock_alignment_stats() -> Dict[str, Any]:
    """Mock alignment statistics for testing."""
    return {"timebase_source": "nominal_rate", "mapping": "nearest", "offset_s": 0.0, "max_jitter_s": 0.0005, "p95_jitter_s": 0.0003, "aligned_samples": 100}


@pytest.fixture
def mock_provenance() -> Dict[str, Any]:
    """Mock provenance metadata for testing."""
    return {
        "config_hash": "abc123def456",
        "session_hash": "789ghi012jkl",
        "software": {"name": "w2t_bkin", "version": "0.1.0", "python_version": "3.10.0"},
        "git": {"commit": "main@1234567", "branch": "main", "dirty": False},
        "timebase": {"source": "nominal_rate", "mapping": "nearest", "offset_s": 0.0},
        "created_at": "2025-01-01T12:00:00Z",
    }


# ============================================================================
# Utility Fixtures
# ============================================================================


@pytest.fixture
def write_json():
    """Helper to write JSON files in tests."""

    def _write(path: Path, data: Dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path

    return _write


@pytest.fixture
def read_json():
    """Helper to read JSON files in tests."""

    def _read(path: Path) -> Dict[str, Any]:
        with open(path, "r") as f:
            return json.load(f)

    return _read


# ============================================================================
# Markers
# ============================================================================


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests (may be slow)")
    config.addinivalue_line("markers", "unit: marks tests as fast unit tests")
    config.addinivalue_line("markers", "requires_ffmpeg: marks tests that require ffmpeg installed")
    config.addinivalue_line("markers", "requires_models: marks tests that require pretrained models")
