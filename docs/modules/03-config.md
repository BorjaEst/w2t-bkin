# Config Module

**Phase:** 0 (Foundation)  
**Status:** ✅ Complete  
**Requirements:** FR-10, FR-15, FR-TB-\*, NFR-10, NFR-11

## Purpose

Loads and validates configuration files (config.toml, session.toml) using strict Pydantic schemas. Enforces enum constraints, conditional validation, and computes deterministic hashes for reproducibility.

## Key Functions

### Configuration Loading

```python
def load_config(path: Union[str, Path]) -> Config:
    """Load and validate configuration from TOML file.

    Performs strict schema validation including:
    - Required/forbidden keys (extra="forbid")
    - Enum validation for timebase.source, timebase.mapping, logging.level
    - Numeric validation for jitter_budget_s >= 0
    - Conditional validation for ttl_id and neuropixels_stream

    Args:
        path: Path to config.toml file (str or Path)

    Returns:
        Validated Config instance

    Raises:
        ValidationError: If config violates schema
        FileNotFoundError: If config file doesn't exist
        ValueError: If enum values or conditionals invalid

    Example:
        >>> from w2t_bkin.config import load_config
        >>> from pathlib import Path
        >>> cfg = load_config(Path("config.toml"))
        >>> print(cfg.project.name)
    """

def load_session(path: Union[str, Path]) -> Session:
    """Load and validate session metadata from TOML file.

    Performs strict schema validation including:
    - Required/forbidden keys (extra="forbid")
    - Camera TTL reference validation

    Args:
        path: Path to session.toml file (str or Path)

    Returns:
        Validated Session instance

    Raises:
        ValidationError: If session violates schema
        FileNotFoundError: If session file doesn't exist

    Example:
        >>> from w2t_bkin.config import load_session
        >>> session = load_session(Path("session.toml"))
        >>> print(session.session.id)
    """
```

### Hash Computation

```python
def compute_config_hash(config: Config) -> str:
    """Compute deterministic hash of config content.

    Canonicalizes config by converting to dict and hashing with sorted keys.
    Comments are not included in the model, so they're automatically stripped.

    Canonicalization process:
    1. Convert to dict with config.model_dump()
    2. Pass to utils.compute_hash() which:
       - Sorts keys recursively
       - Creates compact JSON representation
       - Computes SHA256 hash

    Args:
        config: Config instance

    Returns:
        SHA256 hex digest (64 characters)

    Example:
        >>> from w2t_bkin.config import load_config, compute_config_hash
        >>> cfg = load_config(Path("config.toml"))
        >>> hash1 = compute_config_hash(cfg)
        >>> hash2 = compute_config_hash(cfg)
        >>> assert hash1 == hash2  # Deterministic
    """

def compute_session_hash(session: Session) -> str:
    """Compute deterministic hash of session content.

    Canonicalizes session by converting to dict and hashing with sorted keys.
    Comments are not included in the model, so they're automatically stripped.

    Same canonicalization process as config hash.

    Args:
        session: Session instance

    Returns:
        SHA256 hex digest (64 characters)
    """
```

## Configuration Schema

### config.toml Structure

```toml
[project]
name = "string"

[paths]
raw_root = "path/to/raw"
intermediate_root = "path/to/intermediate"
output_root = "path/to/output"
metadata_file = "session.toml"
models_root = "path/to/models"

[timebase]
source = "nominal_rate" | "ttl" | "neuropixels"
mapping = "nearest" | "linear"
jitter_budget_s = 0.010  # float >= 0
offset_s = 0.0
ttl_id = "optional, required if source=ttl"
neuropixels_stream = "optional, required if source=neuropixels"

[acquisition]
concat_strategy = "ffconcat"

[verification]
mismatch_tolerance_frames = 0  # int >= 0
warn_on_mismatch = false

[bpod]
parse = true

[video.transcode]
enabled = false
codec = "h264"
crf = 20
preset = "fast"
keyint = 15

[nwb]
link_external_video = true
lab = "Lab Name"
institution = "Institution Name"
file_name_template = "{session.id}.nwb"
session_description_template = "Session {session.id}"

[qc]
generate_report = true
out_template = "qc/{session.id}"
include_verification = true

[logging]
level = "INFO" | "DEBUG" | "WARNING" | "ERROR" | "CRITICAL"
structured = false

[labels.dlc]
run_inference = false
model = "path/to/model.pb"

[labels.sleap]
run_inference = false
model = "path/to/model.h5"

[facemap]
run_inference = false
ROIs = ["face", "whiskers"]
```

