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
        assert "DLC" in model_info.scorer
        assert "BA_W2T_test" in model_info.scorer

    def test_Should_RaiseError_When_ConfigYamlMissing(self):
        """Should raise DLCInferenceError when config.yaml missing."""
        nonexistent_path = Path("tests/fixtures/models/dlc/nonexistent.yaml")

        with pytest.raises(DLCInferenceError) as exc_info:
            validate_dlc_model(nonexistent_path)

        assert "not found" in str(exc_info.value).lower()

    def test_Should_RaiseError_When_ConfigYamlInvalid(self):
        """Should raise DLCInferenceError when config.yaml invalid."""
        # Test with empty YAML
        empty_path = Path("tests/fixtures/models/dlc/invalid_empty.yaml")

        with pytest.raises(DLCInferenceError) as exc_info:
            validate_dlc_model(empty_path)

        assert "missing required fields" in str(exc_info.value).lower()

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

    @pytest.mark.skip(reason="T3: Not yet implemented")
    def test_Should_PredictH5Path_When_VideoProvided(self):
        """Should predict H5 output path following DLC naming."""
        # TODO: Implement after T3
        pass

    @pytest.mark.skip(reason="T3: Not yet implemented")
    def test_Should_PredictCsvPath_When_CsvRequested(self):
        """Should predict CSV output path when save_as_csv=True."""
        # TODO: Implement after T3
        pass


class TestGPUSelection:
    """Test GPU auto-detection and selection (T4)."""

    @pytest.mark.skip(reason="T4: Not yet implemented")
    def test_Should_AutoDetectGPU_When_Available(self):
        """Should auto-detect first GPU when available."""
        # TODO: Implement after T4 with mocked TensorFlow
        pass

    @pytest.mark.skip(reason="T4: Not yet implemented")
    def test_Should_ReturnNone_When_NoGPU(self):
        """Should return None for CPU-only systems."""
        # TODO: Implement after T4 with mocked TensorFlow
        pass


class TestBatchInference:
    """Test batch DLC inference (T5)."""

    @pytest.mark.skip(reason="T5: Not yet implemented")
    def test_Should_ProcessAllVideos_When_BatchProvided(self):
        """Should process all videos in single batch."""
        # TODO: Implement after T5 with mocked deeplabcut.analyze_videos
        pass

    @pytest.mark.skip(reason="T5: Not yet implemented")
    def test_Should_HandlePartialFailure_When_OneVideoFails(self):
        """Should continue batch when one video fails."""
        # TODO: Implement after T5
        pass

    @pytest.mark.skip(reason="T5: Not yet implemented")
    def test_Should_RaiseError_When_ModelInvalid(self):
        """Should raise DLCInferenceError when model invalid."""
        # TODO: Implement after T5
        pass
