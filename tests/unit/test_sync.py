"""Unit tests for sync module (Phase 2 - Red Phase).

Tests timebase provider abstraction, mapping strategies (nearest, linear),
jitter computation, budget enforcement, and alignment stats persistence.

Requirements: FR-TB-1..6, FR-17
Acceptance: A8, A9, A10, A11, A12, A17, A19, A20
"""

from datetime import datetime
import json
from pathlib import Path

import pytest

from w2t_bkin.domain import AlignmentStats, Config, TimebaseConfig
from w2t_bkin.sync import (
    JitterBudgetExceeded,
    NeuropixelsProvider,
    NominalRateProvider,
    SyncError,
    TimebaseProvider,
    TTLProvider,
    align_samples,
    compute_jitter_stats,
    create_alignment_stats,
    create_timebase_provider,
    enforce_jitter_budget,
    map_linear,
    map_nearest,
    write_alignment_stats,
)


class TestTimebaseProviderCreation:
    """Test timebase provider factory and instantiation."""

    def test_Should_CreateNominalRateProvider_When_SourceIsNominalRate(self, valid_config: Config):
        """FR-TB-4: Create nominal rate provider from config."""
        config = valid_config

        provider = create_timebase_provider(config, manifest=None)

        assert isinstance(provider, NominalRateProvider)
        assert provider.source == "nominal_rate"

    def test_Should_CreateTTLProvider_When_SourceIsTTL(self, ttl_config: Config, ttl_files):
        """FR-TB-3: Create TTL provider when source='ttl'."""
        from w2t_bkin.domain import Manifest, ManifestCamera, ManifestTTL

        # Create manifest with actual TTL files
        manifest = Manifest(
            session_id="test-session",
            cameras=[
                ManifestCamera(
                    camera_id="cam0",
                    ttl_id="ttl_camera",
                    video_files=[],
                    frame_count=1000,
                    ttl_pulse_count=1000,
                )
            ],
            ttls=[
                ManifestTTL(
                    ttl_id="ttl_camera",
                    files=ttl_files,
                )
            ],
        )

        config = ttl_config

        provider = create_timebase_provider(config, manifest=manifest)

        assert isinstance(provider, TTLProvider)
        assert provider.source == "ttl"
        assert provider.ttl_id == config.timebase.ttl_id

    def test_Should_CreateNeuropixelsProvider_When_SourceIsNeuropixels(self, neuropixels_config: Config):
        """FR-TB-2: Create Neuropixels provider when source='neuropixels'."""
        config = neuropixels_config

        provider = create_timebase_provider(config, manifest=None)

        assert isinstance(provider, NeuropixelsProvider)
        assert provider.source == "neuropixels"
        assert provider.stream == config.timebase.neuropixels_stream

    def test_Should_ApplyOffset_When_OffsetConfigured(self, valid_config: Config):
        """FR-TB-5: Provider should respect configured offset_s."""
        config = valid_config
        offset = config.timebase.offset_s

        provider = create_timebase_provider(config, manifest=None)
        timestamps = provider.get_timestamps(n_samples=100)

        assert timestamps[0] == offset


class TestNominalRateProvider:
    """Test nominal rate timebase provider."""

    def test_Should_GenerateSyntheticTimestamps_When_UsingNominalRate(self):
        """FR-TB-4: Generate timestamps from nominal rate."""
        rate = 30.0
        offset_s = 0.0
        n_samples = 100

        provider = NominalRateProvider(rate=rate, offset_s=offset_s)
        timestamps = provider.get_timestamps(n_samples)

        assert len(timestamps) == n_samples
        assert timestamps[0] == offset_s
        assert timestamps[-1] == pytest.approx((n_samples - 1) / rate, rel=1e-6)

    def test_Should_ApplyOffsetCorrectly_When_OffsetNonZero(self):
        """Nominal rate provider should apply offset to all timestamps."""
        rate = 30.0
        offset_s = 10.0
        n_samples = 10

        provider = NominalRateProvider(rate=rate, offset_s=offset_s)
        timestamps = provider.get_timestamps(n_samples)

        assert timestamps[0] == offset_s
        assert timestamps[5] == pytest.approx(offset_s + 5 / rate, rel=1e-6)


