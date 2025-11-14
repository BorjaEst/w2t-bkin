# Sync Module

**Phase:** 2 (Synchronization)  
**Status:** ✅ Complete  
**Requirements:** FR-TB-1..6, FR-17

## Purpose

Provides timebase provider abstraction, mapping strategies for aligning derived data (pose, facemap, behavioral events) to a session reference timebase, jitter computation, and alignment statistics persistence. Supports multiple timebase sources (nominal rate, TTL, Neuropixels) with configurable mapping strategies (nearest, linear).

## Key Concepts

### Timebase Provider

An abstract interface for obtaining timestamps from different sources:

- **NominalRateProvider**: Synthetic timestamps from nominal acquisition rate (e.g., 30 Hz)
- **TTLProvider**: Real timestamps loaded from TTL pulse log files
- **NeuropixelsProvider**: High-rate timestamps from DAQ/Neuropixels (stub implementation)

### Mapping Strategies

Methods for aligning sample times to reference timebase:

- **nearest**: Maps each sample to the closest reference timestamp (simple, fast)
- **linear**: Interpolates between bracketing reference timestamps (smoother, more accurate)

### Jitter Budget

Maximum acceptable timing misalignment between sample times and reference timebase. Pipeline enforces this budget before NWB assembly to ensure data quality (FR-TB-6, A17).

## Key Functions

### Timebase Provider Factory

```python
def create_timebase_provider(config: Config, manifest: Optional[Manifest] = None) -> TimebaseProvider:
    """Create timebase provider from config.

    Args:
        config: Pipeline configuration with timebase settings
        manifest: Session manifest (required for TTL provider)

    Returns:
        TimebaseProvider instance (NominalRateProvider, TTLProvider, or NeuropixelsProvider)

    Raises:
        SyncError: If invalid source or missing required data

    Example:
        >>> from w2t_bkin.sync import create_timebase_provider
        >>> provider = create_timebase_provider(config, manifest)
        >>> timestamps = provider.get_timestamps(n_samples=1000)
    """
```

**Behavior by source:**

- `source="nominal_rate"`: Creates NominalRateProvider with default 30 Hz rate
- `source="ttl"`: Requires `config.timebase.ttl_id` and manifest with matching TTL files
- `source="neuropixels"`: Requires `config.timebase.neuropixels_stream`

### Mapping Functions

```python
def map_nearest(sample_times: List[float], reference_times: List[float]) -> List[int]:
    """Map sample times to nearest reference times.

    Args:
        sample_times: Times to align (e.g., from pose or facemap)
        reference_times: Reference timebase timestamps

    Returns:
        List of indices into reference_times

    Raises:
        SyncError: If reference is empty or not monotonic

    Example:
        >>> sample_times = [0.5, 1.5, 2.5]
        >>> reference_times = [0.0, 1.0, 2.0, 3.0]
        >>> indices = map_nearest(sample_times, reference_times)
        >>> # Returns [1, 2, 3] - nearest indices
    """

def map_linear(
    sample_times: List[float],
    reference_times: List[float]
) -> Tuple[List[Tuple[int, int]], List[Tuple[float, float]]]:
    """Map sample times using linear interpolation.

    Args:
        sample_times: Times to align
        reference_times: Reference timebase timestamps

    Returns:
        Tuple of (indices, weights) where:
        - indices: List of (idx0, idx1) tuples for interpolation
        - weights: List of (w0, w1) tuples for interpolation weights

    Raises:
        SyncError: If reference is empty or not monotonic

    Example:
        >>> sample_times = [0.5, 1.5]
        >>> reference_times = [0.0, 1.0, 2.0]
        >>> indices, weights = map_linear(sample_times, reference_times)
        >>> # indices = [(0, 1), (1, 2)]
        >>> # weights = [(0.5, 0.5), (0.5, 0.5)]
    """
```

### Jitter Computation

```python
def compute_jitter_stats(
    sample_times: List[float],
    reference_times: List[float],
    indices: List[int]
) -> Dict[str, float]:
    """Compute jitter statistics for alignment.

    Args:
        sample_times: Original sample times
        reference_times: Reference timebase
        indices: Mapping indices from map_nearest()

    Returns:
        Dictionary with:
        - max_jitter_s: Maximum jitter observed
        - p95_jitter_s: 95th percentile jitter

    Example:
        >>> jitter_stats = compute_jitter_stats(sample_times, ref_times, indices)
        >>> print(f"Max jitter: {jitter_stats['max_jitter_s']:.4f}s")
        >>> print(f"P95 jitter: {jitter_stats['p95_jitter_s']:.4f}s")
    """

def enforce_jitter_budget(max_jitter: float, p95_jitter: float, budget: float) -> None:
    """Enforce jitter budget before NWB assembly.

    Args:
        max_jitter: Maximum jitter observed
        p95_jitter: 95th percentile jitter
        budget: Configured jitter budget (from config.timebase.jitter_budget_s)

    Raises:
        JitterBudgetExceeded: If jitter exceeds budget

    Example:
        >>> try:
        ...     enforce_jitter_budget(0.05, 0.03, budget=0.04)
        ... except JitterBudgetExceeded as e:
        ...     print(f"Jitter budget exceeded: {e}")
    """
```

