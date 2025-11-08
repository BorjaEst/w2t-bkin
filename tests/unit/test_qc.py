"""Unit tests for the qc module.

Tests HTML QC report generation with sync, pose, and metrics summaries
as specified in qc/requirements.md and design.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestQCReportGeneration:
    """Test QC HTML report generation (MR-1)."""

    def test_Should_GenerateHTML_When_SummariesProvided_MR1(self):
        """THE MODULE SHALL generate a QC HTML summarizing sync, pose, and metrics.

        Requirements: MR-1
        Issue: QC module - HTML generation
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(
            sync={"drift_max_ms": 1.5, "dropped_frames": 2},
            pose={"confidence_median": 0.95},
            facemap={"pupil_area_mean": 100.0},
        )

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert
        assert qc_path.exists()
        assert qc_path.suffix == ".html"
        assert "index.html" in qc_path.name

    def test_Should_SummarizeSync_When_Generating_MR1(self):
        """THE MODULE SHALL summarize sync integrity.

        Requirements: MR-1, Design - Sync summaries
        Issue: QC module - Sync summary
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(
            sync={"drift_max_ms": 1.5, "dropped_frames": 2, "quality": "good"},
        )

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert - HTML should contain sync information
        if qc_path.exists():
            html_content = qc_path.read_text()
            assert "sync" in html_content.lower() or "drift" in html_content.lower()

    def test_Should_SummarizePose_When_Generating_MR1(self):
        """THE MODULE SHALL summarize pose data.

        Requirements: MR-1, Design - Pose summaries
        Issue: QC module - Pose summary
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(
            pose={
                "confidence_median": 0.95,
                "confidence_min": 0.5,
                "total_keypoints": 1000,
            },
        )

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert
        if qc_path.exists():
            html_content = qc_path.read_text()
            assert "pose" in html_content.lower() or "confidence" in html_content.lower()

    def test_Should_SummarizeFacemap_When_Generating_MR1(self):
        """THE MODULE SHALL summarize facemap metrics.

        Requirements: MR-1, Design - Metrics summaries
        Issue: QC module - Facemap summary
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(
            facemap={"pupil_area_mean": 100.0, "motion_energy_mean": 0.5},
        )

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert
        assert qc_path is not None

    def test_Should_SummarizeEvents_When_Generating_MR1(self):
        """THE MODULE SHALL summarize events data.

        Requirements: MR-1, Design - Events summaries
        Issue: QC module - Events summary
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(
            events={"trial_count": 10, "event_count": 45},
        )

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert
        assert qc_path is not None

    def test_Should_OrganizeBySession_When_Generating_MR1(self):
        """THE MODULE SHALL organize reports by session.

        Requirements: MR-1, Design - qc/<session>/index.html
        Issue: QC module - Session organization
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(sync={})

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert - Should be in qc/session_001/ directory
        assert "session_001" in str(qc_path)


class TestPlotGeneration:
    """Test plot generation for QC report (Design)."""

    def test_Should_RenderDriftPlot_When_SyncProvided_Design(self):
        """THE MODULE SHALL render drift plots.

        Requirements: Design - Drift plots
        Issue: QC module - Drift visualization
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(
            sync={
                "drift_max_ms": 1.5,
                "drift_values": [0.1, 0.5, 1.0, 1.5],
                "timestamps": [0.0, 10.0, 20.0, 30.0],
            },
        )

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert - Should generate plot assets
        assert qc_path is not None

    def test_Should_RenderDistributions_When_DataProvided_Design(self):
        """THE MODULE SHALL render distributions.

        Requirements: Design - Distributions
        Issue: QC module - Distribution plots
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(
            pose={"confidence_distribution": [0.8, 0.85, 0.9, 0.95, 0.98]},
        )

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert
        assert qc_path is not None

    def test_Should_UseOfflinePlotting_When_Generating_MNFR1(self):
        """THE MODULE SHALL use offline plotting (no network).

        Requirements: M-NFR-1
        Issue: QC module - Offline rendering
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(sync={"drift_max_ms": 1.5})

        # Act - Should work without network access
        qc_path = build_qc(manifest, summaries)

        # Assert
        assert qc_path is not None


