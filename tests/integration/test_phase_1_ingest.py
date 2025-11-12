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
