"""Unit tests for ingest module.

Requirements: FR-1 (Ingest five camera videos), NFR-8 (Data integrity)
Design: design.md §2 (Module Breakdown), §3.1 (Manifest)
"""

import json
from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from w2t_bkin.config import Settings
from w2t_bkin.domain import Manifest, VideoMetadata
from w2t_bkin.ingest import (
    build_manifest,
    discover_events,
    discover_facemap,
    discover_pose,
    discover_sync_files,
    discover_videos,
    extract_video_metadata,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def settings():
    """Default settings for testing."""
    return Settings(
        session={"id": "test_session"},
        video={"pattern": "**/*.mp4", "fps": 30.0},
        sync={"ttl_channels": []},
        events={"patterns": ["**/*_events.ndjson"]},
        labels={"dlc": {"model": ""}, "sleap": {"model": ""}},
        facemap={"run": False},
    )


@pytest.fixture
def mock_session_dir(tmp_path):
    """Create mock session directory with videos and sync file."""
    session_dir = tmp_path / "session_001"
    session_dir.mkdir()

    # Create mock video files
    for i in range(3):
        video_file = session_dir / f"cam{i}.mp4"
        video_file.write_text(f"mock video {i}")

    # Create mock sync file
    sync_file = session_dir / "sync.bin"
    sync_file.write_bytes(b"mock sync data")

    return session_dir


@pytest.fixture
def mock_ffprobe_output():
    """Mock ffprobe JSON output."""
    return {
        "streams": [
            {
                "codec_name": "h264",
                "r_frame_rate": "30/1",
                "duration": "60.5",
                "width": 1920,
                "height": 1080,
            }
        ]
    }


# ============================================================================
# Test: build_manifest - Success Cases
# ============================================================================


def test_build_manifest_with_valid_session(mock_session_dir, settings, mock_ffprobe_output):
    """WHEN building manifest with valid session, THE SYSTEM SHALL create manifest.json."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(mock_ffprobe_output),
            returncode=0,
        )

        manifest_path = build_manifest(mock_session_dir, settings)

        assert manifest_path.exists()
        assert manifest_path.name == "manifest.json"
        assert manifest_path.parent == mock_session_dir


def test_build_manifest_with_custom_output_dir(mock_session_dir, settings, mock_ffprobe_output, tmp_path):
    """WHEN specifying custom output_dir, THE SYSTEM SHALL write manifest there."""
    output_dir = tmp_path / "output"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(mock_ffprobe_output),
            returncode=0,
        )

        manifest_path = build_manifest(mock_session_dir, settings, output_dir)

        assert manifest_path.parent == output_dir
        assert output_dir.exists()


def test_build_manifest_contains_required_fields(mock_session_dir, settings, mock_ffprobe_output):
    """WHEN manifest created, THE SYSTEM SHALL include all required fields."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(mock_ffprobe_output),
            returncode=0,
        )

        manifest_path = build_manifest(mock_session_dir, settings)

        with open(manifest_path) as f:
            manifest_data = json.load(f)

        assert "session_id" in manifest_data
        assert "videos" in manifest_data
        assert "sync" in manifest_data
        assert "events" in manifest_data
        assert "pose" in manifest_data
        assert "facemap" in manifest_data
        assert "config_snapshot" in manifest_data
        assert "provenance" in manifest_data


def test_build_manifest_includes_video_metadata(mock_session_dir, settings, mock_ffprobe_output):
    """WHEN videos discovered, THE SYSTEM SHALL include metadata in manifest."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(mock_ffprobe_output),
            returncode=0,
        )

        manifest_path = build_manifest(mock_session_dir, settings)

        with open(manifest_path) as f:
            manifest_data = json.load(f)

        assert len(manifest_data["videos"]) == 3

        for i, video in enumerate(manifest_data["videos"]):
            assert video["camera_id"] == i
            assert "path" in video
            assert "codec" in video
            assert "fps" in video
            assert "duration" in video
            assert "resolution" in video


def test_build_manifest_uses_session_id_from_settings(mock_session_dir, settings, mock_ffprobe_output):
    """WHEN session.id set in settings, THE SYSTEM SHALL use it for session_id."""
    settings.session.id = "custom_session_id"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(mock_ffprobe_output),
            returncode=0,
        )

        manifest_path = build_manifest(mock_session_dir, settings)

        with open(manifest_path) as f:
            manifest_data = json.load(f)

        assert manifest_data["session_id"] == "custom_session_id"


def test_build_manifest_uses_directory_name_when_no_session_id(mock_session_dir, settings, mock_ffprobe_output):
    """WHEN session.id not set, THE SYSTEM SHALL use directory name as session_id."""
    settings.session.id = ""

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(mock_ffprobe_output),
            returncode=0,
        )

        manifest_path = build_manifest(mock_session_dir, settings)

        with open(manifest_path) as f:
            manifest_data = json.load(f)

        assert manifest_data["session_id"] == mock_session_dir.name


def test_build_manifest_includes_provenance(mock_session_dir, settings, mock_ffprobe_output):
    """WHEN manifest created, THE SYSTEM SHALL include provenance metadata."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(mock_ffprobe_output),
            returncode=0,
        )

        manifest_path = build_manifest(mock_session_dir, settings)

        with open(manifest_path) as f:
            manifest_data = json.load(f)

        assert "git_commit" in manifest_data["provenance"]
        assert "session_dir" in manifest_data["provenance"]
        assert "output_dir" in manifest_data["provenance"]


