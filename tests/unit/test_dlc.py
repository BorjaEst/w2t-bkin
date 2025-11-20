"""Unit tests for DLC inference module.

Tests DLC inference functionality with mocked DeepLabCut API for fast
execution. Integration tests with real DLC models are in test_dlc_integration.py.

Requirements:
    - All REQ-DLC-* requirements from docs/requirements_dlc_inference.md
"""

from pathlib import Path

import pytest

from w2t_bkin.dlc import (
    DLCInferenceError,
    DLCInferenceOptions,
    DLCInferenceResult,
    DLCModelInfo,
    auto_detect_gpu,
    predict_output_paths,
    run_dlc_inference_batch,
    validate_dlc_model,
)


class TestModuleStructure:
    """Test module structure and imports."""

    def test_Should_ImportModels_When_ModuleLoaded(self):
        """Should import all model classes."""
        assert DLCInferenceOptions is not None
        assert DLCInferenceResult is not None
        assert DLCModelInfo is not None

    def test_Should_ImportFunctions_When_ModuleLoaded(self):
        """Should import all public functions."""
        assert run_dlc_inference_batch is not None
        assert validate_dlc_model is not None
        assert predict_output_paths is not None
        assert auto_detect_gpu is not None

    def test_Should_ImportException_When_ModuleLoaded(self):
        """Should import DLCInferenceError exception."""
        assert DLCInferenceError is not None
        assert issubclass(DLCInferenceError, Exception)

    def test_Should_CreateImmutableOptions_When_Instantiated(self):
        """Should create immutable DLCInferenceOptions."""
        options = DLCInferenceOptions(gputouse=0, save_as_csv=True)

        assert options.gputouse == 0
        assert options.save_as_csv is True
        assert options.allow_growth is True  # Default

        # Verify immutability
        with pytest.raises(AttributeError):
            options.gputouse = 1

    def test_Should_CreateImmutableResult_When_Instantiated(self):
        """Should create immutable DLCInferenceResult."""
        result = DLCInferenceResult(
            video_path=Path("test.mp4"),
            h5_output_path=Path("testDLC.h5"),
            csv_output_path=None,
            model_config_path=Path("config.yaml"),
            frame_count=100,
            inference_time_s=5.5,
            gpu_used=0,
            success=True,
        )

        assert result.success is True
        assert result.frame_count == 100

        # Verify immutability
        with pytest.raises(AttributeError):
            result.success = False

    def test_Should_CreateImmutableModelInfo_When_Instantiated(self):
        """Should create immutable DLCModelInfo."""
        model_info = DLCModelInfo(
            config_path=Path("config.yaml"),
            project_path=Path("."),
            scorer="DLC_scorer",
            bodyparts=["nose", "ear"],
            num_outputs=6,
            task="test",
            date="2024-01-01",
        )

        assert model_info.scorer == "DLC_scorer"
        assert len(model_info.bodyparts) == 2
        assert model_info.num_outputs == 6

        # Verify immutability
        with pytest.raises(AttributeError):
            model_info.scorer = "new_scorer"


