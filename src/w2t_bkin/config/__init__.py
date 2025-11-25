"""Configuration models and loading utilities for w2t_bkin.

This package provides Pydantic models for validating configuration files (config.toml)
and functions for loading and hashing configurations.

Models are defined in .models submodule and re-exported here for convenience.
Loading functions are defined in w2t_bkin.config_loader and re-exported here.
"""

# Config models - from config/models.py
from .models import (
    AcquisitionConfig,
    BpodConfig,
    Config,
    DLCConfig,
    FacemapConfig,
    LabelsConfig,
    LoggingConfig,
    NWBConfig,
    PathsConfig,
    ProjectConfig,
    QCConfig,
    SLEAPConfig,
    TimebaseConfig,
    TranscodeConfig,
    VerificationConfig,
    VideoConfig,
)


# Config loading functions - from w2t_bkin.config_loader
# Import at runtime to avoid circular import issues
def __getattr__(name):
    """Lazy import of config loading functions to avoid circular imports."""
    if name in ("load_config", "load_session", "compute_config_hash", "compute_session_hash"):
        from w2t_bkin import config_loader

        return getattr(config_loader, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Models
    "Config",
    "ProjectConfig",
    "PathsConfig",
    "TimebaseConfig",
    "AcquisitionConfig",
    "VerificationConfig",
    "BpodConfig",
    "VideoConfig",
    "TranscodeConfig",
    "NWBConfig",
    "QCConfig",
    "LoggingConfig",
    "LabelsConfig",
    "DLCConfig",
    "SLEAPConfig",
    "FacemapConfig",
    # Functions (lazy-loaded)
    "load_config",
    "load_session",
    "compute_config_hash",
    "compute_session_hash",
]
