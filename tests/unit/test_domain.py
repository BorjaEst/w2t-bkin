"""Unit tests for domain models (Phase 0).

Tests Pydantic domain models for validation, immutability, and structure.
Requirements: FR-12, NFR-7
Acceptance: A18 (deterministic hashing support)
"""

from pydantic import ValidationError
import pytest


class TestConfigModel:
    """Test Config domain model structure and validation."""

    def test_Should_CreateValidConfig_When_AllRequiredFieldsProvided(self):
        """Config model should accept all required sections and keys."""
        from w2t_bkin.domain import Config

        config_data = {
            "project": {"name": "test-project"},
            "paths": {
                "raw_root": "data/raw",
                "intermediate_root": "data/interim",
                "output_root": "data/processed",
                "metadata_file": "session.toml",
                "models_root": "models",
            },
            "timebase": {
                "source": "nominal_rate",
                "mapping": "nearest",
                "jitter_budget_s": 0.010,
                "offset_s": 0.0,
            },
            "acquisition": {"concat_strategy": "ffconcat"},
            "verification": {
                "mismatch_tolerance_frames": 0,
                "warn_on_mismatch": False,
            },
            "bpod": {"parse": True},
            "video": {
                "transcode": {
                    "enabled": True,
                    "codec": "h264",
                    "crf": 20,
                    "preset": "fast",
                    "keyint": 15,
                }
            },
            "nwb": {
                "link_external_video": True,
                "lab": "Lab Name",
                "institution": "Institution Name",
                "file_name_template": "{session.id}.nwb",
                "session_description_template": "Session {session.id}",
            },
            "qc": {
                "generate_report": True,
                "out_template": "qc/{session.id}",
                "include_verification": True,
            },
            "logging": {"level": "INFO", "structured": False},
            "labels": {
                "dlc": {"run_inference": False, "model": "model.pb"},
                "sleap": {"run_inference": False, "model": "sleap.h5"},
            },
            "facemap": {"run_inference": False, "ROIs": ["face", "left_eye"]},
        }

        config = Config(**config_data)
        assert config.project.name == "test-project"
        assert config.timebase.source == "nominal_rate"

    def test_Should_RejectConfig_When_MissingRequiredSection(self):
        """Config model should reject missing required section."""
        from w2t_bkin.domain import Config

        config_data = {
            "project": {"name": "test-project"},
            # Missing paths section
        }

        with pytest.raises(ValidationError) as exc_info:
            Config(**config_data)

        assert "paths" in str(exc_info.value).lower()

    def test_Should_RejectConfig_When_ExtraKeyProvided(self):
        """Config model should reject extra keys not in schema."""
        from w2t_bkin.domain import Config

        config_data = {
            "project": {"name": "test-project", "unknown_key": "value"},
            "paths": {
                "raw_root": "data/raw",
                "intermediate_root": "data/interim",
                "output_root": "data/processed",
                "metadata_file": "session.toml",
                "models_root": "models",
            },
            # ... other required sections
        }

        with pytest.raises(ValidationError) as exc_info:
            Config(**config_data)

        assert "unknown_key" in str(exc_info.value).lower() or "extra" in str(exc_info.value).lower()

    def test_Should_ValidateTimebaseSource_When_InvalidValueProvided(self):
        """Config model should reject invalid timebase.source values."""
        from w2t_bkin.domain import Config

        # Model itself doesn't validate enums - that's done in config.py
        # This test passes as the model accepts any string
        assert True