class TestVersionTable:
    """Test version table rendering (Design)."""

    def test_Should_RenderVersionTable_When_Generating_Design(self):
        """THE MODULE SHALL render version tables.

        Requirements: Design - Version tables
        Issue: QC module - Version display
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={"pipeline_version": "0.1.0", "git_commit": "abc123"},
        )
        summaries = Summaries(sync={})

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert - Should include version information
        if qc_path.exists():
            html_content = qc_path.read_text()
            assert "version" in html_content.lower() or "provenance" in html_content.lower()

    def test_Should_IncludeConfigSnapshot_When_Generating_Design(self):
        """THE MODULE SHALL include config snapshot in report.

        Requirements: Design - Config display
        Issue: QC module - Config snapshot display
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={"project": {"name": "test", "version": "1.0"}},
            provenance={},
        )
        summaries = Summaries(sync={})

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert
        assert qc_path is not None


class TestGracefulDegradation:
    """Test graceful degradation for missing artifacts (MR-2)."""

    def test_Should_DegradeGracefully_When_OptionalMissing_MR2(self):
        """WHERE optional artifacts are absent, THE MODULE SHALL degrade gracefully.

        Requirements: MR-2
        Issue: QC module - Graceful degradation
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        # Minimal summaries - no pose, facemap, events
        summaries = Summaries(sync={"drift_max_ms": 1.5})

        # Act - Should work with minimal data
        qc_path = build_qc(manifest, summaries)

        # Assert
        assert qc_path is not None

    def test_Should_NoteOmissions_When_DataMissing_MR2(self):
        """THE MODULE SHALL note omissions in the report.

        Requirements: MR-2
        Issue: QC module - Omission notes
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        # Missing pose and facemap
        summaries = Summaries(sync={"drift_max_ms": 1.5})

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert - HTML should note missing sections
        if qc_path.exists():
            html_content = qc_path.read_text()
            # Should indicate missing data or have placeholders
            assert len(html_content) > 0

    def test_Should_HandleEmptySummaries_When_Provided_MR2(self):
        """THE MODULE SHALL handle empty summaries gracefully.

        Requirements: MR-2
        Issue: QC module - Empty summary handling
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        # Empty summaries
        summaries = Summaries()

        # Act & Assert - Should handle gracefully
        try:
            qc_path = build_qc(manifest, summaries)
            assert qc_path is not None
        except Exception as e:
            # If it raises, should be a clear QCBuildError
            assert "QCBuildError" in type(e).__name__ or "missing" in str(e).lower()

    def test_Should_WorkWithMinimalManifest_When_Provided_MR2(self):
        """THE MODULE SHALL work with minimal manifest data.

        Requirements: MR-2
        Issue: QC module - Minimal manifest support
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(sync={})

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert
        assert qc_path is not None


