"""Tests for ttl module (TTL signals loading and EventsTable extraction).

Tests the ttl module for TTL signal loading from files and conversion to
ndx-events EventsTable format.
"""

from datetime import datetime

import numpy as np
from pynwb import NWBFile
import pytest

from w2t_bkin.ingest.events import EventsTable, TTLError, add_ttl_table_to_nwb, extract_ttl_table


class TestExtractTTLTable:
    """Test EventsTable creation from TTL pulses."""

    def test_creates_events_table_with_single_channel(self):
        """Should create EventsTable from single TTL channel."""
        ttl_pulses = {"ttl_camera": [0.0, 0.033, 0.066, 0.099]}

        table = extract_ttl_table(ttl_pulses)

        assert isinstance(table, EventsTable)
        assert len(table.timestamp) == 4
        assert np.allclose(table.timestamp[:], [0.0, 0.033, 0.066, 0.099])
        assert all(channel == "ttl_camera" for channel in table["channel"][:])

    def test_creates_events_table_with_multiple_channels(self):
        """Should merge and sort events from multiple channels."""
        ttl_pulses = {"ttl_camera": [0.0, 0.033, 0.066], "ttl_cue": [0.050, 0.100]}

        table = extract_ttl_table(ttl_pulses)

        assert len(table.timestamp) == 5
        # Should be sorted by timestamp
        assert np.allclose(table.timestamp[:], [0.0, 0.033, 0.050, 0.066, 0.100])

        # Channels should match timestamps
        expected_channels = ["ttl_camera", "ttl_camera", "ttl_cue", "ttl_camera", "ttl_cue"]
        assert list(table["channel"][:]) == expected_channels

    def test_uses_custom_descriptions(self):
        """Should use provided descriptions for each channel."""
        ttl_pulses = {"ttl_camera": [0.0, 0.033]}
        descriptions = {"ttl_camera": "Camera frame sync at 30 Hz"}

        table = extract_ttl_table(ttl_pulses, descriptions=descriptions)

        assert all(desc == "Camera frame sync at 30 Hz" for desc in table["ttl_description"][:])

    def test_uses_custom_sources(self):
        """Should use provided sources for each channel."""
        ttl_pulses = {"ttl_camera": [0.0, 0.033]}
        sources = {"ttl_camera": "FLIR Blackfly S"}

        table = extract_ttl_table(ttl_pulses, sources=sources)

        assert all(src == "FLIR Blackfly S" for src in table["source"][:])

    def test_uses_default_description_when_not_provided(self):
        """Should use default description when not provided."""
        ttl_pulses = {"ttl_camera": [0.0]}

        table = extract_ttl_table(ttl_pulses)

        assert table["ttl_description"][0] == "TTL pulses from ttl_camera"

    def test_uses_default_source_when_not_provided(self):
        """Should use 'unknown' as default source."""
        ttl_pulses = {"ttl_camera": [0.0]}

        table = extract_ttl_table(ttl_pulses)

        assert table["source"][0] == "unknown"

    def test_raises_on_empty_ttl_pulses(self):
        """Should raise TTLError when ttl_pulses is empty."""
        with pytest.raises(TTLError, match="empty"):
            extract_ttl_table({})

    def test_raises_on_all_channels_empty(self):
        """Should raise TTLError when all channels have no pulses."""
        ttl_pulses = {"ttl_camera": [], "ttl_cue": []}

        with pytest.raises(TTLError, match="No valid TTL pulses"):
            extract_ttl_table(ttl_pulses)

    def test_skips_empty_channels(self):
        """Should skip channels with no pulses and log warning."""
        ttl_pulses = {"ttl_camera": [0.0, 0.033], "ttl_empty": []}

        table = extract_ttl_table(ttl_pulses)

        # Should only have events from ttl_camera
        assert len(table.timestamp) == 2
        assert all(channel == "ttl_camera" for channel in table["channel"][:])

    def test_handles_large_number_of_pulses(self):
        """Should handle large pulse counts efficiently (performance test)."""
        # Generate 10k pulses at 1kHz (simulates camera frames)
        ttl_pulses = {"ttl_high_freq": list(np.arange(0, 10, 0.001))}

        table = extract_ttl_table(ttl_pulses)

        assert len(table.timestamp) == 10000
        # Verify sorting maintained
        assert np.allclose(np.diff(table.timestamp[:]), 0.001, atol=1e-6)

    def test_handles_float_precision(self):
        """Should preserve timestamp precision."""
        ttl_pulses = {"ttl_test": [0.123456789, 1.987654321]}

        table = extract_ttl_table(ttl_pulses)

        assert table.timestamp[0] == pytest.approx(0.123456789)
        assert table.timestamp[1] == pytest.approx(1.987654321)

    def test_sorts_by_timestamp_across_channels(self):
        """Should sort all pulses by timestamp regardless of channel."""
        ttl_pulses = {"ttl_b": [0.100, 0.300], "ttl_a": [0.050, 0.200]}

        table = extract_ttl_table(ttl_pulses)

        # Should be sorted: 0.050, 0.100, 0.200, 0.300
        assert np.allclose(table.timestamp[:], [0.050, 0.100, 0.200, 0.300])
        expected_channels = ["ttl_a", "ttl_b", "ttl_a", "ttl_b"]
        assert list(table["channel"][:]) == expected_channels

    def test_custom_table_name(self):
        """Should use provided table name."""
        ttl_pulses = {"ttl_camera": [0.0]}

        table = extract_ttl_table(ttl_pulses, name="CustomTTLs")

        assert table.name == "CustomTTLs"

    def test_table_description_includes_channel_count(self):
        """Should include channel count in table description."""
        ttl_pulses = {"ttl_camera": [0.0, 0.033], "ttl_cue": [1.0]}

        table = extract_ttl_table(ttl_pulses)

        assert "2 channels" in table.description
        assert "3 total pulses" in table.description