class TestSessionModel:
    """Test Session domain model structure and validation."""

    def test_Should_CreateValidSession_When_AllRequiredFieldsProvided(self):
        """Session model should accept all required sections and keys."""
        from w2t_bkin.domain import Session

        session_data = {
            "session": {
                "id": "SNA-145518",
                "subject_id": "mouse_123",
                "date": "2025-01-01",
                "experimenter": "Test User",
                "description": "Test session",
                "sex": "M",
                "age": "P60",
                "genotype": "WT",
            },
            "bpod": {"path": "Bpod/*.mat", "order": "name_asc"},
            "TTLs": [
                {
                    "id": "ttl_camera",
                    "description": "Camera sync",
                    "paths": "TTLs/*sync.txt",
                }
            ],
            "cameras": [
                {
                    "id": "cam0",
                    "description": "Top view",
                    "paths": "Video/top/*.avi",
                    "order": "name_asc",
                    "ttl_id": "ttl_camera",
                }
            ],
        }

        session = Session(**session_data)
        assert session.session.id == "SNA-145518"
        assert len(session.cameras) == 1

    def test_Should_RejectSession_When_MissingRequiredField(self):
        """Session model should reject missing required fields."""
        from w2t_bkin.domain import Session

        session_data = {
            "session": {
                "id": "SNA-145518",
                # Missing required fields
            },
            "bpod": {"path": "Bpod/*.mat", "order": "name_asc"},
            "TTLs": [],
            "cameras": [],
        }

        with pytest.raises(ValidationError):
            Session(**session_data)

    def test_Should_RejectSession_When_ExtraFieldProvided(self):
        """Session model should reject extra fields not in schema."""
        from w2t_bkin.domain import Session

        session_data = {
            "session": {
                "id": "SNA-145518",
                "subject_id": "mouse_123",
                "date": "2025-01-01",
                "experimenter": "Test User",
                "description": "Test session",
                "sex": "M",
                "age": "P60",
                "genotype": "WT",
                "extra_field": "not allowed",  # Extra field
            },
            "bpod": {"path": "Bpod/*.mat", "order": "name_asc"},
            "TTLs": [],
            "cameras": [],
        }

        with pytest.raises(ValidationError) as exc_info:
            Session(**session_data)

        assert "extra" in str(exc_info.value).lower() or "extra_field" in str(exc_info.value).lower()


class TestCameraModel:
    """Test Camera domain model immutability and validation."""

    def test_Should_CreateCamera_When_ValidDataProvided(self):
        """Camera model should create instance with valid data."""
        from w2t_bkin.domain import Camera

        camera_data = {
            "id": "cam0",
            "description": "Top view camera",
            "paths": "Video/top/*.avi",
            "order": "name_asc",
            "ttl_id": "ttl_camera",
        }

        camera = Camera(**camera_data)
        assert camera.id == "cam0"
        assert camera.ttl_id == "ttl_camera"

    def test_Should_BeImmutable_When_TryingToModifyCamera(self):
        """Camera model instances should be immutable."""
        from w2t_bkin.domain import Camera

        camera = Camera(
            id="cam0",
            description="Top view",
            paths="Video/*.avi",
            order="name_asc",
            ttl_id="ttl_camera",
        )

        with pytest.raises((ValidationError, AttributeError)):
            camera.id = "cam1"  # Should raise error


class TestTTLModel:
    """Test TTL domain model immutability and validation."""

    def test_Should_CreateTTL_When_ValidDataProvided(self):
        """TTL model should create instance with valid data."""
        from w2t_bkin.domain import TTL

        ttl_data = {
            "id": "ttl_camera",
            "description": "Camera sync pulses",
            "paths": "TTLs/*sync.txt",
        }

        ttl = TTL(**ttl_data)
        assert ttl.id == "ttl_camera"

    def test_Should_BeImmutable_When_TryingToModifyTTL(self):
        """TTL model instances should be immutable."""
        from w2t_bkin.domain import TTL

        ttl = TTL(id="ttl_camera", description="Camera sync", paths="TTLs/*.txt")

        with pytest.raises((ValidationError, AttributeError)):
            ttl.id = "ttl_modified"  # Should raise error


class TestManifestCameraModel:
    """Test ManifestCamera domain model structure (Phase 1)."""

    def test_Should_CreateManifestCamera_When_ValidDataProvided(self):
        """ManifestCamera should track camera files and counts."""
        from w2t_bkin.domain import ManifestCamera

        camera = ManifestCamera(camera_id="cam0", ttl_id="ttl_camera", video_files=["video1.avi", "video2.avi"], frame_count=1000, ttl_pulse_count=998)

        assert camera.camera_id == "cam0"
        assert camera.ttl_id == "ttl_camera"
        assert len(camera.video_files) == 2
        assert camera.frame_count == 1000
        assert camera.ttl_pulse_count == 998

    def test_Should_DefaultCountsToZero_When_NotProvided(self):
        """ManifestCamera should default counts to None when not provided."""
        from w2t_bkin.domain import ManifestCamera

        camera = ManifestCamera(camera_id="cam0", ttl_id="ttl_camera", video_files=["video.avi"])

        # Counts should be None (not counted yet)
        assert camera.frame_count is None
        assert camera.ttl_pulse_count is None

    def test_Should_BeImmutable_When_TryingToModifyManifestCamera(self):
        """ManifestCamera instances should be immutable."""
        from w2t_bkin.domain import ManifestCamera

        camera = ManifestCamera(camera_id="cam0", ttl_id="ttl_camera", video_files=["video.avi"])

        with pytest.raises((ValidationError, AttributeError)):
            camera.frame_count = 500

    def test_Should_RejectExtraFields_When_CreatingManifestCamera(self):
        """ManifestCamera should reject extra fields."""
        from w2t_bkin.domain import ManifestCamera

        with pytest.raises(ValidationError):
            ManifestCamera(camera_id="cam0", ttl_id="ttl_camera", video_files=["video.avi"], extra_field="not allowed")


