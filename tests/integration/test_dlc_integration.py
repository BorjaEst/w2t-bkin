"""Integration tests for DLC inference workflow.

Tests end-to-end DLC functionality including:
- Model validation and loading
- Batch video inference
- Output file generation
- GPU selection modes
- Error handling and partial failures
"""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import yaml

from w2t_bkin.dlc import DLCInferenceOptions, DLCInferenceResult, predict_output_paths, run_dlc_inference_batch, validate_dlc_model
from w2t_bkin.dlc.core import DLCInferenceError

# =============================================================================
# Model Validation Tests
# =============================================================================


def test_dlc_model_validation_with_fixture(dlc_model_config):
    """Test DLC model validation with fixture config."""
    model_info = validate_dlc_model(dlc_model_config)

    assert model_info.task == "BA_W2T_test"
    assert model_info.date == "2024-01-01"
    assert len(model_info.bodyparts) == 5
    assert "nose" in model_info.bodyparts
    assert "trial_light" in model_info.bodyparts
    assert model_info.num_outputs == 15  # 5 bodyparts * 3 (x, y, likelihood)


def test_dlc_output_path_prediction(dlc_model_config, dlc_test_videos, dlc_output_dir):
    """Test output path prediction for DLC inference."""
    model_info = validate_dlc_model(dlc_model_config)

    for video_path in dlc_test_videos:
        paths = predict_output_paths(video_path, model_info, dlc_output_dir, save_csv=False)

        # Check H5 path structure
        h5_path = paths["h5"]
        assert h5_path.parent == dlc_output_dir
        assert h5_path.suffix == ".h5"
        assert model_info.scorer in h5_path.name
        assert video_path.stem in h5_path.name

        # Test with CSV enabled
        paths_with_csv = predict_output_paths(video_path, model_info, dlc_output_dir, save_csv=True)
        csv_path = paths_with_csv["csv"]
        assert csv_path.parent == dlc_output_dir
        assert csv_path.suffix == ".csv"
        assert model_info.scorer in csv_path.name


# =============================================================================
# Batch Inference Tests (Mocked)
# =============================================================================


@patch("w2t_bkin.dlc.core.deeplabcut", create=True)
def test_dlc_batch_inference_success(mock_dlc_module, dlc_model_config, dlc_test_videos, dlc_output_dir):
    """Test successful batch DLC inference (mocked)."""
    # Configure mock to simulate successful DLC inference
    mock_dlc_module.analyze_videos = MagicMock(return_value=None)

    # Create mock H5 outputs (DLC would create these)
    model_info = validate_dlc_model(dlc_model_config)
    for video_path in dlc_test_videos:
        paths = predict_output_paths(video_path, model_info, dlc_output_dir)
        # Simulate DLC creating the H5 file
        paths["h5"].parent.mkdir(parents=True, exist_ok=True)
        paths["h5"].touch()

    # Patch at import time inside run_dlc_inference_batch
    with patch.dict("sys.modules", {"deeplabcut": mock_dlc_module}):
        options = DLCInferenceOptions(gputouse=-1, save_as_csv=False)  # Use CPU mode
        results = run_dlc_inference_batch(dlc_test_videos, dlc_model_config, dlc_output_dir, options)

    # Verify results
    assert len(results) == 3
    assert all(r.success for r in results)
    assert all(r.h5_output_path.exists() for r in results)
    assert all(r.error_message is None for r in results)
    assert mock_dlc_module.analyze_videos.called


@patch("w2t_bkin.dlc.core.deeplabcut", create=True)
def test_dlc_batch_inference_partial_failure(mock_dlc_module, dlc_model_config, dlc_test_videos, dlc_output_dir):
    """Test batch inference with partial failures (mocked)."""
    # Mock DLC to raise exception during analyze_videos
    mock_dlc_module.analyze_videos = MagicMock(side_effect=RuntimeError("Simulated DLC inference failure"))

    # Patch at import time
    with patch.dict("sys.modules", {"deeplabcut": mock_dlc_module}):
        options = DLCInferenceOptions(gputouse=-1, save_as_csv=False, allow_fallback=False)
        results = run_dlc_inference_batch(dlc_test_videos, dlc_model_config, dlc_output_dir, options)

    # Verify all failed (since analyze_videos failed for entire batch)
    assert len(results) == 3
    assert all(not r.success for r in results)
    assert all(r.error_message is not None for r in results)