class TestAddTTLTableToNWB:
    """Test adding TTL events to NWBFile."""

    @pytest.fixture
    def minimal_nwbfile(self):
        """Create minimal NWBFile for testing."""
        return NWBFile(
            session_description="Test session",
            identifier="test-001",
            session_start_time=datetime.now(),
        )

    def test_adds_events_table_to_nwbfile(self, minimal_nwbfile):
        """Should add EventsTable to NWBFile events collection."""
        ttl_pulses = {"ttl_camera": [0.0, 0.033, 0.066]}

        nwbfile = add_ttl_table_to_nwb(minimal_nwbfile, ttl_pulses)

        assert "TTLEvents" in nwbfile.acquisition
        assert isinstance(nwbfile.acquisition["TTLEvents"], EventsTable)
        assert len(nwbfile.acquisition["TTLEvents"].timestamp) == 3

    def test_uses_custom_container_name(self, minimal_nwbfile):
        """Should use provided container name."""
        ttl_pulses = {"ttl_camera": [0.0]}

        nwbfile = add_ttl_table_to_nwb(minimal_nwbfile, ttl_pulses, container_name="HardwareEvents")

        assert "HardwareEvents" in nwbfile.acquisition

    def test_passes_descriptions_and_sources(self, minimal_nwbfile):
        """Should pass through descriptions and sources to EventsTable."""
        ttl_pulses = {"ttl_camera": [0.0]}
        descriptions = {"ttl_camera": "Test camera"}
        sources = {"ttl_camera": "Test source"}

        nwbfile = add_ttl_table_to_nwb(
            minimal_nwbfile,
            ttl_pulses,
            descriptions=descriptions,
            sources=sources,
        )

        table = nwbfile.acquisition["TTLEvents"]
        assert table["ttl_description"][0] == "Test camera"
        assert table["source"][0] == "Test source"

    def test_returns_modified_nwbfile(self, minimal_nwbfile):
        """Should return the modified NWBFile."""
        ttl_pulses = {"ttl_camera": [0.0]}

        result = add_ttl_table_to_nwb(minimal_nwbfile, ttl_pulses)

        assert result is minimal_nwbfile
        assert "TTLEvents" in result.acquisition