class TestTTLProvider:
    """Test TTL-based timebase provider."""

    def test_Should_LoadTTLTimestamps_When_ValidTTLFiles(self, ttl_files):
        """FR-TB-3: Load timestamps from TTL files."""
        ttl_id = "ttl_camera"
        offset_s = 0.0

        provider = TTLProvider(ttl_id=ttl_id, ttl_files=ttl_files, offset_s=offset_s)
        timestamps = provider.get_timestamps()

        assert len(timestamps) > 0
        assert all(isinstance(t, float) for t in timestamps)
        assert timestamps == sorted(timestamps)

    def test_Should_RaiseError_When_TTLFilesMissing(self):
        """Missing TTL files should raise error."""
        ttl_id = "ttl_camera"
        ttl_files = ["/nonexistent/ttl.txt"]

        with pytest.raises(SyncError, match="TTL file not found"):
            TTLProvider(ttl_id=ttl_id, ttl_files=ttl_files, offset_s=0.0)

    def test_Should_ApplyOffset_When_LoadingTTL(self, ttl_files):
        """TTL provider should apply offset to all timestamps."""
        ttl_id = "ttl_camera"
        offset_s = 5.0

        provider_no_offset = TTLProvider(ttl_id=ttl_id, ttl_files=ttl_files, offset_s=0.0)
        provider_with_offset = TTLProvider(ttl_id=ttl_id, ttl_files=ttl_files, offset_s=offset_s)

        timestamps_no_offset = provider_no_offset.get_timestamps()
        timestamps_with_offset = provider_with_offset.get_timestamps()

        assert timestamps_with_offset[0] == pytest.approx(timestamps_no_offset[0] + offset_s)


class TestMappingStrategies:
    """Test nearest and linear mapping strategies."""

    def test_Should_MapUsingNearest_When_StrategyIsNearest(self):
        """FR-TB-6: Nearest neighbor mapping."""
        reference_times = [0.0, 1.0, 2.0, 3.0, 4.0]
        sample_times = [0.3, 1.5, 2.8]

        indices = map_nearest(sample_times, reference_times)

        assert len(indices) == len(sample_times)
        assert indices[0] == 0
        assert indices[2] == 3

    def test_Should_MapUsingLinear_When_StrategyIsLinear(self):
        """FR-TB-6: Linear interpolation mapping."""
        reference_times = [0.0, 1.0, 2.0, 3.0, 4.0]
        sample_times = [0.5, 1.5, 2.5]

        indices, weights = map_linear(sample_times, reference_times)

        assert len(indices) == len(sample_times)
        assert len(weights) == len(sample_times)
        assert indices[0] == (0, 1)
        assert weights[0] == pytest.approx((0.5, 0.5))

    def test_Should_ProduceLowerJitter_When_UsingLinearVsNearest(self):
        """A20: Linear mapping should produce lower jitter than nearest."""
        reference_times = [0.0, 0.5, 1.0, 1.5, 2.0]
        sample_times = [0.25, 0.75, 1.25, 1.75]

        indices_nearest = map_nearest(sample_times, reference_times)
        indices_linear, _ = map_linear(sample_times, reference_times)

        jitter_nearest = compute_jitter_stats(sample_times, reference_times, indices_nearest)
        # For linear, compute jitter using first index of each tuple
        indices_linear_first = [idx[0] for idx in indices_linear]
        jitter_linear = compute_jitter_stats(sample_times, reference_times, indices_linear_first)

        assert jitter_linear["max_jitter_s"] <= jitter_nearest["max_jitter_s"]
        assert jitter_linear["p95_jitter_s"] <= jitter_nearest["p95_jitter_s"]


