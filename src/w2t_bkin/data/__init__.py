"""Data management module for W2T-BKIN pipeline."""

from w2t_bkin.data.manager import (
    ExperimentConfig,
    FilePattern,
    SessionConfig,
    SubjectConfig,
    ValidationResult,
    add_session,
    add_subject,
    detect_file_patterns,
    ensure_parent_dir,
    import_raw_data,
    init_experiment,
    read_toml,
    validate_experiment_structure,
    validate_toml_syntax,
    write_toml,
)

__all__ = [
    # Configuration dataclasses
    "ExperimentConfig",
    "SubjectConfig",
    "SessionConfig",
    "FilePattern",
    "ValidationResult",
    # Experiment management
    "init_experiment",
    "add_subject",
    "add_session",
    "import_raw_data",
    "detect_file_patterns",
    "validate_experiment_structure",
    # File system utilities
    "ensure_parent_dir",
    # TOML utilities
    "read_toml",
    "write_toml",
    "validate_toml_syntax",
]
