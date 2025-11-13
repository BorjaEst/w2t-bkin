# Domain Module

**Phase:** 0 (Foundation)  
**Status:** ✅ Complete  
**Requirements:** FR-1, FR-2, FR-4, FR-5, FR-6, FR-7, FR-8, NFR-1, NFR-2

## Purpose

Defines immutable Pydantic models representing pipeline data structures. Enforces strict schemas, frozen models, and validation rules. Central to pipeline correctness and reproducibility (NFR-1).

## Core Domain Models

### Configuration Models

```python
class Config(BaseModel):
    """Top-level configuration model (strict schema)."""
    model_config = {"frozen": True, "extra": "forbid"}

    project: ProjectConfig
    paths: PathsConfig
    timebase: TimebaseConfig
    acquisition: AcquisitionConfig
    verification: VerificationConfig
    bpod: BpodConfig
    video: VideoConfig
    nwb: NWBConfig
    qc: QCConfig
    logging: LoggingConfig
    labels: LabelsConfig
    facemap: FacemapConfig

class ProjectConfig(BaseModel):
    """Project identification."""
    model_config = {"frozen": True, "extra": "forbid"}
    name: str

class PathsConfig(BaseModel):
    """Path configuration for data directories."""
    model_config = {"frozen": True, "extra": "forbid"}

    raw_root: str
    intermediate_root: str
    output_root: str
    metadata_file: str
    models_root: str

class TimebaseConfig(BaseModel):
    """Timebase configuration for session reference clock."""
    model_config = {"frozen": True, "extra": "forbid"}

    source: str  # Enum: "ttl", "bpod", "video", "neuropixels"
    mapping: str  # Enum: alignment strategy
    jitter_budget_s: float
    offset_s: float
    ttl_id: Optional[str] = None
    neuropixels_stream: Optional[str] = None

class AcquisitionConfig(BaseModel):
    """Acquisition policies."""
    model_config = {"frozen": True, "extra": "forbid"}
    concat_strategy: str

class VerificationConfig(BaseModel):
    """Verification policies for frame/TTL matching."""
    model_config = {"frozen": True, "extra": "forbid"}

    mismatch_tolerance_frames: int
    warn_on_mismatch: bool

class BpodConfig(BaseModel):
    """Bpod parsing configuration."""
    model_config = {"frozen": True, "extra": "forbid"}
    parse: bool

class TranscodeConfig(BaseModel):
    """Video transcoding configuration."""
    model_config = {"frozen": True, "extra": "forbid"}

    enabled: bool
    codec: str
    crf: int
    preset: str
    keyint: int

class VideoConfig(BaseModel):
    """Video processing configuration."""
    model_config = {"frozen": True, "extra": "forbid"}
    transcode: TranscodeConfig

class NWBConfig(BaseModel):
    """NWB export configuration."""
    model_config = {"frozen": True, "extra": "forbid"}

    link_external_video: bool
    lab: str
    institution: str
    file_name_template: str
    session_description_template: str

class QCConfig(BaseModel):
    """QC report configuration."""
    model_config = {"frozen": True, "extra": "forbid"}

    generate_report: bool
    out_template: str
    include_verification: bool

class LoggingConfig(BaseModel):
    """Logging configuration."""
    model_config = {"frozen": True, "extra": "forbid"}

    level: str
    structured: bool

class DLCConfig(BaseModel):
    """DeepLabCut configuration."""
    model_config = {"frozen": True, "extra": "forbid"}

    run_inference: bool
    model: str

class SLEAPConfig(BaseModel):
    """SLEAP configuration."""
    model_config = {"frozen": True, "extra": "forbid"}

    run_inference: bool
    model: str

class LabelsConfig(BaseModel):
    """Pose estimation labels configuration."""
    model_config = {"frozen": True, "extra": "forbid"}

    dlc: DLCConfig
    sleap: SLEAPConfig

class FacemapConfig(BaseModel):
    """Facemap configuration."""
    model_config = {"frozen": True, "extra": "forbid"}

    run_inference: bool
    ROIs: List[str]
```

### Session Models