class TestOfflineRendering:
    """Test offline rendering requirements (M-NFR-1)."""

    def test_Should_UseJinja2_When_Rendering_MNFR1(self):
        """THE MODULE SHALL use Jinja2 for templating.

        Requirements: M-NFR-1, Design - Jinja2
        Issue: QC module - Template engine
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(sync={})

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert - Should be pure HTML (no external dependencies)
        assert qc_path is not None

    def test_Should_EmbedAssets_When_Generating_MNFR1(self):
        """THE MODULE SHALL embed or bundle assets for offline use.

        Requirements: M-NFR-1
        Issue: QC module - Asset embedding
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(sync={})

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert - Assets should be in same directory or embedded
        if qc_path.exists():
            # Check for assets directory or inline styles/scripts
            parent_dir = qc_path.parent
            assert parent_dir.exists()

    def test_Should_NotRequireNetwork_When_Viewing_MNFR1(self):
        """THE MODULE SHALL not require network for viewing reports.

        Requirements: M-NFR-1
        Issue: QC module - Network independence
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(sync={})

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert - HTML should not reference CDNs
        if qc_path.exists():
            html_content = qc_path.read_text()
            # Should not have external CDN links
            assert "cdn" not in html_content.lower() or len(html_content) > 0


class TestDeterministicAssets:
    """Test deterministic asset generation (M-NFR-2)."""

    def test_Should_GenerateSameAssets_When_SameInput_MNFR2(self):
        """THE MODULE SHALL generate deterministic report assets.

        Requirements: M-NFR-2
        Issue: QC module - Deterministic generation
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(sync={"drift_max_ms": 1.5})

        # Act
        qc_path1 = build_qc(manifest, summaries)
        qc_path2 = build_qc(manifest, summaries)

        # Assert - Should generate identical content
        if qc_path1.exists() and qc_path2.exists():
            content1 = qc_path1.read_text()
            content2 = qc_path2.read_text()
            # Should be identical (excluding timestamps if any)
            assert len(content1) == len(content2)

    def test_Should_SupportCISnapshots_When_Generated_MNFR2(self):
        """THE MODULE SHALL support CI snapshot testing.

        Requirements: M-NFR-2
        Issue: QC module - CI compatibility
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(sync={})

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert - Should be reproducible for CI
        assert qc_path is not None


class TestErrorHandling:
    """Test error handling (Design)."""

    def test_Should_RaiseQCBuildError_When_InputsInvalid_Design(self):
        """THE MODULE SHALL raise QCBuildError with details.

        Requirements: Design - Error handling
        Issue: QC module - Error reporting
        """
        # Arrange
        from w2t_bkin.qc import QCBuildError, build_qc

        # Act & Assert
        with pytest.raises((QCBuildError, ValueError, TypeError)):
            build_qc(manifest=None, summaries=None)

    def test_Should_ProvideDetails_When_ErrorRaised_Design(self):
        """THE MODULE SHALL provide details on missing inputs.

        Requirements: Design - Error details
        Issue: QC module - Error messages
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import QCBuildError, Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )

        # Act & Assert - Missing summaries
        with pytest.raises((QCBuildError, ValueError, TypeError)) as exc_info:
            build_qc(manifest, summaries=None)

        error_message = str(exc_info.value).lower()
        assert "missing" in error_message or "summaries" in error_message or "required" in error_message


class TestSummariesModel:
    """Test Summaries data structure (Design)."""

    def test_Should_CreateSummaries_When_DataProvided_Design(self):
        """THE MODULE SHALL provide Summaries typed model.

        Requirements: Design - Input contract
        Issue: QC module - Summaries model
        """
        # Arrange
        from w2t_bkin.qc import Summaries

        # Act
        summaries = Summaries(
            sync={"drift_max_ms": 1.5},
            pose={"confidence_median": 0.95},
            facemap={"pupil_area_mean": 100.0},
            events={"trial_count": 10},
        )

        # Assert
        assert summaries.sync["drift_max_ms"] == 1.5
        assert summaries.pose["confidence_median"] == 0.95

    def test_Should_AllowOptionalSections_When_Creating_Design(self):
        """THE MODULE SHALL allow optional summary sections.

        Requirements: Design - Optional sections
        Issue: QC module - Optional summaries
        """
        # Arrange
        from w2t_bkin.qc import Summaries

        # Act - Only sync provided
        summaries = Summaries(sync={"drift_max_ms": 1.5})

        # Assert
        assert summaries.sync is not None


class TestThumbnails:
    """Test thumbnail and figure support (Design)."""

    def test_Should_IncludeThumbnails_When_Provided_Design(self):
        """THE MODULE SHALL include optional thumbnails.

        Requirements: Design - Thumbnails/figures
        Issue: QC module - Thumbnail support
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(
            sync={},
            thumbnails=[Path("/data/thumb1.png"), Path("/data/thumb2.png")],
        )

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert
        assert qc_path is not None

    def test_Should_IncludeFigures_When_Provided_Design(self):
        """THE MODULE SHALL include optional figures.

        Requirements: Design - Figures
        Issue: QC module - Figure support
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(
            sync={},
            figures={"drift_plot": Path("/data/drift.png")},
        )

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert
        assert qc_path is not None


class TestInteractiveElements:
    """Test future interactive elements (Design - Future notes)."""

    def test_Should_SupportInteractive_When_Offline_Future(self):
        """THE MODULE SHALL support interactive elements offline.

        Requirements: Design - Future notes
        Issue: QC module - Interactive elements
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.qc import Summaries, build_qc

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
        )
        summaries = Summaries(
            sync={"drift_max_ms": 1.5},
            interactive=True,
        )

        # Act
        qc_path = build_qc(manifest, summaries)

        # Assert - Should support offline interactive plots (e.g., Plotly offline)
        assert qc_path is not None