@patch("w2t_bkin.dlc.core.deeplabcut", create=True)
def test_dlc_gpu_selection_modes(mock_dlc_module, dlc_model_config, dlc_test_videos, dlc_output_dir):
    """Test different GPU selection modes."""
    mock_dlc_module.analyze_videos = MagicMock(return_value=None)

    # Create mock outputs
    model_info = validate_dlc_model(dlc_model_config)
    for video_path in dlc_test_videos:
        paths = predict_output_paths(video_path, model_info, dlc_output_dir)
        paths["h5"].parent.mkdir(parents=True, exist_ok=True)
        paths["h5"].touch()

    # Patch at import time
    with patch.dict("sys.modules", {"deeplabcut": mock_dlc_module}):
        # Test CPU mode (-1) - should always work
        options_cpu = DLCInferenceOptions(gputouse=-1, save_as_csv=False)
        results = run_dlc_inference_batch(dlc_test_videos, dlc_model_config, dlc_output_dir, options_cpu)
        assert all(r.success for r in results)


@patch("w2t_bkin.dlc.core.deeplabcut", create=True)
def test_dlc_csv_output_option(mock_dlc_module, dlc_model_config, dlc_test_videos, dlc_output_dir):
    """Test CSV output generation option."""
    mock_dlc_module.analyze_videos = MagicMock(return_value=None)

    # Create mock outputs (H5 and CSV)
    model_info = validate_dlc_model(dlc_model_config)
    for video_path in dlc_test_videos:
        paths = predict_output_paths(video_path, model_info, dlc_output_dir, save_csv=True)
        paths["h5"].parent.mkdir(parents=True, exist_ok=True)
        paths["h5"].touch()
        paths["csv"].touch()

    # Patch at import time
    with patch.dict("sys.modules", {"deeplabcut": mock_dlc_module}):
        options = DLCInferenceOptions(gputouse=-1, save_as_csv=True)
        results = run_dlc_inference_batch(dlc_test_videos, dlc_model_config, dlc_output_dir, options)

    # Verify CSV was requested
    assert mock_dlc_module.analyze_videos.called
    call_kwargs = mock_dlc_module.analyze_videos.call_args[1]
    assert call_kwargs.get("save_as_csv") is True


# =============================================================================
# Error Handling Tests
# =============================================================================


def test_dlc_invalid_model_config(dlc_test_videos, dlc_output_dir, fixtures_root):
    """Test handling of invalid DLC model config."""
    invalid_config = fixtures_root / "models" / "dlc" / "missing_task.yaml"

    with pytest.raises(DLCInferenceError, match="missing required fields"):
        validate_dlc_model(invalid_config)


def test_dlc_missing_model_config(dlc_test_videos, dlc_output_dir, tmp_path):
    """Test handling of missing model config file."""
    missing_config = tmp_path / "nonexistent_config.yaml"

    with pytest.raises(DLCInferenceError, match="not found"):
        validate_dlc_model(missing_config)


@patch("w2t_bkin.dlc.core.deeplabcut", create=True)
def test_dlc_empty_video_list(mock_dlc_module, dlc_model_config, dlc_output_dir):
    """Test batch inference with empty video list."""
    mock_dlc_module.analyze_videos = MagicMock(return_value=None)

    with patch.dict("sys.modules", {"deeplabcut": mock_dlc_module}):
        options = DLCInferenceOptions(gputouse=-1)
        results = run_dlc_inference_batch([], dlc_model_config, dlc_output_dir, options)

    assert results == []
    assert not mock_dlc_module.analyze_videos.called


# =============================================================================
# Integration with Pipeline (Smoke Test)
# =============================================================================


def test_dlc_fixtures_available(dlc_test_videos, dlc_model_config, dlc_output_dir):
    """Smoke test: verify all DLC fixtures are accessible."""
    # Check videos exist
    for video_path in dlc_test_videos:
        assert video_path.exists(), f"Missing test video: {video_path}"
        assert video_path.stat().st_size > 0, f"Empty test video: {video_path}"

    # Check model config exists and is valid YAML
    assert dlc_model_config.exists(), f"Missing model config: {dlc_model_config}"
    with open(dlc_model_config, "r") as f:
        config_data = yaml.safe_load(f)
    assert config_data is not None
    assert "Task" in config_data
    assert "bodyparts" in config_data

    # Check output directory is writable
    assert dlc_output_dir.exists()
    assert dlc_output_dir.is_dir()
    test_file = dlc_output_dir / "test_write.tmp"
    test_file.write_text("test")
    assert test_file.exists()
    test_file.unlink()