class TestModelValidation:
    """Test DLC model validation (T2)."""

    def test_Should_ValidateModel_When_ConfigYamlExists(self):
        """Should validate DLC model and extract metadata."""
        config_path = Path("tests/fixtures/models/dlc/valid_config.yaml")

        model_info = validate_dlc_model(config_path)

        assert model_info.config_path == config_path
        assert model_info.project_path == config_path.parent
        assert model_info.task == "BA_W2T_test"
        assert model_info.date == "2024-01-01"
        assert len(model_info.bodyparts) == 5
        assert "nose" in model_info.bodyparts
        assert "trial_light" in model_info.bodyparts
        assert model_info.num_outputs == 15  # 5 bodyparts × 3 (x, y, likelihood)
        # Scorer should not include "DLC_" prefix - that's added in filenames
        assert "DLC" not in model_info.scorer
        assert "BA_W2T_test" in model_info.scorer

    def test_Should_RaiseError_When_ConfigYamlMissing(self):
        """Should raise DLCInferenceError when config.yaml missing."""
        nonexistent_path = Path("tests/fixtures/models/dlc/nonexistent.yaml")

        with pytest.raises(DLCInferenceError) as exc_info:
            validate_dlc_model(nonexistent_path)

        assert "not found" in str(exc_info.value).lower()

    def test_Should_RaiseError_When_ConfigYamlInvalid(self):
        """Should raise DLCInferenceError when config.yaml invalid."""
        # Test with empty YAML (None)
        empty_path = Path("tests/fixtures/models/dlc/invalid_empty.yaml")

        with pytest.raises(DLCInferenceError) as exc_info:
            validate_dlc_model(empty_path)

        # Empty YAML is parsed as None, which is not a dict
        assert "must contain a yaml dictionary" in str(exc_info.value).lower()

    def test_Should_RaiseError_When_ConfigIsNotDict(self):
        """Should raise DLCInferenceError when config.yaml is not a dictionary."""
        not_dict_path = Path("tests/fixtures/models/dlc/invalid_not_dict.yaml")

        with pytest.raises(DLCInferenceError) as exc_info:
            validate_dlc_model(not_dict_path)

        assert "must contain a yaml dictionary" in str(exc_info.value).lower()

    def test_Should_RaiseError_When_MissingTaskField(self):
        """Should raise DLCInferenceError when 'Task' field missing."""
        missing_task_path = Path("tests/fixtures/models/dlc/missing_task.yaml")

        with pytest.raises(DLCInferenceError) as exc_info:
            validate_dlc_model(missing_task_path)

        assert "missing required fields" in str(exc_info.value).lower()
        assert "Task" in str(exc_info.value)

    def test_Should_RaiseError_When_MissingBodypartsField(self):
        """Should raise DLCInferenceError when 'bodyparts' field missing."""
        missing_bodyparts_path = Path("tests/fixtures/models/dlc/missing_bodyparts.yaml")

        with pytest.raises(DLCInferenceError) as exc_info:
            validate_dlc_model(missing_bodyparts_path)

        assert "missing required fields" in str(exc_info.value).lower()
        assert "bodyparts" in str(exc_info.value)

    def test_Should_RaiseError_When_BodypartsEmpty(self):
        """Should raise DLCInferenceError when bodyparts list is empty."""
        empty_bodyparts_path = Path("tests/fixtures/models/dlc/empty_bodyparts.yaml")

        with pytest.raises(DLCInferenceError) as exc_info:
            validate_dlc_model(empty_bodyparts_path)

        assert "bodyparts" in str(exc_info.value).lower()
        assert "empty" in str(exc_info.value).lower()

    def test_Should_RaiseError_When_ConfigIsDirectory(self):
        """Should raise DLCInferenceError when path is a directory."""
        dir_path = Path("tests/fixtures/models/dlc")

        with pytest.raises(DLCInferenceError) as exc_info:
            validate_dlc_model(dir_path)

        assert "must be a file" in str(exc_info.value).lower()


class TestOutputPaths:
    """Test output path prediction (T3)."""

    def test_Should_PredictH5Path_When_VideoProvided(self):
        """Should predict H5 output path following DLC naming."""
        # Create mock model info
        # Note: scorer does NOT include "DLC_" prefix - that's added in the filename
        model_info = DLCModelInfo(
            config_path=Path("models/dlc/config.yaml"),
            project_path=Path("models/dlc"),
            scorer="resnet50_BA_W2T_test20240101shuffle1_150000",
            bodyparts=["nose", "ear"],
            num_outputs=6,
            task="BA_W2T_test",
            date="2024-01-01",
        )

        # Test with simple video name
        paths = predict_output_paths(
            video_path=Path("session/video.mp4"),
            model_info=model_info,
            output_dir=Path("output"),
            save_csv=False,
        )

        assert "h5" in paths
        assert paths["h5"] == Path("output/videoDLC_resnet50_BA_W2T_test20240101shuffle1_150000.h5")
        assert "csv" not in paths

    def test_Should_PredictCsvPath_When_CsvRequested(self):
        """Should predict CSV output path when save_as_csv=True."""
        model_info = DLCModelInfo(
            config_path=Path("models/dlc/config.yaml"),
            project_path=Path("models/dlc"),
            scorer="resnet50_test_scorer",
            bodyparts=["nose"],
            num_outputs=3,
            task="test",
            date="2024-01-01",
        )

        paths = predict_output_paths(
            video_path=Path("cam0.avi"),
            model_info=model_info,
            output_dir=Path("dlc_output"),
            save_csv=True,
        )

        assert "h5" in paths
        assert "csv" in paths
        assert paths["h5"] == Path("dlc_output/cam0DLC_resnet50_test_scorer.h5")
        assert paths["csv"] == Path("dlc_output/cam0DLC_resnet50_test_scorer.csv")

    def test_Should_HandleComplexVideoNames_When_SpecialCharacters(self):
        """Should handle video names with dots, underscores, and dates."""
        model_info = DLCModelInfo(
            config_path=Path("config.yaml"),
            project_path=Path("."),
            scorer="scorer",
            bodyparts=["nose"],
            num_outputs=3,
            task="test",
            date="2024-01-01",
        )

        # Test with complex filename
        paths = predict_output_paths(
            video_path=Path("cam0_2024-09-22-16-05-39.mp4"),
            model_info=model_info,
            output_dir=Path("out"),
            save_csv=False,
        )

        # Should preserve video stem exactly
        assert paths["h5"] == Path("out/cam0_2024-09-22-16-05-39DLC_scorer.h5")


