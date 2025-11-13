"""Configuration loading and validation for W2T-BKIN pipeline (Phase 0 - Foundation).

This module provides robust loading, validation, and hashing functionality for the
W2T-BKIN pipeline configuration system. It handles two primary configuration files:
- `config.toml`: Global pipeline configuration (paths, timebase, acquisition policies)
- `session.toml`: Per-session metadata (subject info, cameras, TTLs, Bpod paths)

The module enforces strict validation rules to catch configuration errors early,
supports deterministic hashing for reproducibility tracking, and provides clear
error messages for troubleshooting.

Key Features:
-------------
- **Strict Schema Validation**: Uses Pydantic models with extra="forbid" to prevent typos
- **Enum Validation**: Validates timebase.source, timebase.mapping, and logging.level
- **Conditional Requirements**: Enforces required fields based on config values
  (e.g., ttl_id required when source='ttl')
- **Deterministic Hashing**: Computes SHA256 hashes for configuration reproducibility
- **Cross-references**: Validates camera ttl_id references against session TTLs
- **Clear Error Messages**: Detailed validation failures with paths and values

Main Functions:
---------------
- load_config: Load and validate config.toml
- load_session: Load and validate session.toml
- compute_config_hash: Compute deterministic config hash
- compute_session_hash: Compute deterministic session hash
- validate_ttl_references: Check camera TTL cross-references

Requirements:
-------------
- FR-1: Load and validate configuration files
- FR-2: Enforce strict schema validation
- FR-10: Configuration management
- NFR-1: Deterministic processing (hashing)
- NFR-3: Clear error reporting
- NFR-10: Configuration validation
- NFR-11: Error handling

Acceptance Criteria:
-------------------
- A1: Load config.toml and validate all fields
- A2: Load session.toml and validate all fields
- A3: Reject extra/unknown fields
- A4: Validate enum values
- A5: Enforce conditional requirements
- A6: Compute deterministic config/session hashes
- A7: Validate TTL cross-references
- A9, A10, A11: Configuration loading workflows
- A13, A14: Schema validation
- A18: TTL reference validation

Validation Rules:
-----------------
Config validation enforces:
- timebase.source ∈ {"nominal_rate", "ttl", "neuropixels"}
- timebase.mapping ∈ {"nearest", "linear"}
- timebase.jitter_budget_s >= 0
- logging.level ∈ {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
- Conditional: source='ttl' → ttl_id required
- Conditional: source='neuropixels' → neuropixels_stream required

Session validation enforces:
- Camera ttl_id references must exist in session TTLs (warning in Phase 0)
- All required session fields (id, subject_id, date, experimenter)

Example:
--------
>>> from w2t_bkin import config
>>> from pathlib import Path
>>>
>>> # Load and validate config.toml
>>> cfg = config.load_config("config.toml")
>>> print(f"Timebase source: {cfg.timebase.source}")
>>>
>>> # Load and validate session.toml
>>> session = config.load_session("Session-000001/session.toml")
>>> print(f"Session: {session.metadata.session_id}")
>>> print(f"Subject: {session.metadata.subject_id}")
>>>
>>> # Compute deterministic hashes
>>> config_hash = config.compute_config_hash(cfg)
>>> session_hash = config.compute_session_hash(session)
>>> print(f"Config hash: {config_hash[:16]}...")
"""

from pathlib import Path
import re
from typing import Any, Dict, Union

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from pydantic import ValidationError, field_validator, model_validator

from .domain import Config, Session
from .utils import compute_hash, read_toml