```python
class Session(BaseModel):
    """Session configuration model (strict schema)."""
    model_config = {"frozen": True, "extra": "forbid"}

    session: SessionMetadata
    bpod: BpodSession
    TTLs: List[TTL]
    cameras: List[Camera]

class SessionMetadata(BaseModel):
    """Session metadata."""
    model_config = {"frozen": True, "extra": "forbid"}

    id: str
    subject_id: str
    date: str
    experimenter: str
    description: str
    sex: str
    age: str
    genotype: str

class BpodSession(BaseModel):
    """Bpod file configuration for session."""
    model_config = {"frozen": True, "extra": "forbid"}

    path: str
    order: str

class TTL(BaseModel):
    """TTL configuration (immutable)."""
    model_config = {"frozen": True, "extra": "forbid"}

    id: str
    description: str
    paths: str

class Camera(BaseModel):
    """Camera configuration (immutable)."""
    model_config = {"frozen": True, "extra": "forbid"}

    id: str
    description: str
    paths: str
    order: str
    ttl_id: str
```

### Manifest Model

```python
class Manifest(BaseModel):
    """Manifest tracking discovered files."""
    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str
    cameras: List[ManifestCamera] = Field(default_factory=list)
    ttls: List[ManifestTTL] = Field(default_factory=list)
    bpod_files: Optional[List[str]] = None

class ManifestCamera(BaseModel):
    """Camera entry in manifest."""
    model_config = {"frozen": True, "extra": "forbid"}

    camera_id: str
    ttl_id: str
    video_files: List[str]
    frame_count: int = 0
    ttl_pulse_count: int = 0

class ManifestTTL(BaseModel):
    """TTL entry in manifest."""
    model_config = {"frozen": True, "extra": "forbid"}

    ttl_id: str
    files: List[str]
```

### Provenance Model

```python
class Provenance(BaseModel):
    """Provenance metadata."""
    model_config = {"frozen": True, "extra": "forbid"}

    config_hash: str  # SHA256 of config.toml
    session_hash: str  # SHA256 of session.toml

# Note: Extended provenance with software/git/timebase info
# is planned but not yet implemented. Current minimal version
# supports basic reproducibility requirements.
```

### Pose Models

```python
class PoseBundle(BaseModel):
    """Harmonized pose data bundle aligned to reference timebase."""
    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str
    camera_id: str
    model_name: str
    skeleton: str  # Canonical skeleton name
    frames: List[PoseFrame]
    alignment_method: str  # "nearest" or "linear"
    mean_confidence: float
    generated_at: str

class PoseFrame(BaseModel):
    """Pose data for a single frame."""
    model_config = {"frozen": True, "extra": "forbid"}

    frame_index: int
    timestamp: float  # Aligned timestamp
    keypoints: List[PoseKeypoint]
    source: str  # "dlc" or "sleap"

class PoseKeypoint(BaseModel):
    """Single keypoint in pose estimation."""
    model_config = {"frozen": True, "extra": "forbid"}

    name: str
    x: float
    y: float
    confidence: float
```

### Event Models

```python
class Trial(BaseModel):
    """Trial data extracted from Bpod."""
    model_config = {"frozen": True, "extra": "forbid"}

    trial_number: int
    start_time: float
    stop_time: float
    outcome: str

class TrialEvent(BaseModel):
    """Behavioral event extracted from Bpod."""
    model_config = {"frozen": True, "extra": "forbid"}

    event_type: str
    timestamp: float
    trial_number: int

class TrialSummary(BaseModel):
    """Bpod summary for QC report."""
    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str
    total_trials: int
    outcome_counts: dict
    event_categories: List[str]
    bpod_files: List[str]
    generated_at: str
```

### Verification Models

```python
class CameraVerificationResult(BaseModel):
    """Verification result for a single camera."""
    model_config = {"frozen": True, "extra": "forbid"}

    camera_id: str
    ttl_id: str
    frame_count: int
    ttl_pulse_count: int
    mismatch: int
    verifiable: bool
    status: str  # "pass", "failed", "unverifiable"

class VerificationSummary(BaseModel):
    """Verification summary for frame/TTL counts."""
    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str
    cameras: List[CameraVerificationResult]
    generated_at: str

class VerificationResult(BaseModel):
    """Result of manifest verification."""
    model_config = {"frozen": True, "extra": "forbid"}

    status: str
    camera_results: List[CameraVerificationResult] = Field(default_factory=list)
```

### Alignment Models (Phase 2)