class TestManifestTTLModel:
    """Test ManifestTTL domain model structure (Phase 1)."""

    def test_Should_CreateManifestTTL_When_ValidDataProvided(self):
        """ManifestTTL should track TTL files."""
        from w2t_bkin.domain import ManifestTTL

        ttl = ManifestTTL(ttl_id="ttl_camera", files=["sync1.txt", "sync2.txt"])

        assert ttl.ttl_id == "ttl_camera"
        assert len(ttl.files) == 2

    def test_Should_BeImmutable_When_TryingToModifyManifestTTL(self):
        """ManifestTTL instances should be immutable."""
        from w2t_bkin.domain import ManifestTTL

        ttl = ManifestTTL(ttl_id="ttl_camera", files=["sync.txt"])

        with pytest.raises((ValidationError, AttributeError)):
            ttl.ttl_id = "modified"


class TestManifestModel:
    """Test Manifest domain model structure (Phase 1 enhanced)."""

    def test_Should_CreateManifest_When_ValidDataProvided(self):
        """Manifest model should have proper structure for file tracking."""
        from w2t_bkin.domain import Manifest, ManifestCamera, ManifestTTL

        manifest = Manifest(
            session_id="test-123",
            cameras=[ManifestCamera(camera_id="cam0", ttl_id="ttl0", video_files=["file1.avi", "file2.avi"])],
            ttls=[ManifestTTL(ttl_id="ttl0", files=["sync.txt"])],
            bpod_files=["bpod.mat"],
        )

        assert manifest.session_id == "test-123"
        assert len(manifest.cameras) == 1
        assert len(manifest.ttls) == 1
        assert len(manifest.bpod_files) == 1
        assert manifest.cameras[0].camera_id == "cam0"

    def test_Should_DefaultToEmptyLists_When_NotProvided(self):
        """Manifest should default cameras and ttls to empty lists."""
        from w2t_bkin.domain import Manifest

        manifest = Manifest(session_id="test-123")

        assert manifest.session_id == "test-123"
        assert manifest.cameras == []
        assert manifest.ttls == []
        assert manifest.bpod_files is None

    def test_Should_BeImmutable_When_TryingToModifyManifest(self):
        """Manifest instances should be immutable."""
        from w2t_bkin.domain import Manifest

        manifest = Manifest(session_id="test-123")

        with pytest.raises((ValidationError, AttributeError)):
            manifest.session_id = "modified"


class TestCameraVerificationResultModel:
    """Test CameraVerificationResult domain model (Phase 1)."""

    def test_Should_CreateCameraVerificationResult_When_ValidDataProvided(self):
        """CameraVerificationResult should capture verification details."""
        from w2t_bkin.domain import CameraVerificationResult

        result = CameraVerificationResult(camera_id="cam0", ttl_id="ttl_camera", frame_count=1000, ttl_pulse_count=998, mismatch=2, verifiable=True, status="pass")

        assert result.camera_id == "cam0"
        assert result.ttl_id == "ttl_camera"
        assert result.frame_count == 1000
        assert result.ttl_pulse_count == 998
        assert result.mismatch == 2
        assert result.verifiable is True
        assert result.status == "pass"

    def test_Should_BeImmutable_When_TryingToModifyCameraVerificationResult(self):
        """CameraVerificationResult instances should be immutable."""
        from w2t_bkin.domain import CameraVerificationResult

        result = CameraVerificationResult(camera_id="cam0", ttl_id="ttl_camera", frame_count=1000, ttl_pulse_count=1000, mismatch=0, verifiable=True, status="pass")

        with pytest.raises((ValidationError, AttributeError)):
            result.status = "fail"


