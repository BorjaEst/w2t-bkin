"""Integration tests for Phase 4 — NWB Assembly (RED Phase).

Tests end-to-end NWB file creation from ingest through assembly,
including external video links, rate-based ImageSeries, optional modalities,
and provenance embedding.

Requirements: FR-7, NFR-6, NFR-1, NFR-2, NFR-11
Acceptance: A1, A12
GitHub Issue: #5
"""

import json
from pathlib import Path

import pytest

from w2t_bkin.domain import Config, Manifest


class TestBasicNWBAssembly:
    """Test basic NWB assembly from manifest."""

    def test_Should_CreateNWB_When_ManifestProvided_Issue5(
        self,
        fixture_session_path,
        fixture_session_toml,
        minimal_config_dict,
        tmp_work_dir,
    ):
        """Should create basic NWB file from Session-000001 manifest (FR-7, A1)."""
        from w2t_bkin.config import load_session
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.nwb import assemble_nwb

        # Load config and session
        config_dict = minimal_config_dict.copy()
        config_dict["paths"]["raw_root"] = str(fixture_session_path.parent)
        config = Config(**config_dict)

        session = load_session(fixture_session_toml)

        # Build manifest (Phase 1)
        manifest = build_manifest(config, session)

        # Create provenance
        provenance = {
            "config_hash": "test_hash",
            "session_hash": "test_session_hash",
            "timebase": {"source": "nominal_rate", "mapping": "nearest", "offset_s": 0.0},
        }

        # Assemble NWB
        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)

        nwb_path = assemble_nwb(manifest=manifest, config=config, provenance=provenance, output_dir=output_dir)

        # Verify NWB file created
        assert nwb_path.exists()
        assert nwb_path.suffix == ".nwb"
        assert "Session-000001" in nwb_path.name

    def test_Should_IncludeAllCameras_When_MultipleInManifest_Issue5(
        self,
        fixture_session_path,
        fixture_session_toml,
        minimal_config_dict,
        tmp_work_dir,
    ):
        """Should include ImageSeries for all cameras (FR-7)."""
        from pynwb import NWBHDF5IO

        from w2t_bkin.config import load_session
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.nwb import assemble_nwb

        # Setup
        config_dict = minimal_config_dict.copy()
        config_dict["paths"]["raw_root"] = str(fixture_session_path.parent)
        config = Config(**config_dict)
        session = load_session(fixture_session_toml)
        manifest = build_manifest(config, session)

        # Assemble NWB
        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)

        nwb_path = assemble_nwb(manifest=manifest, config=config, provenance={}, output_dir=output_dir)

        # Read and verify
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()

            # Should have ImageSeries for each camera
            camera_count = len([c for c in manifest.cameras])
            assert len(nwbfile.acquisition) >= camera_count


class TestRateBasedTiming:
    """Test rate-based ImageSeries timing (no per-frame timestamps)."""

    def test_Should_UseRateTiming_When_NominalRateTimebase_Issue5(
        self,
        fixture_session_path,
        minimal_config_dict,
        tmp_work_dir,
    ):
        """Should use rate-based timing for ImageSeries (FR-7, NFR-6, A12)."""
        from pynwb import NWBHDF5IO

        from w2t_bkin.nwb import assemble_nwb

        # Create minimal manifest
        manifest = {
            "session_id": "Session-000001",
            "cameras": [
                {
                    "camera_id": "cam0_top",
                    "video_path": str(fixture_session_path / "Video" / "top" / "cam0_2025-01-01-00-00-00.avi"),
                    "frame_rate": 30.0,
                    "frame_count": 100,
                }
            ],
        }

        # Assemble NWB
        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)

        nwb_path = assemble_nwb(manifest=manifest, config=minimal_config_dict, provenance={"timebase": {"source": "nominal_rate"}}, output_dir=output_dir)

        # Verify rate-based timing
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()
            image_series = list(nwbfile.acquisition.values())[0]

            # Should have rate, not timestamps array
            assert hasattr(image_series, "rate")
            assert image_series.rate == 30.0
            assert hasattr(image_series, "starting_time")


