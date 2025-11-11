"""Configuration loading and validation for W2T-BKIN pipeline (Phase 0).

Loads and validates config.toml and session.toml files with strict schema enforcement,
enum validation, conditional requirements, and deterministic hashing.

Requirements: FR-10, NFR-10, NFR-11
Acceptance: A9, A10, A11, A13, A14, A18
"""

from pathlib import Path
import re
from typing import Any, Dict

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from pydantic import ValidationError, field_validator, model_validator

from .domain import Config, Session
from .utils import compute_hash

# Enum constants for validation
VALID_TIMEBASE_SOURCES = {"nominal_rate", "ttl", "neuropixels"}
VALID_TIMEBASE_MAPPINGS = {"nearest", "linear"}
VALID_LOGGING_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def load_config(path: Path) -> Config:
    """Load and validate configuration from TOML file.

    Performs strict schema validation including:
    - Required/forbidden keys (extra="forbid")
    - Enum validation for timebase.source, timebase.mapping, logging.level
    - Numeric validation for jitter_budget_s >= 0
    - Conditional validation for ttl_id and neuropixels_stream

    Args:
        path: Path to config.toml file

    Returns:
        Validated Config instance

    Raises:
        ValidationError: If config violates schema
        FileNotFoundError: If config file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    # Validate enums before Pydantic validation
    _validate_config_enums(data)

    # Validate conditional requirements
    _validate_config_conditionals(data)

    return Config(**data)


def load_session(path: Path) -> Session:
    """Load and validate session metadata from TOML file.

    Performs strict schema validation including:
    - Required/forbidden keys (extra="forbid")
    - Camera TTL reference validation

    Args:
        path: Path to session.toml file

    Returns:
        Validated Session instance

    Raises:
        ValidationError: If session violates schema
        FileNotFoundError: If session file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"Session file not found: {path}")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    # Validate camera TTL references
    _validate_camera_ttl_references(data)

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
