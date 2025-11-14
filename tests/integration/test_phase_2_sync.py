"""Integration tests for Phase 2 — Sync and Timebase Alignment.

Tests the complete synchronization workflow: timebase provider creation,
alignment of derived data, jitter computation, budget enforcement, and
alignment stats persistence.

Requirements: FR-TB-1, FR-TB-2, FR-TB-3, FR-TB-4, FR-TB-5, FR-TB-6, FR-17
Acceptance: A8, A9, A10, A11, A12, A17, A19, A20
GitHub Issue: #3
"""

import json
from pathlib import Path
from typing import Dict

import pytest

from w2t_bkin.config import load_config, load_session
from w2t_bkin.domain import AlignmentStats, Config, Manifest
from w2t_bkin.ingest import build_and_count_manifest
from w2t_bkin.sync import JitterBudgetExceeded, align_samples, create_alignment_stats, create_timebase_provider, write_alignment_stats


@pytest.mark.integration
def test_Should_CreateNominalTimebase_When_ConfiguredCorrectly_Issue3(
    fixture_session_path,
    fixture_session_toml,
    minimal_config_dict,
):
    """Should create nominal rate timebase provider from config.

    Requirements: FR-TB-1, FR-TB-4
    Acceptance: A8, A9
    """
    # Load config with nominal_rate timebase (default)
    config_dict = minimal_config_dict.copy()
    config_dict["paths"]["raw_root"] = str(fixture_session_path.parent.parent)

    # Create Config instance
    config = Config(**config_dict)

    # Create timebase provider
    provider = create_timebase_provider(config, manifest=None)

    # Verify provider type and properties
    assert provider.source == "nominal_rate"
    assert provider.offset_s == config.timebase.offset_s

    # Get timestamps
    timestamps = provider.get_timestamps(n_samples=100)
    assert len(timestamps) == 100
    assert timestamps[0] == config.timebase.offset_s
    assert all(timestamps[i] < timestamps[i + 1] for i in range(len(timestamps) - 1))


@pytest.mark.integration
def test_Should_CreateTTLTimebase_When_ConfiguredWithManifest_Issue3(
    fixture_session_path,
    fixture_session_toml,
    minimal_config_dict,
):
    """Should create TTL timebase provider when source='ttl' and manifest provided.

    Requirements: FR-TB-1, FR-TB-3
    Acceptance: A8, A10
    """
    # Load config with TTL timebase
    config_dict = minimal_config_dict.copy()
    config_dict["paths"]["raw_root"] = str(fixture_session_path.parent)  # parent of Session-000001
    config_dict["timebase"] = {
        "source": "ttl",
        "mapping": "nearest",
        "jitter_budget_s": 0.01,
        "offset_s": 0.0,
        "ttl_id": "ttl_camera",
    }

    config = Config(**config_dict)
    session = load_session(fixture_session_toml)

    # Build manifest to get TTL files
    manifest = build_and_count_manifest(config, session)

    # Create TTL provider
    provider = create_timebase_provider(config, manifest=manifest)

    # Verify provider
    assert provider.source == "ttl"
    assert hasattr(provider, "ttl_id")

    # Get timestamps (should load from actual TTL files)
    timestamps = provider.get_timestamps()
    assert len(timestamps) > 0
    assert all(timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1))


@pytest.mark.integration
def test_Should_AlignDerivedSamples_When_UsingNominalTimebase_Issue3(
    fixture_session_path,
    minimal_config_dict,
):
    """Should align derived data samples to nominal rate timebase.

    Requirements: FR-TB-6, FR-17
    Acceptance: A11, A12
    """
    # Setup config
    config_dict = minimal_config_dict.copy()
    config_dict["paths"]["raw_root"] = str(fixture_session_path.parent.parent)
    config = Config(**config_dict)

    # Create timebase provider
    provider = create_timebase_provider(config, manifest=None)

    # Generate reference timestamps (100 samples at 30 Hz)
    reference_times = provider.get_timestamps(n_samples=100)

    # Simulate derived data samples (e.g., pose data at slightly different times)
    # Sample every 3rd frame with slight jitter
    sample_times = [reference_times[i] + 0.001 for i in range(0, 100, 3)]

    # Align samples
    result = align_samples(sample_times, reference_times, config.timebase, enforce_budget=False)

    # Verify alignment result
    assert "indices" in result
    assert "jitter_stats" in result
    assert "mapping" in result
    assert result["mapping"] == config.timebase.mapping

    # Verify jitter is reasonable
    jitter = result["jitter_stats"]
    assert jitter["max_jitter_s"] < 0.1
    assert jitter["p95_jitter_s"] < 0.1