class TestExternalFileLinks:
    """Test external video file linking."""

    def test_Should_LinkExternalFile_When_Enabled_Issue5(
        self,
        fixture_session_path,
        minimal_config_dict,
        tmp_work_dir,
    ):
        """Should create external_file links instead of embedding (FR-7)."""
        from pynwb import NWBHDF5IO

        from w2t_bkin.nwb import assemble_nwb

        # Create manifest with real video file
        video_path = fixture_session_path / "Video" / "top" / "cam0_2025-01-01-00-00-00.avi"

        manifest = {
            "session_id": "Session-000001",
            "cameras": [
                {
                    "camera_id": "cam0_top",
                    "video_path": str(video_path),
                    "frame_rate": 30.0,
                    "frame_count": 100,
                }
            ],
        }

        # Assemble NWB with external links enabled
        config = minimal_config_dict.copy()
        config["nwb"]["link_external_video"] = True

        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)

        nwb_path = assemble_nwb(manifest=manifest, config=config, provenance={}, output_dir=output_dir)

        # Verify external file link
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()
            image_series = list(nwbfile.acquisition.values())[0]

            # Should have external_file attribute
            assert hasattr(image_series, "external_file")
            assert str(video_path) in image_series.external_file[0]


class TestOptionalModalitiesIntegration:
    """Test integration of optional pose/facemap/bpod data."""

    @pytest.mark.skip(reason="RED Phase: requires Phase 3 completion and NWB implementation")
    def test_Should_IncludePose_When_BundleProvided_Issue5(
        self,
        fixture_session_path,
        minimal_config_dict,
        tmp_work_dir,
    ):
        """Should include ndx-pose containers when pose bundle provided (FR-7)."""
        from w2t_bkin.nwb import assemble_nwb

        # Create mock pose bundle
        pose_bundle = {
            "session_id": "Session-000001",
            "camera_id": "cam0_top",
            "skeleton": ["nose", "ear_left", "ear_right"],
            "frames": [],  # Pose data
        }

        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)

        nwb_path = assemble_nwb(
            manifest={"session_id": "Session-000001"}, config=minimal_config_dict, provenance={}, pose_bundles=[pose_bundle], output_dir=output_dir
        )

        # Verify pose included in NWB
        assert nwb_path.exists()

    @pytest.mark.skip(reason="RED Phase: requires Phase 3 completion and NWB implementation")
    def test_Should_IncludeFacemap_When_BundleProvided_Issue5(
        self,
        fixture_session_path,
        minimal_config_dict,
        tmp_work_dir,
    ):
        """Should include BehavioralTimeSeries when facemap bundle provided (FR-7)."""
        from w2t_bkin.nwb import assemble_nwb

        # Create mock facemap bundle
        facemap_bundle = {
            "session_id": "Session-000001",
            "camera_id": "cam0_top",
            "signals": {},  # Facemap signals
        }

        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)

        nwb_path = assemble_nwb(
            manifest={"session_id": "Session-000001"}, config=minimal_config_dict, provenance={}, facemap_bundles=[facemap_bundle], output_dir=output_dir
        )

        # Verify facemap included in NWB
        assert nwb_path.exists()

    @pytest.mark.skip(reason="RED Phase: requires events implementation and NWB integration")
    def test_Should_IncludeBpodTrials_When_SummaryProvided_Issue5(
        self,
        fixture_session_path,
        minimal_config_dict,
        tmp_work_dir,
    ):
        """Should include Trials TimeIntervals when Bpod summary provided (FR-11)."""
        from w2t_bkin.events import BpodSummary
        from w2t_bkin.nwb import assemble_nwb

        # Create Bpod summary
        bpod_summary = BpodSummary(
            session_id="Session-000001",
            total_trials=100,
            outcome_counts={"hit": 60, "miss": 40},
            event_categories=["reward", "stimulus"],
            bpod_files=["/path/to/bpod.mat"],
            generated_at="2025-11-12T12:00:00Z",
        )

        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)

        nwb_path = assemble_nwb(
            manifest={"session_id": "Session-000001"}, config=minimal_config_dict, provenance={}, bpod_summary=bpod_summary, output_dir=output_dir
        )

        # Verify Bpod trials/events included
        assert nwb_path.exists()


