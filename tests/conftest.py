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
# Config Object Fixtures (Pydantic Models)
# ============================================================================


@pytest.fixture
def valid_config(tmp_path):
    """Valid Config object with nominal_rate timebase for testing.

    Returns a fully-configured Config domain model suitable for
    testing business logic that requires Config objects.
    """
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

    return Config(
        project=ProjectConfig(name="test-project"),
        paths=PathsConfig(
            raw_root=str(tmp_path / "raw"),
            intermediate_root=str(tmp_path / "interim"),
            output_root=str(tmp_path / "output"),
            metadata_file="session.toml",
            models_root=str(tmp_path / "models"),
        ),
        timebase=TimebaseConfig(
            source="nominal_rate",
            mapping="nearest",
            jitter_budget_s=0.010,
            offset_s=0.0,
        ),
        acquisition=AcquisitionConfig(concat_strategy="ffconcat"),
        verification=VerificationConfig(mismatch_tolerance_frames=0, warn_on_mismatch=False),
        bpod=BpodConfig(parse=True),
        video=VideoConfig(transcode=TranscodeConfig(enabled=False, codec="h264", crf=20, preset="fast", keyint=15)),
        nwb=NWBConfig(
            link_external_video=True,
            lab="Test Lab",
            institution="Test Institution",
            file_name_template="{session.id}.nwb",
            session_description_template="Test session {session.id}",
        ),
        qc=QCConfig(generate_report=True, out_template="qc/{session.id}", include_verification=True),
        logging=LoggingConfig(level="INFO", structured=False),
        labels=LabelsConfig(
            dlc=DLCConfig(run_inference=False, model="dlc.pb"),
            sleap=SLEAPConfig(run_inference=False, model="sleap.h5"),
        ),
        facemap=FacemapConfig(run_inference=False, ROIs=["face"]),
    )


@pytest.fixture
def ttl_config(valid_config):
    """Config object with TTL timebase.

    Derives from valid_config and modifies timebase to use TTL source.
    """
    config_dict = valid_config.model_dump()
    config_dict["timebase"]["source"] = "ttl"
    config_dict["timebase"]["ttl_id"] = "ttl_camera"

    from w2t_bkin.domain import Config

    return Config(**config_dict)


@pytest.fixture
def neuropixels_config(valid_config):
    """Config object with Neuropixels timebase.

    Derives from valid_config and modifies timebase to use Neuropixels source.
    """
    config_dict = valid_config.model_dump()
    config_dict["timebase"]["source"] = "neuropixels"
    config_dict["timebase"]["neuropixels_stream"] = "AP0"

    from w2t_bkin.domain import Config

    return Config(**config_dict)


# ============================================================================
# Manifest Object Fixtures (Pydantic Models)
# ============================================================================


@pytest.fixture
def valid_manifest():
    """Valid Manifest object for testing.

    Returns a minimal but valid Manifest domain model with one camera
    and one TTL, suitable for testing business logic.
    """
    from w2t_bkin.domain import Manifest, ManifestCamera, ManifestTTL

    return Manifest(
        session_id="test-session",
        cameras=[
            ManifestCamera(
                camera_id="cam0",
                ttl_id="ttl_camera",
                video_files=["/path/to/video.avi"],
                frame_count=1000,
                ttl_pulse_count=1000,
            )
        ],
        ttls=[
            ManifestTTL(
                ttl_id="ttl_camera",
                files=["/path/to/ttl.txt"],
            )
        ],
    )


@pytest.fixture
def ttl_files(tmp_path):
    """Create test TTL files with timestamps.

    Creates a TTL file with 100 pulses at 30 FPS (0.033s intervals).
    Returns list of file paths for use with TTL providers.
    """
    ttl_dir = tmp_path / "ttls"
    ttl_dir.mkdir()

    ttl_file = ttl_dir / "test_ttl.txt"
    timestamps = [f"{i * 0.033:.6f}\n" for i in range(100)]
    ttl_file.write_text("".join(timestamps))

    return [str(ttl_file)]


@pytest.fixture
def ttl_manifest(ttl_files):
    """Create a minimal Manifest with TTL configuration for testing.

    Returns a Manifest domain model with one camera and one TTL channel,
    suitable for testing TTL-based synchronization.
    """
    from w2t_bkin.domain import Manifest, ManifestCamera, ManifestTTL

    return Manifest(
        session_id="test-session",
        cameras=[
            ManifestCamera(
                camera_id="cam0",
                ttl_id="ttl_camera",
                video_files=[],
                frame_count=1000,
                ttl_pulse_count=1000,
            )
        ],
        ttls=[
            ManifestTTL(
                ttl_id="ttl_camera",
                files=ttl_files,
            )
        ],
    )


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