### Alignment Workflow

```python
def align_samples(
    sample_times: List[float],
    reference_times: List[float],
    config: TimebaseConfig,
    enforce_budget: bool = False
) -> Dict:
    """Align samples to reference timebase.

    Args:
        sample_times: Times to align
        reference_times: Reference timebase
        config: Timebase configuration (mapping strategy, jitter budget)
        enforce_budget: Whether to enforce jitter budget (raises exception if exceeded)

    Returns:
        Dictionary with:
        - indices: Mapping indices (list of int for nearest, tuple for linear)
        - jitter_stats: Dict with max_jitter_s and p95_jitter_s
        - mapping: Strategy used ("nearest" or "linear")

    Raises:
        JitterBudgetExceeded: If enforce_budget=True and budget exceeded
        SyncError: If invalid mapping strategy

    Example:
        >>> result = align_samples(
        ...     sample_times=[0.5, 1.5, 2.5],
        ...     reference_times=[0.0, 1.0, 2.0, 3.0],
        ...     config=config.timebase,
        ...     enforce_budget=True
        ... )
        >>> indices = result['indices']
        >>> jitter = result['jitter_stats']
    """
```

### Alignment Stats Persistence

```python
def create_alignment_stats(
    timebase_source: str,
    mapping: str,
    offset_s: float,
    max_jitter_s: float,
    p95_jitter_s: float,
    aligned_samples: int
) -> AlignmentStats:
    """Create alignment stats instance.

    Args:
        timebase_source: Source of timebase ("nominal_rate", "ttl", "neuropixels")
        mapping: Mapping strategy used ("nearest", "linear")
        offset_s: Offset applied to timebase
        max_jitter_s: Maximum jitter observed
        p95_jitter_s: 95th percentile jitter
        aligned_samples: Number of samples aligned

    Returns:
        AlignmentStats domain model (Pydantic)

    Example:
        >>> stats = create_alignment_stats(
        ...     timebase_source="ttl",
        ...     mapping="nearest",
        ...     offset_s=0.0,
        ...     max_jitter_s=0.033,
        ...     p95_jitter_s=0.020,
        ...     aligned_samples=1000
        ... )
    """

def write_alignment_stats(stats: AlignmentStats, output_path: Path) -> None:
    """Write alignment stats to JSON sidecar.

    Args:
        stats: AlignmentStats instance
        output_path: Output file path (e.g., alignment_stats.json)

    Example:
        >>> from pathlib import Path
        >>> write_alignment_stats(stats, Path("data/interim/alignment_stats.json"))
    """
```

## Timebase Providers

### NominalRateProvider

Generates synthetic timestamps from a nominal acquisition rate.

```python
provider = NominalRateProvider(rate=30.0, offset_s=0.0)
timestamps = provider.get_timestamps(n_samples=1000)
# Returns: [0.0, 0.0333..., 0.0666..., ..., 33.3]
```

**Use case:** When no hardware timestamps available, assumes constant frame rate.

### TTLProvider

Loads real timestamps from TTL pulse log files.

```python
provider = TTLProvider(
    ttl_id="camera_sync",
    ttl_files=["/data/raw/session_001/ttl_camera_sync.txt"],
    offset_s=0.0
)
timestamps = provider.get_timestamps()  # n_samples ignored
# Returns: [0.123, 0.156, 0.189, ..., 100.234]
```

**File format:** One timestamp per line (float, in seconds).

**Behavior:**

- Loads all TTL files and concatenates timestamps
- Sorts timestamps and applies offset
- Raises SyncError if file not found or parse fails

### NeuropixelsProvider

Stub implementation for high-rate DAQ timestamps (30 kHz default).

```python
provider = NeuropixelsProvider(stream="imec0.ap", offset_s=0.0)
timestamps = provider.get_timestamps(n_samples=30000)
# Returns: [0.0, 0.0000333..., 0.0000666..., ..., 1.0]
```

**Note:** Currently generates synthetic 30 kHz timestamps. Full implementation requires SpikeGLX or Open Ephys integration.

## Error Handling