# ============================================================================
# Test: build_manifest - Error Cases
# ============================================================================


def test_build_manifest_with_nonexistent_session_dir(settings, tmp_path):
    """WHEN session directory doesn't exist, THE SYSTEM SHALL raise FileNotFoundError."""
    nonexistent_dir = tmp_path / "nonexistent"

    with pytest.raises(FileNotFoundError) as exc_info:
        build_manifest(nonexistent_dir, settings)

    assert "not found" in str(exc_info.value).lower()


def test_build_manifest_with_no_videos(tmp_path, settings):
    """WHEN no videos found, THE SYSTEM SHALL raise ValueError."""
    empty_dir = tmp_path / "empty_session"
    empty_dir.mkdir()

    # Create sync file
    sync_file = empty_dir / "sync.bin"
    sync_file.write_bytes(b"sync")

    with pytest.raises(ValueError) as exc_info:
        build_manifest(empty_dir, settings)

    assert "no videos found" in str(exc_info.value).lower()


def test_build_manifest_with_no_sync_files(tmp_path, settings, mock_ffprobe_output):
    """WHEN no sync files found, THE SYSTEM SHALL raise ValueError."""
    session_dir = tmp_path / "no_sync_session"
    session_dir.mkdir()

    # Create video file
    video_file = session_dir / "cam0.mp4"
    video_file.write_text("mock video")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(mock_ffprobe_output),
            returncode=0,
        )

        with pytest.raises(ValueError) as exc_info:
            build_manifest(session_dir, settings)

        assert "no sync files found" in str(exc_info.value).lower()


def test_build_manifest_with_ffprobe_failure(mock_session_dir, settings):
    """WHEN ffprobe fails, THE SYSTEM SHALL raise RuntimeError."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["ffprobe"],
            stderr="ffprobe error",
        )

        with pytest.raises(RuntimeError) as exc_info:
            build_manifest(mock_session_dir, settings)

        assert "ffprobe failed" in str(exc_info.value).lower()


# ============================================================================
# Test: discover_videos
# ============================================================================


def test_discover_videos_finds_multiple_videos(mock_session_dir, settings):
    """WHEN multiple videos exist, THE SYSTEM SHALL discover all matching pattern."""
    videos = discover_videos(mock_session_dir, settings)

    assert len(videos) == 3
    assert all(v.suffix == ".mp4" for v in videos)
    assert all(v.is_absolute() for v in videos)


def test_discover_videos_returns_sorted_list(mock_session_dir, settings):
    """WHEN discovering videos, THE SYSTEM SHALL return sorted list."""
    videos = discover_videos(mock_session_dir, settings)

    names = [v.name for v in videos]
    assert names == sorted(names)


def test_discover_videos_with_no_matches(tmp_path, settings):
    """WHEN no videos match pattern, THE SYSTEM SHALL return empty list."""
    empty_dir = tmp_path / "no_videos"
    empty_dir.mkdir()

    videos = discover_videos(empty_dir, settings)

    assert videos == []


def test_discover_videos_with_custom_pattern(mock_session_dir, settings):
    """WHEN custom pattern specified, THE SYSTEM SHALL use it for discovery."""
    # Create additional .avi file
    avi_file = mock_session_dir / "cam_extra.avi"
    avi_file.write_text("avi video")

    settings.video.pattern = "**/*.avi"
    videos = discover_videos(mock_session_dir, settings)

    assert len(videos) == 1
    assert videos[0].suffix == ".avi"


def test_discover_videos_with_nested_directories(tmp_path, settings):
    """WHEN videos in nested directories, THE SYSTEM SHALL discover them."""
    session_dir = tmp_path / "nested_session"
    subdir = session_dir / "subdir"
    subdir.mkdir(parents=True)

    video1 = session_dir / "cam0.mp4"
    video2 = subdir / "cam1.mp4"
    video1.write_text("video1")
    video2.write_text("video2")

    videos = discover_videos(session_dir, settings)

    assert len(videos) == 2


# ============================================================================
# Test: extract_video_metadata
# ============================================================================


def test_extract_video_metadata_with_valid_video(tmp_path, mock_ffprobe_output):
    """WHEN extracting metadata from valid video, THE SYSTEM SHALL return VideoMetadata."""
    video_path = tmp_path / "test.mp4"
    video_path.write_text("mock video")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(mock_ffprobe_output),
            returncode=0,
        )

        metadata = extract_video_metadata(video_path, camera_id=0)

        assert isinstance(metadata, VideoMetadata)
        assert metadata.camera_id == 0
        assert metadata.codec == "h264"
        assert metadata.fps == 30.0
        assert metadata.duration == 60.5
        assert metadata.resolution == (1920, 1080)


def test_extract_video_metadata_with_nonexistent_file(tmp_path):
    """WHEN video file doesn't exist, THE SYSTEM SHALL raise FileNotFoundError."""
    nonexistent = tmp_path / "nonexistent.mp4"

    with pytest.raises(FileNotFoundError) as exc_info:
        extract_video_metadata(nonexistent, camera_id=0)

    assert "not found" in str(exc_info.value).lower()