class TestJitterComputation:
    """Test jitter statistics computation."""

    def test_Should_ComputeMaxJitter_When_AligningSamples(self):
        """Compute maximum jitter between sample and reference times."""
        reference_times = [0.0, 1.0, 2.0, 3.0]
        sample_times = [0.1, 1.2, 1.9, 3.1]
        indices = [0, 1, 2, 3]

        stats = compute_jitter_stats(sample_times, reference_times, indices)

        assert "max_jitter_s" in stats
        assert stats["max_jitter_s"] == pytest.approx(0.2, rel=1e-6)

    def test_Should_ComputeP95Jitter_When_AligningSamples(self):
        """Compute 95th percentile jitter."""
        reference_times = [float(i) for i in range(100)]
        sample_times = [i + 0.05 for i in range(100)]
        indices = list(range(100))

        stats = compute_jitter_stats(sample_times, reference_times, indices)

        assert "p95_jitter_s" in stats
        assert stats["p95_jitter_s"] == pytest.approx(0.05, rel=1e-2)

    def test_Should_ReturnZeroJitter_When_PerfectAlignment(self):
        """Perfect alignment should have zero jitter."""
        reference_times = [0.0, 1.0, 2.0, 3.0]
        sample_times = reference_times.copy()
        indices = [0, 1, 2, 3]

        stats = compute_jitter_stats(sample_times, reference_times, indices)

        assert stats["max_jitter_s"] == pytest.approx(0.0)
        assert stats["p95_jitter_s"] == pytest.approx(0.0)


class TestJitterBudgetEnforcement:
    """Test jitter budget enforcement before NWB assembly."""

    def test_Should_PassValidation_When_JitterWithinBudget(self):
        """A17: Allow NWB assembly when jitter within budget."""
        max_jitter = 0.005
        p95_jitter = 0.003
        budget = 0.010

        enforce_jitter_budget(max_jitter, p95_jitter, budget)

    def test_Should_RaiseError_When_MaxJitterExceedsBudget(self):
        """A17: Abort NWB assembly when max jitter exceeds budget."""
        max_jitter = 0.015
        p95_jitter = 0.008
        budget = 0.010

        with pytest.raises(JitterBudgetExceeded, match="exceeds budget"):
            enforce_jitter_budget(max_jitter, p95_jitter, budget)

    def test_Should_IncludeDiagnostics_When_BudgetExceeded(self):
        """Error should include diagnostic information."""
        max_jitter = 0.015
        p95_jitter = 0.012
        budget = 0.010

        with pytest.raises(JitterBudgetExceeded) as exc_info:
            enforce_jitter_budget(max_jitter, p95_jitter, budget)

        error_msg = str(exc_info.value)
        assert "0.015" in error_msg or "15" in error_msg
        assert "0.010" in error_msg or "10" in error_msg


class TestAlignmentProcess:
    """Test complete alignment workflow."""

    def test_Should_ProduceAlignmentIndices_When_AligningSamples(self):
        """Generate alignment indices for derived data."""
        config = TimebaseConfig(
            source="nominal_rate",
            mapping="nearest",
            jitter_budget_s=0.010,
            offset_s=0.0,
        )
        reference_times = [0.0, 0.5, 1.0, 1.5, 2.0]
        sample_times = [0.3, 0.8, 1.3, 1.8]

        result = align_samples(sample_times, reference_times, config)

        assert "indices" in result
        assert "jitter_stats" in result
        assert len(result["indices"]) == len(sample_times)

    def test_Should_RecordMappingStrategy_When_Aligning(self):
        """Alignment result should record mapping strategy used."""
        config = TimebaseConfig(
            source="nominal_rate",
            mapping="linear",
            jitter_budget_s=0.010,
            offset_s=0.0,
        )
        reference_times = [0.0, 1.0, 2.0]
        sample_times = [0.5, 1.5]

        result = align_samples(sample_times, reference_times, config)

        assert result["mapping"] == "linear"

    def test_Should_EnforceBudget_When_AlignmentComplete(self):
        """Alignment should enforce jitter budget automatically."""
        config = TimebaseConfig(
            source="nominal_rate",
            mapping="nearest",
            jitter_budget_s=0.001,
            offset_s=0.0,
        )
        reference_times = [0.0, 1.0, 2.0]
        sample_times = [0.5, 1.5]

        with pytest.raises(JitterBudgetExceeded):
            align_samples(sample_times, reference_times, config, enforce_budget=True)