class TestGPUSelection:
    """Test GPU auto-detection and selection (T4)."""

    def test_Should_AutoDetectGPU_When_Available(self, monkeypatch):
        """Should auto-detect first GPU when available."""

        # Mock TensorFlow to simulate GPU available
        class MockTF:
            class config:
                @staticmethod
                def list_physical_devices(device_type):
                    # Return mock GPU devices
                    return [{"name": "/physical_device:GPU:0"}]

        # Patch tensorflow import
        import sys

        monkeypatch.setitem(sys.modules, "tensorflow", MockTF())

        # Test auto-detection
        gpu_index = auto_detect_gpu()

        assert gpu_index == 0

    def test_Should_ReturnNone_When_NoGPU(self, monkeypatch):
        """Should return None for CPU-only systems."""

        # Mock TensorFlow to simulate no GPU
        class MockTF:
            class config:
                @staticmethod
                def list_physical_devices(device_type):
                    # Return empty list (no GPUs)
                    return []

        # Patch tensorflow import
        import sys

        monkeypatch.setitem(sys.modules, "tensorflow", MockTF())

        # Test auto-detection
        gpu_index = auto_detect_gpu()

        assert gpu_index is None

    def test_Should_ReturnNone_When_TensorFlowNotAvailable(self, monkeypatch):
        """Should return None when TensorFlow is not installed."""
        # Simulate ImportError for TensorFlow
        import builtins
        import sys

        # Remove tensorflow from modules if it exists
        monkeypatch.delitem(sys.modules, "tensorflow", raising=False)

        # Make import fail
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "tensorflow":
                raise ImportError("TensorFlow not installed")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Test auto-detection
        gpu_index = auto_detect_gpu()

        assert gpu_index is None

    def test_Should_ReturnNone_When_GPUDetectionFails(self, monkeypatch):
        """Should gracefully handle errors during GPU detection."""

        # Mock TensorFlow to raise an exception
        class MockTF:
            class config:
                @staticmethod
                def list_physical_devices(device_type):
                    raise RuntimeError("GPU detection failed")

        # Patch tensorflow import
        import sys

        monkeypatch.setitem(sys.modules, "tensorflow", MockTF())

        # Test auto-detection (should handle exception and return None)
        gpu_index = auto_detect_gpu()

        assert gpu_index is None