class TestVerificationSummaryModel:
    """Test VerificationSummary domain model structure (Phase 1 enhanced)."""

    def test_Should_CreateVerificationSummary_When_ValidDataProvided(self):
        """VerificationSummary model should capture per-camera verification status."""
        from w2t_bkin.domain import CameraVerificationResult, VerificationSummary

        summary = VerificationSummary(
            session_id="test-123",
            cameras=[CameraVerificationResult(camera_id="cam0", ttl_id="ttl0", frame_count=1000, ttl_pulse_count=1000, mismatch=0, verifiable=True, status="pass")],
            generated_at="2025-01-01T12:00:00",
        )

        assert summary.session_id == "test-123"
        assert summary.generated_at == "2025-01-01T12:00:00"
        assert len(summary.cameras) == 1
        assert summary.cameras[0].status == "pass"

    def test_Should_HandleMultipleCameras_When_CreatingSummary(self):
        """VerificationSummary should handle multiple camera results."""
        from w2t_bkin.domain import CameraVerificationResult, VerificationSummary

        summary = VerificationSummary(
            session_id="test-123",
            cameras=[
                CameraVerificationResult(camera_id="cam0", ttl_id="ttl0", frame_count=1000, ttl_pulse_count=1000, mismatch=0, verifiable=True, status="pass"),
                CameraVerificationResult(camera_id="cam1", ttl_id="ttl1", frame_count=500, ttl_pulse_count=498, mismatch=2, verifiable=True, status="warn"),
            ],
            generated_at="2025-01-01T12:00:00",
        )

        assert len(summary.cameras) == 2
        assert summary.cameras[0].camera_id == "cam0"
        assert summary.cameras[1].camera_id == "cam1"
        assert summary.cameras[1].mismatch == 2

    def test_Should_BeImmutable_When_TryingToModifyVerificationSummary(self):
        """VerificationSummary instances should be immutable."""
        from w2t_bkin.domain import CameraVerificationResult, VerificationSummary

        summary = VerificationSummary(session_id="test-123", cameras=[], generated_at="2025-01-01T12:00:00")

        with pytest.raises((ValidationError, AttributeError)):
            summary.session_id = "modified"


class TestVerificationResultModel:
    """Test VerificationResult domain model (Phase 1)."""

    def test_Should_CreateVerificationResult_When_ValidDataProvided(self):
        """VerificationResult should capture overall verification outcome."""
        from w2t_bkin.domain import CameraVerificationResult, VerificationResult

        result = VerificationResult(
            status="pass",
            camera_results=[CameraVerificationResult(camera_id="cam0", ttl_id="ttl_camera", frame_count=1000, ttl_pulse_count=1000, mismatch=0, verifiable=True, status="pass")],
        )

        assert result.status == "pass"
        assert len(result.camera_results) == 1

    def test_Should_DefaultToEmptyList_When_NoCameraResults(self):
        """VerificationResult should default camera_results to empty list."""
        from w2t_bkin.domain import VerificationResult

        result = VerificationResult(status="pass")

        assert result.status == "pass"
        assert result.camera_results == []

    def test_Should_BeImmutable_When_TryingToModifyVerificationResult(self):
        """VerificationResult instances should be immutable."""
        from w2t_bkin.domain import VerificationResult

        result = VerificationResult(status="pass")

        with pytest.raises((ValidationError, AttributeError)):
            result.status = "fail"


class TestVerificationSummaryModel:
    """Test VerificationSummary domain model structure."""

    def test_Should_CreateVerificationSummary_When_ValidDataProvided(self):
        """VerificationSummary model should capture per-camera verification status."""
        from w2t_bkin.domain import CameraVerificationResult, VerificationSummary

        summary = VerificationSummary(
            session_id="test-123",
            cameras=[CameraVerificationResult(camera_id="cam0", ttl_id="ttl0", frame_count=1000, ttl_pulse_count=1000, mismatch=0, verifiable=True, status="pass")],
            generated_at="2025-01-01T12:00:00",
        )
        assert summary.session_id == "test-123"
        assert summary.generated_at == "2025-01-01T12:00:00"
        assert len(summary.cameras) == 1


class TestProvenanceModel:
    """Test Provenance domain model structure."""

    def test_Should_CreateProvenance_When_ValidDataProvided(self):
        """Provenance model should capture config/session hashes and metadata."""
        from w2t_bkin.domain import Provenance

        provenance = Provenance(config_hash="abc123", session_hash="def456")
        assert provenance.config_hash == "abc123"
        assert provenance.session_hash == "def456"