```python
from w2t_bkin.sync import SyncError, JitterBudgetExceeded

# Missing TTL configuration
try:
    provider = create_timebase_provider(config, manifest)
except SyncError as e:
    print(f"Sync error: {e}")

# Jitter budget exceeded
try:
    result = align_samples(sample_times, ref_times, config, enforce_budget=True)
except JitterBudgetExceeded as e:
    print(f"Jitter exceeds budget: {e}")

# Non-monotonic reference
try:
    indices = map_nearest([1.0, 2.0], [2.0, 1.0, 3.0])  # Not sorted!
except SyncError as e:
    print(f"Reference not monotonic: {e}")
```

### Exception Types

**SyncError (base):**

- Invalid timebase source
- Missing required configuration (ttl_id, neuropixels_stream)
- TTL file not found or unparseable
- Empty or non-monotonic reference timebase
- Invalid mapping strategy

**JitterBudgetExceeded (extends SyncError):**

- Max jitter exceeds configured budget
- P95 jitter exceeds configured budget

## Testing

### Test Coverage

**test_sync.py:**

- `test_Should_CreateNominalRateProvider_When_SourceIsNominalRate()`
- `test_Should_CreateTTLProvider_When_SourceIsTTL()`
- `test_Should_RaiseError_When_TTLIdMissing()`
- `test_Should_RaiseError_When_NeuropixelsStreamMissing()`
- `test_Should_GenerateTimestamps_When_NominalRateProviderUsed()`
- `test_Should_LoadTimestamps_When_TTLProviderUsed()`
- `test_Should_MapNearest_When_SampleTimesProvided()`
- `test_Should_MapLinear_When_InterpolationRequested()`
- `test_Should_ComputeJitterStats_When_AlignmentPerformed()`
- `test_Should_EnforceJitterBudget_When_Enabled()`
- `test_Should_AlignSamples_When_ConfigProvided()`
- `test_Should_WriteAlignmentStats_When_StatsCreated()`

**Run tests:**

```bash
pytest tests/unit/test_sync.py -v
```

## Usage Examples

### Complete alignment workflow

```python
from w2t_bkin import config, sync
from pathlib import Path

# 1. Load configuration
cfg = config.load_config("config.toml")
session = config.load_session("session.toml")

# 2. Build manifest (from ingest phase)
from w2t_bkin.ingest import build_and_count_manifest
manifest = build_and_count_manifest(cfg, session)

# 3. Create timebase provider
provider = sync.create_timebase_provider(cfg, manifest)

# 4. Get reference timestamps
# For TTL: uses actual timestamps from files
# For nominal_rate: generates synthetic timestamps
n_frames = 1000
reference_times = provider.get_timestamps(n_samples=n_frames)

# 5. Align derived data (e.g., pose keypoints)
pose_timestamps = [0.5, 1.0, 1.5, 2.0, 2.5]  # From pose tracking
alignment_result = sync.align_samples(
    sample_times=pose_timestamps,
    reference_times=reference_times,
    config=cfg.timebase,
    enforce_budget=True
)

# 6. Extract alignment info
indices = alignment_result['indices']
jitter_stats = alignment_result['jitter_stats']
mapping = alignment_result['mapping']

print(f"Aligned {len(indices)} pose samples")
print(f"Max jitter: {jitter_stats['max_jitter_s']:.4f}s")
print(f"P95 jitter: {jitter_stats['p95_jitter_s']:.4f}s")
print(f"Mapping strategy: {mapping}")

# 7. Create and persist alignment stats
stats = sync.create_alignment_stats(
    timebase_source=cfg.timebase.source,
    mapping=cfg.timebase.mapping,
    offset_s=cfg.timebase.offset_s,
    max_jitter_s=jitter_stats['max_jitter_s'],
    p95_jitter_s=jitter_stats['p95_jitter_s'],
    aligned_samples=len(indices)
)

output_path = Path("data/interim/alignment_stats.json")
sync.write_alignment_stats(stats, output_path)
```

### Timebase source examples

#### Nominal rate (synthetic)

```python
# config.toml
[timebase]
source = "nominal_rate"
offset_s = 0.0
mapping = "nearest"
jitter_budget_s = 0.05

# Python
provider = sync.create_timebase_provider(cfg)
timestamps = provider.get_timestamps(n_samples=1000)
# [0.0, 0.0333, 0.0666, ..., 33.3] @ 30 Hz
```

#### TTL-based

```python
# config.toml
[timebase]
source = "ttl"
ttl_id = "camera_sync"
offset_s = 0.0
mapping = "linear"
jitter_budget_s = 0.033

# session.toml
[[TTLs]]
id = "camera_sync"
paths = ["ttl_camera_sync.txt"]

# Python
provider = sync.create_timebase_provider(cfg, manifest)
timestamps = provider.get_timestamps()
# [0.123, 0.156, 0.189, ..., 100.234] (from TTL file)
```