def test_extract_video_metadata_with_ffprobe_error(tmp_path):
    """WHEN ffprobe fails, THE SYSTEM SHALL raise RuntimeError."""
    video_path = tmp_path / "test.mp4"
    video_path.write_text("mock video")

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["ffprobe"],
            stderr="Invalid data",
        )

        with pytest.raises(RuntimeError) as exc_info:
            extract_video_metadata(video_path, camera_id=0)

        assert "ffprobe failed" in str(exc_info.value).lower()


def test_extract_video_metadata_with_timeout(tmp_path):
    """WHEN ffprobe times out, THE SYSTEM SHALL raise RuntimeError."""
    video_path = tmp_path / "test.mp4"
    video_path.write_text("mock video")

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ffprobe"], timeout=30)

        with pytest.raises(RuntimeError) as exc_info:
            extract_video_metadata(video_path, camera_id=0)

        assert "timeout" in str(exc_info.value).lower()


def test_extract_video_metadata_with_no_video_stream(tmp_path):
    """WHEN video has no video stream, THE SYSTEM SHALL raise RuntimeError."""
    video_path = tmp_path / "test.mp4"
    video_path.write_text("mock video")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"streams": []}),
            returncode=0,
        )

        with pytest.raises(RuntimeError) as exc_info:
            extract_video_metadata(video_path, camera_id=0)

        assert "no video stream" in str(exc_info.value).lower()


def test_extract_video_metadata_with_invalid_json(tmp_path):
    """WHEN ffprobe output is invalid JSON, THE SYSTEM SHALL raise RuntimeError."""
    video_path = tmp_path / "test.mp4"
    video_path.write_text("mock video")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="invalid json",
            returncode=0,
        )

        with pytest.raises(RuntimeError) as exc_info:
            extract_video_metadata(video_path, camera_id=0)

        assert "failed to parse" in str(exc_info.value).lower()


def test_extract_video_metadata_parses_frame_rate_correctly(tmp_path):
    """WHEN frame rate is fraction, THE SYSTEM SHALL parse to float correctly."""
    video_path = tmp_path / "test.mp4"
    video_path.write_text("mock video")

    test_cases = [
        ("30/1", 30.0),
        ("60/1", 60.0),
        ("24000/1001", 23.976023976023978),
    ]

    for fps_str, expected_fps in test_cases:
        ffprobe_output = {
            "streams": [
                {
                    "codec_name": "h264",
                    "r_frame_rate": fps_str,
                    "duration": "10.0",
                    "width": 640,
                    "height": 480,
                }
            ]
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=json.dumps(ffprobe_output),
                returncode=0,
            )

            metadata = extract_video_metadata(video_path, camera_id=0)
            assert abs(metadata.fps - expected_fps) < 1e-6