```python
class AlignmentStats(BaseModel):
    """Alignment statistics for timebase."""
    model_config = {"frozen": True, "extra": "forbid"}

    timebase_source: str
    mapping: str
    offset_s: float
    max_jitter_s: float
    p95_jitter_s: float
    aligned_samples: int
```

### Facemap Models (Phase 3)

```python
class FacemapBundle(BaseModel):
    """Facemap data bundle aligned to reference timebase."""
    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str
    camera_id: str
    rois: List[FacemapROI]
    signals: List[FacemapSignal]
    alignment_method: str  # "nearest" or "linear"
    generated_at: str

    @model_validator(mode="after")
    def validate_signals_match_rois(self) -> "FacemapBundle":
        """Validate that all signals reference defined ROIs."""
        roi_names = {roi.name for roi in self.rois}
        for signal in self.signals:
            if signal.roi_name not in roi_names:
                raise ValueError(
                    f"Signal references undefined ROI: {signal.roi_name}. "
                    f"Defined ROIs: {roi_names}"
                )
        return self

class FacemapROI(BaseModel):
    """Region of interest for Facemap analysis."""
    model_config = {"frozen": True, "extra": "forbid"}

    name: str
    x: int
    y: int
    width: int
    height: int

class FacemapSignal(BaseModel):
    """Time series signal from Facemap ROI."""
    model_config = {"frozen": True, "extra": "forbid"}

    roi_name: str
    timestamps: List[float]  # Aligned timestamps
    values: List[float]
    sampling_rate: float
```

### Transcode Models (Phase 3)

```python
class TranscodedVideo(BaseModel):
    """Metadata for a transcoded video file."""
    model_config = {"frozen": True, "extra": "forbid"}

    camera_id: str
    original_path: Path
    output_path: Path  # Transcoded file path
    codec: str
    checksum: str  # Content-addressed hash
    frame_count: int

class TranscodeOptions(BaseModel):
    """Transcoding configuration options."""
    model_config = {"frozen": True, "extra": "forbid"}

    codec: str
    crf: int
    preset: str
    keyint: int
```

## Model Design Principles

### Immutability (NFR-2)

```python
# ✅ All models use model_config with frozen=True
class Config(BaseModel):
    model_config = {"frozen": True, "extra": "forbid"}
    paths: PathsConfig

# ❌ This will raise ValidationError (FrozenInstanceError)
config.paths = new_paths  # Cannot modify frozen model
```

### Strict Validation (NFR-1)

```python
# Pydantic validates on construction
try:
    config = Config(**data)
except ValidationError as e:
    print(f"Schema violation: {e}")

# Extra fields forbidden
try:
    config = Config(**{"paths": {...}, "unknown_field": "value"})
except ValidationError as e:
    print(f"Extra field not allowed: {e}")
```

### Model Config Pattern

All models use `model_config` dict instead of deprecated `Config` class:

```python
class MyModel(BaseModel):
    model_config = {"frozen": True, "extra": "forbid"}
    # frozen=True: Immutability after construction
    # extra="forbid": Reject unknown fields
```

### Explicit Types

```python
# Use str for enums (validated at runtime or via validators)
source: str  # e.g., "ttl", "bpod", "video"

# Use Optional for nullable fields
bpod_files: Optional[List[str]] = None

# Use List with element types
cameras: List[Camera]

# Use Field for defaults
cameras: List[ManifestCamera] = Field(default_factory=list)
```

### Composition

```python
# Models compose via nesting
class Config(BaseModel):
    paths: PathsConfig  # Nested model
    timebase: TimebaseConfig
    verification: VerificationConfig
```

### Custom Validators

```python
# Use @model_validator for cross-field validation
class FacemapBundle(BaseModel):
    @model_validator(mode="after")
    def validate_signals_match_rois(self) -> "FacemapBundle":
        """Validate that all signals reference defined ROIs."""
        roi_names = {roi.name for roi in self.rois}
        for signal in self.signals:
            if signal.roi_name not in roi_names:
                raise ValueError(f"Signal references undefined ROI: {signal.roi_name}")
        return self
```

## Validation Rules

### Path Validation

```python
from pydantic import field_validator

class PathsConfig(BaseModel):
    model_config = {"frozen": True, "extra": "forbid"}
    raw_root: str
    output_root: str

    @field_validator('raw_root', 'output_root')
    @classmethod
    def validate_path_exists(cls, v):
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Path does not exist: {v}")
        return v
```

