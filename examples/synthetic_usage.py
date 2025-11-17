"""Example: Using synthetic data for rapid prototyping and testing.

This script demonstrates how to use the synthetic data generation package
to quickly create test sessions and verify pipeline behavior without
needing real experimental data.

Usage:
    python examples/synthetic_usage.py
"""

from pathlib import Path
import sys

# Add project root to path so we can import synthetic
sys.path.insert(0, str(Path(__file__).parent.parent))

from synthetic.scenarios import happy_path, mismatch_counts, multi_camera
from w2t_bkin.config import load_config, load_session
from w2t_bkin.ingest import build_and_count_manifest, verify_manifest


def example_1_happy_path():
    """Example 1: Generate and verify a perfect session."""
    print("\n=== Example 1: Happy Path Session ===")

    # Generate a synthetic session
    session = happy_path.make_session(
        root=Path("temp/example_sessions/happy"),
        session_id="example-happy-001",
        n_frames=100,
        seed=42,
        use_ffmpeg=False,  # Use stubs for speed
    )

    print(f"✓ Generated session at: {session.raw_dir}")
    print(f"  - Config: {session.config_path}")
    print(f"  - Session: {session.session_path}")
    print(f"  - Videos: {len(session.camera_video_paths)} camera(s)")
    print(f"  - TTLs: {len(session.ttl_paths)} channel(s)")

    # Load and verify
    config = load_config(session.config_path)
    session_data = load_session(session.session_path)

    manifest = build_and_count_manifest(config, session_data)
    result = verify_manifest(manifest, tolerance=5)

    print(f"✓ Verification: {result.status}")
    print(f"  - Camera: {result.camera_results[0].camera_id}")
    print(f"  - Frames: {result.camera_results[0].frame_count}")
    print(f"  - Pulses: {result.camera_results[0].ttl_pulse_count}")
    print(f"  - Mismatch: {result.camera_results[0].mismatch}")


def example_2_mismatch_detection():
    """Example 2: Test mismatch detection logic."""
    print("\n=== Example 2: Mismatch Detection ===")

    # Generate session with deliberate mismatch
    session = mismatch_counts.make_session(
        root=Path("temp/example_sessions/mismatch"),
        session_id="example-mismatch-001",
        n_frames=100,
        n_pulses=95,  # 5 frame mismatch
        seed=42,
        use_ffmpeg=False,
    )

    print(f"✓ Generated session with mismatch")
    print(f"  - Expected frames: 100")
    print(f"  - Expected pulses: 95")
    print(f"  - Expected mismatch: 5")

    # Verify
    config = load_config(session.config_path)
    session_data = load_session(session.session_path)
    manifest = build_and_count_manifest(config, session_data)
    result = verify_manifest(manifest, tolerance=5)

    print(f"✓ Verification: {result.status}")
    print(f"  - Actual mismatch: {result.camera_results[0].mismatch}")
    print(f"  - Within tolerance: {result.camera_results[0].mismatch <= 5}")


def example_3_multi_camera():
    """Example 3: Multi-camera session."""
    print("\n=== Example 3: Multi-Camera Session ===")

    # Generate multi-camera session
    session = multi_camera.make_session(
        root=Path("temp/example_sessions/multi"),
        session_id="example-multi-001",
        n_cameras=3,
        n_frames=64,
        seed=42,
        use_ffmpeg=False,
    )

    print(f"✓ Generated multi-camera session")
    print(f"  - Cameras: {len(session.camera_video_paths)}")
    for cam_id, videos in session.camera_video_paths.items():
        print(f"    - {cam_id}: {len(videos)} video(s)")
    print(f"  - TTL channels: {len(session.ttl_paths)}")
    for ttl_id in session.ttl_paths.keys():
        print(f"    - {ttl_id}")

    # Verify all cameras
    config = load_config(session.config_path)
    session_data = load_session(session.session_path)
    manifest = build_and_count_manifest(config, session_data)
    result = verify_manifest(manifest, tolerance=5)

    print(f"✓ Verification: {result.status}")
    for cam_result in result.camera_results:
        print(f"  - {cam_result.camera_id}: {cam_result.status} (mismatch={cam_result.mismatch})")


def example_4_with_bpod():
    """Example 4: Session with Bpod behavioral data."""
    print("\n=== Example 4: Session with Bpod Data ===")

    try:
        import scipy  # noqa: F401

        # Generate session with Bpod trials
        session = happy_path.make_session_with_bpod(
            root=Path("temp/example_sessions/bpod"),
            session_id="example-bpod-001",
            n_frames=100,
            n_trials=20,
            seed=42,
            use_ffmpeg=False,
        )

        print(f"✓ Generated session with Bpod data")
        print(f"  - Bpod file: {session.bpod_path}")
        print(f"  - Expected trials: 20")

        # Load Bpod file to verify
        from scipy.io import loadmat

        bpod_data = loadmat(session.bpod_path, struct_as_record=False, squeeze_me=True)
        n_trials = bpod_data["SessionData"].nTrials

        print(f"✓ Bpod file loaded successfully")
        print(f"  - Actual trials: {n_trials}")
        print(f"  - Trial types: {bpod_data['SessionData'].TrialTypes[:5]}... (first 5)")

    except ImportError:
        print("⚠ Scipy not installed - skipping Bpod example")
        print("  Install with: pip install scipy")


def example_5_custom_scenario():
    """Example 5: Create a custom scenario."""
    print("\n=== Example 5: Custom Scenario ===")

    from synthetic.models import SyntheticCamera, SyntheticSessionParams, SyntheticTTL
    from synthetic.session_synth import create_session

    # Define custom parameters
    params = SyntheticSessionParams(
        session_id="example-custom-001",
        subject_id="mouse_123",
        experimenter="Dr. Smith",
        date="2025-01-20",
        cameras=[
            SyntheticCamera(
                camera_id="top_cam",
                ttl_id="sync_ttl",
                frame_count=150,
                fps=60.0,  # High-speed camera
                resolution=(1280, 720),
            ),
            SyntheticCamera(
                camera_id="side_cam",
                ttl_id="sync_ttl",  # Shared TTL
                frame_count=150,
                fps=60.0,
                resolution=(640, 480),
            ),
        ],
        ttls=[
            SyntheticTTL(
                ttl_id="sync_ttl",
                pulse_count=150,
                period_s=1.0 / 60.0,  # 60 Hz
                jitter_s=0.0005,  # 0.5ms jitter
            )
        ],
        with_bpod=False,
        seed=42,
    )

    # Generate
    session = create_session(
        root=Path("temp/example_sessions/custom"),
        params=params,
        use_ffmpeg=False,
    )

    print(f"✓ Generated custom session")
    print(f"  - Session ID: {params.session_id}")
    print(f"  - Subject: {params.subject_id}")
    print(f"  - Cameras: {len(params.cameras)}")
    print(f"  - Frame rate: {params.cameras[0].fps} fps")
    print(f"  - Resolution: {params.cameras[0].resolution}")
    print(f"  - Shared TTL: {params.cameras[0].ttl_id == params.cameras[1].ttl_id}")


def main():
    """Run all examples."""
    print("=" * 70)
    print("Synthetic Data Generation Examples")
    print("=" * 70)

    example_1_happy_path()
    example_2_mismatch_detection()
    example_3_multi_camera()
    example_4_with_bpod()
    example_5_custom_scenario()

    print("\n" + "=" * 70)
    print("✓ All examples completed successfully!")
    print("=" * 70)
    print("\nGenerated files are in: temp/example_sessions/")
    print("Explore the synthetic/ package for more options.")


if __name__ == "__main__":
    main()