class TestBatchInference:
    """Test batch DLC inference (T5)."""

    def test_Should_ProcessAllVideos_When_BatchProvided(self, tmp_path, monkeypatch):
        """Should process all videos in single batch."""
        # Setup test files
        config_path = Path("tests/fixtures/models/dlc/valid_config.yaml")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create mock video files
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        # Mock deeplabcut
        analyze_calls = []

        def mock_analyze_videos(config, videos, destfolder, gputouse, save_as_csv, allow_growth):
            analyze_calls.append(
                {
                    "config": config,
                    "videos": videos,
                    "destfolder": destfolder,
                    "gputouse": gputouse,
                    "save_as_csv": save_as_csv,
                    "allow_growth": allow_growth,
                }
            )
            # Create mock H5 output for each video
            for video in videos:
                video_path = Path(video)
                # Get model info to build output name
                model_info = validate_dlc_model(Path(config))
                h5_name = f"{video_path.stem}DLC_{model_info.scorer}.h5"
                h5_path = Path(destfolder) / h5_name
                # Create mock H5 file with pandas
                import pandas as pd

                df = pd.DataFrame({"frame": [0, 1, 2]})
                df.to_hdf(h5_path, key="data", mode="w")

        class MockDLC:
            analyze_videos = staticmethod(mock_analyze_videos)

        import sys

        monkeypatch.setitem(sys.modules, "deeplabcut", MockDLC)

        # Run batch inference
        results = run_dlc_inference_batch(
            video_paths=[video1, video2],
            model_config_path=config_path,
            output_dir=output_dir,
            options=DLCInferenceOptions(gputouse=0, save_as_csv=False),
        )

        # Verify results
        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].video_path == video1
        assert results[1].video_path == video2
        assert all(r.h5_output_path.exists() for r in results)
        assert all(r.gpu_used == 0 for r in results)
        assert all(r.frame_count == 3 for r in results)

        # Verify DLC was called correctly
        assert len(analyze_calls) == 2
        assert all(call["gputouse"] == 0 for call in analyze_calls)
        assert all(call["save_as_csv"] is False for call in analyze_calls)

    def test_Should_HandlePartialFailure_When_OneVideoFails(self, tmp_path, monkeypatch):
        """Should continue batch when one video fails."""
        config_path = Path("tests/fixtures/models/dlc/valid_config.yaml")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create mock video files
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"  # This one will fail
        video3 = tmp_path / "video3.mp4"
        video1.touch()
        video2.touch()
        video3.touch()

        # Mock deeplabcut to fail on second video
        def mock_analyze_videos(config, videos, destfolder, **kwargs):
            video_path = Path(videos[0])
            if video_path.name == "video2.mp4":
                raise RuntimeError("Video processing failed")

            # Success case - create H5 output
            model_info = validate_dlc_model(Path(config))
            h5_name = f"{video_path.stem}DLC_{model_info.scorer}.h5"
            h5_path = Path(destfolder) / h5_name
            import pandas as pd

            df = pd.DataFrame({"frame": [0, 1]})
            df.to_hdf(h5_path, key="data", mode="w")

        class MockDLC:
            analyze_videos = staticmethod(mock_analyze_videos)

        import sys

        monkeypatch.setitem(sys.modules, "deeplabcut", MockDLC)

        # Run batch inference
        results = run_dlc_inference_batch(
            video_paths=[video1, video2, video3],
            model_config_path=config_path,
            output_dir=output_dir,
        )

        # Verify results
        assert len(results) == 3
        assert results[0].success is True  # video1 succeeded
        assert results[1].success is False  # video2 failed
        assert results[2].success is True  # video3 succeeded (continued after failure)
        assert "Video processing failed" in results[1].error_message
        assert results[1].h5_output_path is None

    def test_Should_RaiseError_When_ModelInvalid(self, tmp_path):
        """Should raise DLCInferenceError when model invalid."""
        # Use non-existent config path
        invalid_config = tmp_path / "nonexistent_config.yaml"
        output_dir = tmp_path / "output"

        video = tmp_path / "video.mp4"
        video.touch()

        # Should raise during model validation
        with pytest.raises(DLCInferenceError) as exc_info:
            run_dlc_inference_batch(
                video_paths=[video],
                model_config_path=invalid_config,
                output_dir=output_dir,
            )

        assert "not found" in str(exc_info.value).lower()

    def test_Should_UseDefaultOptions_When_NoneProvided(self, tmp_path, monkeypatch):
        """Should use default inference options when none provided."""
        config_path = Path("tests/fixtures/models/dlc/valid_config.yaml")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        video = tmp_path / "video.mp4"
        video.touch()

        # Mock deeplabcut and capture options
        captured_options = {}

        def mock_analyze_videos(config, videos, destfolder, gputouse, save_as_csv, allow_growth):
            captured_options["gputouse"] = gputouse
            captured_options["save_as_csv"] = save_as_csv
            captured_options["allow_growth"] = allow_growth
            # Create mock output
            model_info = validate_dlc_model(Path(config))
            h5_name = f"{Path(videos[0]).stem}DLC_{model_info.scorer}.h5"
            h5_path = Path(destfolder) / h5_name
            import pandas as pd

            df = pd.DataFrame({"frame": [0]})
            df.to_hdf(h5_path, key="data", mode="w")

        class MockDLC:
            analyze_videos = staticmethod(mock_analyze_videos)

        import sys

        monkeypatch.setitem(sys.modules, "deeplabcut", MockDLC)

        # Mock GPU detection to return None (CPU)
        monkeypatch.setattr("w2t_bkin.dlc.core.auto_detect_gpu", lambda: None)

        # Run without options
        results = run_dlc_inference_batch(video_paths=[video], model_config_path=config_path, output_dir=output_dir, options=None)

        # Verify default options were used
        assert results[0].success
        assert captured_options["gputouse"] is None  # Auto-detected (CPU)
        assert captured_options["save_as_csv"] is False  # Default
        assert captured_options["allow_growth"] is True  # Default