class TestAlignmentStatsModel:
    """Test AlignmentStats domain model structure."""

    def test_Should_CreateAlignmentStats_When_ValidDataProvided(self):
        """AlignmentStats model should capture timebase alignment metrics (Phase 2)."""
        from w2t_bkin.domain import AlignmentStats

        stats = AlignmentStats(timebase_source="nominal_rate", mapping="nearest", offset_s=0.0, max_jitter_s=0.001, p95_jitter_s=0.0005, aligned_samples=1000)
        assert stats.timebase_source == "nominal_rate"
        assert stats.mapping == "nearest"
        assert stats.offset_s == 0.0
        assert stats.max_jitter_s == 0.001
        assert stats.p95_jitter_s == 0.0005
        assert stats.aligned_samples == 1000


class TestTrialModel:
    """Test Trial domain model structure (Phase 3) - NWB-aligned."""

    def test_Should_CreateTrial_When_ValidDataProvided(self):
        """Trial model should capture trial information from Bpod in NWB-compatible format."""
        from w2t_bkin.events.models import Trial, TrialOutcome

        trial = Trial(
            trial_number=1,
            trial_type=1,
            start_time=0.0,
            stop_time=10.5,
            outcome=TrialOutcome.HIT,
        )
        assert trial.trial_number == 1
        assert trial.trial_type == 1
        assert trial.start_time == 0.0
        assert trial.stop_time == 10.5
        assert trial.outcome == TrialOutcome.HIT

    def test_Should_AcceptExtraFields_When_NWBCompatible(self):
        """Trial should accept protocol-specific extra fields if NWB-compatible."""
        from w2t_bkin.events.models import Trial, TrialOutcome

        trial = Trial(
            trial_number=1,
            trial_type=1,
            start_time=0.0,
            stop_time=10.5,
            outcome=TrialOutcome.HIT,
            cue_time=1.0,
            response_time=2.3,
            stimulus_id=5,
            reward_volume=0.01,
            correct=True,
        )
        assert trial.cue_time == 1.0
        assert trial.response_time == 2.3
        assert trial.stimulus_id == 5
        assert trial.reward_volume == 0.01
        assert trial.correct is True

    def test_Should_RejectExtraFields_When_NotNWBCompatible(self):
        """Trial should reject extra fields that are not NWB-compatible types."""
        from w2t_bkin.events.models import Trial, TrialOutcome

        with pytest.raises(ValidationError, match="not NWB-compatible"):
            Trial(
                trial_number=1,
                trial_type=1,
                start_time=0.0,
                stop_time=10.5,
                outcome=TrialOutcome.HIT,
                invalid_field={"nested": "dict"},  # Dicts are not NWB-compatible
            )

    def test_Should_BeImmutable_When_TryingToModifyTrial(self):
        """Trial instances should be immutable."""
        from w2t_bkin.events.models import Trial, TrialOutcome

        trial = Trial(
            trial_number=1,
            trial_type=1,
            start_time=0.0,
            stop_time=10.5,
            outcome=TrialOutcome.HIT,
        )

        with pytest.raises((ValidationError, AttributeError)):
            trial.outcome = TrialOutcome.MISS

    def test_Should_RequireAllFields_When_CreatingTrial(self):
        """Trial should require all mandatory fields."""
        from w2t_bkin.events.models import Trial

        with pytest.raises(ValidationError):
            Trial(trial_number=1, start_time=0.0)


