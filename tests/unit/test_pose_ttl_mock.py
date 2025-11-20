"""Unit tests for pose TTL mock generation module.

Tests cover:
- Likelihood series loading from DLC H5 files
- Signal transition detection (rising, falling, both)
- Duration filtering logic
- Frame-to-timestamp conversion
- End-to-end TTL generation with various options
- Custom predicate-based generation
- File writing and format validation
- Error handling and edge cases
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from w2t_bkin.pose.core import PoseError
from w2t_bkin.pose.ttl_mock import (
    TTLMockOptions,
    detect_signal_transitions,
    filter_by_duration,
    frames_to_timestamps,
    generate_and_write_ttl_from_pose,
    generate_ttl_from_custom_predicate,
    generate_ttl_from_dlc_likelihood,
    load_dlc_likelihood_series,
    write_ttl_timestamps,
)


class TestTTLMockOptions:
    """Test TTLMockOptions validation and configuration."""

    def test_Should_CreateOptions_When_ValidDataProvided(self):
        """TTLMockOptions should accept valid configuration."""
        options = TTLMockOptions(
            bodypart="trial_light",
            likelihood_threshold=0.99,
            min_duration_frames=301,
            fps=150.0,
            transition_type="rising",
        )
        assert options.bodypart == "trial_light"
        assert options.likelihood_threshold == 0.99
        assert options.min_duration_frames == 301
        assert options.fps == 150.0
        assert options.transition_type == "rising"

    def test_Should_UseDefaults_When_OnlyBodypartProvided(self):
        """TTLMockOptions should use sensible defaults."""
        options = TTLMockOptions(bodypart="nose")
        assert options.likelihood_threshold == 0.99
        assert options.min_duration_frames == 1
        assert options.fps == 30.0
        assert options.transition_type == "rising"

    def test_Should_RaiseError_When_EmptyBodypart(self):
        """TTLMockOptions should reject empty bodypart."""
        with pytest.raises(ValueError, match="non-empty"):
            TTLMockOptions(bodypart="")

    def test_Should_RaiseError_When_InvalidLikelihood(self):
        """TTLMockOptions should reject invalid likelihood threshold."""
        with pytest.raises(ValueError):
            TTLMockOptions(bodypart="nose", likelihood_threshold=1.5)
        with pytest.raises(ValueError):
            TTLMockOptions(bodypart="nose", likelihood_threshold=-0.1)

    def test_Should_RaiseError_When_InvalidTransitionType(self):
        """TTLMockOptions should reject invalid transition types."""
        with pytest.raises(ValueError):
            TTLMockOptions(bodypart="nose", transition_type="invalid")


class TestLoadDLCLikelihoodSeries:
    """Test DLC likelihood series extraction."""

    @pytest.fixture
    def mock_dlc_h5(self, tmp_path):
        """Create mock DLC H5 file."""
        scorer = "DLC_model"
        bodyparts = ["nose", "trial_light", "left_ear"]
        coords = ["x", "y", "likelihood"]

        # Create MultiIndex columns
        columns = pd.MultiIndex.from_product([[scorer], bodyparts, coords], names=["scorer", "bodyparts", "coords"])

        # Create sample data (100 frames)
        n_frames = 100
        data = {}
        for bp in bodyparts:
            data[(scorer, bp, "x")] = np.random.rand(n_frames) * 640
            data[(scorer, bp, "y")] = np.random.rand(n_frames) * 480
            # trial_light has high likelihood, others lower
            if bp == "trial_light":
                data[(scorer, bp, "likelihood")] = np.random.uniform(0.95, 1.0, n_frames)
            else:
                data[(scorer, bp, "likelihood")] = np.random.uniform(0.5, 0.95, n_frames)

        df = pd.DataFrame(data)
        h5_path = tmp_path / "test_pose.h5"
        df.to_hdf(h5_path, key="df_with_missing", mode="w")
        return h5_path

    def test_Should_LoadLikelihood_When_ValidFileAndBodypart(self, mock_dlc_h5):
        """Should successfully load likelihood series."""
        likelihood = load_dlc_likelihood_series(mock_dlc_h5, "trial_light")
        assert isinstance(likelihood, pd.Series)
        assert len(likelihood) == 100
        assert likelihood.min() >= 0.95
        assert likelihood.max() <= 1.0

    def test_Should_RaiseError_When_FileNotFound(self):
        """Should raise PoseError for missing file."""
        with pytest.raises(PoseError, match="not found"):
            load_dlc_likelihood_series(Path("/nonexistent/pose.h5"), "nose")

    def test_Should_RaiseError_When_BodypartNotFound(self, mock_dlc_h5):
        """Should raise PoseError for invalid bodypart."""
        with pytest.raises(PoseError, match="not found"):
            load_dlc_likelihood_series(mock_dlc_h5, "invalid_bodypart")

    def test_Should_AutoDetectScorer_When_ScorerNotProvided(self, mock_dlc_h5):
        """Should auto-detect scorer from file."""
        likelihood = load_dlc_likelihood_series(mock_dlc_h5, "nose", scorer=None)
        assert len(likelihood) == 100


class TestDetectSignalTransitions:
    """Test signal transition detection logic."""

    def test_Should_DetectRisingEdges_When_SignalChanges(self):
        """Should detect OFF→ON transitions."""
        signal = pd.Series([False, False, True, True, False, True, True])
        onsets, offsets = detect_signal_transitions(signal, "rising")
        assert onsets == [2, 5]
        assert offsets == []

    def test_Should_DetectFallingEdges_When_SignalChanges(self):
        """Should detect ON→OFF transitions."""
        signal = pd.Series([False, True, True, False, False, True, False])
        onsets, offsets = detect_signal_transitions(signal, "falling")
        assert onsets == []
        assert offsets == [3, 6]

    def test_Should_DetectBothEdges_When_BothMode(self):
        """Should detect both rising and falling edges."""
        signal = pd.Series([False, True, True, False, True])
        onsets, offsets = detect_signal_transitions(signal, "both")
        assert onsets == [1, 4]
        assert offsets == [3]

    def test_Should_HandleEmpty_When_NoTransitions(self):
        """Should return empty lists for constant signal."""
        signal = pd.Series([True, True, True])
        onsets, offsets = detect_signal_transitions(signal, "both")
        # Frame 0 with True is detected as onset (shift fills with False)
        assert onsets == [0]
        assert offsets == []

    def test_Should_HandleStartHigh_When_FirstFrameTrue(self):
        """Should detect onset at frame 0 when signal starts high."""
        signal = pd.Series([True, True, False])
        onsets, offsets = detect_signal_transitions(signal, "rising")
        assert onsets == [0]  # Onset detected at frame 0


class TestFilterByDuration:
    """Test duration-based filtering."""

    def test_Should_FilterShortPulses_When_MinDurationSet(self):
        """Should only keep phases meeting minimum duration."""
        onsets = [10, 50, 100]
        offsets = [15, 55, 400]  # Durations: 5, 5, 300
        filtered_onsets, filtered_offsets = filter_by_duration(onsets, offsets, min_duration_frames=10)
        assert filtered_onsets == [100]
        assert filtered_offsets == [400]

    def test_Should_KeepAll_When_AllMeetDuration(self):
        """Should keep all phases if all meet threshold."""
        onsets = [10, 50, 100]
        offsets = [30, 70, 120]  # All durations >= 20
        filtered_onsets, filtered_offsets = filter_by_duration(onsets, offsets, min_duration_frames=15)
        assert len(filtered_onsets) == 3
        assert len(filtered_offsets) == 3

    def test_Should_HandleEmpty_When_NoPhases(self):
        """Should handle empty input gracefully."""
        filtered_onsets, filtered_offsets = filter_by_duration([], [], min_duration_frames=10)
        assert filtered_onsets == []
        assert filtered_offsets == []

    def test_Should_HandleMismatch_When_UnequalLengths(self):
        """Should handle mismatched onset/offset counts."""
        onsets = [10, 50, 100]
        offsets = [30, 70]  # Missing final offset
        filtered_onsets, filtered_offsets = filter_by_duration(onsets, offsets, min_duration_frames=10)
        assert len(filtered_onsets) == len(filtered_offsets)


class TestFramesToTimestamps:
    """Test frame index to timestamp conversion."""

    def test_Should_ConvertFrames_When_StandardFPS(self):
        """Should convert frames to timestamps correctly."""
        frames = [0, 150, 300]
        timestamps = frames_to_timestamps(frames, fps=150.0)
        assert timestamps == [0.0, 1.0, 2.0]

    def test_Should_ApplyOffset_When_OffsetProvided(self):
        """Should add offset to all timestamps."""
        frames = [0, 30, 60]
        timestamps = frames_to_timestamps(frames, fps=30.0, offset_s=10.0)
        assert timestamps == [10.0, 11.0, 12.0]

    def test_Should_HandleEmpty_When_NoFrames(self):
        """Should return empty list for empty input."""
        timestamps = frames_to_timestamps([], fps=30.0)
        assert timestamps == []

    def test_Should_HandleHighFPS_When_HighFrameRate(self):
        """Should handle high frame rates correctly."""
        frames = [0, 1000, 2000]
        timestamps = frames_to_timestamps(frames, fps=1000.0)
        assert timestamps == [0.0, 1.0, 2.0]


class TestGenerateTTLFromDLCLikelihood:
    """Test end-to-end TTL generation from likelihood data."""

    @pytest.fixture
    def mock_trial_light_h5(self, tmp_path):
        """Create DLC H5 with simulated trial light signal."""
        scorer = "DLC_model"
        bodyparts = ["trial_light"]
        coords = ["x", "y", "likelihood"]

        columns = pd.MultiIndex.from_product([[scorer], bodyparts, coords], names=["scorer", "bodyparts", "coords"])

        # Simulate trial light pattern:
        # Frames 0-99: OFF (low likelihood)
        # Frames 100-450: ON (high likelihood) - 351 frames
        # Frames 451-500: OFF
        # Frames 501-550: ON - only 50 frames (below 301 threshold)
        # Frames 551-599: OFF
        n_frames = 600
        likelihood = np.zeros(n_frames)
        likelihood[100:451] = 0.995  # First ON phase (351 frames)
        likelihood[501:551] = 0.995  # Second ON phase (50 frames)

        data = {
            (scorer, "trial_light", "x"): np.random.rand(n_frames) * 640,
            (scorer, "trial_light", "y"): np.random.rand(n_frames) * 480,
            (scorer, "trial_light", "likelihood"): likelihood,
        }

        df = pd.DataFrame(data)
        h5_path = tmp_path / "trial_light.h5"
        df.to_hdf(h5_path, key="df_with_missing", mode="w")
        return h5_path

    def test_Should_DetectOnsets_When_RisingEdgeMode(self, mock_trial_light_h5):
        """Should detect rising edges with no duration filter."""
        options = TTLMockOptions(
            bodypart="trial_light",
            likelihood_threshold=0.99,
            min_duration_frames=1,
            fps=150.0,
            transition_type="rising",
        )
        timestamps = generate_ttl_from_dlc_likelihood(mock_trial_light_h5, options)
        # Should detect 2 onsets at frames 100 and 501
        assert len(timestamps) == 2
        assert timestamps[0] == pytest.approx(100 / 150.0)
        assert timestamps[1] == pytest.approx(501 / 150.0)

    def test_Should_FilterShortPulses_When_MinDurationSet(self, mock_trial_light_h5):
        """Should filter pulses shorter than minimum duration."""
        options = TTLMockOptions(
            bodypart="trial_light",
            likelihood_threshold=0.99,
            min_duration_frames=350,  # 351 frames required, set to 350
            fps=150.0,
            transition_type="rising",
        )
        timestamps = generate_ttl_from_dlc_likelihood(mock_trial_light_h5, options)
        # Should detect 1 onset (351-frame pulse meets 350 threshold, 50-frame filtered)
        assert len(timestamps) == 1
        assert timestamps[0] == pytest.approx(100 / 150.0)

    def test_Should_DetectOffsets_When_FallingEdgeMode(self, mock_trial_light_h5):
        """Should detect falling edges."""
        options = TTLMockOptions(
            bodypart="trial_light",
            likelihood_threshold=0.99,
            min_duration_frames=1,
            fps=150.0,
            transition_type="falling",
        )
        timestamps = generate_ttl_from_dlc_likelihood(mock_trial_light_h5, options)
        # Should detect 2 offsets at frames 451 and 551
        assert len(timestamps) == 2
        assert timestamps[0] == pytest.approx(451 / 150.0)
        assert timestamps[1] == pytest.approx(551 / 150.0)

    def test_Should_DetectBoth_When_BothEdgeMode(self, mock_trial_light_h5):
        """Should detect both rising and falling edges."""
        options = TTLMockOptions(
            bodypart="trial_light",
            likelihood_threshold=0.99,
            min_duration_frames=1,
            fps=150.0,
            transition_type="both",
        )
        timestamps = generate_ttl_from_dlc_likelihood(mock_trial_light_h5, options)
        # Should detect 4 transitions total
        assert len(timestamps) == 4
        # Should be sorted
        assert timestamps == sorted(timestamps)


class TestGenerateTTLFromCustomPredicate:
    """Test custom predicate-based TTL generation."""

    @pytest.fixture
    def mock_movement_h5(self, tmp_path):
        """Create DLC H5 with nose movement pattern."""
        scorer = "DLC_model"
        bodyparts = ["nose"]
        coords = ["x", "y", "likelihood"]

        columns = pd.MultiIndex.from_product([[scorer], bodyparts, coords], names=["scorer", "bodyparts", "coords"])

        # Create movement pattern: stationary, then big jump, then stationary
        n_frames = 100
        x_positions = np.concatenate([np.full(30, 100.0), np.full(40, 200.0), np.full(30, 210.0)])  # Big jump at frame 30  # Small drift

        data = {
            (scorer, "nose", "x"): x_positions,
            (scorer, "nose", "y"): np.full(n_frames, 240.0),
            (scorer, "nose", "likelihood"): np.full(n_frames, 0.99),
        }

        df = pd.DataFrame(data)
        h5_path = tmp_path / "movement.h5"
        df.to_hdf(h5_path, key="df_with_missing", mode="w")
        return h5_path

    def test_Should_DetectMovement_When_CustomPredicate(self, mock_movement_h5):
        """Should detect movement using custom predicate."""

        def detect_large_movement(df):
            scorer = df.columns.get_level_values(0)[0]
            x = df[(scorer, "nose", "x")]
            dx = x.diff().abs()
            return dx > 50  # Detect movements > 50 pixels

        options = TTLMockOptions(bodypart="nose", fps=30.0, transition_type="rising", min_duration_frames=1)
        timestamps = generate_ttl_from_custom_predicate(mock_movement_h5, detect_large_movement, options)

        # Should detect onset at frame 30 (where big jump occurs)
        assert len(timestamps) >= 1
        assert timestamps[0] == pytest.approx(30 / 30.0)


class TestWriteTTLTimestamps:
    """Test TTL file writing."""

    def test_Should_WriteFile_When_TimestampsProvided(self, tmp_path):
        """Should write timestamps to file correctly."""
        timestamps = [0.0, 1.5, 3.0, 4.5]
        output_path = tmp_path / "TTLs" / "test.txt"
        write_ttl_timestamps(timestamps, output_path)

        assert output_path.exists()
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 4
        assert float(lines[0]) == pytest.approx(0.0)
        assert float(lines[3]) == pytest.approx(4.5)

    def test_Should_SortTimestamps_When_Unsorted(self, tmp_path):
        """Should sort timestamps before writing."""
        timestamps = [3.0, 0.0, 4.5, 1.5]
        output_path = tmp_path / "test.txt"
        write_ttl_timestamps(timestamps, output_path)

        lines = output_path.read_text().strip().split("\n")
        values = [float(line) for line in lines]
        assert values == sorted(values)

    def test_Should_CreateDirectory_When_ParentMissing(self, tmp_path):
        """Should create parent directories automatically."""
        output_path = tmp_path / "deep" / "nested" / "path" / "test.txt"
        write_ttl_timestamps([1.0, 2.0], output_path)
        assert output_path.exists()


class TestGenerateAndWriteTTLFromPose:
    """Test convenience function for generation and writing."""

    @pytest.fixture
    def simple_h5(self, tmp_path):
        """Create simple DLC H5 file."""
        scorer = "DLC_model"
        bodyparts = ["marker"]
        coords = ["x", "y", "likelihood"]

        columns = pd.MultiIndex.from_product([[scorer], bodyparts, coords], names=["scorer", "bodyparts", "coords"])

        # Simple pattern: 3 high-likelihood pulses
        n_frames = 100
        likelihood = np.zeros(n_frames)
        likelihood[10:20] = 0.99  # Pulse 1
        likelihood[40:50] = 0.99  # Pulse 2
        likelihood[70:80] = 0.99  # Pulse 3

        data = {
            (scorer, "marker", "x"): np.random.rand(n_frames) * 640,
            (scorer, "marker", "y"): np.random.rand(n_frames) * 480,
            (scorer, "marker", "likelihood"): likelihood,
        }

        df = pd.DataFrame(data)
        h5_path = tmp_path / "simple.h5"
        df.to_hdf(h5_path, key="df_with_missing", mode="w")
        return h5_path

    def test_Should_GenerateAndWrite_When_Called(self, simple_h5, tmp_path):
        """Should generate and write TTL file in one call."""
        output_path = tmp_path / "TTLs" / "marker.txt"
        options = TTLMockOptions(bodypart="marker", likelihood_threshold=0.95, fps=30.0, min_duration_frames=1, transition_type="rising")

        count = generate_and_write_ttl_from_pose(simple_h5, output_path, options)

        assert count == 3
        assert output_path.exists()
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 3


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_Should_HandleEmptySignal_When_NoHighLikelihood(self, tmp_path):
        """Should handle case where no frames exceed threshold."""
        scorer = "DLC_model"
        columns = pd.MultiIndex.from_product([[scorer], ["marker"], ["x", "y", "likelihood"]], names=["scorer", "bodyparts", "coords"])

        data = {
            (scorer, "marker", "x"): np.random.rand(100) * 640,
            (scorer, "marker", "y"): np.random.rand(100) * 480,
            (scorer, "marker", "likelihood"): np.full(100, 0.5),  # All below threshold
        }

        df = pd.DataFrame(data)
        h5_path = tmp_path / "low_conf.h5"
        df.to_hdf(h5_path, key="df_with_missing", mode="w")

        options = TTLMockOptions(bodypart="marker", likelihood_threshold=0.99, fps=30.0)
        timestamps = generate_ttl_from_dlc_likelihood(h5_path, options)
        assert timestamps == []

    def test_Should_HandleSingleFrame_When_OneFrameFile(self, tmp_path):
        """Should handle single-frame files."""
        scorer = "DLC_model"
        columns = pd.MultiIndex.from_product([[scorer], ["marker"], ["x", "y", "likelihood"]], names=["scorer", "bodyparts", "coords"])

        data = {(scorer, "marker", "x"): [100.0], (scorer, "marker", "y"): [200.0], (scorer, "marker", "likelihood"): [0.99]}

        df = pd.DataFrame(data)
        h5_path = tmp_path / "single.h5"
        df.to_hdf(h5_path, key="df_with_missing", mode="w")

        options = TTLMockOptions(bodypart="marker", fps=30.0)
        timestamps = generate_ttl_from_dlc_likelihood(h5_path, options)
        # Single high-confidence frame detected as onset at frame 0
        assert len(timestamps) == 1
        assert timestamps[0] == 0.0