# ============================================================================
# Bpod & Events Fixtures
# ============================================================================


@pytest.fixture
def mock_session_with_ttl(tmp_path):
    """Create a Session with TTL configuration for alignment testing."""
    from w2t_bkin.domain import TTL, BpodSession, BpodTrialType, Session, SessionMetadata

    ttl_dir = tmp_path / "TTLs"
    ttl_dir.mkdir()

    # Create TTL pulse file with absolute timestamps
    ttl_file = ttl_dir / "ttl_cue.txt"
    ttl_file.write_text("10.0\n25.0\n40.0\n")

    return Session(
        session=SessionMetadata(
            id="test-session",
            subject_id="mouse-001",
            date="2025-11-13",
            experimenter="Test",
            description="Test session",
            sex="M",
            age="P60",
            genotype="WT",
        ),
        bpod=BpodSession(
            path="Bpod/*.mat",
            order="name_asc",
            trial_types=[
                BpodTrialType(
                    trial_type=1,
                    description="Type 1 trials",
                    sync_signal="W2L_Audio",
                    sync_ttl="ttl_cue",
                ),
                BpodTrialType(
                    trial_type=2,
                    description="Type 2 trials",
                    sync_signal="A2L_Audio",
                    sync_ttl="ttl_cue",
                ),
            ],
        ),
        TTLs=[
            TTL(
                id="ttl_cue",
                description="Cue TTL",
                paths="TTLs/ttl_cue.txt",
            ),
        ],
        cameras=[],
        session_dir=str(tmp_path),
    )


@pytest.fixture
def valid_bpod_file(tmp_path, monkeypatch):
    """Create a minimal valid Bpod .mat file for testing."""
    bpod_file = tmp_path / "test_bpod.mat"

    # Mock loadmat to return valid data
    def mock_loadmat(path, squeeze_me=True, struct_as_record=False):
        return {
            "SessionData": {
                "nTrials": 1,
                "TrialStartTimestamp": [0.0],
                "TrialEndTimestamp": [10.0],
                "RawEvents": {"Trial": [{"States": {"HIT": [8.0, 8.1]}, "Events": {}}]},
            }
        }

    bpod_file.write_text("")

    from w2t_bkin import events

    monkeypatch.setattr(events, "loadmat", mock_loadmat)

    return bpod_file


@pytest.fixture
def sample_bpod_data():
    """Create sample Bpod data structure for testing indexing and I/O operations."""
    import numpy as np

    return {
        "SessionData": {
            "nTrials": 5,
            "TrialStartTimestamp": np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
            "TrialEndTimestamp": np.array([0.5, 1.5, 2.5, 3.5, 4.5]),
            "TrialTypes": np.array([1, 2, 1, 2, 1]),
            "TrialSettings": [{"param": 1}, {"param": 2}, {"param": 1}, {"param": 2}, {"param": 1}],
            "RawEvents": {
                "Trial": [
                    {"States": {"HIT": [0.1, 0.2]}, "Events": {"Port1In": [0.15]}},
                    {"States": {"Miss": [0.1, 0.2]}, "Events": {"Port1In": [0.15]}},
                    {"States": {"HIT": [0.1, 0.2]}, "Events": {"Port1In": [0.15]}},
                    {"States": {"Miss": [0.1, 0.2]}, "Events": {"Port1In": [0.15]}},
                    {"States": {"HIT": [0.1, 0.2]}, "Events": {"Port1In": [0.15]}},
                ]
            },
        }
    }


