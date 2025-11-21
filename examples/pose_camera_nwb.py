#!/usr/bin/env python3
"""Example: Pose Estimation + Camera → NWB (simplified).

Goal
----
Show **how to create NWB files from DeepLabCut pose data and video** with a clear
understanding of the data pipeline:

1. Camera system (raw data)
   - Video files recorded at known frame rate (fps)
   - Stored in raw/Session-XXXXX/Video/camera_id/
   - Each frame has an implicit timestamp: t = frame_idx / fps

2. Pose estimation system (interim data)
   - DLC processes videos → outputs H5 files with keypoint trajectories
   - Stored in interim/Session-XXXXX/Pose/camera_id/
   - H5 format: pandas DataFrame with MultiIndex (scorer, bodyparts, coords)
   - Each pose frame corresponds to a video frame (same frame_idx)

3. NWB assembly (output data)
   - Combines video metadata + pose data into standardized NWB format
   - Video referenced externally (not embedded)
   - Pose data stored in PoseEstimation processing module
   - Uses nominal timebase: t = frame_idx / fps

Core idea
---------
For pose estimation data, the alignment is straightforward:

    t_abs = frame_idx / fps

Since DLC processes video frames sequentially, the frame index in the H5 file
corresponds directly to the video frame index. We create a nominal timebase
and align pose frames to it.

Data flow
---------
1. Generate synthetic session with known structure (raw/ and interim/ folders)
2. Import DLC H5 → List[Dict] with frame_idx, keypoints, confidence
3. Create nominal timebase: t = frame_idx / fps
4. Align pose to timebase → PoseFrame objects with timestamps
5. Build PoseBundle (module-local model for NWB assembly)
6. Assemble NWB with manifest + config + pose bundle
7. Generate visualizations (keypoint overlays, trajectories)

Example usage
-------------
    $ python examples/pose_camera_nwb.py

With custom parameters:
    $ N_FRAMES=600 FPS=60.0 python examples/pose_camera_nwb.py
"""

from datetime import datetime
import json
from pathlib import Path
import shutil

import numpy as np
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from figures.pose import plot_pose_keypoints_grid
from synthetic import build_interim_pose, build_raw_folder
from w2t_bkin.domain.session import BpodSession, Camera
from w2t_bkin.domain.session import Session as SessionModel
from w2t_bkin.domain.session import SessionMetadata
from w2t_bkin.nwb import assemble_nwb
from w2t_bkin.pose import align_pose_to_timebase, harmonize_dlc_to_canonical, import_dlc_pose


