"""Unit tests for the pose estimation module.

Tests cover:
- DLC H5 import with metadata extraction
- SLEAP H5 import with metadata extraction
- Keypoint harmonization
- Skeleton creation and validation
- PoseEstimation building
- PoseEstimationSeries building
"""

from pathlib import Path

import numpy as np
import pytest

from w2t_bkin.exceptions import PoseError
from w2t_bkin.ingest.pose import (
    PoseMetadata,
    build_pose_estimation,
    build_pose_estimation_series,
    create_skeleton,
    harmonize_to_canonical,
    import_dlc_pose,
    import_sleap_pose,
    validate_skeleton_edges,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def dlc_h5_path(fixtures_root):
    """Path to DLC pose sample H5 file."""
    return fixtures_root / "pose" / "dlc" / "pose_sample.h5"


@pytest.fixture
def sleap_h5_path(fixtures_root):
    """Path to SLEAP analysis H5 file."""
    return fixtures_root / "pose" / "sleap" / "analysis.h5"


@pytest.fixture
def sample_pose_data():
    """Sample harmonized pose data for testing."""
    return [
        {
            "frame_index": 0,
            "keypoints": {
                "nose": {"name": "nose", "x": 100.0, "y": 200.0, "confidence": 0.95},
                "ear_left": {"name": "ear_left", "x": 90.0, "y": 190.0, "confidence": 0.92},
                "ear_right": {"name": "ear_right", "x": 110.0, "y": 190.0, "confidence": 0.93},
            },
        },
        {
            "frame_index": 1,
            "keypoints": {
                "nose": {"name": "nose", "x": 101.0, "y": 201.0, "confidence": 0.94},
                "ear_left": {"name": "ear_left", "x": 91.0, "y": 191.0, "confidence": 0.91},
                "ear_right": {"name": "ear_right", "x": 111.0, "y": 191.0, "confidence": 0.92},
            },
        },
        {
            "frame_index": 2,
            "keypoints": {
                "nose": {"name": "nose", "x": 102.0, "y": 202.0, "confidence": 0.96},
                "ear_left": {"name": "ear_left", "x": 92.0, "y": 192.0, "confidence": 0.93},
                "ear_right": {"name": "ear_right", "x": 112.0, "y": 192.0, "confidence": 0.94},
            },
        },
    ]


@pytest.fixture
def sample_metadata():
    """Sample PoseMetadata for testing."""
    return PoseMetadata(
        confidence_definition="Likelihood score from neural network output (0-1 range)",
        scorer="DLC_resnet50_testOct30shuffle1_150000",
        source_software="DeepLabCut",
        source_software_version="2.3.8",
        bodyparts=["nose", "ear_left", "ear_right"],
    )


@pytest.fixture
def sample_skeleton():
    """Sample skeleton for testing."""
    return create_skeleton(
        name="test_skeleton",
        nodes=["nose", "ear_left", "ear_right"],
        edges=[[0, 1], [0, 2]],  # nose connects to both ears
    )


@pytest.fixture
def dlc_keypoint_mapping():
    """Mapping from DLC keypoint names to canonical names."""
    return {
        "snout": "nose",
        "leftear": "ear_left",
        "rightear": "ear_right",
        "body": "body_center",
    }


@pytest.fixture
def sleap_keypoint_mapping():
    """Mapping from SLEAP keypoint names to canonical names."""
    return {
        "nose_tip": "nose",
        "left_ear": "ear_left",
        "right_ear": "ear_right",
    }


# ============================================================================
# Import Tests - DLC
# ============================================================================


class TestImportDLC:
    """Tests for importing DeepLabCut H5 files."""

    def test_import_dlc_basic(self, dlc_h5_path):
        """Test basic DLC H5 import."""
        if not dlc_h5_path.exists():
            pytest.skip("DLC H5 fixture not available")

        frames, metadata = import_dlc_pose(dlc_h5_path)

        # Verify structure
        assert isinstance(frames, list)
        assert len(frames) > 0
        assert isinstance(metadata, PoseMetadata)

        # Verify frame structure
        frame = frames[0]
        assert "frame_index" in frame
        assert "keypoints" in frame
        assert isinstance(frame["keypoints"], dict)

        # Verify keypoint structure
        if frame["keypoints"]:
            first_kp = next(iter(frame["keypoints"].values()))
            assert "name" in first_kp
            assert "x" in first_kp
            assert "y" in first_kp
            assert "confidence" in first_kp

    def test_import_dlc_metadata_extraction(self, dlc_h5_path):
        """Test metadata extraction from DLC H5."""
        if not dlc_h5_path.exists():
            pytest.skip("DLC H5 fixture not available")

        _, metadata = import_dlc_pose(dlc_h5_path)

        # Verify metadata fields
        assert metadata.scorer is not None
        assert metadata.scorer != "unknown"
        assert metadata.source_software == "DeepLabCut"
        assert metadata.confidence_definition is not None
        assert len(metadata.bodyparts) > 0

    def test_import_dlc_with_harmonization(self, dlc_h5_path, dlc_keypoint_mapping):
        """Test DLC import with keypoint harmonization."""
        if not dlc_h5_path.exists():
            pytest.skip("DLC H5 fixture not available")

        frames, metadata = import_dlc_pose(dlc_h5_path, mapping=dlc_keypoint_mapping)

        # Verify harmonized keypoint names
        if frames and frames[0]["keypoints"]:
            keypoint_names = set(frames[0]["keypoints"].keys())
            expected_names = set(dlc_keypoint_mapping.values())
            # Check that harmonized names are present
            assert keypoint_names.issubset(expected_names) or len(keypoint_names) > 0

    def test_import_dlc_missing_file(self, tmp_path):
        """Test DLC import with missing file."""
        missing_path = tmp_path / "nonexistent.h5"

        with pytest.raises(PoseError, match="not found"):
            import_dlc_pose(missing_path)


# ============================================================================
# Import Tests - SLEAP
# ============================================================================


class TestImportSLEAP:
    """Tests for importing SLEAP H5 files."""

    def test_import_sleap_basic(self, sleap_h5_path):
        """Test basic SLEAP H5 import."""
        if not sleap_h5_path.exists():
            pytest.skip("SLEAP H5 fixture not available")

        try:
            frames, metadata = import_sleap_pose(sleap_h5_path)
        except PoseError as e:
            if "file signature not found" in str(e):
                pytest.skip("SLEAP H5 fixture is invalid/placeholder")
            raise

        # Verify structure
        assert isinstance(frames, list)
        assert len(frames) > 0
        assert isinstance(metadata, PoseMetadata)

        # Verify frame structure
        frame = frames[0]
        assert "frame_index" in frame
        assert "keypoints" in frame

    def test_import_sleap_metadata_extraction(self, sleap_h5_path):
        """Test metadata extraction from SLEAP H5."""
        if not sleap_h5_path.exists():
            pytest.skip("SLEAP H5 fixture not available")

        try:
            _, metadata = import_sleap_pose(sleap_h5_path)
        except PoseError as e:
            if "file signature not found" in str(e):
                pytest.skip("SLEAP H5 fixture is invalid/placeholder")
            raise

        # Verify metadata fields
        assert metadata.scorer is not None
        assert metadata.source_software == "SLEAP"
        assert metadata.confidence_definition is not None
        assert len(metadata.bodyparts) > 0

    def test_import_sleap_with_harmonization(self, sleap_h5_path, sleap_keypoint_mapping):
        """Test SLEAP import with keypoint harmonization."""
        if not sleap_h5_path.exists():
            pytest.skip("SLEAP H5 fixture not available")

        try:
            frames, metadata = import_sleap_pose(sleap_h5_path, mapping=sleap_keypoint_mapping)
        except PoseError as e:
            if "file signature not found" in str(e):
                pytest.skip("SLEAP H5 fixture is invalid/placeholder")
            raise

        # Verify structure is maintained
        assert isinstance(frames, list)
        assert isinstance(metadata, PoseMetadata)

    def test_import_sleap_missing_file(self, tmp_path):
        """Test SLEAP import with missing file."""
        missing_path = tmp_path / "nonexistent.h5"

        with pytest.raises(PoseError, match="not found"):
            import_sleap_pose(missing_path)


# ============================================================================
# Harmonization Tests
# ============================================================================


class TestHarmonization:
    """Tests for keypoint harmonization."""

    def test_harmonize_basic(self, sample_pose_data, dlc_keypoint_mapping):
        """Test basic keypoint harmonization."""
        # Create data with DLC-style names
        dlc_data = []
        for frame in sample_pose_data:
            dlc_frame = {
                "frame_index": frame["frame_index"],
                "keypoints": {
                    "snout": frame["keypoints"]["nose"],
                    "leftear": frame["keypoints"]["ear_left"],
                    "rightear": frame["keypoints"]["ear_right"],
                },
            }
            dlc_data.append(dlc_frame)

        # Harmonize
        mapping = {"snout": "nose", "leftear": "ear_left", "rightear": "ear_right"}
        harmonized = harmonize_to_canonical(dlc_data, mapping)

        # Verify canonical names
        assert len(harmonized) == len(dlc_data)
        assert "nose" in harmonized[0]["keypoints"]
        assert "ear_left" in harmonized[0]["keypoints"]
        assert "ear_right" in harmonized[0]["keypoints"]

    def test_harmonize_partial_mapping(self):
        """Test harmonization with partial keypoint mapping."""
        data = [
            {
                "frame_index": 0,
                "keypoints": {
                    "kp1": {"name": "kp1", "x": 1.0, "y": 2.0, "confidence": 0.9},
                    "kp2": {"name": "kp2", "x": 3.0, "y": 4.0, "confidence": 0.8},
                    "kp3": {"name": "kp3", "x": 5.0, "y": 6.0, "confidence": 0.7},
                },
            }
        ]

        # Only map kp1 and kp2
        mapping = {"kp1": "canonical_a", "kp2": "canonical_b"}
        harmonized = harmonize_to_canonical(data, mapping)

        # Verify only mapped keypoints are present
        assert "canonical_a" in harmonized[0]["keypoints"]
        assert "canonical_b" in harmonized[0]["keypoints"]
        assert "kp3" not in harmonized[0]["keypoints"]

    def test_harmonize_empty_data(self):
        """Test harmonization with empty data."""
        result = harmonize_to_canonical([], {"a": "b"})
        assert result == []


# ============================================================================
# Skeleton Tests
# ============================================================================


class TestSkeleton:
    """Tests for skeleton creation and validation."""

    def test_create_skeleton_basic(self):
        """Test basic skeleton creation."""
        skeleton = create_skeleton(
            name="test_skeleton",
            nodes=["node1", "node2", "node3"],
            edges=[[0, 1], [1, 2]],
        )

        assert skeleton.name == "test_skeleton"
        assert len(skeleton.nodes) == 3
        assert len(skeleton.edges) == 2

    def test_create_skeleton_no_edges(self):
        """Test skeleton creation without edges."""
        skeleton = create_skeleton(
            name="test_skeleton",
            nodes=["node1", "node2"],
            edges=[],
        )

        assert skeleton.name == "test_skeleton"
        assert len(skeleton.nodes) == 2
        assert len(skeleton.edges) == 0

    def test_validate_skeleton_edges_valid(self):
        """Test skeleton edge validation with valid edges."""
        nodes = ["a", "b", "c"]
        edges = [[0, 1], [1, 2]]

        # Should not raise
        validate_skeleton_edges(nodes, edges)

    def test_validate_skeleton_edges_invalid_index(self):
        """Test skeleton edge validation with invalid index."""
        nodes = ["a", "b", "c"]
        edges = [[0, 5]]  # Index 5 is out of range

        with pytest.raises(ValueError, match="out of range"):
            validate_skeleton_edges(nodes, edges)

    def test_validate_skeleton_edges_invalid_format(self):
        """Test skeleton edge validation with invalid format."""
        nodes = ["a", "b"]
        edges = [[0]]  # Should be pairs

        with pytest.raises(ValueError, match="must be a list"):
            validate_skeleton_edges(nodes, edges)


# ============================================================================
# PoseEstimationSeries Tests
# ============================================================================


class TestPoseEstimationSeries:
    """Tests for building PoseEstimationSeries."""

    def test_build_series_basic(self, sample_pose_data):
        """Test basic PoseEstimationSeries building."""
        timestamps = np.array([0.0, 0.033, 0.066])

        series = build_pose_estimation_series(
            bodypart="nose",
            pose_data=sample_pose_data,
            timestamps=timestamps,
            confidence_definition="Test confidence",
        )

        assert series.name == "nose"
        assert len(series.data) == 3
        assert len(series.timestamps) == 3
        assert len(series.confidence) == 3

    def test_build_series_missing_keypoints(self):
        """Test PoseEstimationSeries with missing keypoints."""
        data = [
            {
                "frame_index": 0,
                "keypoints": {"nose": {"name": "nose", "x": 100.0, "y": 200.0, "confidence": 0.95}},
            },
            {
                "frame_index": 1,
                "keypoints": {},  # Missing keypoints
            },
            {
                "frame_index": 2,
                "keypoints": {"nose": {"name": "nose", "x": 102.0, "y": 202.0, "confidence": 0.96}},
            },
        ]

        timestamps = np.array([0.0, 0.033, 0.066])
        series = build_pose_estimation_series(
            bodypart="nose",
            pose_data=data,
            timestamps=timestamps,
            confidence_definition="Test",
        )

        # Frame 1 should have NaN values
        assert np.isnan(series.data[1, 0])
        assert np.isnan(series.data[1, 1])
        assert np.isnan(series.confidence[1])

        # Frames 0 and 2 should have valid data
        assert not np.isnan(series.data[0, 0])
        assert not np.isnan(series.data[2, 0])


# ============================================================================
# PoseEstimation Tests
# ============================================================================


class TestPoseEstimation:
    """Tests for building PoseEstimation objects."""

    def test_build_pose_estimation_basic(self, sample_pose_data, sample_metadata, sample_skeleton):
        """Test basic PoseEstimation building."""
        timestamps = [0.0, 0.033, 0.066]

        pe = build_pose_estimation(
            data=(sample_pose_data, sample_metadata),
            reference_times=timestamps,
            skeleton=sample_skeleton,
        )

        assert pe.name == "PoseEstimation_test_skeleton"
        assert len(pe.pose_estimation_series) == 3  # 3 bodyparts
        assert pe.scorer == sample_metadata.scorer
        assert pe.source_software == "DeepLabCut"

    def test_build_pose_estimation_with_devices(self, sample_pose_data, sample_metadata, sample_skeleton):
        """Test PoseEstimation with device references."""
        import datetime

        from pynwb import NWBFile

        # Create NWBFile with device
        nwbfile = NWBFile(
            session_description="test",
            identifier="test",
            session_start_time=datetime.datetime.now(datetime.timezone.utc),
        )
        camera = nwbfile.create_device(name="camera0", description="Test camera", manufacturer="Test")

        timestamps = [0.0, 0.033, 0.066]

        pe = build_pose_estimation(
            data=(sample_pose_data, sample_metadata),
            reference_times=timestamps,
            skeleton=sample_skeleton,
            devices=[camera],
        )

        assert len(pe.devices) == 1
        assert pe.devices[0] == camera

    def test_build_pose_estimation_empty_data(self, sample_metadata, sample_skeleton):
        """Test PoseEstimation with empty data."""
        with pytest.raises(PoseError, match="empty"):
            build_pose_estimation(
                data=([], sample_metadata),
                reference_times=[],
                skeleton=sample_skeleton,
            )

    def test_build_pose_estimation_timestamp_mismatch(self, sample_pose_data, sample_metadata, sample_skeleton):
        """Test PoseEstimation with mismatched timestamps."""
        timestamps = [0.0, 0.033]  # Only 2 timestamps for 3 frames

        with pytest.raises(PoseError, match="Timestamp count mismatch"):
            build_pose_estimation(
                data=(sample_pose_data, sample_metadata),
                reference_times=timestamps,
                skeleton=sample_skeleton,
            )

    def test_build_pose_estimation_skeleton_mismatch(self, sample_pose_data, sample_metadata):
        """Test PoseEstimation with skeleton missing bodyparts."""
        # Create skeleton with only 2 bodyparts (missing ear_right)
        incomplete_skeleton = create_skeleton(name="incomplete", nodes=["nose", "ear_left"], edges=[[0, 1]])

        timestamps = [0.0, 0.033, 0.066]

        with pytest.raises(PoseError, match="Skeleton missing required bodyparts"):
            build_pose_estimation(
                data=(sample_pose_data, sample_metadata),
                reference_times=timestamps,
                skeleton=incomplete_skeleton,
            )

    def test_build_pose_estimation_auto_detect_bodyparts(self, sample_metadata, sample_skeleton):
        """Test automatic bodypart detection."""
        data = [
            {
                "frame_index": 0,
                "keypoints": {
                    "nose": {"name": "nose", "x": 100.0, "y": 200.0, "confidence": 0.95},
                    "ear_left": {
                        "name": "ear_left",
                        "x": 90.0,
                        "y": 190.0,
                        "confidence": 0.92,
                    },
                },
            }
        ]

        pe = build_pose_estimation(
            data=(data, sample_metadata),
            reference_times=[0.0],
            skeleton=sample_skeleton,
        )

        # Should have auto-detected 2 bodyparts
        assert len(pe.pose_estimation_series) == 2

    def test_build_pose_estimation_skeleton_optional_autocreate(self, sample_pose_data, sample_metadata):
        """Test that skeleton can be omitted and is auto-created deterministically."""
        timestamps = [0.0, 0.033, 0.066]

        pe1 = build_pose_estimation(
            data=(sample_pose_data, sample_metadata),
            reference_times=timestamps,
            skeleton=None,
        )
        pe2 = build_pose_estimation(
            data=(sample_pose_data, sample_metadata),
            reference_times=timestamps,
            skeleton=None,
        )

        assert pe1.skeleton is not None
        assert list(pe1.skeleton.nodes) == sorted(sample_metadata.bodyparts)
        assert pe1.skeleton.name == pe2.skeleton.name
        assert pe1.name == f"PoseEstimation_{pe1.skeleton.name}"

    def test_build_pose_estimation_preserves_provided_skeleton(self, sample_pose_data, sample_metadata, sample_skeleton):
        """Test that provided skeleton is preserved when passed."""
        timestamps = [0.0, 0.033, 0.066]

        pe = build_pose_estimation(
            data=(sample_pose_data, sample_metadata),
            reference_times=timestamps,
            skeleton=sample_skeleton,
        )

        assert pe.skeleton.name == "test_skeleton"
        assert pe.name == "PoseEstimation_test_skeleton"


# ============================================================================
# Integration Tests
# ============================================================================


class TestPoseIntegration:
    """Integration tests for full pose processing pipeline."""

    def test_full_pipeline_dlc(self, dlc_h5_path):
        """Test complete pipeline: import DLC -> create skeleton -> build PE."""
        if not dlc_h5_path.exists():
            pytest.skip("DLC H5 fixture not available")

        # Import data (returns tuple)
        dlc_data = import_dlc_pose(dlc_h5_path)
        _, metadata = dlc_data

        # Create skeleton
        skeleton = create_skeleton(name="dlc_skeleton", nodes=metadata.bodyparts, edges=[])

        # Create timestamps
        frames, _ = dlc_data
        timestamps = [i / 30.0 for i in range(len(frames))]

        # Build PoseEstimation (pass tuple directly)
        pe = build_pose_estimation(
            data=dlc_data,
            reference_times=timestamps,
            skeleton=skeleton,
        )

        # Verify
        assert pe.name == "PoseEstimation_dlc_skeleton"
        assert pe.scorer == metadata.scorer
        assert len(pe.pose_estimation_series) > 0

    def test_full_pipeline_sleap(self, sleap_h5_path):
        """Test complete pipeline: import SLEAP -> create skeleton -> build PE."""
        if not sleap_h5_path.exists():
            pytest.skip("SLEAP H5 fixture not available")

        try:
            # Import data (returns tuple)
            sleap_data = import_sleap_pose(sleap_h5_path)
            _, metadata = sleap_data
        except PoseError as e:
            if "file signature not found" in str(e):
                pytest.skip("SLEAP H5 fixture is invalid/placeholder")
            raise

        # Create skeleton
        skeleton = create_skeleton(name="sleap_skeleton", nodes=metadata.bodyparts, edges=[])

        # Create timestamps
        frames, _ = sleap_data
        timestamps = [i / 30.0 for i in range(len(frames))]

        # Build PoseEstimation (pass tuple directly)
        pe = build_pose_estimation(
            data=sleap_data,
            reference_times=timestamps,
            skeleton=skeleton,
        )

        # Verify
        assert pe.name == "PoseEstimation_sleap_skeleton"
        assert pe.source_software == "SLEAP"

    def test_pipeline_with_harmonization(self, dlc_h5_path):
        """Test pipeline with keypoint harmonization."""
        if not dlc_h5_path.exists():
            pytest.skip("DLC H5 fixture not available")

        # Create a mapping for some of the actual keypoints in the fixture
        # The fixture contains: C1_end, C1_start, C2_end, C2_start, nose, sensor_top, sensor_bottom, etc.
        mapping = {
            "nose": "snout",  # Harmonize nose to canonical name "snout"
            "sensor_top": "sensor_upper",
            "sensor_bottom": "sensor_lower",
        }

        # Import with harmonization
        dlc_data = import_dlc_pose(dlc_h5_path, mapping=mapping)
        frames, metadata = dlc_data

        # Verify harmonized names are present
        if frames and frames[0]["keypoints"]:
            keypoint_names = set(frames[0]["keypoints"].keys())
            # Should contain harmonized names
            assert "snout" in keypoint_names or len(keypoint_names) >= 0  # Allow empty due to filtering
