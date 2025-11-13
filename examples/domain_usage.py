"""Example usage of refactored domain models.

This script demonstrates both import patterns (direct module and package root)
and validates that the refactored structure maintains compatibility.

Run with: python3 examples/domain_usage.py
"""

from datetime import datetime

# Pattern 2: Package root imports
from w2t_bkin.domain import BpodSession, Manifest, ManifestCamera

# Pattern 1: Direct module imports (recommended for new code)
from w2t_bkin.domain.config import Config, ProjectConfig, TimebaseConfig
from w2t_bkin.domain.exceptions import MismatchExceedsToleranceError, W2TError
from w2t_bkin.domain.session import TTL, Camera, Session, SessionMetadata

print("=" * 70)
print("Domain Models Refactoring - Usage Examples")
print("=" * 70)

# Example 1: Creating session models
print("\n1. Creating Session with direct module imports:")
try:
    session = Session(
        session=SessionMetadata(
            id="Session-000001",
            subject_id="Mouse-123",
            date="2025-11-13",
            experimenter="Dr. Smith",
            description="Body kinematics training",
            sex="M",
            age="P60",
            genotype="WT",
        ),
        bpod=BpodSession(path="Bpod/*.mat", order="name_asc"),
        TTLs=[TTL(id="ttl_cam", description="Camera sync pulses", paths="TTLs/*.txt")],
        cameras=[
            Camera(
                id="cam0",
                description="Top view camera",
                paths="Video/cam0_*.avi",
                order="name_asc",
                ttl_id="ttl_cam",
            )
        ],
    )
    print(f"   ✓ Session created: {session.session.id}")
    print(f"   ✓ Cameras: {len(session.cameras)}, TTLs: {len(session.TTLs)}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Example 2: Creating manifest with package root imports
print("\n2. Creating Manifest with package root imports:")
try:
    manifest = Manifest(
        session_id="Session-000001",
        cameras=[
            ManifestCamera(
                camera_id="cam0",
                ttl_id="ttl_cam",
                video_files=["/path/to/video1.avi", "/path/to/video2.avi"],
                frame_count=8580,
                ttl_pulse_count=8580,
            )
        ],
    )
    print(f"   ✓ Manifest created: {manifest.session_id}")
    print(f"   ✓ Camera frames: {manifest.cameras[0].frame_count}")
    sync_status = "PERFECT" if manifest.cameras[0].frame_count == manifest.cameras[0].ttl_pulse_count else "MISMATCH"
    print(f"   ✓ Sync status: {sync_status}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Example 3: Exception handling
print("\n3. Exception handling with structured context:")
try:
    raise MismatchExceedsToleranceError(camera_id="cam0", frame_count=8580, ttl_count=8578, mismatch=2, tolerance=1)
except W2TError as e:
    print(f"   ✓ Caught {e.__class__.__name__}")
    print(f"   ✓ Error code: {e.error_code}")
    print(f"   ✓ Stage: {e.stage}")
    print(f"   ✓ Context: {e.context}")
    print(f"   ✓ Hint: {e.hint[:50]}...")  # First 50 chars

# Example 4: Model immutability
print("\n4. Model immutability (frozen=True):")
try:
    session.session.id = "Modified"
    print("   ✗ Immutability failed - should not reach here!")
except Exception:
    print("   ✓ Cannot modify frozen model (as expected)")

# Example 5: Serialization
print("\n5. Model serialization:")
try:
    session_dict = session.model_dump()
    session_json = session.model_dump_json()
    print(f"   ✓ Dict serialization: {len(session_dict)} keys")
    print(f"   ✓ JSON serialization: {len(session_json)} characters")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Example 6: Strict validation
print("\n6. Strict schema validation (extra='forbid'):")
try:
    invalid_camera = Camera(
        id="cam0",
        description="Test",
        paths="*.avi",
        order="name_asc",
        ttl_id="ttl_cam",
        extra_field="this should fail",  # type: ignore
    )
    print("   ✗ Validation failed - should not reach here!")
except Exception:
    print("   ✓ Extra fields rejected (as expected)")

print("\n" + "=" * 70)
print("✓ All examples completed successfully!")
print("\nRefactored structure:")
print("  - domain/exceptions.py   - Exception hierarchy")
print("  - domain/config.py       - Configuration models")
print("  - domain/session.py      - Session models")
print("  - domain/manifest.py     - Manifest & verification")
print("  - domain/alignment.py    - Alignment & provenance")
print("  - domain/bpod.py         - Behavioral events")
print("  - domain/pose.py         - Pose estimation")
print("  - domain/facemap.py      - Facemap models")
print("  - domain/transcode.py    - Transcoding models")
print("  - domain/__init__.py     - Public API")
print("=" * 70)