class TestAlignmentStatsSidecar:
    """Test alignment stats persistence and content."""

    def test_Should_CreateAlignmentStats_When_AlignmentComplete(self):
        """FR-17, A8: Create alignment stats with all required fields."""
        timebase_source = "nominal_rate"
        mapping = "nearest"
        offset_s = 0.0
        max_jitter = 0.005
        p95_jitter = 0.003
        aligned_samples = 1000

        stats = create_alignment_stats(
            timebase_source=timebase_source,
            mapping=mapping,
            offset_s=offset_s,
            max_jitter_s=max_jitter,
            p95_jitter_s=p95_jitter,
            aligned_samples=aligned_samples,
        )

        assert isinstance(stats, AlignmentStats)
        assert stats.timebase_source == timebase_source
        assert stats.mapping == mapping
        assert stats.offset_s == offset_s
        assert stats.max_jitter_s == max_jitter
        assert stats.p95_jitter_s == p95_jitter
        assert stats.aligned_samples == aligned_samples

    def test_Should_PersistToJSON_When_WritingAlignmentStats(self, tmp_path: Path):
        """Write alignment stats to JSON sidecar."""
        stats = AlignmentStats(
            timebase_source="ttl",
            mapping="linear",
            offset_s=0.5,
            max_jitter_s=0.008,
            p95_jitter_s=0.005,
            aligned_samples=5000,
        )
        output_path = tmp_path / "alignment_stats.json"

        write_alignment_stats(stats, output_path)

        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)
        assert data["timebase_source"] == "ttl"
        assert data["mapping"] == "linear"
        assert data["max_jitter_s"] == 0.008

    def test_Should_IncludeTimestamp_When_WritingStats(self, tmp_path: Path):
        """Alignment stats should include generation timestamp."""
        stats = AlignmentStats(
            timebase_source="nominal_rate",
            mapping="nearest",
            offset_s=0.0,
            max_jitter_s=0.005,
            p95_jitter_s=0.003,
            aligned_samples=1000,
        )
        output_path = tmp_path / "alignment_stats.json"

        write_alignment_stats(stats, output_path)

        with open(output_path) as f:
            data = json.load(f)
        assert "generated_at" in data
        datetime.fromisoformat(data["generated_at"])


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_Should_HandleEmptyReferenceTimebase_When_NoSamples(self):
        """Handle case where reference timebase has no samples."""
        reference_times = []
        sample_times = [0.5, 1.0]

        with pytest.raises(SyncError, match="empty.*reference"):
            map_nearest(sample_times, reference_times)

    def test_Should_HandleEmptySampleSet_When_NoSamplesToAlign(self):
        """Handle case where no samples need alignment."""
        reference_times = [0.0, 1.0, 2.0]
        sample_times = []

        indices = map_nearest(sample_times, reference_times)

        assert len(indices) == 0

    def test_Should_HandleNonMonotonicTimestamps_When_InvalidData(self):
        """Detect and reject non-monotonic timestamps."""
        reference_times = [0.0, 2.0, 1.0, 3.0]
        sample_times = [0.5, 1.5]

        with pytest.raises(SyncError, match="monotonic"):
            map_nearest(sample_times, reference_times)

    def test_Should_WarnOnLargeSampleGap_When_AligningSparseData(self):
        """Warn when sample time falls far from any reference time."""
        reference_times = [0.0, 1.0, 10.0, 11.0]
        sample_times = [5.0]

        with pytest.warns(UserWarning, match="large gap"):
            indices = map_nearest(sample_times, reference_times)

        assert len(indices) == 1


# =============================================================================
# Note: Fixtures for test_sync.py are now in tests/conftest.py
# =============================================================================
# The following shared fixtures are available from conftest.py:
# - valid_config: Config object with nominal_rate timebase
# - ttl_config: Config object with TTL timebase
# - neuropixels_config: Config object with Neuropixels timebase
# - valid_manifest: Manifest object with one camera and TTL
# - ttl_files: Test TTL files with timestamps
# =============================================================================