class ExampleSettings(BaseSettings):
    """Settings for Pose + Camera NWB Example."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    output_root: Path = Field(default=Path("output/pose_camera_nwb"), description="Root directory for synthetic session and output files")
    session_id: str = Field(default="Session-000001", description="Session identifier")
    camera_id: str = Field(default="cam0", description="Camera identifier")
    fps: float = Field(default=30.0, description="Video frame rate (Hz)")
    model_name: str = Field(default="dlc_demo", description="DLC model identifier")

    # Synthetic generation parameters
    n_frames: int = Field(default=300, description="Number of frames to generate")
    n_keypoints: int = Field(default=3, description="Number of keypoints (nose, left_ear, right_ear)")
    seed: int = Field(default=42, description="Random seed for reproducible generation")
    cleanup: bool = Field(default=False, description="Remove existing output directory before running")


if __name__ == "__main__":
    """Run the Pose + Camera → NWB demo."""
    settings = ExampleSettings()

    print("=" * 80)
    print("Example: Pose Estimation + Camera → NWB (simplified)")
    print("=" * 80)

    # Clean output directory if requested
    if settings.output_root.exists() and settings.cleanup:
        shutil.rmtree(settings.output_root)
    settings.output_root.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------------
    # PHASE 0: Generate Synthetic Session
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 0: Generate Synthetic Session")
    print("=" * 80)

    print(f"\nGenerating synthetic session:")
    print(f"  - Session ID:       {settings.session_id}")
    print(f"  - Camera:           {settings.camera_id}")
    print(f"  - Frames:           {settings.n_frames}")
    print(f"  - FPS:              {settings.fps}")
    print(f"  - Keypoints:        {settings.n_keypoints} (nose, left_ear, right_ear)")
    print(f"  - Seed:             {settings.seed}")

    # Build raw folder (videos only)
    print("\nStep 0.1: Build raw folder with videos")
    raw_result = build_raw_folder(
        out_root=settings.output_root / "raw",
        project_name="pose_camera_demo",
        session_id=settings.session_id,
        camera_ids=[settings.camera_id],
        ttl_ids=[],  # No TTLs needed for pose example
        n_frames=settings.n_frames,
        fps=settings.fps,
        segments_per_camera=1,
        seed=settings.seed,
    )

    video_path = raw_result.video_paths[0]  # Single camera
    print(f"  ✓ Raw artifacts:")
    print(f"      Config:    {raw_result.config_path}")
    print(f"      Session:   {raw_result.session_path}")
    print(f"      Video:     {video_path}")

    # Build interim pose data (simulates DLC processing of videos)
    print("\nStep 0.2: Build interim pose data (simulates DLC processing)")
    pose_result = build_interim_pose(
        interim_root=settings.output_root / "interim",
        session_id=settings.session_id,
        camera_ids=[settings.camera_id],
        n_frames=settings.n_frames,
        fps=settings.fps,
        keypoints=["nose", "left_ear", "right_ear"],
        confidence_mean=0.95,
        confidence_std=0.05,
        dropout_rate=0.02,
        seed=settings.seed,
    )

    h5_path = pose_result.pose_paths[0]  # Single camera
    print(f"  ✓ Interim artifacts:")
    print(f"      Pose H5:   {h5_path}")

    # ---------------------------------------------------------------------
    # PHASE 1: Import DLC Pose Data
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 1: Import DLC Pose Data")
    print("=" * 80)

    print(f"\nImporting DLC H5 from interim folder:")
    print(f"  File: {h5_path}")

    pose_data = import_dlc_pose(h5_path)

    # Extract keypoint names from first frame
    keypoints = list(pose_data[0]["keypoints"].keys()) if pose_data else []

    # Compute confidence statistics inline
    confidences = []
    for frame in pose_data:
        for kp_data in frame["keypoints"].values():
            confidences.append(kp_data["confidence"])
    conf_array = np.array(confidences)

    print(f"\nPose data overview:")
    print(f"  - Frames imported:  {len(pose_data)}")
    print(f"  - Keypoints:        {len(keypoints)} ({', '.join(keypoints)})")
    print(f"  - Confidence stats:")
    print(f"      Mean ± Std:     {conf_array.mean():.3f} ± {conf_array.std():.3f}")
    print(f"      Range:          {conf_array.min():.3f} - {conf_array.max():.3f}")
    print(f"      P25/P50/P95:    {np.percentile(conf_array, 25):.3f} / {np.percentile(conf_array, 50):.3f} / {np.percentile(conf_array, 95):.3f}")

    # Show example of first frame structure
    if pose_data:
        first_frame = pose_data[0]
        print(f"\nExample frame structure (frame {first_frame['frame_index']}):")
        for kp_name, kp_data in list(first_frame["keypoints"].items())[:2]:
            print(f"  - {kp_name}: x={kp_data['x']:.1f}, y={kp_data['y']:.1f}, conf={kp_data['confidence']:.3f}")
        if len(first_frame["keypoints"]) > 2:
            print(f"  ... and {len(first_frame['keypoints']) - 2} more keypoints")

    # ---------------------------------------------------------------------
    # PHASE 2: Create Nominal Timebase and Align (NWB-First)
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 2: Create Nominal Timebase and Align (NWB-First)")
    print("=" * 80)

    print("\nStep 2.1: Create nominal timebase")
    print(f"  Formula: t = frame_idx / fps")
    print(f"  FPS: {settings.fps} Hz")

    reference_times = np.arange(len(pose_data)) / settings.fps

    print(f"  Time span: 0.000 - {reference_times[-1]:.3f} s ({len(reference_times)} frames)")

    # Show example for first few frames
    print(f"\nExample timebase mapping:")
    for i in [0, 1, 2, len(reference_times) - 1]:
        if i < len(reference_times):
            print(f"  - Frame {i:3d} → t = {reference_times[i]:.3f} s")

    print("\nStep 2.2: Harmonize DLC keypoints to canonical schema")
    print(f"  Using identity mapping (no skeleton conversion)")
    # Create identity mapping for demonstration
    identity_mapping = {kp: kp for kp in keypoints}
    harmonized_pose = harmonize_dlc_to_canonical(pose_data, identity_mapping)
    print(f"  ✓ Harmonized {len(harmonized_pose)} frames")

    print("\nStep 2.3: Align pose frames and build PoseEstimation (NWB-native)")
    print(f"  Alignment method: nearest")
    print(f"  Source: dlc")
    print(f"  Mode: NWB-first (returns PoseEstimation directly)")

    # NEW: Use NWB-first mode to get PoseEstimation directly
    pose_estimation = align_pose_to_timebase(
        data=harmonized_pose,
        reference_times=reference_times,
        mapping="nearest",
        source="dlc",
        camera_id=settings.camera_id,
        bodyparts=keypoints,
        skeleton_edges=None,  # Could provide skeleton connectivity here
        model_name=settings.model_name,
    )

    print(f"  ✓ Created PoseEstimation with {len(pose_estimation.pose_estimation_series)} keypoint series")

    # Show PoseEstimation details
    print(f"\nPoseEstimation structure:")
    print(f"  - Name:             {pose_estimation.name}")
    print(f"  - Scorer:           {pose_estimation.scorer}")
    print(f"  - Source software:  {pose_estimation.source_software}")
    print(f"  - Keypoints:        {len(pose_estimation.pose_estimation_series)}")
    print(f"  - Skeleton nodes:   {len(pose_estimation.skeleton.nodes)}")

    # Show example series
    if pose_estimation.pose_estimation_series:
        first_kp = list(pose_estimation.pose_estimation_series.keys())[0]
        series = pose_estimation.pose_estimation_series[first_kp]
        print(f"\nExample series ('{first_kp}'):")
        print(f"  - Data shape:       {series.data.shape} (frames, xy)")
        print(f"  - First position:   x={series.data[0, 0]:.1f}, y={series.data[0, 1]:.1f}")
        print(f"  - Confidence:       {series.confidence[0]:.3f}")
        print(f"  - Timestamps:       {len(series.timestamps)} frames")

    # ---------------------------------------------------------------------
    # PHASE 3: Build Session Manifest (Simplified - No PoseBundle)
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 3: Build Session Manifest (NWB-First)")
    print("=" * 80)

    print("\nStep 3.1: Create session manifest")
    print(f"  Note: PoseEstimation is already in NWB format")
    print(f"  No intermediate PoseBundle needed with NWB-first approach")
    print(f"  ✓ PoseEstimation ready for direct inclusion in NWB file")

    # ---------------------------------------------------------------------
    # PHASE 4: Build Manifest and Config
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 4: Build Manifest and Config")
    print("=" * 80)

    print("\nStep 4.1: Build camera metadata")
    # Build inline (no helper function)
    camera_metadata = {
        "camera_id": settings.camera_id,
        "video_path": str(video_path.resolve()),
        "frame_rate": settings.fps,
        "frame_count": settings.n_frames,
        "starting_time": 0.0,
        "manufacturer": "Demo",
        "description": f"Camera {settings.camera_id}",
    }
    print(f"  Camera ID:       {camera_metadata['camera_id']}")
    print(f"  Video:           {Path(camera_metadata['video_path']).name}")
    print(f"  Frame rate:      {camera_metadata['frame_rate']} Hz")
    print(f"  Frame count:     {camera_metadata['frame_count']}")

    print("\nStep 4.2: Build manifest (NWB-first)")
    manifest = {
        "session_id": settings.session_id,
        "cameras": [camera_metadata],
        "pose_estimations": [pose_estimation],  # Direct NWB objects
    }
    print(f"  Session ID:      {manifest['session_id']}")
    print(f"  Cameras:         {len(manifest['cameras'])}")
    print(f"  Pose data:       {len(manifest['pose_estimations'])} PoseEstimation(s)")

    print("\nStep 4.3: Build config")
    config = {
        "nwb": {
            "session_description": f"Pose + Camera demo session {settings.session_id}",
            "file_name_template": "{session_id}.nwb",
            "lab": "Demo Lab",
            "institution": "Demo Institution",
            "experimenter": ["Demo User"],
        }
    }
    print(f"  Lab:             {config['nwb']['lab']}")
    print(f"  Institution:     {config['nwb']['institution']}")

    # ---------------------------------------------------------------------
    # PHASE 5: Assemble NWB File
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 5: Assemble NWB File")
    print("=" * 80)

    output_dir = settings.output_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nOutput directory: {output_dir}")

    # Build provenance dict inline
    provenance = {
        "timebase": {
            "source": "nominal_rate",
            "fps": settings.fps,
            "alignment_method": "nearest",
        },
        "software": {
            "name": "w2t_bkin",
            "version": "0.1.0-dev",
            "example": "pose_camera_nwb.py",
        },
        "generated_at": datetime.now().isoformat(),
    }

    # NWB-first mode: extract PoseEstimation from manifest
    pose_estimations_list = manifest.get("pose_estimations", [])

    nwb_path = assemble_nwb(
        manifest=manifest,
        config=config,
        provenance=provenance,
        output_dir=output_dir,
        pose_estimations=pose_estimations_list,  # NWB-first mode
    )

    nwb_size_kb = nwb_path.stat().st_size / 1024

    # Get frame count from PoseEstimation
    n_frames = len(pose_estimation.pose_estimation_series[keypoints[0]].data) if keypoints else 0

    print(f"\n  ✓ NWB file created: {nwb_path}")
    print(f"    Size:          {nwb_size_kb:.1f} KB")
    print(f"    Cameras:       1")
    print(f"    Pose frames:   {n_frames}")

    # ---------------------------------------------------------------------
    # PHASE 6: Generate Visualizations (TODO: Update for NWB-first mode)
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 6: Generate Visualizations")
    print("=" * 80)

    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nFigures directory: {figures_dir}")

    # TODO: Update plot_pose_keypoints_grid to accept PoseEstimation instead of PoseBundle
    print("\nStep 6.1: Pose keypoints grid (skipped - requires PoseBundle adaptation)")
    print("  Note: Visualization functions will be updated in next iteration")

    # Create pose summary JSON
    print("\nStep 6.2: Pose summary JSON")
    pose_summary = {
        "session_id": settings.session_id,
        "camera_id": settings.camera_id,
        "model_name": settings.model_name,
        "total_frames": n_frames,
        "mean_confidence": float(conf_array.mean()),
        "keypoints": keypoints,
        "fps": settings.fps,
        "duration_s": float(reference_times[-1]),
        "nwb_file": str(nwb_path),
        "nwb_size_kb": float(nwb_size_kb),
    }

    summary_path = output_dir / "pose_summary.json"
    with open(summary_path, "w") as f:
        json.dump(pose_summary, f, indent=2)
    print(f"  ✓ Saved: {summary_path}")

    # ---------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    print(f"\nGenerated artifacts:")
    print(f"  - NWB file:        {nwb_path}")
    print(f"  - Pose summary:    {summary_path}")

    print(f"\nPose statistics:")
    print(f"  - Total frames:    {n_frames}")
    print(f"  - Mean confidence: {conf_array.mean():.3f}")
    print(f"  - Duration:        {reference_times[-1]:.3f} s")
    print(f"  - Keypoints:       {len(keypoints)}")

    print(f"\nData flow summary (NWB-First):")
    print(f"  1. Synthetic session → raw/ (videos) + interim/ (DLC H5)")
    print(f"  2. DLC H5 → import_dlc_pose() → {len(pose_data)} frames")
    print(f"  3. Harmonize → align_pose_to_timebase() → PoseEstimation (NWB-native)")
    print(f"  4. PoseEstimation → NWB assembly → {nwb_path.name}")
    print(f"  5. No intermediate PoseBundle needed!")

    print("\nDone.")