@pytest.fixture
def parsed_bpod_data():
    """Realistic Bpod structure with 3 trials."""
    return {
        "SessionData": {
            "nTrials": 3,
            "TrialStartTimestamp": [0.0, 10.0, 20.0],
            "TrialEndTimestamp": [9.0, 19.0, 29.0],
            "TrialTypes": [1, 2, 1],
            "TrialSettings": [
                {"GUI": {"rewardamount_R": 35, "reward_delay": 0.4}},
                {"GUI": {"rewardamount_R": 35, "reward_delay": 0.4}},
                {"GUI": {"rewardamount_R": 35, "reward_delay": 0.4}},
            ],
            "RawEvents": {
                "Trial": [
                    {
                        "States": {
                            "ITI": [0.0, 7.0],
                            "Response_window": [7.0, 8.5],
                            "HIT": [8.5, 8.6],
                            "RightReward": [8.6, 9.0],
                            "Miss": [float("nan"), float("nan")],
                        },
                        "Events": {
                            "Flex1Trig2": [0.0001, 7.1],
                            "BNC1High": [1.5, 8.5],
                            "BNC1Low": [1.6, 8.6],
                            "Tup": [7.0, 8.5, 8.6, 9.0],
                        },
                    },
                    {
                        "States": {
                            "ITI": [0.0, 6.0],
                            "Response_window": [6.0, 8.0],
                            "Miss": [8.0, 8.1],
                            "HIT": [float("nan"), float("nan")],
                            "RightReward": [float("nan"), float("nan")],
                        },
                        "Events": {
                            "Flex1Trig2": [0.0001, 6.1],
                            "Tup": [6.0, 8.0, 8.1],
                        },
                    },
                    {
                        "States": {
                            "ITI": [0.0, 7.5],
                            "Response_window": [7.5, 9.0],
                            "HIT": [9.0, 9.1],
                            "RightReward": [9.1, 9.5],
                            "Miss": [float("nan"), float("nan")],
                        },
                        "Events": {
                            "Flex1Trig2": [0.0001, 7.6],
                            "BNC1High": [2.0, 9.0],
                            "BNC1Low": [2.1, 9.1],
                            "Tup": [7.5, 9.0, 9.1, 9.5],
                        },
                    },
                ]
            },
        }
    }


@pytest.fixture
def trial_list():
    """List of Trial objects for testing event summary creation."""
    from w2t_bkin.domain import Trial, TrialOutcome

    return [
        Trial(trial_number=1, trial_type=1, start_time=0.0, stop_time=9.0, outcome=TrialOutcome.HIT),
        Trial(trial_number=2, trial_type=1, start_time=10.0, stop_time=19.0, outcome=TrialOutcome.MISS),
        Trial(trial_number=3, trial_type=1, start_time=20.0, stop_time=29.0, outcome=TrialOutcome.HIT),
    ]


@pytest.fixture
def event_list():
    """List of TrialEvent objects for testing event summary creation."""
    from w2t_bkin.domain import TrialEvent

    return [
        TrialEvent(event_type="Flex1Trig2", timestamp=0.0001, metadata={"trial_number": 1.0}),
        TrialEvent(event_type="BNC1High", timestamp=1.5, metadata={"trial_number": 1.0}),
        TrialEvent(event_type="BNC1Low", timestamp=1.6, metadata={"trial_number": 1.0}),
        TrialEvent(event_type="Flex1Trig2", timestamp=7.1, metadata={"trial_number": 1.0}),
        TrialEvent(event_type="BNC1High", timestamp=8.5, metadata={"trial_number": 1.0}),
        TrialEvent(event_type="Flex1Trig2", timestamp=0.0001, metadata={"trial_number": 2.0}),
        TrialEvent(event_type="Flex1Trig2", timestamp=0.0001, metadata={"trial_number": 3.0}),
        TrialEvent(event_type="BNC1High", timestamp=2.0, metadata={"trial_number": 3.0}),
        TrialEvent(event_type="BNC1Low", timestamp=2.1, metadata={"trial_number": 3.0}),
    ]


@pytest.fixture
def bpod_data_with_sync():
    """Bpod data with sync signals for TTL alignment testing."""
    return {
        "SessionData": {
            "nTrials": 3,
            "TrialStartTimestamp": [0.0, 0.0, 0.0],
            "TrialEndTimestamp": [9.0, 8.5, 10.0],
            "TrialTypes": [1, 2, 1],
            "RawEvents": {
                "Trial": [
                    {
                        "States": {
                            "ITI": [0.0, 5.0],
                            "W2L_Audio": [6.0, 7.0],  # Sync signal for type 1
                            "HIT": [7.5, 7.6],
                        },
                        "Events": {"Port1In": [7.5]},
                    },
                    {
                        "States": {
                            "ITI": [0.0, 4.0],
                            "A2L_Audio": [5.0, 6.0],  # Sync signal for type 2
                            "Miss": [7.0, 7.1],
                        },
                        "Events": {},
                    },
                    {
                        "States": {
                            "ITI": [0.0, 5.5],
                            "W2L_Audio": [6.5, 7.5],  # Sync signal for type 1
                            "HIT": [8.0, 8.1],
                        },
                        "Events": {"Port1In": [8.0]},
                    },
                ]
            },
            "Info": {
                "SessionDate": "13-Nov-2025",
                "SessionStartTime_UTC": "10:00:00",
            },
        }
    }
