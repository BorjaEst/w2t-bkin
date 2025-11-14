# Ingest Module

**Phase:** 1 (Ingest + Verify)  
**Status:** ✅ Complete  
**Requirements:** FR-1, FR-2, FR-3, FR-13, FR-15, FR-16

## Purpose

Discovers camera video files, TTL pulse logs, and Bpod files declared in configuration. Builds a manifest with absolute paths and verifies frame/TTL count matching. Implements fail-fast abort logic when mismatches exceed tolerance.

## Key Functions

### Manifest building (explicit workflow)

The ingest module exposes an explicit two-step API plus a convenience helper:

```python
def discover_files(config: Config, session: Session) -> Manifest:
    """Discover files from session configuration without counting.

    - Resolves raw_root and session directory paths.
    - Discovers camera video files, TTL pulse log files, and Bpod files via glob patterns.
    - Populates Manifest with paths only; frame_count and ttl_pulse_count remain None.
    """

def populate_manifest_counts(manifest: Manifest) -> Manifest:
    """Populate frame and TTL pulse counts for a manifest.

    - Iterates over TTL files and uses count_ttl_pulses() to compute total pulses per ttl_id.
    - Uses count_video_frames() to compute total frames per camera.
    - Returns a new Manifest instance with frame_count/ttl_pulse_count set on each camera.
    """

def build_and_count_manifest(config: Config, session: Session) -> Manifest:
    """Discover files and count frames/TTL pulses in one call (convenience).

    Equivalent to:
        manifest = discover_files(config, session)
        manifest = populate_manifest_counts(manifest)
    """
```

### Frame Counting

```python
def count_video_frames(video_path: Path) -> int:
    """Count frames in a video file using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        Number of frames in video (0 if file doesn't exist or is empty)

    Raises:
        IngestError: If video file cannot be analyzed (wrapped from utils.VideoAnalysisError)

    Note:
        - Uses utils.run_ffprobe() which counts frames with ffprobe
        - Returns 0 for missing or empty files (with warning)
        - Raises IngestError for unreadable/corrupted videos
    """

def count_ttl_pulses(ttl_path: Path) -> int:
    """Count TTL pulses from log file.

    Expected format: One timestamp per line

    Args:
        ttl_path: Path to TTL log file

    Returns:
        Number of pulses in file (0 if file doesn't exist)

    Note:
        - Counts non-empty lines in file
        - Returns 0 (no exception) if file not found
    """

def compute_mismatch(frame_count: int, ttl_pulse_count: int) -> int:
    """Compute absolute mismatch between frame and TTL counts.

    Args:
        frame_count: Number of video frames
        ttl_pulse_count: Number of TTL pulses

    Returns:
        Absolute difference
    """
```

### Verification

```python
def verify_manifest(manifest: Manifest, tolerance: int, warn_on_mismatch: bool = False) -> VerificationResult:
    """Verify frame/TTL counts for all cameras in manifest.

    For each camera:
    1. Compute mismatch = |frame_count - ttl_pulse_count|
    2. Compare mismatch to tolerance
    3. Abort if mismatch > tolerance (FR-3)
    4. Warn if mismatch > 0 and warn_on_mismatch=True (FR-16)

    Args:
        manifest: Manifest with camera data (must have frame_count/ttl_pulse_count)
        tolerance: Maximum allowed mismatch
        warn_on_mismatch: Whether to warn on mismatch within tolerance

    Returns:
        VerificationResult with status and per-camera results

    Raises:
        VerificationError: If any camera mismatch > tolerance (FR-3)

    Example:
        >>> result = verify_manifest(manifest, tolerance=10, warn_on_mismatch=True)
        >>> for cam_result in result.camera_results:
        ...     print(f"{cam_result.camera_id}: {cam_result.status}")
    """

def validate_ttl_references(session: Session) -> None:
    """Validate that all camera ttl_id references exist in session TTLs.

    Args:
        session: Session configuration

    Warns if camera references non-existent TTL (FR-15).
    """

def check_camera_verifiable(camera, ttl_ids: Set[str]) -> bool:
    """Check if camera is verifiable (has valid TTL reference).

    Args:
        camera: Camera configuration
        ttl_ids: Set of valid TTL IDs

    Returns:
        True if camera is verifiable, False otherwise
    """

def create_verification_summary(manifest: Manifest) -> Dict:
    """Create verification summary dict from manifest.

    Args:
        manifest: Manifest with verification data

    Returns:
        Dictionary suitable for JSON serialization
    """

def write_verification_summary(summary: VerificationSummary, output_path: Path) -> None:
    """Write verification summary to JSON file.

    Args:
        summary: VerificationSummary instance
        output_path: Output file path
    """
```

### Additional Helper Functions