class TestProvenanceEmbedding:
    """Test provenance metadata embedding in NWB."""

    def test_Should_EmbedProvenance_When_Assembling_Issue5(
        self,
        fixture_session_path,
        minimal_config_dict,
        tmp_work_dir,
    ):
        """Should embed provenance metadata in NWB (NFR-11, A5)."""
        from pynwb import NWBHDF5IO

        from w2t_bkin.nwb import assemble_nwb

        provenance = {
            "config_hash": "abc123def456",
            "session_hash": "789ghi012jkl",
            "software": {"name": "w2t_bkin", "version": "0.1.0"},
            "timebase": {"source": "nominal_rate", "mapping": "nearest", "offset_s": 0.0},
        }

        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)

        nwb_path = assemble_nwb(manifest={"session_id": "Session-000001"}, config=minimal_config_dict, provenance=provenance, output_dir=output_dir)

        # Verify provenance embedded
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()

            # Should have custom provenance fields
            assert hasattr(nwbfile, "lab_meta_data") or "provenance" in nwbfile.fields


class TestEndToEndPipeline:
    """Test complete pipeline from ingest through NWB assembly."""

    @pytest.mark.skip(reason="RED Phase: requires Phase 0-4 completion")
    def test_Should_CompleteFullPipeline_When_AllStagesRun_Issue5(
        self,
        fixture_session_path,
        fixture_session_toml,
        minimal_config_dict,
        tmp_work_dir,
    ):
        """Should complete ingest → sync → NWB pipeline (A1)."""
        from w2t_bkin.config import load_session
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.nwb import assemble_nwb
        from w2t_bkin.sync import create_timebase_provider

        # Phase 0: Config
        config_dict = minimal_config_dict.copy()
        config_dict["paths"]["raw_root"] = str(fixture_session_path.parent)
        config = Config(**config_dict)
        session = load_session(fixture_session_toml)

        # Phase 1: Ingest
        manifest = build_manifest(config, session)

        # Phase 2: Sync
        provider = create_timebase_provider(config, manifest=None)

        # Phase 4: NWB Assembly
        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)

        provenance = {
            "config_hash": "test_hash",
            "timebase": {"source": config.timebase.source},
        }

        nwb_path = assemble_nwb(manifest=manifest, config=config, provenance=provenance, output_dir=output_dir)

        # Verify complete NWB
        assert nwb_path.exists()
        assert nwb_path.suffix == ".nwb"


class TestDeterministicOutput:
    """Test deterministic NWB output for reproducibility."""

    @pytest.mark.skip(reason="RED Phase: requires NWB implementation")
    def test_Should_ProduceSameNWB_When_SameInputs_Issue5(
        self,
        fixture_session_path,
        minimal_config_dict,
        tmp_work_dir,
    ):
        """Should produce identical NWB when inputs unchanged (NFR-1)."""
        from w2t_bkin.nwb import assemble_nwb

        manifest = {"session_id": "Session-000001", "cameras": []}
        provenance = {"config_hash": "abc123"}

        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Assemble twice
        nwb_path1 = assemble_nwb(manifest, minimal_config_dict, provenance, output_dir)
        nwb_path2 = assemble_nwb(manifest, minimal_config_dict, provenance, output_dir)

        # Compare file hashes (deterministic container order)
        import hashlib

        def file_hash(path):
            return hashlib.sha256(path.read_bytes()).hexdigest()

        assert file_hash(nwb_path1) == file_hash(nwb_path2)