@pytest.mark.integration
def test_Should_EnforceJitterBudget_When_ExceededDuringAlignment_Issue3(
    fixture_session_path,
    minimal_config_dict,
):
    """Should raise JitterBudgetExceeded when alignment jitter exceeds budget.

    Requirements: FR-TB-6, A17
    """
    # Setup config with very strict jitter budget
    config_dict = minimal_config_dict.copy()
    config_dict["paths"]["raw_root"] = str(fixture_session_path.parent.parent)
    config_dict["timebase"]["jitter_budget_s"] = 0.0001  # 100 microseconds

    config = Config(**config_dict)

    # Create timebase provider
    provider = create_timebase_provider(config, manifest=None)
    reference_times = provider.get_timestamps(n_samples=100)

    # Create samples with large jitter that will exceed budget
    sample_times = [reference_times[i] + 0.5 for i in range(0, 100, 3)]

    # Should raise JitterBudgetExceeded
    with pytest.raises(JitterBudgetExceeded) as exc_info:
        align_samples(sample_times, reference_times, config.timebase, enforce_budget=True)

    assert "budget" in str(exc_info.value).lower()


@pytest.mark.integration
def test_Should_PersistAlignmentStats_When_AlignmentCompletes_Issue3(
    fixture_session_path,
    minimal_config_dict,
    tmp_work_dir,
):
    """Should write alignment_stats.json with all required fields.

    Requirements: FR-17, FR-TB-5
    Acceptance: A8, A9, A12
    """
    # Setup config
    config_dict = minimal_config_dict.copy()
    config_dict["paths"]["raw_root"] = str(fixture_session_path.parent.parent)
    config = Config(**config_dict)

    # Create timebase and align samples
    provider = create_timebase_provider(config, manifest=None)
    reference_times = provider.get_timestamps(n_samples=100)
    sample_times = [reference_times[i] for i in range(0, 100, 3)]

    result = align_samples(sample_times, reference_times, config.timebase, enforce_budget=False)

    # Create alignment stats
    stats = create_alignment_stats(
        timebase_source=config.timebase.source,
        mapping=result["mapping"],
        offset_s=config.timebase.offset_s,
        max_jitter_s=result["jitter_stats"]["max_jitter_s"],
        p95_jitter_s=result["jitter_stats"]["p95_jitter_s"],
        aligned_samples=len(sample_times),
    )

    # Write to file
    stats_path = tmp_work_dir / "alignment_stats.json"
    write_alignment_stats(stats, stats_path)

    # Verify file exists and contains required fields
    assert stats_path.exists()

    with open(stats_path, "r") as f:
        data = json.load(f)

    # Verify required fields (FR-17, FR-TB-5)
    required_fields = [
        "timebase_source",
        "mapping",
        "offset_s",
        "max_jitter_s",
        "p95_jitter_s",
        "aligned_samples",
    ]

    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

    # Verify values
    assert data["timebase_source"] == "nominal_rate"
    assert data["mapping"] == config.timebase.mapping
    assert data["offset_s"] == config.timebase.offset_s
    assert data["aligned_samples"] == len(sample_times)


@pytest.mark.integration
def test_Should_UseLinearMapping_When_ConfiguredForLowerJitter_Issue3(
    fixture_session_path,
    minimal_config_dict,
):
    """Should produce lower jitter when using linear vs nearest mapping.

    Requirements: FR-TB-6
    Acceptance: A20
    """
    # Setup base config
    config_dict = minimal_config_dict.copy()
    config_dict["paths"]["raw_root"] = str(fixture_session_path.parent.parent)

    # Create reference timebase
    base_config = Config(**config_dict)
    provider = create_timebase_provider(base_config, manifest=None)
    reference_times = provider.get_timestamps(n_samples=100)

    # Create samples between reference times to test interpolation
    sample_times = [reference_times[i] + 0.015 for i in range(0, 100, 3)]

    # Test with nearest mapping
    config_nearest = config_dict.copy()
    config_nearest["timebase"]["mapping"] = "nearest"
    result_nearest = align_samples(sample_times, reference_times, Config(**config_nearest).timebase, enforce_budget=False)

    # Test with linear mapping
    config_linear = config_dict.copy()
    config_linear["timebase"]["mapping"] = "linear"
    result_linear = align_samples(sample_times, reference_times, Config(**config_linear).timebase, enforce_budget=False)

    # Linear should have lower or equal jitter (A20)
    jitter_nearest = result_nearest["jitter_stats"]
    jitter_linear = result_linear["jitter_stats"]

    assert jitter_linear["max_jitter_s"] <= jitter_nearest["max_jitter_s"]
    assert jitter_linear["p95_jitter_s"] <= jitter_nearest["p95_jitter_s"]