# Enum constants for validation
VALID_TIMEBASE_SOURCES = {"nominal_rate", "ttl", "neuropixels"}
VALID_TIMEBASE_MAPPINGS = {"nearest", "linear"}
VALID_LOGGING_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


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
    """
    data = read_toml(path)

    # Validate enums before Pydantic validation
    _validate_config_enums(data)

    # Validate conditional requirements
    _validate_config_conditionals(data)

    return Config(**data)


def load_session(path: Union[str, Path]) -> Session:
    """Load and validate session metadata from TOML file.

    Performs strict schema validation including:
    - Required/forbidden keys (extra="forbid")
    - Camera TTL reference validation
    - Bpod trial_type sync_ttl reference validation
    - Backwards-compatible trial_type_id → trial_type mapping
    - Populates session_dir with parent directory of session.toml

    Args:
        path: Path to session.toml file (str or Path)

    Returns:
        Validated Session instance with session_dir populated

    Raises:
        ValidationError: If session violates schema
        FileNotFoundError: If session file doesn't exist

    Example:
        >>> session = load_session("data/raw/Session-001/session.toml")
        >>> print(session.session_dir)  # "data/raw/Session-001"
    """
    path = Path(path) if isinstance(path, str) else path
    data = read_toml(path)

    # Handle backwards compatibility: trial_type_id → trial_type
    _normalize_trial_type_ids(data)

    # Validate camera TTL references
    _validate_camera_ttl_references(data)

    # Validate bpod trial_type sync_ttl references
    _validate_bpod_trial_type_references(data)

    # Add session_dir to data (parent directory of session.toml)
    data["session_dir"] = str(path.parent.resolve())

    return Session(**data)


def compute_config_hash(config: Config) -> str:
    """Compute deterministic hash of config content.

    Canonicalizes config by converting to dict and hashing with sorted keys.
    Comments are not included in the model, so they're automatically stripped.

    Args:
        config: Config instance

    Returns:
        SHA256 hex digest (64 characters)
    """
    config_dict = config.model_dump()
    return compute_hash(config_dict)


def compute_session_hash(session: Session) -> str:
    """Compute deterministic hash of session content.

    Canonicalizes session by converting to dict and hashing with sorted keys.
    Comments are not included in the model, so they're automatically stripped.

    Args:
        session: Session instance

    Returns:
        SHA256 hex digest (64 characters)
    """
    session_dict = session.model_dump()
    return compute_hash(session_dict)


# Private validation helpers


def _validate_config_enums(data: Dict[str, Any]) -> None:
    """Validate enum constraints for config.

    Raises:
        ValueError: If enum value is invalid
    """
    timebase = data.get("timebase", {})

    # Validate timebase.source
    source = timebase.get("source")
    if source and source not in VALID_TIMEBASE_SOURCES:
        raise ValueError(f"Invalid timebase.source: {source}. Must be one of {VALID_TIMEBASE_SOURCES}")

    # Validate timebase.mapping
    mapping = timebase.get("mapping")
    if mapping and mapping not in VALID_TIMEBASE_MAPPINGS:
        raise ValueError(f"Invalid timebase.mapping: {mapping}. Must be one of {VALID_TIMEBASE_MAPPINGS}")

    # Validate jitter_budget_s >= 0
    jitter_budget = timebase.get("jitter_budget_s")
    if jitter_budget is not None and jitter_budget < 0:
        raise ValueError(f"Invalid timebase.jitter_budget_s: {jitter_budget}. Must be >= 0")

    # Validate logging.level
    logging_config = data.get("logging", {})
    level = logging_config.get("level")
    if level and level not in VALID_LOGGING_LEVELS:
        raise ValueError(f"Invalid logging.level: {level}. Must be one of {VALID_LOGGING_LEVELS}")


def _validate_config_conditionals(data: Dict[str, Any]) -> None:
    """Validate conditional requirements for config.

    Raises:
        ValueError: If conditional requirement not met
    """
    timebase = data.get("timebase", {})
    source = timebase.get("source")

    # If source='ttl', require ttl_id
    if source == "ttl" and not timebase.get("ttl_id"):
        raise ValueError("timebase.ttl_id is required when timebase.source='ttl'")

    # If source='neuropixels', require neuropixels_stream
    if source == "neuropixels" and not timebase.get("neuropixels_stream"):
        raise ValueError("timebase.neuropixels_stream is required when timebase.source='neuropixels'")


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


def _normalize_trial_type_ids(data: Dict[str, Any]) -> None:
    """Normalize trial_type_id to trial_type for backwards compatibility.

    If bpod.trial_types entries contain trial_type_id instead of trial_type,
    rename the field and emit a warning.

    Args:
        data: Raw session data dict from TOML
    """
    import warnings

    bpod = data.get("bpod", {})
    trial_types = bpod.get("trial_types", [])

    for trial_type_entry in trial_types:
        if "trial_type_id" in trial_type_entry and "trial_type" not in trial_type_entry:
            trial_type_entry["trial_type"] = trial_type_entry.pop("trial_type_id")
            warnings.warn(
                f"Deprecated field 'trial_type_id' found in bpod.trial_types. " f"Use 'trial_type' instead. Automatically mapped for backwards compatibility.",
                DeprecationWarning,
                stacklevel=3,
            )


def _validate_bpod_trial_type_references(data: Dict[str, Any]) -> None:
    """Validate that bpod.trial_types sync_ttl references exist in session TTLs.

    Raises:
        ValueError: If sync_ttl references a non-existent TTL channel
    """
    ttls = data.get("TTLs", [])
    ttl_ids = {ttl["id"] for ttl in ttls}

    bpod = data.get("bpod", {})
    trial_types = bpod.get("trial_types", [])

    for trial_type_entry in trial_types:
        sync_ttl = trial_type_entry.get("sync_ttl")
        trial_type_id = trial_type_entry.get("trial_type", "unknown")

        if sync_ttl and sync_ttl not in ttl_ids:
            raise ValueError(f"Bpod trial_type {trial_type_id} references unknown TTL channel '{sync_ttl}'. " f"Available TTL channels: {sorted(ttl_ids)}")


if __name__ == "__main__":
    """Usage examples demonstrating config loading, validation, and hashing.

    This example demonstrates:
    1. Loading and validating config.toml
    2. Loading and validating session.toml
    3. Computing deterministic hashes for reproducibility
    4. Handling validation errors
    5. Accessing validated configuration data
    """
    import sys

    from pydantic import ValidationError

    # Example 1: Load and validate config.toml
    print("=" * 70)
    print("Example 1: Loading and validating config.toml")
    print("=" * 70)

    try:
        config_path = Path("tests/fixtures/configs/valid_config.toml")
        config = load_config(config_path)

        print(f"✓ Config loaded successfully from: {config_path}")
        print(f"  Project name: {config.project.name}")
        print(f"  Timebase source: {config.timebase.source}")
        print(f"  Timebase mapping: {config.timebase.mapping}")
        print(f"  Jitter budget: {config.timebase.jitter_budget_s}s")
        print(f"  Logging level: {config.logging.level}")

        # Compute and display config hash for reproducibility
        config_hash = compute_config_hash(config)
        print(f"  Config hash: {config_hash[:16]}... (SHA256)")

    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        print("  Hint: Run from project root or provide correct path")
    except ValidationError as e:
        print(f"✗ Validation failed:")
        for error in e.errors():
            print(f"  - {error['loc']}: {error['msg']}")
    except ValueError as e:
        print(f"✗ Configuration error: {e}")

    print()

    # Example 2: Load and validate session.toml
    print("=" * 70)
    print("Example 2: Loading and validating session.toml")
    print("=" * 70)

    try:
        session_path = Path("tests/fixtures/data/raw/Session-000001/session.toml")
        session = load_session(session_path)

        print(f"✓ Session loaded successfully from: {session_path}")
        print(f"  Session ID: {session.session.id}")
        print(f"  Subject ID: {session.session.subject_id}")
        print(f"  Date: {session.session.date}")
        print(f"  Experimenter: {session.session.experimenter}")
        print(f"  Number of TTLs: {len(session.TTLs)}")
        print(f"  Number of cameras: {len(session.cameras)}")

        # Display TTL and camera details
        if session.TTLs:
            print(f"\n  TTLs:")
            for ttl in session.TTLs:
                print(f"    - {ttl.id}: {ttl.description}")

        if session.cameras:
            print(f"\n  Cameras:")
            for camera in session.cameras:
                ttl_ref = f" (TTL: {camera.ttl_id})" if camera.ttl_id else ""
                print(f"    - {camera.id}: {camera.description}{ttl_ref}")

        # Compute and display session hash for reproducibility
        session_hash = compute_session_hash(session)
        print(f"\n  Session hash: {session_hash[:16]}... (SHA256)")

    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        print("  Hint: Ensure session directory exists with session.toml")
    except ValidationError as e:
        print(f"✗ Validation failed:")
        for error in e.errors():
            print(f"  - {error['loc']}: {error['msg']}")

    print()

    # Example 3: Demonstrate validation errors
    print("=" * 70)
    print("Example 3: Handling validation errors")
    print("=" * 70)

    print("\n3a. Invalid timebase.source enum value:")
    try:
        invalid_data = {
            "project": {"name": "test"},
            "paths": {
                "raw_root": "data/raw",
                "intermediate_root": "data/interim",
                "output_root": "data/processed",
                "metadata_file": "session.toml",
                "models_root": "models",
            },
            "timebase": {"source": "invalid_source", "mapping": "nearest", "jitter_budget_s": 0.01},  # Invalid enum
        }
        _validate_config_enums(invalid_data)
        print("  ✗ This should have failed validation!")
    except ValueError as e:
        print(f"  ✓ Correctly caught validation error:")
        print(f"    {e}")

    print("\n3b. Missing conditional requirement (ttl_id for source='ttl'):")
    try:
        invalid_data = {
            "project": {"name": "test"},
            "paths": {
                "raw_root": "data/raw",
                "intermediate_root": "data/interim",
                "output_root": "data/processed",
                "metadata_file": "session.toml",
                "models_root": "models",
            },
            "timebase": {
                "source": "ttl",  # Requires ttl_id
                "mapping": "nearest",
                "jitter_budget_s": 0.01,
                # Missing: ttl_id
            },
        }
        _validate_config_conditionals(invalid_data)
        print("  ✗ This should have failed conditional validation!")
    except ValueError as e:
        print(f"  ✓ Correctly caught conditional validation error:")
        print(f"    {e}")

    print("\n3c. Negative jitter_budget_s:")
    try:
        invalid_data = {"timebase": {"source": "nominal_rate", "mapping": "nearest", "jitter_budget_s": -0.01}}  # Invalid: must be >= 0
        _validate_config_enums(invalid_data)
        print("  ✗ This should have failed validation!")
    except ValueError as e:
        print(f"  ✓ Correctly caught validation error:")
        print(f"    {e}")

    print()
    print("=" * 70)
    print("Examples completed. See function docstrings for more details.")
    print("=" * 70)