### session.toml Structure

```toml
[session]
id = "Session-000001"
subject_id = "Mouse-001"
date = "2025-11-12"
experimenter = "Experimenter Name"
description = "Session description"
sex = "M" | "F" | "U"
age = "P90"
genotype = "WT"

[bpod]
path = "path/to/bpod_001.mat"
order = "1"

[[TTLs]]
id = "ttl0"
description = "Camera TTL pulses"
paths = "path/to/ttl0.txt"

[[cameras]]
id = "cam0"
description = "Front camera"
paths = "path/to/cam0.avi"
order = "0"
ttl_id = "ttl0"
```

**Note:** Unlike the documentation's array notation, the actual implementation uses:

- `bpod.path` and `bpod.order` as single strings (not arrays)
- `TTLs.paths` and `cameras.paths` as single strings (not arrays)
- `order` fields are strings that get validated/converted to integers

## Validation Rules

### Strict Schema (FR-10)

- **No extra keys allowed** (`extra="forbid"` in Pydantic model_config)
- **All required keys must be present** (Pydantic validates on construction)
- **Enum values strictly validated** (custom pre-validation in load functions)

### Enum Constraints

```python
# Validated in _validate_config_enums()
VALID_TIMEBASE_SOURCES = {"nominal_rate", "ttl", "neuropixels"}
VALID_TIMEBASE_MAPPINGS = {"nearest", "linear"}
VALID_LOGGING_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

# timebase.source
assert config.timebase.source in VALID_TIMEBASE_SOURCES

# timebase.mapping
assert config.timebase.mapping in VALID_TIMEBASE_MAPPINGS

# logging.level
assert config.logging.level in VALID_LOGGING_LEVELS

# timebase.jitter_budget_s
assert config.timebase.jitter_budget_s >= 0.0
```

### Conditional Validation (FR-TB-2, FR-TB-3)

```python
# Validated in _validate_config_conditionals()

# IF source="ttl" THEN ttl_id REQUIRED
if config.timebase.source == "ttl":
    if not config.timebase.ttl_id:
        raise ValueError("timebase.ttl_id is required when timebase.source='ttl'")

# IF source="neuropixels" THEN neuropixels_stream REQUIRED
if config.timebase.source == "neuropixels":
    if not config.timebase.neuropixels_stream:
        raise ValueError("timebase.neuropixels_stream is required when timebase.source='neuropixels'")
```

### Camera TTL Reference Validation (FR-15)

```python
# Validated in _validate_camera_ttl_references()
# In Phase 0: structure validation only (no warnings emitted)
# In Phase 1+: warnings for unverifiable cameras

def _validate_camera_ttl_references(data: Dict[str, Any]) -> None:
    """Validate that camera ttl_id references exist in session TTLs.

    This is a warning condition, not a hard error in Phase 0.
    """
    ttls = data.get("TTLs", [])
    ttl_ids = {ttl["id"] for ttl in ttls}

    cameras = data.get("cameras", [])
    for camera in cameras:
        ttl_id = camera.get("ttl_id")
        if ttl_id and ttl_id not in ttl_ids:
            # In Phase 0, we just validate structure
            # In Phase 1, this would emit a warning
            pass
```

### Bpod Order Validation (A16)

**Note:** The current domain model has `bpod.path` and `bpod.order` as single strings, not arrays. If multiple Bpod files are needed, this validation would apply to an array structure.

```python
# Future validation for multiple Bpod files:
# Bpod files must have contiguous, unique orders starting from 1
orders = [f.order for f in session.bpod.files]
assert len(orders) == len(set(orders))  # No duplicates
assert orders == list(range(1, len(orders) + 1))  # Contiguous 1..N
```

## Error Handling

```python
from w2t_bkin.config import load_config, load_session
from pydantic import ValidationError

# Config loading errors
try:
    config = load_config(Path("config.toml"))
except FileNotFoundError as e:
    print(f"Config file not found: {e}")
except ValueError as e:
    print(f"Validation error (enum/conditional): {e}")
except ValidationError as e:
    print(f"Schema validation failed: {e}")
    for error in e.errors():
        print(f"  - {error['loc']}: {error['msg']}")

# Session loading errors
try:
    session = load_session(Path("session.toml"))
except FileNotFoundError as e:
    print(f"Session file not found: {e}")
except ValidationError as e:
    print(f"Schema validation failed: {e}")
```

### Common ValidationError Types

**Missing required field:**

