"""Integration tests for Phase 1 — Ingest and Verify.

Covers: manifest discovery, frame/TTL counting, verification behavior (abort/warn),
unverifiable camera warnings, and sidecar writing.

Requirements: FR-1, FR-2, FR-3, FR-13, FR-15, FR-16
Acceptance: A6, A7
"""

import json
import os
from pathlib import Path

import pytest


def _write_lines(path: Path, n: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for _ in range(n):
            f.write("1\n")


@pytest.mark.integration
def test_real_session_001_end_to_end_ingest(
    fixture_session_path,
    fixture_session_toml,
    minimal_config_dict,
    tmp_work_dir,
):
    """Test complete ingest workflow with real Session-000001 data.

    This is an end-to-end integration test using actual video files,
    TTL files, and Bpod data from Session-000001.

    Requirements: FR-1 (discovery), FR-2 (counting), FR-3 (verification)
    """
    from w2t_bkin.config import load_config, load_session
    from w2t_bkin.domain import Config
    from w2t_bkin.ingest import (
        build_manifest,
        count_ttl_pulses,
        count_video_frames,
        create_verification_summary,
        verify_manifest,
        write_verification_summary,
    )

    # Load session from real data
    session = load_session(fixture_session_toml)

    # Create config pointing to real data
    config_dict = minimal_config_dict.copy()
    config_dict["paths"]["raw_root"] = str(fixture_session_path.parent)
    config_dict["paths"]["output_root"] = str(tmp_work_dir / "processed")
    config_dict["paths"]["intermediate_root"] = str(tmp_work_dir / "interim")
    config = Config(**config_dict)

    # Phase 1: Build manifest (FR-1 - Discovery)
    manifest = build_manifest(config, session)

    # Assertions on discovered files
    assert manifest.session_id == "Session-000001"
    assert len(manifest.cameras) == 2, "Should discover 2 cameras (cam0 top, cam1 pupil_left)"
    assert len(manifest.ttls) == 3, "Should discover 3 TTL channels"
    assert manifest.bpod_files is not None and len(manifest.bpod_files) > 0, "Should discover Bpod file"

    # Verify camera discovery
    camera_ids = {cam.camera_id for cam in manifest.cameras}
    assert "cam0" in camera_ids
    assert "cam1" in camera_ids

    # Verify TTL discovery
    ttl_ids = {ttl.ttl_id for ttl in manifest.ttls}
    assert "ttl_hitmiss" in ttl_ids
    assert "ttl_camera" in ttl_ids
    assert "ttl_cue" in ttl_ids

    # Verify each camera has video files
    for cam in manifest.cameras:
        assert len(cam.video_files) > 0, f"Camera {cam.camera_id} should have video files"
        # Check files exist
        for video_file in cam.video_files:
            assert Path(video_file).exists(), f"Video file should exist: {video_file}"

    # Verify TTL files exist
    for ttl in manifest.ttls:
        assert len(ttl.files) > 0, f"TTL {ttl.ttl_id} should have files"
        for ttl_file in ttl.files:
            assert Path(ttl_file).exists(), f"TTL file should exist: {ttl_file}"

    # Phase 2: Count frames and pulses (FR-2)
    for cam in manifest.cameras:
        frame_count = count_video_frames(Path(cam.video_files[0]))
        assert frame_count > 0, f"Camera {cam.camera_id} should have frames"

        # Find corresponding TTL file
        ttl_entry = next((t for t in manifest.ttls if t.ttl_id == cam.ttl_id), None)
        if ttl_entry and ttl_entry.files:
            ttl_count = count_ttl_pulses(Path(ttl_entry.files[0]))
            assert ttl_count > 0, f"TTL {cam.ttl_id} should have pulses"

    # Phase 3: Create verification summary
    verification = create_verification_summary(manifest)
    assert verification["session_id"] == manifest.session_id
    assert len(verification["cameras"]) == len(manifest.cameras)

    # Phase 4: Write verification summary (sidecar)
    output_path = tmp_work_dir / "interim" / "verification_summary.json"
    from w2t_bkin.domain import VerificationSummary

    verification_model = VerificationSummary(**verification)
    write_verification_summary(verification_model, output_path)

    assert output_path.exists(), "Verification summary should be written"

    # Read back and verify structure
    with open(output_path, "r") as f:
        data = json.load(f)

    assert "session_id" in data
    assert "cameras" in data
    assert "generated_at" in data
    assert isinstance(data["cameras"], list)

    for cam_result in data["cameras"]:
        assert "camera_id" in cam_result
        assert "ttl_id" in cam_result
        assert "frame_count" in cam_result
        assert "ttl_pulse_count" in cam_result
        assert "mismatch" in cam_result
        assert "verifiable" in cam_result
        assert "status" in cam_result


@pytest.mark.integration
@pytest.mark.xfail(reason="Bpod parsing needs to handle scipy.io mat_struct objects - implementation pending")
def test_real_session_001_bpod_parsing(fixture_session_path, fixture_session_toml):
    """Test Bpod file parsing with real Session-000001 data.

    Requirements: FR-11 (Bpod parsing)
    """
    from w2t_bkin.config import load_session
    from w2t_bkin.events import (
        extract_behavioral_events,
        extract_trials,
        parse_bpod_mat,
    )

    session = load_session(fixture_session_toml)

    # Find Bpod file
    bpod_pattern = fixture_session_path / session.bpod.path
    import glob

    bpod_files = glob.glob(str(bpod_pattern))

    assert len(bpod_files) > 0, "Should find at least one Bpod file"

    bpod_file = Path(bpod_files[0])
    assert bpod_file.exists(), "Bpod file should exist"

    # Parse Bpod file
    bpod_data = parse_bpod_mat(bpod_file)
    assert bpod_data is not None, "Should successfully parse Bpod .mat file"

    # Extract trials
    trials = extract_trials(bpod_data)
    assert len(trials) > 0, "Should extract trials from Bpod data"

    # Verify trial structure
    for trial in trials[:5]:  # Check first 5 trials
        assert "trial_number" in trial
        assert "start_time" in trial
        assert "end_time" in trial
        assert "outcome" in trial

    # Extract behavioral events
    events = extract_behavioral_events(bpod_data)
    assert len(events) > 0, "Should extract behavioral events"

    # Verify event structure
    for event in events[:5]:
        assert "event_type" in event
        assert "timestamp" in event
        assert "trial_number" in event


@pytest.mark.integration
def test_real_session_001_ttl_parsing(fixture_session_path, fixture_session_toml):
    """Test TTL file parsing with real Session-000001 data.

    Requirements: FR-1 (TTL discovery), FR-2 (TTL counting)
    """
    from w2t_bkin.config import load_session
    from w2t_bkin.ingest import count_ttl_pulses

    session = load_session(fixture_session_toml)

    # Test each TTL channel
    for ttl_config in session.TTLs:
        ttl_pattern = fixture_session_path / ttl_config.paths
        import glob

        ttl_files = glob.glob(str(ttl_pattern))

        assert len(ttl_files) > 0, f"Should find TTL files for {ttl_config.id}"

        for ttl_file in ttl_files:
            ttl_path = Path(ttl_file)
            assert ttl_path.exists(), f"TTL file should exist: {ttl_path}"

            # Count pulses
            pulse_count = count_ttl_pulses(ttl_path)
            assert pulse_count >= 0, f"Should count pulses in {ttl_path.name}"

            # Verify file is readable
            with open(ttl_path, "r") as f:
                lines = f.readlines()
                assert len(lines) == pulse_count, "Pulse count should match line count"


@pytest.mark.integration
def test_real_session_001_video_discovery(fixture_session_path, fixture_session_toml):
    """Test video file discovery with real Session-000001 data.

    Requirements: FR-1 (Video discovery)
    """
    import glob

    from w2t_bkin.config import load_session

    session = load_session(fixture_session_toml)

    # Test each camera
    for camera_config in session.cameras:
        video_pattern = fixture_session_path / camera_config.paths
        video_files = sorted(glob.glob(str(video_pattern)))

        assert len(video_files) > 0, f"Should find video files for camera {camera_config.id}"

        for video_file in video_files:
            video_path = Path(video_file)
            assert video_path.exists(), f"Video file should exist: {video_path}"
            assert video_path.suffix == ".avi", "Video files should be .avi format"
            assert video_path.stat().st_size > 0, "Video files should not be empty"


@pytest.mark.integration
def test_real_session_001_complete_manifest(
    fixture_session_path,
    fixture_session_toml,
    minimal_config_dict,
    expected_camera_count,
    expected_ttl_count,
    expected_bpod_file_count,
):
    """Test complete manifest building with all real Session-000001 components.

    Requirements: FR-1 (Complete discovery workflow)
    """
    from w2t_bkin.config import load_session
    from w2t_bkin.domain import Config
    from w2t_bkin.ingest import build_manifest

    session = load_session(fixture_session_toml)

    config_dict = minimal_config_dict.copy()
    config_dict["paths"]["raw_root"] = str(fixture_session_path.parent)
    config = Config(**config_dict)

    manifest = build_manifest(config, session)

    # Verify completeness
    assert manifest.session_id == session.session.id
    assert len(manifest.cameras) == expected_camera_count
    assert len(manifest.ttls) == expected_ttl_count
    assert len(manifest.bpod_files) == expected_bpod_file_count

    # Verify all paths are absolute
    for camera in manifest.cameras:
        for video_file in camera.video_files:
            assert Path(video_file).is_absolute(), "Video paths should be absolute"

    for ttl in manifest.ttls:
        for ttl_file in ttl.files:
            assert Path(ttl_file).is_absolute(), "TTL paths should be absolute"

    for bpod_file in manifest.bpod_files:
        assert Path(bpod_file).is_absolute(), "Bpod paths should be absolute"


# ===========================================================================
# Synthetic data tests (for specific edge cases)
# ===========================================================================


def test_successful_ingest_and_verification(tmp_path):
    """Build a manifest, count frames/TTLs and verify successfully."""
    from w2t_bkin.config import compute_config_hash, load_config
    from w2t_bkin.domain import Manifest, ManifestCamera
    from w2t_bkin.ingest import (
        build_manifest,
        count_ttl_pulses,
        count_video_frames,
        create_verification_summary,
        verify_manifest,
        write_verification_summary,
    )

    # Load canonical config & session fixtures
    config = load_config(Path(__file__).parent.parent / "fixtures" / "configs" / "valid_config.toml")
    session = __import__("w2t_bkin.config", fromlist=["load_session"]).load_session(
        Path(__file__).parent.parent / "fixtures" / "sessions" / "valid_session.toml"
    )

    # Patch raw_root to tmp_path
    config = config.model_copy(update={"paths": config.paths.model_copy(update={"raw_root": str(tmp_path)})})

    # Create session files: video files and TTL files with matching counts for BOTH cameras
    session_dir = Path(config.paths.raw_root) / session.session.id

    # Create video files for cam0 (top)
    video_dir0 = session_dir / "Video" / "top"
    video_dir0.mkdir(parents=True, exist_ok=True)
    video_file0 = video_dir0 / "cam0_001.avi"
    video_file0.write_text("")  # empty dummy file

    # Create video files for cam1 (pupil_left)
    video_dir1 = session_dir / "Video" / "pupil_left"
    video_dir1.mkdir(parents=True, exist_ok=True)
    video_file1 = video_dir1 / "cam1_001.avi"
    video_file1.write_text("")  # empty dummy file

    # Create TTL files with 1000 pulses
    ttl_dir = session_dir / "TTLs"
    ttl_file = ttl_dir / "sync_xa_7_0.txt"
    _write_lines(ttl_file, 1000)

    # Build manifest
    manifest0 = build_manifest(config, session)

    # Fill counts into new manifest instance
    cameras_filled = []
    for cam in manifest0.cameras:
        fc = count_video_frames(Path(cam.video_files[0]))
        # find ttl file for this ttl_id
        ttl_entry = next((t for t in manifest0.ttls if t.ttl_id == cam.ttl_id), None)
        ttl_path = Path(ttl_entry.files[0]) if ttl_entry and ttl_entry.files else ttl_file
        tc = count_ttl_pulses(ttl_path)
        cameras_filled.append(ManifestCamera(camera_id=cam.camera_id, ttl_id=cam.ttl_id, video_files=cam.video_files, frame_count=fc, ttl_pulse_count=tc))

    manifest = Manifest(session_id=manifest0.session_id, cameras=cameras_filled, ttls=manifest0.ttls, bpod_files=manifest0.bpod_files)

    # Verify (tolerance is 2 in fixture config)
    result = verify_manifest(manifest, tolerance=config.verification.mismatch_tolerance_frames, warn_on_mismatch=config.verification.warn_on_mismatch)
    assert result.status == "verified"

    # Create and write verification summary
    vs = create_verification_summary(manifest)
    out_path = tmp_path / "verification_summary.json"
    # write_verification_summary expects VerificationSummary model, but write_json accepts dict via domain
    write_verification_summary(__import__("w2t_bkin.domain", fromlist=["VerificationSummary"]).VerificationSummary(**vs), out_path)

    # Read back and assert
    with open(out_path, "r") as f:
        data = json.load(f)

    assert data["session_id"] == manifest.session_id
    assert len(data["cameras"]) == len(manifest.cameras)


def test_abort_on_mismatch_exceeds_tolerance(tmp_path):
    """If mismatch > tolerance, verification should raise VerificationError."""
    from w2t_bkin.config import load_config
    from w2t_bkin.domain import Manifest, ManifestCamera
    from w2t_bkin.ingest import build_manifest, verify_manifest

    config = load_config(Path(__file__).parent.parent / "fixtures" / "configs" / "valid_config.toml")
    session = __import__("w2t_bkin.config", fromlist=["load_session"]).load_session(
        Path(__file__).parent.parent / "fixtures" / "sessions" / "valid_session.toml"
    )

    config = config.model_copy(update={"paths": config.paths.model_copy(update={"raw_root": str(tmp_path)})})

    # Create video files for both cameras (frame count stub -> 1000) and TTL file with fewer pulses
    session_dir = Path(config.paths.raw_root) / session.session.id
    (session_dir / "Video" / "top").mkdir(parents=True, exist_ok=True)
    (session_dir / "Video" / "top" / "cam0_001.avi").write_text("")
    (session_dir / "Video" / "pupil_left").mkdir(parents=True, exist_ok=True)
    (session_dir / "Video" / "pupil_left" / "cam1_001.avi").write_text("")

    ttl_dir = session_dir / "TTLs"
    ttl_dir.mkdir(parents=True, exist_ok=True)
    # Create TTL file with 900 pulses
    ttl_file = ttl_dir / "sync_xa_7_0.txt"
    _write_lines(ttl_file, 900)

    manifest0 = build_manifest(config, session)

    cameras_filled = []
    for cam in manifest0.cameras:
        cameras_filled.append(ManifestCamera(camera_id=cam.camera_id, ttl_id=cam.ttl_id, video_files=cam.video_files, frame_count=1000, ttl_pulse_count=900))

    manifest = Manifest(session_id=manifest0.session_id, cameras=cameras_filled, ttls=manifest0.ttls, bpod_files=manifest0.bpod_files)

    # Use tolerance smaller than mismatch (e.g., tolerance 50, mismatch 100)
    with pytest.raises(__import__("w2t_bkin.ingest", fromlist=["VerificationError"]).VerificationError):
        verify_manifest(manifest, tolerance=50, warn_on_mismatch=False)


def test_warn_on_mismatch_within_tolerance(tmp_path, caplog):
    """When mismatch <= tolerance and warn_on_mismatch=True, a warning should be emitted."""
    from w2t_bkin.config import load_config
    from w2t_bkin.domain import Manifest, ManifestCamera
    from w2t_bkin.ingest import build_manifest, verify_manifest

    config = load_config(Path(__file__).parent.parent / "fixtures" / "configs" / "valid_config.toml")
    session = __import__("w2t_bkin.config", fromlist=["load_session"]).load_session(
        Path(__file__).parent.parent / "fixtures" / "sessions" / "valid_session.toml"
    )

    config = config.model_copy(update={"paths": config.paths.model_copy(update={"raw_root": str(tmp_path)})})

    session_dir = Path(config.paths.raw_root) / session.session.id
    (session_dir / "Video" / "top").mkdir(parents=True, exist_ok=True)
    (session_dir / "Video" / "top" / "cam0_001.avi").write_text("")
    (session_dir / "Video" / "pupil_left").mkdir(parents=True, exist_ok=True)
    (session_dir / "Video" / "pupil_left" / "cam1_001.avi").write_text("")

    ttl_dir = session_dir / "TTLs"
    ttl_dir.mkdir(parents=True, exist_ok=True)
    # Create TTL file with 995 pulses (mismatch = 5)
    ttl_file = ttl_dir / "sync_xa_7_0.txt"
    _write_lines(ttl_file, 995)

    manifest0 = build_manifest(config, session)

    cameras_filled = []
    for cam in manifest0.cameras:
        cameras_filled.append(ManifestCamera(camera_id=cam.camera_id, ttl_id=cam.ttl_id, video_files=cam.video_files, frame_count=1000, ttl_pulse_count=995))

    manifest = Manifest(session_id=manifest0.session_id, cameras=cameras_filled, ttls=manifest0.ttls, bpod_files=manifest0.bpod_files)

    caplog.clear()
    caplog.set_level("WARNING")

    # Should not raise, but should emit a warning when warn_on_mismatch=True
    result = verify_manifest(manifest, tolerance=10, warn_on_mismatch=True)
    assert result.status == "verified"
    assert any("has mismatch of" in rec.message for rec in caplog.records)


def test_unverifiable_camera_warns(caplog):
    """Cameras that reference missing TTL ids should be flagged as unverifiable (warning)."""
    from w2t_bkin.domain import BpodSession, Camera, Session, SessionMetadata
    from w2t_bkin.ingest import validate_ttl_references

    # Build a session with a camera referencing a non-existent ttl id
    meta = SessionMetadata(id="s1", subject_id="sub", date="2025-01-01", experimenter="u", description="d", sex="M", age="P60", genotype="WT")
    bpod = BpodSession(path="Bpod/*.mat", order="name_asc")
    cameras = [Camera(id="cam0", description="top", paths="Video/top/*.avi", order="name_asc", ttl_id="missing_ttl")]
    ttls = []
    session = Session(session=meta, bpod=bpod, TTLs=ttls, cameras=cameras)

    caplog.set_level("WARNING")
    validate_ttl_references(session)
    assert any("unverifiable" in rec.message.lower() or "references ttl_id" in rec.message.lower() for rec in caplog.records)
