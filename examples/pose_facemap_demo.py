"""Demonstration of synthetic pose and facemap generation (v0.2.0).

This script showcases the new pose tracking and facemap analysis generators
added in version 0.2.0 of the synthetic data package.
"""

from pathlib import Path
import sys

# Add repo root to path for imports
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

import numpy as np

from synthetic.facemap_synth import FacemapParams, create_facemap_output
from synthetic.pose_synth import PoseParams, create_dlc_pose_csv
from synthetic.scenarios.happy_path import make_complete_session, make_session_with_facemap, make_session_with_pose


def demo_1_pose_generation():
    """Demo 1: Generate pose tracking data."""
    print("\n" + "=" * 70)
    print("=== Demo 1: Pose Tracking Generation ===")
    print("=" * 70)

    # Create pose data with custom parameters
    params = PoseParams(
        keypoints=["nose", "left_ear", "right_ear", "left_eye", "right_eye"],
        n_frames=50,
        image_width=640,
        image_height=480,
        confidence_mean=0.95,
        confidence_std=0.03,
        motion_smoothness=5.0,
        dropout_rate=0.05,  # 5% missing data
    )

    pose_path = create_dlc_pose_csv(Path("temp/demo/pose_tracking.csv"), params, seed=42)

    print(f"✓ Generated pose CSV: {pose_path}")
    print(f"  - Keypoints: {len(params.keypoints)}")
    print(f"  - Frames: {params.n_frames}")
    print(f"  - Mean confidence: {params.confidence_mean}")
    print(f"  - Dropout rate: {params.dropout_rate * 100}%")

    # Load and display sample
    from w2t_bkin.pose import import_dlc_pose

    frames = import_dlc_pose(pose_path)
    print(f"\n✓ Loaded {len(frames)} frames with pipeline")

    # Show first frame
    first_frame = frames[0]
    print(f"\nSample frame {first_frame['frame_index']}:")
    for kp_name, kp_data in first_frame["keypoints"].items():
        print(f"  - {kp_name}: x={kp_data['x']:.2f}, y={kp_data['y']:.2f}, conf={kp_data['confidence']:.3f}")


def demo_2_facemap_generation():
    """Demo 2: Generate facemap motion tracking."""
    print("\n" + "=" * 70)
    print("=== Demo 2: Facemap Motion Tracking ===")
    print("=" * 70)

    # Create facemap data with custom parameters
    params = FacemapParams(
        n_frames=50,
        motion_frequency=2.0,  # 2 Hz dominant frequency
        motion_amplitude=50.0,
        pupil_size_range=(50.0, 150.0),
        pupil_motion_speed=5.0,
        sample_rate=30.0,
    )

    facemap_path = create_facemap_output(Path("temp/demo/facemap_data.npy"), params, seed=42)

    print(f"✓ Generated facemap .npy: {facemap_path}")
    print(f"  - Frames: {params.n_frames}")
    print(f"  - Motion frequency: {params.motion_frequency} Hz")
    print(f"  - Pupil size range: {params.pupil_size_range}")

    # Load and display sample
    data = np.load(facemap_path, allow_pickle=True).item()

    print(f"\n✓ Loaded facemap data")
    print(f"  - Motion energy shape: {data['motion'].shape}")
    print(f"  - Pupil area shape: {data['pupil']['area'].shape}")
    print(f"  - Pupil COM shape: {data['pupil']['com'].shape}")

    # Show statistics
    print(f"\nMotion energy stats:")
    print(f"  - Mean: {data['motion'].mean():.2f}")
    print(f"  - Std: {data['motion'].std():.2f}")
    print(f"  - Range: [{data['motion'].min():.2f}, {data['motion'].max():.2f}]")

    print(f"\nPupil area stats:")
    print(f"  - Mean: {data['pupil']['area'].mean():.2f}")
    print(f"  - Range: [{data['pupil']['area'].min():.2f}, {data['pupil']['area'].max():.2f}]")


def demo_3_session_with_pose():
    """Demo 3: Generate complete session with pose."""
    print("\n" + "=" * 70)
    print("=== Demo 3: Complete Session with Pose ===")
    print("=" * 70)

    session = make_session_with_pose(
        root=Path("temp/demo/session_pose"),
        n_frames=30,
        keypoints=["nose", "left_ear", "right_ear"],
        seed=42,
        use_ffmpeg=False,
    )

    print(f"✓ Generated session with pose tracking")
    print(f"  - Config: {session.config_path}")
    print(f"  - Session: {session.session_path}")
    print(f"  - Videos: {list(session.camera_video_paths.values())}")
    print(f"  - TTLs: {list(session.ttl_paths.values())}")
    print(f"  - Pose: {session.pose_path}")


def demo_4_session_with_facemap():
    """Demo 4: Generate complete session with facemap."""
    print("\n" + "=" * 70)
    print("=== Demo 4: Complete Session with Facemap ===")
    print("=" * 70)

    session = make_session_with_facemap(
        root=Path("temp/demo/session_facemap"),
        n_frames=30,
        seed=42,
        use_ffmpeg=False,
    )

    print(f"✓ Generated session with facemap tracking")
    print(f"  - Config: {session.config_path}")
    print(f"  - Session: {session.session_path}")
    print(f"  - Videos: {list(session.camera_video_paths.values())}")
    print(f"  - TTLs: {list(session.ttl_paths.values())}")
    print(f"  - Facemap: {session.facemap_path}")


def demo_5_complete_session():
    """Demo 5: Generate session with ALL modalities."""
    print("\n" + "=" * 70)
    print("=== Demo 5: Complete Session (All Modalities) ===")
    print("=" * 70)

    session = make_complete_session(
        root=Path("temp/demo/session_complete"),
        n_frames=30,
        n_trials=10,
        keypoints=["nose", "left_ear", "right_ear"],
        seed=42,
        use_ffmpeg=False,
    )

    print(f"✓ Generated complete session with ALL modalities")
    print(f"\nFile inventory:")
    print(f"  - Config: {session.config_path.exists()} ✓")
    print(f"  - Session: {session.session_path.exists()} ✓")
    print(f"  - Videos: {len(session.camera_video_paths)} camera(s) ✓")
    print(f"  - TTLs: {len(session.ttl_paths)} channel(s) ✓")
    print(f"  - Bpod: {session.bpod_path.exists() if session.bpod_path else False} ✓")
    print(f"  - Pose: {session.pose_path.exists() if session.pose_path else False} ✓")
    print(f"  - Facemap: {session.facemap_path.exists() if session.facemap_path else False} ✓")

    print(f"\n🎉 All modalities generated successfully!")


def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("Synthetic Data Package v0.2.0 — Pose & Facemap Demo")
    print("=" * 70)

    try:
        demo_1_pose_generation()
        demo_2_facemap_generation()
        demo_3_session_with_pose()
        demo_4_session_with_facemap()
        demo_5_complete_session()

        print("\n" + "=" * 70)
        print("✓ All demos completed successfully!")
        print("=" * 70)
        print(f"\nGenerated files are in: temp/demo/")
        print("Explore the synthetic/ package for more options.")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