```python
def load_manifest(manifest_path: Union[str, Path]) -> dict:
    """Load manifest from JSON file (Phase 1 stub).

    Args:
        manifest_path: Path to manifest.json (str or Path)

    Returns:
        Dictionary with manifest data

    Raises:
        IngestError: If file not found or invalid

    Note:
        Returns mock data if file doesn't exist (for testing)
    """

def discover_sessions(raw_root) -> list:
    """Discover session directories (Phase 1 stub).

    Args:
        raw_root: Root directory for raw data (str, Path, or dict)

    Returns:
        List of session Path objects

    Note:
        Looks for directories matching "Session-*" pattern
    """

def load_config(config_path: Union[str, Path]) -> dict:
    """Load config from TOML file (Phase 0 stub).

    Args:
        config_path: Path to config.toml (str or Path)

    Returns:
        Dictionary with configuration (spec-compliant structure)

    Raises:
        IngestError: If file not found or invalid

    Note:
        Delegates to w2t_bkin.config.load_config()
    """

def ingest_session(session_path: Path, config: dict) -> dict:
    """Ingest a session (Phase 1 stub).

    Args:
        session_path: Path to session directory
        config: Configuration dictionary

    Returns:
        Manifest dictionary

    Raises:
        IngestError: If ingestion fails

    Note:
        Stub implementation - returns minimal manifest
    """
```

## Verification Logic (FR-2, FR-3, FR-16)

### Mismatch Computation

```python
# Using compute_mismatch() helper
mismatch = compute_mismatch(frame_count, ttl_pulse_count)
# Returns: abs(frame_count - ttl_pulse_count)
```

### Tolerance Checking

```python
# In verify_manifest()
for camera in manifest.cameras:
    mismatch = compute_mismatch(camera.frame_count, camera.ttl_pulse_count)

    if mismatch > tolerance:
        # FR-3: Abort with diagnostic
        error_msg = (
            f"Camera {camera.camera_id} verification failed:\n"
            f"  ttl_id: {camera.ttl_id}\n"
            f"  frame_count: {camera.frame_count}\n"
            f"  ttl_pulse_count: {camera.ttl_pulse_count}\n"
            f"  mismatch: {mismatch} (tolerance: {tolerance})"
        )
        raise VerificationError(error_msg)

    # Within tolerance
    if mismatch > 0 and warn_on_mismatch:
        # FR-16: Warn if configured
        logger.warning(
            f"Camera {camera.camera_id} has mismatch of {mismatch} frames "
            f"(within tolerance of {tolerance})"
        )
```

### Unverifiable Cameras (FR-15)

```python
# In validate_ttl_references()
ttl_ids = {ttl.id for ttl in session.TTLs}

for camera in session.cameras:
    if camera.ttl_id and camera.ttl_id not in ttl_ids:
        logger.warning(
            f"Camera {camera.id} references ttl_id '{camera.ttl_id}' "
            f"which does not exist in session TTLs. Camera is unverifiable."
        )

# Helper function to check verifiability
def check_camera_verifiable(camera, ttl_ids: Set[str]) -> bool:
    return bool(camera.ttl_id and camera.ttl_id in ttl_ids)
```

## Manifest schema

```python
class ManifestCamera(BaseModel):
    """Camera entry in manifest."""
    camera_id: str
    ttl_id: str
    video_files: List[str]  # Absolute paths (not video_paths)
    frame_count: Optional[int] = None  # Populated by counting
    ttl_pulse_count: Optional[int] = None  # Populated by counting

class ManifestTTL(BaseModel):
    """TTL entry in manifest."""
    ttl_id: str
    files: List[str]  # Absolute paths

class Manifest(BaseModel):
    """Manifest tracking discovered files."""
    session_id: str
    cameras: List[ManifestCamera] = Field(default_factory=list)
    ttls: List[ManifestTTL] = Field(default_factory=list)
    bpod_files: Optional[List[str]] = None  # Absolute paths
```

## Verification Summary Schema (FR-13)

```json
{
  "session_id": "Session-000001",
  "cameras": [
    {
      "camera_id": "cam0",
      "ttl_id": "ttl0",
      "frame_count": 18000,
      "ttl_pulse_count": 18000,
      "mismatch": 0,
      "verifiable": true,
      "status": "pass"
    }
  ],
  "generated_at": "2025-11-12T12:00:00Z"
}
```

## Error Handling

```python
from w2t_bkin.ingest import IngestError, VerificationError

# Ingestion errors
try:
    manifest = build_and_count_manifest(config, session)
except IngestError as e:
    print(f"Ingestion failed: {e}")
    # Example: "No video files found for camera cam0 with pattern: ..."

# Verification errors
try:
    result = verify_manifest(manifest, tolerance=10, warn_on_mismatch=True)
except VerificationError as e:
    print(f"Verification failed: {e}")
    # Multi-line error message with camera details
```

### Exception Types

**IngestError:**