### Timebase Validation

```python
class TimebaseConfig(BaseModel):
    model_config = {"frozen": True, "extra": "forbid"}
    source: str
    jitter_budget_s: float

    @field_validator('jitter_budget_s')
    @classmethod
    def validate_jitter(cls, v):
        if v < 0:
            raise ValueError("jitter_budget_s must be >= 0")
        return v
```

### Model Validator (Cross-field)

```python
class FacemapBundle(BaseModel):
    rois: List[FacemapROI]
    signals: List[FacemapSignal]

    @model_validator(mode="after")
    def validate_signals_match_rois(self) -> "FacemapBundle":
        """Validate that all signals reference defined ROIs."""
        roi_names = {roi.name for roi in self.rois}
        for signal in self.signals:
            if signal.roi_name not in roi_names:
                raise ValueError(f"Signal references undefined ROI: {signal.roi_name}")
        return self
```

## Usage Examples

### Load and validate configuration

```python
from w2t_bkin.domain import Config
from pydantic import ValidationError

try:
    config = Config(**toml_data)
    print(f"Timebase source: {config.timebase.source}")
except ValidationError as e:
    print(f"Invalid config: {e}")
```

### Create immutable manifest

```python
from w2t_bkin.domain import Manifest, ManifestCamera, ManifestTTL
from pydantic import Field

manifest = Manifest(
    session_id="Session-001",
    cameras=[
        ManifestCamera(
            camera_id="cam0",
            ttl_id="ttl0",
            video_files=["/data/cam0_part1.avi"],
            frame_count=18000,
            ttl_pulse_count=18000
        )
    ],
    ttls=[
        ManifestTTL(
            ttl_id="ttl0",
            files=["/data/ttl0.txt"]
        )
    ],
    bpod_files=None
)

# Immutable: This fails
try:
    manifest.session_id = "new_id"
except Exception as e:
    print(f"Cannot modify: {e}")  # FrozenInstanceError
```

### Build provenance record

```python
from w2t_bkin.domain import Provenance

provenance = Provenance(
    config_hash="abc123...",
    session_hash="def456..."
)

# Note: Extended provenance with software/git/timebase info
# is planned for future implementation
```

## Testing

**Test file:** `tests/unit/test_domain.py`

**Coverage:**

- ✅ Config model validation
- ✅ Session model validation
- ✅ Immutability enforcement (frozen models)
- ✅ Nested model composition
- ✅ Optional field handling
- ✅ ValidationError on schema violations
- ✅ Extra field rejection (extra="forbid")
- ✅ Custom validators (@field_validator, @model_validator)

**Run tests:**

```bash
pytest tests/unit/test_domain.py -v
```

## Performance Notes

- **Model construction:** ~1-10ms (Pydantic validation)
- **Immutability:** Zero runtime overhead (compile-time enforcement)
- **Hash computation:** O(n) in model size (for provenance hashing)

## Design Decisions

1. **Frozen models:** Immutability prevents accidental mutation (NFR-2)
2. **Pydantic v2 API:** Use `model_config` dict instead of deprecated `Config` class
3. **Extra field rejection:** `extra="forbid"` ensures strict schema adherence
4. **Composition over inheritance:** Models compose via nesting
5. **Explicit optionals:** Use `Optional[T]` for nullable fields
6. **Field defaults:** Use `Field(default_factory=list)` for mutable defaults
7. **String enums:** Use `str` type with runtime validation (more flexible than `Literal`)
8. **Custom validators:** Use `@field_validator` and `@model_validator` for validation logic
9. **Minimal Provenance:** Current implementation uses basic 2-field provenance (future: expand to 7 fields)
10. **Comprehensive models:** Cover all pipeline phases (Foundation through QC)

## Related Modules

- **config:** Loads Config and Session models from TOML
- **ingest:** Creates Manifest model
- **sync:** Reads TimebaseConfig, creates aligned timestamps
- **pose:** Creates PoseBundle model
- **events:** Creates BpodTrials model
- **nwb:** Consumes Provenance for metadata

## Further Reading

- [Requirements: NFR-1/2](../../requirements.md#non-functional-requirements-ears) - Correctness + Immutability
- [Design: Domain Models](../../design.md#domain-driven-design) - DDD principles
- [Pydantic Documentation](https://docs.pydantic.dev/) - Validation patterns