def test_extract_video_metadata_converts_path_to_absolute(tmp_path):
    """WHEN video path is relative, THE SYSTEM SHALL convert to absolute."""
    video_path = tmp_path / "test.mp4"
    video_path.write_text("mock video")

    ffprobe_output = {
        "streams": [
            {
                "codec_name": "h264",
                "r_frame_rate": "30/1",
                "duration": "10.0",
                "width": 640,
                "height": 480,
            }
        ]
    }

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(ffprobe_output),
            returncode=0,
        )

        # Pass relative path
        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            metadata = extract_video_metadata("test.mp4", camera_id=0)
            assert metadata.path.is_absolute()
        finally:
            os.chdir(original_cwd)


# ============================================================================
# Test: discover_sync_files
# ============================================================================


def test_discover_sync_files_with_configured_ttl_channels(tmp_path):
    """WHEN TTL channels configured, THE SYSTEM SHALL discover from config."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    sync_file = session_dir / "sync.bin"
    sync_file.write_bytes(b"sync data")

    # Create settings with configured TTL channel
    from w2t_bkin.config import Settings, TTLChannelConfig

    settings = Settings(sync={"ttl_channels": [{"path": "sync.bin", "name": "trigger", "polarity": "rising"}]})

    sync_files = discover_sync_files(session_dir, settings)

    assert len(sync_files) == 1
    assert sync_files[0]["type"] == "ttl"
    assert sync_files[0]["name"] == "trigger"
    assert sync_files[0]["polarity"] == "rising"


def test_discover_sync_files_with_fallback_detection(tmp_path, settings):
    """WHEN no TTL channels configured, THE SYSTEM SHALL use fallback patterns."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    sync_file = session_dir / "sync.bin"
    sync_file.write_bytes(b"sync data")

    settings.sync.ttl_channels = []

    sync_files = discover_sync_files(session_dir, settings)

    assert len(sync_files) == 1
    assert sync_files[0]["type"] == "auto_detected"


def test_discover_sync_files_with_multiple_patterns(tmp_path, settings):
    """WHEN multiple sync files match patterns, THE SYSTEM SHALL discover all."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    (session_dir / "sync1.bin").write_bytes(b"sync1")
    (session_dir / "sync2.csv").write_bytes(b"sync2")
    (session_dir / "ttl.bin").write_bytes(b"ttl")

    settings.sync.ttl_channels = []

    sync_files = discover_sync_files(session_dir, settings)

    assert len(sync_files) == 3


def test_discover_sync_files_returns_absolute_paths(tmp_path, settings):
    """WHEN discovering sync files, THE SYSTEM SHALL return absolute paths."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    sync_file = session_dir / "sync.bin"
    sync_file.write_bytes(b"sync data")

    settings.sync.ttl_channels = []

    sync_files = discover_sync_files(session_dir, settings)

    assert len(sync_files) == 1
    assert Path(sync_files[0]["path"]).is_absolute()


def test_discover_sync_files_with_no_sync_files(tmp_path, settings):
    """WHEN no sync files found, THE SYSTEM SHALL return empty list."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    settings.sync.ttl_channels = []

    sync_files = discover_sync_files(empty_dir, settings)

    assert sync_files == []


# ============================================================================
# Test: discover_events
# ============================================================================


def test_discover_events_finds_matching_files(tmp_path, settings):
    """WHEN event files match patterns, THE SYSTEM SHALL discover them."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    event_file = session_dir / "trial_events.ndjson"
    event_file.write_text('{"type": "event"}')

    events = discover_events(session_dir, settings)

    assert len(events) == 1
    assert events[0]["kind"] == "behavioral"
    assert events[0]["format"] == "ndjson"


def test_discover_events_with_no_files(tmp_path, settings):
    """WHEN no event files found, THE SYSTEM SHALL return empty list."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    events = discover_events(empty_dir, settings)

    assert events == []


def test_discover_events_with_multiple_patterns(tmp_path, settings):
    """WHEN multiple patterns configured, THE SYSTEM SHALL check all."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    (session_dir / "training_events.ndjson").write_text("{}")
    (session_dir / "trial_stats_events.ndjson").write_text("{}")

    settings.events.patterns = ["**/*training*.ndjson", "**/*trial_stats*.ndjson"]

    events = discover_events(session_dir, settings)

    assert len(events) == 2


# ============================================================================
# Test: discover_pose
# ============================================================================


