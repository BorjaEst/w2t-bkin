#!/usr/bin/env python3
"""Simple validation script for optional camera verification logic.

This script demonstrates the fixed behavior without requiring a full test environment.
Run with: python3 tests/unit/validate_optional_camera_fix.py
"""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from w2t_bkin.exceptions import MismatchExceedsToleranceError, VerificationError
from w2t_bkin.models import SessionConfig
from w2t_bkin.operations.verification import verify_camera_ttl_sync


def test_optional_camera_missing_videos():
    """Test that optional camera with no videos skips verification even if TTL exists."""
    print("TEST 1: Optional camera with no videos (frame_count=0) + TTL exists")

    session_config = SessionConfig(
        config={},
        metadata={
            "cameras": [
                {
                    "id": "face_right",
                    "ttl_id": "ttl_camera",
                    "optional": True,
                }
            ]
        },
        config_path=None,
        session_dir=None,
        output_dir=None,
    )

    frame_counts = {"face_right": 0}  # No frames discovered
    ttl_counts = {"ttl_camera": 510392}  # TTL channel exists with pulses

    try:
        verify_camera_ttl_sync(
            frame_counts=frame_counts,
            ttl_counts=ttl_counts,
            session_config=session_config,
            tolerance=0,
        )
        print("✓ PASS: No exception raised (camera skipped as expected)\n")
        return True
    except Exception as e:
        print(f"✗ FAIL: Unexpected exception: {e}\n")
        return False


def test_optional_camera_not_discovered():
    """Test that optional camera not in frame_counts dict skips verification."""
    print("TEST 2: Optional camera not discovered (not in frame_counts)")

    session_config = SessionConfig(
        config={},
        metadata={
            "cameras": [
                {
                    "id": "face_right",
                    "ttl_id": "ttl_camera",
                    "optional": True,
                }
            ]
        },
        config_path=None,
        session_dir=None,
        output_dir=None,
    )

    frame_counts = {}  # Camera not discovered
    ttl_counts = {"ttl_camera": 510392}

    try:
        verify_camera_ttl_sync(
            frame_counts=frame_counts,
            ttl_counts=ttl_counts,
            session_config=session_config,
            tolerance=0,
        )
        print("✓ PASS: No exception raised (camera skipped as expected)\n")
        return True
    except Exception as e:
        print(f"✗ FAIL: Unexpected exception: {e}\n")
        return False


def test_required_camera_missing():
    """Test that non-optional camera with no videos raises VerificationError."""
    print("TEST 3: Required camera not discovered (should fail)")

    session_config = SessionConfig(
        config={},
        metadata={
            "cameras": [
                {
                    "id": "face_left",
                    "ttl_id": "ttl_camera",
                    "optional": False,
                }
            ]
        },
        config_path=None,
        session_dir=None,
        output_dir=None,
    )

    frame_counts = {}  # Camera not discovered
    ttl_counts = {"ttl_camera": 510392}

    try:
        verify_camera_ttl_sync(
            frame_counts=frame_counts,
            ttl_counts=ttl_counts,
            session_config=session_config,
            tolerance=0,
        )
        print("✗ FAIL: No exception raised (should have raised VerificationError)\n")
        return False
    except VerificationError as e:
        print(f"✓ PASS: Raised VerificationError as expected: {e.message}\n")
        return True
    except Exception as e:
        print(f"✗ FAIL: Wrong exception type: {type(e).__name__}: {e}\n")
        return False


def test_optional_camera_with_videos_mismatched():
    """Test that optional camera with videos present still verifies sync."""
    print("TEST 4: Optional camera WITH videos but mismatched (should fail)")

    session_config = SessionConfig(
        config={},
        metadata={
            "cameras": [
                {
                    "id": "face_right",
                    "ttl_id": "ttl_camera",
                    "optional": True,
                }
            ]
        },
        config_path=None,
        session_dir=None,
        output_dir=None,
    )

    frame_counts = {"face_right": 100}  # Videos discovered
    ttl_counts = {"ttl_camera": 200}  # Mismatch

    try:
        verify_camera_ttl_sync(
            frame_counts=frame_counts,
            ttl_counts=ttl_counts,
            session_config=session_config,
            tolerance=0,
        )
        print("✗ FAIL: No exception raised (should have raised MismatchExceedsToleranceError)\n")
        return False
    except MismatchExceedsToleranceError as e:
        print(f"✓ PASS: Raised MismatchExceedsToleranceError as expected: {e.message}\n")
        return True
    except Exception as e:
        print(f"✗ FAIL: Wrong exception type: {type(e).__name__}: {e}\n")
        return False


def main():
    """Run all validation tests."""
    print("=" * 70)
    print("Optional Camera Verification Logic Validation")
    print("=" * 70)
    print()

    results = [
        test_optional_camera_missing_videos(),
        test_optional_camera_not_discovered(),
        test_required_camera_missing(),
        test_optional_camera_with_videos_mismatched(),
    ]

    print("=" * 70)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✓ ALL TESTS PASSED ({passed}/{total})")
        print("=" * 70)
        return 0
    else:
        print(f"✗ SOME TESTS FAILED ({passed}/{total} passed)")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