@pytest.mark.integration
def test_Should_HandleRealSessionAlignment_When_UsingSession000001Data_Issue3(
    fixture_session_path,
    fixture_session_toml,
    minimal_config_dict,
    tmp_work_dir,
):
    """Should align real Session-000001 data with timebase provider.

    Requirements: FR-TB-1, FR-TB-6, FR-17
    Acceptance: A8, A9, A11, A12
    """
    # Load real config and session
    config_dict = minimal_config_dict.copy()
    config_dict["paths"]["raw_root"] = str(fixture_session_path.parent)  # parent of Session-000001
    config = Config(**config_dict)

    session = load_session(fixture_session_toml)
    manifest = build_and_count_manifest(config, session)

    # Create nominal rate timebase for camera frames (8580 frames at 30 Hz)
    provider = create_timebase_provider(config, manifest=None)
    expected_frames = 8580  # From real Session-000001 data
    reference_times = provider.get_timestamps(n_samples=expected_frames)

    # Simulate derived data (e.g., pose at every 10th frame)
    sample_indices = list(range(0, expected_frames, 10))
    sample_times = [reference_times[i] for i in sample_indices]

    # Align samples
    result = align_samples(sample_times, reference_times, config.timebase, enforce_budget=False)

    # Verify alignment
    assert len(result["indices"]) == len(sample_times)
    assert result["mapping"] == "nearest"

    # Create and persist alignment stats
    stats = create_alignment_stats(
        timebase_source=config.timebase.source,
        mapping=result["mapping"],
        offset_s=config.timebase.offset_s,
        max_jitter_s=result["jitter_stats"]["max_jitter_s"],
        p95_jitter_s=result["jitter_stats"]["p95_jitter_s"],
        aligned_samples=len(sample_times),
    )

    stats_path = tmp_work_dir / "alignment_stats_session_000001.json"
    write_alignment_stats(stats, stats_path)

    # Verify stats file
    assert stats_path.exists()

    with open(stats_path, "r") as f:
        data = json.load(f)

    assert data["aligned_samples"] == len(sample_times)
    assert data["timebase_source"] == "nominal_rate"
    assert data["max_jitter_s"] < 0.1  # Should be very low for synthetic alignment


@pytest.mark.integration
def test_Should_RecordProvenanceFields_When_AlignmentStatsCreated_Issue3(
    fixture_session_path,
    minimal_config_dict,
):
    """Should include all provenance fields in alignment stats.

    Requirements: FR-TB-5, FR-17
    Acceptance: A18
    """
    # Setup config
    config_dict = minimal_config_dict.copy()
    config_dict["paths"]["raw_root"] = str(fixture_session_path.parent.parent)
    config_dict["timebase"]["offset_s"] = 1.5  # Non-zero offset for testing
    config = Config(**config_dict)

    # Create dummy alignment result
    stats = create_alignment_stats(
        timebase_source=config.timebase.source,
        mapping=config.timebase.mapping,
        offset_s=config.timebase.offset_s,
        max_jitter_s=0.002,
        p95_jitter_s=0.001,
        aligned_samples=100,
    )

    # Verify AlignmentStats has all provenance fields (FR-TB-5)
    assert stats.timebase_source == "nominal_rate"
    assert stats.mapping == "nearest"
    assert stats.offset_s == 1.5
    assert stats.max_jitter_s == 0.002
    assert stats.p95_jitter_s == 0.001
    assert stats.aligned_samples == 100


@pytest.mark.integration
def test_Should_FailGracefully_When_TTLMissingWithTTLSource_Issue3(
    fixture_session_path,
    minimal_config_dict,
):
    """Should raise clear error when TTL source configured but manifest missing.

    Requirements: FR-TB-3
    """
    # Setup config with TTL source
    config_dict = minimal_config_dict.copy()
    config_dict["paths"]["raw_root"] = str(fixture_session_path.parent.parent)
    config_dict["timebase"] = {
        "source": "ttl",
        "mapping": "nearest",
        "jitter_budget_s": 0.01,
        "offset_s": 0.0,
        "ttl_id": "ttl_camera",
    }

    config = Config(**config_dict)

    # Should raise SyncError when manifest is None
    from w2t_bkin.sync import SyncError

    with pytest.raises(SyncError) as exc_info:
        create_timebase_provider(config, manifest=None)

    assert "manifest" in str(exc_info.value).lower()