def test_discover_pose_finds_dlc_files(tmp_path, settings):
    """WHEN DLC model configured, THE SYSTEM SHALL discover DLC files."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    dlc_file = session_dir / "video_DLC_resnet50.h5"
    dlc_file.write_text("dlc data")

    settings.labels.dlc.model = "model.pb"

    pose_files = discover_pose(session_dir, settings)

    assert len(pose_files) == 1
    assert pose_files[0]["format"] == "dlc"
    assert pose_files[0]["model"] == "model.pb"


def test_discover_pose_finds_sleap_files(tmp_path, settings):
    """WHEN SLEAP model configured, THE SYSTEM SHALL discover SLEAP files."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    sleap_file = session_dir / "predictions.slp"
    sleap_file.write_text("sleap data")

    settings.labels.sleap.model = "model.h5"

    pose_files = discover_pose(session_dir, settings)

    assert len(pose_files) == 1
    assert pose_files[0]["format"] == "sleap"
    assert pose_files[0]["model"] == "model.h5"


def test_discover_pose_with_no_models_configured(tmp_path, settings):
    """WHEN no pose models configured, THE SYSTEM SHALL return empty list."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    (session_dir / "video_DLC.h5").write_text("dlc")

    settings.labels.dlc.model = ""
    settings.labels.sleap.model = ""

    pose_files = discover_pose(session_dir, settings)

    assert pose_files == []


def test_discover_pose_with_both_dlc_and_sleap(tmp_path, settings):
    """WHEN both DLC and SLEAP configured, THE SYSTEM SHALL discover both."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    (session_dir / "video_DLC.h5").write_text("dlc")
    (session_dir / "predictions.slp").write_text("sleap")

    settings.labels.dlc.model = "dlc_model.pb"
    settings.labels.sleap.model = "sleap_model.h5"

    pose_files = discover_pose(session_dir, settings)

    assert len(pose_files) == 2


# ============================================================================
# Test: discover_facemap
# ============================================================================


def test_discover_facemap_finds_files_when_enabled(tmp_path, settings):
    """WHEN facemap enabled, THE SYSTEM SHALL discover facemap files."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    facemap_file = session_dir / "video_facemap.npy"
    facemap_file.write_text("facemap data")

    settings.facemap.run = True
    settings.facemap.roi = "face"

    facemap_files = discover_facemap(session_dir, settings)

    assert len(facemap_files) == 1
    assert facemap_files[0]["roi"] == "face"


def test_discover_facemap_returns_empty_when_disabled(tmp_path, settings):
    """WHEN facemap disabled, THE SYSTEM SHALL return empty list."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    (session_dir / "video_facemap.npy").write_text("facemap")

    settings.facemap.run = False

    facemap_files = discover_facemap(session_dir, settings)

    assert facemap_files == []


def test_discover_facemap_with_no_files(tmp_path, settings):
    """WHEN no facemap files found, THE SYSTEM SHALL return empty list."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    settings.facemap.run = True

    facemap_files = discover_facemap(empty_dir, settings)

    assert facemap_files == []


# ============================================================================
# Test: Edge Cases
# ============================================================================


def test_build_manifest_with_relative_session_dir(tmp_path, settings, mock_ffprobe_output):
    """WHEN session_dir is relative, THE SYSTEM SHALL resolve to absolute."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    (session_dir / "cam0.mp4").write_text("video")
    (session_dir / "sync.bin").write_bytes(b"sync")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(mock_ffprobe_output),
            returncode=0,
        )

        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            manifest_path = build_manifest("session", settings)

            with open(manifest_path) as f:
                manifest_data = json.load(f)

            # All paths should be absolute
            assert Path(manifest_data["provenance"]["session_dir"]).is_absolute()
            for video in manifest_data["videos"]:
                assert Path(video["path"]).is_absolute()
        finally:
            os.chdir(original_cwd)


def test_build_manifest_creates_output_directory(tmp_path, settings, mock_ffprobe_output):
    """WHEN output directory doesn't exist, THE SYSTEM SHALL create it."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    (session_dir / "cam0.mp4").write_text("video")
    (session_dir / "sync.bin").write_bytes(b"sync")

    output_dir = tmp_path / "nonexistent" / "nested" / "output"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(mock_ffprobe_output),
            returncode=0,
        )

        manifest_path = build_manifest(session_dir, settings, output_dir)

        assert output_dir.exists()
        assert manifest_path.parent == output_dir


def test_build_manifest_with_empty_session_directory(tmp_path, settings):
    """WHEN session directory is empty, THE SYSTEM SHALL raise ValueError."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with pytest.raises(ValueError):
        build_manifest(empty_dir, settings)


def test_discover_videos_with_absolute_and_relative_paths(tmp_path, settings):
    """WHEN discovering videos, THE SYSTEM SHALL always return absolute paths."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    (session_dir / "cam0.mp4").write_text("video")

    videos = discover_videos(session_dir, settings)

    assert all(v.is_absolute() for v in videos)