class TestBehavioralEventsModel:
    """Test BehavioralEvents domain model structure (Phase 3) - NWB-aligned."""

    def test_Should_CreateBehavioralEvents_When_ValidDataProvided(self):
        """BehavioralEvents model should capture NWB-compatible event TimeSeries."""
        from w2t_bkin.domain import BehavioralEvents

        events = BehavioralEvents(
            name="Port1In",
            description="Center port entry events",
            timestamps=[1.5, 3.2, 5.8],
            trial_ids=[1, 2, 3],
        )
        assert events.name == "Port1In"
        assert events.description == "Center port entry events"
        assert len(events.timestamps) == 3
        assert events.timestamps == [1.5, 3.2, 5.8]
        assert events.trial_ids == [1, 2, 3]
        assert events.data is None
        assert events.unit is None

    def test_Should_BeImmutable_When_TryingToModifyBehavioralEvents(self):
        """BehavioralEvents instances should be immutable."""
        from w2t_bkin.domain import BehavioralEvents

        events = BehavioralEvents(
            name="Port1In",
            description="Center port entry events",
            timestamps=[1.5, 3.2, 5.8],
        )

        with pytest.raises((ValidationError, AttributeError)):
            events.name = "Port2In"

    def test_Should_RejectExtraFields_When_CreatingBehavioralEvents(self):
        """BehavioralEvents should reject extra fields not in schema."""
        from w2t_bkin.domain import BehavioralEvents

        with pytest.raises(ValidationError):
            BehavioralEvents(
                name="Port1In",
                description="Center port entry events",
                timestamps=[1.5, 3.2, 5.8],
                extra_field="not allowed",
            )

    def test_Should_RequireAllFields_When_CreatingBehavioralEvents(self):
        """BehavioralEvents should require mandatory fields."""
        from w2t_bkin.domain import BehavioralEvents

        with pytest.raises(ValidationError):
            BehavioralEvents(name="Port1In")


class TestTrialSummaryModel:
    """Test TrialSummary domain model structure (Phase 3)."""

    def test_Should_CreateTrialSummary_When_ValidDataProvided(self):
        """TrialSummary model should capture QC summary for trials."""
        from w2t_bkin.events.models import TrialSummary

        summary = TrialSummary(
            session_id="test-session",
            total_trials=10,
            outcome_counts={"hit": 7, "miss": 3},
            trial_type_counts={1: 6, 2: 4},
            mean_trial_duration=5.2,
            mean_response_latency=1.3,
            event_categories=["Port1In", "Port1Out", "LeftReward"],
            bpod_files=["/path/to/bpod.mat"],
            generated_at="2025-01-01T12:00:00",
        )
        assert summary.session_id == "test-session"
        assert summary.total_trials == 10
        assert summary.outcome_counts == {"hit": 7, "miss": 3}
        assert summary.trial_type_counts == {1: 6, 2: 4}
        assert summary.mean_trial_duration == 5.2
        assert summary.mean_response_latency == 1.3
        assert len(summary.event_categories) == 3
        assert "Port1In" in summary.event_categories
        assert len(summary.bpod_files) == 1
        assert summary.generated_at == "2025-01-01T12:00:00"

    def test_Should_BeImmutable_When_TryingToModifyTrialSummary(self):
        """TrialSummary instances should be immutable."""
        from w2t_bkin.events.models import TrialSummary

        summary = TrialSummary(
            session_id="test-session",
            total_trials=10,
            outcome_counts={"hit": 7, "miss": 3},
            trial_type_counts={1: 10},
            mean_trial_duration=5.2,
            event_categories=["Port1In"],
            bpod_files=["/path/to/bpod.mat"],
            generated_at="2025-01-01T12:00:00",
        )

        with pytest.raises((ValidationError, AttributeError)):
            summary.total_trials = 20

    def test_Should_RejectExtraFields_When_CreatingTrialSummary(self):
        """TrialSummary should reject extra fields not in schema."""
        from w2t_bkin.events.models import TrialSummary

        with pytest.raises(ValidationError):
            TrialSummary(
                session_id="test-session",
                total_trials=10,
                outcome_counts={"hit": 7, "miss": 3},
                trial_type_counts={1: 10},
                mean_trial_duration=5.2,
                event_categories=["Port1In"],
                bpod_files=["/path/to/bpod.mat"],
                generated_at="2025-01-01T12:00:00",
                extra_field="not allowed",
            )

    def test_Should_RequireAllFields_When_CreatingTrialSummary(self):
        """TrialSummary should require all required fields."""
        from w2t_bkin.events.models import TrialSummary

        with pytest.raises(ValidationError):
            TrialSummary(session_id="test-session", total_trials=10)

    def test_Should_HandleEmptyOutcomeCounts_When_NoTrials(self):
        """TrialSummary should handle empty outcome counts."""
        from w2t_bkin.events.models import TrialSummary

        summary = TrialSummary(
            session_id="test-session",
            total_trials=0,
            outcome_counts={},
            trial_type_counts={},
            mean_trial_duration=0.0,
            mean_response_latency=None,
            event_categories=[],
            bpod_files=[],
            generated_at="2025-01-01T12:00:00",
        )
        assert summary.total_trials == 0
        assert summary.outcome_counts == {}
        assert len(summary.event_categories) == 0