```python
ValidationError: 1 validation error for Config
project.name
  Field required [type=missing, input_value={...}, input_type=dict]
```

**Extra field forbidden:**

```python
ValidationError: 1 validation error for Config
unknown_field
  Extra inputs are not permitted [type=extra_forbidden, input_value='value', input_type=str]
```

**Invalid enum value:**

```python
ValueError: Invalid timebase.source: invalid_source. Must be one of {'nominal_rate', 'ttl', 'neuropixels'}
```

**Conditional requirement not met:**

```python
ValueError: timebase.ttl_id is required when timebase.source='ttl'
```

## Testing

**Test file:** `tests/unit/test_config.py`

**Coverage:**

- ✅ Valid config loading (A13)
- ✅ Valid session loading (A14)
- ✅ Missing required keys detection (ValidationError)
- ✅ Extra keys rejection (ValidationError with extra_forbidden)
- ✅ Enum validation (ValueError from custom validators)
- ✅ Conditional validation (ttl_id, neuropixels_stream)
- ✅ Camera TTL reference validation (A15)
- ✅ Numeric validation (jitter_budget_s >= 0)
- ✅ Deterministic hash computation (A18)
- ✅ Hash stability across reloads

**Run tests:**

```bash
pytest tests/unit/test_config.py -v
```

## Usage Examples

### Load and validate configuration

```python
from w2t_bkin.config import load_config, load_session, compute_config_hash
from pathlib import Path

# Load files
config = load_config(Path("config.toml"))
session = load_session(Path("session.toml"))

# Compute hashes for provenance
config_hash = compute_config_hash(config)
session_hash = compute_session_hash(session)

print(f"Config: {config.project.name}")
print(f"Session: {session.session.id}")
print(f"Config hash: {config_hash}")
```

### Access nested configuration

```python
# Project info
project_name = config.project.name

# Paths
raw_root = Path(config.paths.raw_root)
output_root = Path(config.paths.output_root)

# Timebase settings
timebase_source = config.timebase.source
mapping_strategy = config.timebase.mapping
jitter_budget = config.timebase.jitter_budget_s

# Session metadata
session_id = session.session.id
cameras = session.cameras
ttls = session.ttls
```

### Validate timebase configuration

```python
from w2t_bkin.config import load_config

config = load_config(Path("config.toml"))

if config.timebase.source == "ttl":
    assert config.timebase.ttl_id is not None, "ttl_id required for TTL timebase"
    print(f"Using TTL timebase: {config.timebase.ttl_id}")
elif config.timebase.source == "neuropixels":
    assert config.timebase.neuropixels_stream is not None
    print(f"Using Neuropixels: {config.timebase.neuropixels_stream}")
else:
    print(f"Using nominal rate with offset={config.timebase.offset_s}s")
```

## Performance Notes

- **Config loading:** ~5-10ms for typical files
- **Session loading:** ~5-10ms for typical files
- **Hash computation:** ~1-2ms (JSON canonicalization + SHA256)

## Design Decisions

1. **Strict schemas:** Extra/missing keys rejected via Pydantic `extra="forbid"` to catch typos early
2. **Immutable models:** All Config/Session objects frozen (Pydantic `model_config = {"frozen": True}`)
3. **Deterministic hashing:** Uses `model_dump()` + sorted keys in `utils.compute_hash()` for reproducibility
4. **Enum validation:** Custom pre-validation functions (`_validate_config_enums`) prevent invalid config at load time
5. **Conditional validation:** Custom pre-validation functions (`_validate_config_conditionals`) enforce timebase-specific requirements
6. **TOML library:** Uses `tomllib` (Python 3.11+) or `tomli` backport for TOML parsing
7. **Separation of concerns:** Validation logic in config.py, domain models in domain.py
8. **Helpful error messages:** ValueError messages clearly state requirements and valid options

## Related Modules

- **domain:** Provides Pydantic models (Config, Session)
- **utils:** Used for hash computation and path operations
- **ingest:** Consumes Config + Session
- **sync:** Uses timebase configuration
- **All modules:** Reference config for settings

## Further Reading

- [Requirements: FR-10](../../requirements.md#functional-requirements-ears) - Configuration-driven requirement
- [Requirements: FR-TB-\*](../../requirements.md#timebase-strategy-config-driven) - Timebase configuration
- [Design: Build Order](../../design.md#build-order--dependencies) - Phase 0 foundation
- [Acceptance: A13, A14](../../requirements.md#acceptance-criteria) - Config/session validation
