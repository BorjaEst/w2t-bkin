"""Unit tests for synthetic pose and facemap generators."""

import csv
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.skip(reason="pose_synth and facemap_synth modules not yet implemented")

# NOTE: These imports will fail until modules are created
# from synthetic.facemap_synth import FacemapParams, create_facemap_output, create_simple_facemap, generate_motion_energy, generate_pupil_area, generate_pupil_com
# from synthetic.pose_synth import PoseParams, create_dlc_pose_csv, create_simple_pose_csv, generate_confidence_scores, generate_smooth_trajectory


class TestPoseGeneration:
    """Tests for pose data generation."""

    def test_generate_smooth_trajectory(self):
        """Test smooth trajectory generation."""
        trajectory = generate_smooth_trajectory(
            n_frames=100,
            start_pos=(320, 240),
            bounds=(0, 0, 640, 480),
            smoothness=5.0,
            seed=42,
        )

        assert trajectory.shape == (100, 2)
        assert np.all(trajectory[:, 0] >= 0) and np.all(trajectory[:, 0] <= 640)
        assert np.all(trajectory[:, 1] >= 0) and np.all(trajectory[:, 1] <= 480)
        assert trajectory[0, 0] == 320
        assert trajectory[0, 1] == 240

    def test_generate_confidence_scores(self):
        """Test confidence score generation."""
        scores = generate_confidence_scores(n_frames=100, mean=0.95, std=0.03, seed=42)

        assert scores.shape == (100,)
        assert np.all(scores >= 0.0) and np.all(scores <= 1.0)
        assert 0.90 < np.mean(scores) < 1.0

    def test_create_dlc_pose_csv_basic(self, tmp_path):
        """Test basic DLC CSV creation."""
        params = PoseParams(
            keypoints=["nose", "left_ear", "right_ear"],
            n_frames=10,
        )

        csv_path = create_dlc_pose_csv(tmp_path / "pose.csv", params, seed=42)

        assert csv_path.exists()

        # Read and validate CSV structure
        with open(csv_path, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Check structure
        assert len(rows) == 13  # 3 header rows + 10 data rows
        assert rows[0][0] == "scorer"
        assert rows[1][0] == "bodyparts"
        assert rows[2][0] == "coords"

        # Check keypoints in header
        assert "nose" in rows[1]
        assert "left_ear" in rows[1]
        assert "right_ear" in rows[1]

        # Check data row
        data_row = rows[3]
        assert data_row[0] == "0"  # Frame index
        assert len(data_row) == 1 + (3 * 3)  # Frame idx + 3 keypoints * 3 values

    def test_create_dlc_pose_csv_deterministic(self, tmp_path):
        """Test pose generation is deterministic."""
        params = PoseParams(keypoints=["nose"], n_frames=5)

        csv1 = create_dlc_pose_csv(tmp_path / "pose1.csv", params, seed=42)
        csv2 = create_dlc_pose_csv(tmp_path / "pose2.csv", params, seed=42)

        # Read both files
        with open(csv1) as f1, open(csv2) as f2:
            content1 = f1.read()
            content2 = f2.read()

        assert content1 == content2

    def test_create_dlc_pose_csv_with_dropout(self, tmp_path):
        """Test pose CSV with missing data."""
        params = PoseParams(
            keypoints=["nose"],
            n_frames=100,
            dropout_rate=0.1,  # 10% dropout
        )

        csv_path = create_dlc_pose_csv(tmp_path / "pose_dropout.csv", params, seed=42)

        # Read and check for low confidence (dropout)
        with open(csv_path) as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Count rows with 0.0 confidence (dropout)
        dropout_count = sum(1 for row in rows[3:] if len(row) > 3 and float(row[3]) == 0.0)  # Skip header  # likelihood column

        # Should have some dropouts (not exact due to randomness)
        assert dropout_count > 0

    def test_create_simple_pose_csv(self, tmp_path):
        """Test simple pose CSV creation."""
        csv_path = create_simple_pose_csv(tmp_path / "simple.csv", n_frames=10, seed=42)

        assert csv_path.exists()

        with open(csv_path) as f:
            lines = f.readlines()

        assert len(lines) == 13  # 3 header + 10 data rows

    def test_pose_integration_with_pipeline(self, tmp_path):
        """Test that generated pose data can be loaded by pipeline."""
        params = PoseParams(
            keypoints=["nose", "left_ear", "right_ear"],
            n_frames=10,
        )

        csv_path = create_dlc_pose_csv(tmp_path / "pose.csv", params, seed=42)

        # Import using pipeline's pose module
        from w2t_bkin.pose import import_dlc_pose

        frames = import_dlc_pose(csv_path)

        assert len(frames) == 10
        assert frames[0]["frame_index"] == 0
        assert "nose" in frames[0]["keypoints"]
        assert frames[0]["keypoints"]["nose"]["x"] > 0
        assert frames[0]["keypoints"]["nose"]["confidence"] > 0.9


class TestFacemapGeneration:
    """Tests for facemap data generation."""

    def test_generate_motion_energy(self):
        """Test motion energy generation."""
        motion = generate_motion_energy(n_frames=100, frequency=2.0, amplitude=50.0, seed=42)

        assert motion.shape == (100,)
        assert np.all(motion >= 0)  # Motion energy is always positive
        assert motion.mean() > 0

    def test_generate_pupil_area(self):
        """Test pupil area generation."""
        area = generate_pupil_area(n_frames=100, size_range=(50.0, 150.0), seed=42)

        assert area.shape == (100,)
        assert np.all(area >= 50.0) and np.all(area <= 150.0)

    def test_generate_pupil_com(self):
        """Test pupil COM generation."""
        com = generate_pupil_com(n_frames=100, image_width=640, image_height=480, seed=42)

        assert com.shape == (100, 2)
        # Check reasonable bounds
        assert np.all(com[:, 0] > 0) and np.all(com[:, 0] < 640)
        assert np.all(com[:, 1] > 0) and np.all(com[:, 1] < 480)

    def test_create_facemap_output_basic(self, tmp_path):
        """Test basic facemap creation."""
        params = FacemapParams(n_frames=50)

        npy_path = create_facemap_output(tmp_path / "facemap.npy", params, seed=42)

        assert npy_path.exists()

        # Load and validate
        data = np.load(npy_path, allow_pickle=True).item()

        assert "motion" in data
        assert "pupil" in data
        assert data["motion"].shape == (50,)
        assert "area" in data["pupil"]
        assert "com" in data["pupil"]
        assert data["pupil"]["area"].shape == (50,)
        assert data["pupil"]["com"].shape == (50, 2)

    def test_create_facemap_output_deterministic(self, tmp_path):
        """Test facemap generation is deterministic."""
        params = FacemapParams(n_frames=10)

        npy1 = create_facemap_output(tmp_path / "facemap1.npy", params, seed=42)
        npy2 = create_facemap_output(tmp_path / "facemap2.npy", params, seed=42)

        data1 = np.load(npy1, allow_pickle=True).item()
        data2 = np.load(npy2, allow_pickle=True).item()

        np.testing.assert_array_equal(data1["motion"], data2["motion"])
        np.testing.assert_array_equal(data1["pupil"]["area"], data2["pupil"]["area"])
        np.testing.assert_array_equal(data1["pupil"]["com"], data2["pupil"]["com"])

    def test_create_simple_facemap(self, tmp_path):
        """Test simple facemap creation."""
        npy_path = create_simple_facemap(tmp_path / "simple.npy", n_frames=20, seed=42)

        assert npy_path.exists()

        data = np.load(npy_path, allow_pickle=True).item()
        assert data["motion"].shape == (20,)

    def test_facemap_integration_with_pipeline(self, tmp_path):
        """Test that generated facemap can be loaded by pipeline."""
        params = FacemapParams(n_frames=10)

        npy_path = create_facemap_output(tmp_path / "facemap.npy", params, seed=42)

        # Load with numpy (pipeline uses this)
        data = np.load(npy_path, allow_pickle=True).item()

        # Validate structure matches fixture format
        assert isinstance(data, dict)
        assert "motion" in data
        assert "pupil" in data
        assert isinstance(data["pupil"], dict)
        assert "area" in data["pupil"]
        assert "com" in data["pupil"]


class TestPoseAndFacemapIntegration:
    """Integration tests for pose and facemap generators."""

    def test_create_complete_session_with_pose_facemap(self, tmp_path):
        """Test creating session with pose and facemap data."""
        # Create pose data
        pose_params = PoseParams(keypoints=["nose", "left_ear", "right_ear"], n_frames=50)
        pose_path = create_dlc_pose_csv(tmp_path / "pose.csv", pose_params, seed=42)

        # Create facemap data
        facemap_params = FacemapParams(n_frames=50)
        facemap_path = create_facemap_output(tmp_path / "facemap.npy", facemap_params, seed=42)

        # Verify both exist
        assert pose_path.exists()
        assert facemap_path.exists()

        # Load and verify frame counts match
        from w2t_bkin.pose import import_dlc_pose

        pose_frames = import_dlc_pose(pose_path)
        facemap_data = np.load(facemap_path, allow_pickle=True).item()

        assert len(pose_frames) == 50
        assert facemap_data["motion"].shape[0] == 50