#### Neuropixels (stub)

```python
# config.toml
[timebase]
source = "neuropixels"
neuropixels_stream = "imec0.ap"
offset_s = 0.0
mapping = "linear"
jitter_budget_s = 0.001

# Python
provider = sync.create_timebase_provider(cfg)
timestamps = provider.get_timestamps(n_samples=30000)
# [0.0, 0.0000333, ..., 1.0] @ 30 kHz (stub)
```

## Performance Notes

- **Timebase creation:** O(n) for TTL file loading, O(1) for nominal/neuropixels
- **map_nearest:** O(n*m) naive, O(n*log(m)) with numpy (n=samples, m=reference)
- **map_linear:** O(n\*log(m)) with binary search (np.searchsorted)
- **Jitter computation:** O(n) over samples
- **Memory:** TTLProvider loads all timestamps into memory (consider streaming for very long sessions)

**Typical performance:**

- Align 10,000 pose samples to 100,000 reference: ~50-100ms
- Load TTL file with 100,000 pulses: ~100-200ms

## Design Decisions

### Why abstract timebase providers?

Allows pipeline to support multiple timing sources without changing downstream code. New sources (e.g., Open Ephys, custom DAQ) can be added by implementing TimebaseProvider interface.

### Why separate mapping strategies?

Different use cases require different trade-offs:

- **nearest**: Fast, simple, good for high-rate data where jitter < inter-sample interval
- **linear**: More accurate for irregular sampling or when jitter matters

Configuration-driven choice allows experimenting without code changes.

### Why enforce jitter budget?

Prevents assembling NWB files with poor alignment quality. Forces explicit decision: fix alignment issue OR increase budget with justification (NFR-7, A17).

### Why Pydantic domain model for stats?

Consistent with pipeline design (domain models in domain.py). Ensures type safety and validation when reading/writing alignment stats.

### Why not align ImageSeries?

ImageSeries use rate-based timing (starting_time + rate) which is independent of timebase choice. Only **derived** data (pose, facemap, events) need alignment to session reference timebase (FR-7, NFR-6).

## Integration with Pipeline

### Phase 0 (Foundation)

Config module validates timebase settings:

- `source` must be "nominal_rate", "ttl", or "neuropixels"
- `ttl_id` required if source="ttl"
- `neuropixels_stream` required if source="neuropixels"
- `jitter_budget_s` must be >= 0

### Phase 1 (Ingest)

Ingest module discovers TTL files and includes them in manifest:

```python
manifest.ttls = [
    ManifestTTL(ttl_id="camera_sync", files=[...], pulse_count=10000)
]
```

### Phase 3 (Optional Modalities)

Pose, facemap, and events modules use sync to align their data:

```python
# Pose alignment
reference_times = provider.get_timestamps(n_samples=frame_count)
alignment = sync.align_samples(pose_times, reference_times, config.timebase)
aligned_pose = [pose_frames[i] for i in alignment['indices']]

# Facemap alignment (similar)
# Events alignment (similar for Bpod-derived timestamps)
```

### Phase 4 (NWB)

NWB module:

- Uses alignment indices to store aligned pose/facemap data
- Writes alignment_stats.json sidecar
- Records timebase source in provenance

### Provenance

```json
{
  "timebase": {
    "source": "ttl",
    "mapping": "linear",
    "offset_s": 0.0,
    "ttl_id": "camera_sync",
    "jitter_budget_s": 0.033
  },
  "alignment_stats": {
    "max_jitter_s": 0.028,
    "p95_jitter_s": 0.015,
    "aligned_samples": 10000
  }
}
```

## Related Modules

- **config:** Validates timebase configuration and provides TimebaseConfig model
- **domain:** Defines AlignmentStats, TimebaseConfig, Manifest models
- **ingest:** Discovers TTL files and includes them in manifest
- **utils:** Provides write_json() for alignment stats persistence
- **pose/facemap/events:** Use sync to align derived data to session reference timebase

## Further Reading

- [Requirements: FR-TB-1..6](../../requirements.md#timebase-strategy) - Timebase strategy
- [Requirements: FR-17](../../requirements.md#functional-requirements-ears) - Timebase provenance
- [Requirements: NFR-13](../../requirements.md#non-functional-requirements) - Timebase versatility
- [Design: Timebase Strategy](../../design.md#timebase-strategy-reference-only) - Architectural rationale
- [AlignmentStats Schema](../../spec/spec-design-w2t-bkin-simplified.md) - Sidecar format