class TestPerformance:
    """Performance tests for large TTL datasets."""

    def test_handles_10k_events_efficiently(self):
        """Should handle 10k events in under 2 seconds (with DataFrame bulk insertion)."""
        import time

        # Generate 10k camera frame TTLs at 30Hz (5.5 minutes of recording)
        ttl_pulses = {"ttl_camera": list(np.arange(0, 333.333, 0.033))}

        start = time.time()
        table = extract_ttl_table(ttl_pulses)
        elapsed = time.time() - start

        expected_count = len(ttl_pulses["ttl_camera"])
        assert len(table.timestamp) == expected_count
        assert expected_count >= 10000, f"Should have at least 10k events, got {expected_count}"
        assert elapsed < 2.0, f"Performance degraded: {elapsed:.3f}s for 10k events (should be < 2s with bulk insertion)"

    def test_handles_multiple_channels_with_many_events(self):
        """Should handle multiple channels with many events efficiently."""
        # Simulate realistic session: 3 channels, 10k events total
        ttl_pulses = {
            "ttl_camera": list(np.arange(0, 333.333, 0.033)),  # 30Hz camera
            "ttl_cue": list(np.arange(0, 300, 3.0)),  # Sparse cues
            "ttl_sync": list(np.arange(0, 300, 0.1)),  # 10Hz sync
        }

        table = extract_ttl_table(ttl_pulses)

        # Should have all events sorted
        total_expected = sum(len(pulses) for pulses in ttl_pulses.values())
        assert len(table.timestamp) == total_expected

        # Verify sorting maintained
        assert np.all(np.diff(table.timestamp[:]) >= 0), "Timestamps not sorted"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_single_pulse(self):
        """Should handle single pulse correctly."""
        ttl_pulses = {"ttl_single": [5.0]}

        table = extract_ttl_table(ttl_pulses)

        assert len(table.timestamp) == 1
        assert table.timestamp[0] == 5.0

    def test_handles_zero_timestamp(self):
        """Should handle timestamp at zero."""
        ttl_pulses = {"ttl_test": [0.0, 1.0]}

        table = extract_ttl_table(ttl_pulses)

        assert table.timestamp[0] == 0.0

    def test_handles_negative_timestamps(self):
        """Should handle negative timestamps (e.g., pre-session offset)."""
        ttl_pulses = {"ttl_test": [-1.0, 0.0, 1.0]}

        table = extract_ttl_table(ttl_pulses)

        assert len(table.timestamp) == 3
        assert table.timestamp[0] == -1.0

    def test_handles_unsorted_input(self):
        """Should sort unsorted input timestamps."""
        ttl_pulses = {"ttl_test": [3.0, 1.0, 2.0]}

        table = extract_ttl_table(ttl_pulses)

        assert np.allclose(table.timestamp[:], [1.0, 2.0, 3.0])

    def test_handles_duplicate_timestamps(self):
        """Should handle duplicate timestamps (e.g., hardware glitch)."""
        ttl_pulses = {"ttl_test": [1.0, 1.0, 2.0]}

        table = extract_ttl_table(ttl_pulses)

        assert len(table.timestamp) == 3
        assert table.timestamp[0] == table.timestamp[1]

    def test_handles_very_long_channel_names(self):
        """Should handle long channel IDs."""
        long_id = "ttl_" + "a" * 100
        ttl_pulses = {long_id: [0.0]}

        table = extract_ttl_table(ttl_pulses)

        assert table["channel"][0] == long_id

    def test_handles_special_characters_in_channel_names(self):
        """Should handle special characters in channel IDs."""
        ttl_pulses = {"ttl_cam-0_sync.v2": [0.0]}

        table = extract_ttl_table(ttl_pulses)

        assert table["channel"][0] == "ttl_cam-0_sync.v2"