- Raised when expected camera video files are not found (via glob pattern)
- Raised when video frame counting fails (wrapped from utils.VideoAnalysisError)
- Message includes details about missing files or analysis failure

**VerificationError:**

- Raised when camera mismatch exceeds tolerance
- Message includes: camera_id, ttl_id, frame_count, ttl_pulse_count, mismatch, tolerance
- Multi-line format for readability

## Testing

**Test file:** `tests/unit/test_ingest.py`, `tests/integration/test_phase_1_ingest.py`

**Coverage:**

- ✅ Manifest building with valid session
- ✅ File discovery (cameras, TTLs, Bpod)
- ✅ Frame counting (ffprobe integration)
- ✅ TTL pulse counting
- ✅ Verification abort on mismatch > tolerance (A6)
- ✅ Warning on mismatch within tolerance (A7)
- ✅ Unverifiable camera handling (A15)
- ✅ Verification summary persistence (FR-13)

**Run tests:**

```bash
pytest tests/unit/test_ingest.py -v
pytest tests/integration/test_phase_1_ingest.py -v
```

## Usage Examples

### Basic ingestion workflow

```python
from pathlib import Path

from w2t_bkin.config import load_config, load_session
from w2t_bkin.domain import VerificationSummary
from w2t_bkin.ingest import (
    build_and_count_manifest,
    create_verification_summary,
    verify_manifest,
    write_verification_summary,
)

# Load configuration
config = load_config(Path("config.toml"))
session = load_session(Path("session.toml"))

# One-step: discover files and count frames/TTLs
manifest = build_and_count_manifest(config, session)
print(f"Found {len(manifest.cameras)} cameras")
print(f"Found {len(manifest.ttls)} TTL channels")

# Verify frame/TTL matching
try:
    tolerance = config.verification.mismatch_tolerance_frames
    warn_on_mismatch = config.verification.warn_on_mismatch

    result = verify_manifest(manifest, tolerance, warn_on_mismatch)
    print("Verification passed!")

    # Create and write summary
    summary_dict = create_verification_summary(manifest)
    summary = VerificationSummary(**summary_dict)

    output_path = Path(config.paths.output_root) / "verification_summary.json"
    write_verification_summary(summary, output_path)

except VerificationError as e:
    print(f"Verification failed:\n{e}")
    raise SystemExit(1)
```

### Handle unverifiable cameras

```python
from w2t_bkin.ingest import validate_ttl_references, check_camera_verifiable

# Check for unverifiable cameras before ingestion
validate_ttl_references(session)  # Logs warnings

# Check individual camera
ttl_ids = {ttl.id for ttl in session.TTLs}
for camera in session.cameras:
    if not check_camera_verifiable(camera, ttl_ids):
        print(f"Warning: {camera.id} is unverifiable")
        print(f"  ttl_id={camera.ttl_id} not found in session")

# Check verification results
result = verify_manifest(manifest, tolerance=10)
for cam_result in result.camera_results:
    if cam_result.mismatch > 0:
        print(f"Note: {cam_result.camera_id} has mismatch={cam_result.mismatch}")
```

## Performance Notes

- **File discovery:** O(n) in file count, filesystem operations with glob patterns
- **Frame counting:** ~100-500ms per video (ffprobe `-count_frames` for accuracy)
- **TTL counting:** ~10-50ms per file (line counting)
- **Total verification:** Typically <5 seconds for 5-10 cameras
- **Error handling:** Missing video files raise IngestError; missing TTL files return 0 (warning only)

## Design Decisions

1. **Fail-fast:** Abort on first mismatch > tolerance (saves time, clear error messages)
2. **Absolute paths:** Manifest contains resolved absolute paths (no ambiguity)
3. **Glob patterns:** Use glob.glob() for flexible file discovery from session config
4. **Separate counting:** Frame/TTL counting done after manifest building (allows inspection)
5. **Graceful degradation:** Missing TTL files warn but don't fail (return 0 counts)
6. **Camera video files required:** Missing camera videos raise IngestError immediately
7. **Sidecar persistence:** verification_summary.json for QC and debugging (NFR-3)
8. **Optional warnings:** Configurable warn_on_mismatch for flexibility
9. **Helper functions:** Stub implementations (load_manifest, discover_sessions, etc.) for phase integration
10. **Manifest schema:** Uses `video_files` (not `video_paths`) and includes count fields

## Related Modules

- **config:** Provides Config + Session
- **utils:** Uses ffprobe, path sanitization, JSON I/O
- **domain:** Uses Manifest, VerificationResult models
- **sync:** Consumes Manifest
- **qc:** Consumes verification_summary.json

## Further Reading

- [Requirements: FR-1/2/3](../../requirements.md#functional-requirements-ears) - Ingestion requirements
- [Requirements: A6, A7](../../requirements.md#acceptance-criteria) - Verification acceptance
- [Design: Fail-Fast](../../design.md#principles) - Early abort strategy
