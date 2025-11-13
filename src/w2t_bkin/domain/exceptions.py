"""Exception hierarchy for W2T-BKIN pipeline.

This module defines a structured exception hierarchy for all pipeline stages.
Each exception includes structured fields (error_code, message, context, hint, stage)
to support detailed error reporting and debugging.

Exception Hierarchy:
-------------------
W2TError (base)
├── ConfigError
│   ├── ConfigMissingKeyError
│   ├── ConfigExtraKeyError
│   └── ConfigValidationError
├── SessionError
│   ├── SessionMissingKeyError
│   ├── SessionExtraKeyError
│   └── SessionValidationError
├── IngestError
│   ├── FileNotFoundError
│   └── VerificationError
│       └── MismatchExceedsToleranceError
├── SyncError
│   ├── TimebaseProviderError
│   ├── JitterExceedsBudgetError
│   └── AlignmentError
├── EventsError
│   └── BpodParseError
├── TranscodeError
├── PoseError
├── FacemapError
├── NWBError
│   └── ExternalToolError
├── ValidationError (nwbinspector)
└── QCError

Design Principles:
-----------------
1. **Structured Context**: All exceptions carry machine-readable context
2. **User Hints**: Actionable suggestions for resolution
3. **Stage Tracking**: Clear indication of where error occurred
4. **Taxonomy Codes**: Stable error codes for programmatic handling

Requirements:
-------------
- Design: Error Taxonomy section
- NFR-3: Observability through structured error reporting

Example:
--------
>>> from w2t_bkin.domain.exceptions import MismatchExceedsToleranceError
>>>
>>> try:
...     raise MismatchExceedsToleranceError(
...         camera_id="cam0",
...         expected=8580,
...         actual=8578,
...         tolerance=1
...     )
... except W2TError as e:
...     print(e.error_code)  # MISMATCH_EXCEEDS_TOLERANCE
...     print(e.context)     # {'camera_id': 'cam0', ...}
...     print(e.hint)        # "Check TTL files for gaps..."
"""

from typing import Any, Dict, Optional


class W2TError(Exception):
    """Base exception for all W2T-BKIN pipeline errors.

    All pipeline exceptions inherit from this class and include structured
    metadata for debugging and reporting.

    Attributes:
        error_code: Stable error code for programmatic handling
        message: Human-readable error description
        context: Machine-readable error context (dict)
        hint: Actionable suggestion for resolution
        stage: Pipeline stage where error occurred
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        hint: Optional[str] = None,
        stage: Optional[str] = None,
    ):
        self.error_code = error_code
        self.message = message
        self.context = context or {}
        self.hint = hint
        self.stage = stage
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format structured error message."""
        parts = [f"[{self.error_code}]", self.message]
        if self.stage:
            parts.insert(1, f"(stage: {self.stage})")
        if self.context:
            parts.append(f"Context: {self.context}")
        if self.hint:
            parts.append(f"Hint: {self.hint}")
        return " ".join(parts)


# Configuration Errors


class ConfigError(W2TError):
    """Configuration-related errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None, hint: Optional[str] = None):
        super().__init__(error_code="CONFIG_ERROR", message=message, context=context, hint=hint, stage="config")


class ConfigMissingKeyError(ConfigError):
    """Required configuration key is missing."""

    def __init__(self, key: str, file_path: str):
        super().__init__(
            message=f"Required configuration key missing: {key}",
            context={"key": key, "file_path": file_path},
            hint=f"Add '{key}' to {file_path}",
        )
        self.error_code = "CONFIG_MISSING_KEY"


class ConfigExtraKeyError(ConfigError):
    """Unknown configuration key detected."""

    def __init__(self, key: str, file_path: str, valid_keys: list):
        super().__init__(
            message=f"Unknown configuration key: {key}",
            context={"key": key, "file_path": file_path, "valid_keys": valid_keys},
            hint=f"Remove '{key}' or check for typos. Valid keys: {', '.join(valid_keys)}",
        )
        self.error_code = "CONFIG_EXTRA_KEY"


class ConfigValidationError(ConfigError):
    """Configuration value validation failed."""

    def __init__(self, key: str, value: Any, expected: str):
        super().__init__(
            message=f"Invalid value for '{key}': {value}",
            context={"key": key, "value": value, "expected": expected},
            hint=f"Expected {expected}",
        )
        self.error_code = "CONFIG_VALIDATION_ERROR"


# Session Errors


class SessionError(W2TError):
    """Session configuration errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None, hint: Optional[str] = None):
        super().__init__(error_code="SESSION_ERROR", message=message, context=context, hint=hint, stage="session")


class SessionMissingKeyError(SessionError):
    """Required session key is missing."""

    def __init__(self, key: str, file_path: str):
        super().__init__(
            message=f"Required session key missing: {key}",
            context={"key": key, "file_path": file_path},
            hint=f"Add '{key}' to {file_path}",
        )
        self.error_code = "SESSION_MISSING_KEY"


class SessionExtraKeyError(SessionError):
    """Unknown session key detected."""

    def __init__(self, key: str, file_path: str, valid_keys: list):
        super().__init__(
            message=f"Unknown session key: {key}",
            context={"key": key, "file_path": file_path, "valid_keys": valid_keys},
            hint=f"Remove '{key}' or check for typos. Valid keys: {', '.join(valid_keys)}",
        )
        self.error_code = "SESSION_EXTRA_KEY"


class SessionValidationError(SessionError):
    """Session value validation failed."""

    def __init__(self, key: str, value: Any, expected: str):
        super().__init__(
            message=f"Invalid value for '{key}': {value}",
            context={"key": key, "value": value, "expected": expected},
            hint=f"Expected {expected}",
        )
        self.error_code = "SESSION_VALIDATION_ERROR"


# Ingest Errors


class IngestError(W2TError):
    """File discovery and ingestion errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None, hint: Optional[str] = None):
        super().__init__(error_code="INGEST_ERROR", message=message, context=context, hint=hint, stage="ingest")


class FileNotFoundError(IngestError):
    """Required file not found during discovery."""

    def __init__(self, pattern: str, search_path: str):
        super().__init__(
            message=f"No files matching pattern: {pattern}",
            context={"pattern": pattern, "search_path": search_path},
            hint=f"Check that files exist in {search_path} and pattern is correct",
        )
        self.error_code = "FILE_NOT_FOUND"


class VerificationError(IngestError):
    """Frame/TTL verification errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None, hint: Optional[str] = None):
        super().__init__(message=message, context=context, hint=hint)
        self.error_code = "VERIFICATION_ERROR"


class MismatchExceedsToleranceError(VerificationError):
    """Frame/TTL mismatch exceeds configured tolerance."""

    def __init__(self, camera_id: str, frame_count: int, ttl_count: int, mismatch: int, tolerance: int):
        super().__init__(
            message=f"Camera '{camera_id}' mismatch ({mismatch} frames) exceeds tolerance ({tolerance})",
            context={
                "camera_id": camera_id,
                "frame_count": frame_count,
                "ttl_count": ttl_count,
                "mismatch": mismatch,
                "tolerance": tolerance,
            },
            hint="Check TTL files for missing pulses or video file corruption. " "Increase verification.mismatch_tolerance_frames if acceptable.",
        )
        self.error_code = "MISMATCH_EXCEEDS_TOLERANCE"


class CameraUnverifiableError(IngestError):
    """Camera cannot be verified (missing TTL reference)."""

    def __init__(self, camera_id: str, ttl_id: str):
        super().__init__(
            message=f"Camera '{camera_id}' references unknown TTL '{ttl_id}'",
            context={"camera_id": camera_id, "ttl_id": ttl_id},
            hint=f"Add TTL entry for '{ttl_id}' to session.toml or correct camera.ttl_id",
        )
        self.error_code = "CAMERA_UNVERIFIABLE"


# Sync Errors


class SyncError(W2TError):
    """Timebase synchronization errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None, hint: Optional[str] = None):
        super().__init__(error_code="SYNC_ERROR", message=message, context=context, hint=hint, stage="sync")


class TimebaseProviderError(SyncError):
    """Timebase provider initialization failed."""

    def __init__(self, source: str, reason: str):
        super().__init__(
            message=f"Failed to initialize timebase provider '{source}': {reason}",
            context={"source": source, "reason": reason},
            hint="Check that timebase source files exist and are readable",
        )
        self.error_code = "TIMEBASE_PROVIDER_ERROR"


class JitterExceedsBudgetError(SyncError):
    """Alignment jitter exceeds configured budget."""

    def __init__(self, max_jitter_s: float, p95_jitter_s: float, budget_s: float):
        super().__init__(
            message=f"Alignment jitter (max={max_jitter_s:.6f}s, p95={p95_jitter_s:.6f}s) exceeds budget ({budget_s}s)",
            context={"max_jitter_s": max_jitter_s, "p95_jitter_s": p95_jitter_s, "budget_s": budget_s},
            hint="Increase timebase.jitter_budget_s or investigate timing quality. " "Check TTL pulse spacing and video frame rate stability.",
        )
        self.error_code = "JITTER_EXCEEDS_BUDGET"


class AlignmentError(SyncError):
    """Sample alignment failed."""

    def __init__(self, reason: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message=f"Sample alignment failed: {reason}", context=context, hint="Check timebase configuration and data quality")
        self.error_code = "ALIGNMENT_ERROR"


# Events Errors


class EventsError(W2TError):
    """Behavioral events parsing errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None, hint: Optional[str] = None):
        super().__init__(error_code="EVENTS_ERROR", message=message, context=context, hint=hint, stage="events")


class BpodParseError(EventsError):
    """Bpod MATLAB file parsing failed."""

    def __init__(self, reason: str, file_path: Optional[str] = None):
        context = {"reason": reason}
        if file_path:
            context["file_path"] = file_path
        super().__init__(
            message=f"Failed to parse Bpod file: {reason}",
            context=context,
            hint="Check that file is a valid Bpod .mat file and not corrupted",
        )
        self.error_code = "BPOD_PARSE_ERROR"


class BpodValidationError(EventsError):
    """Bpod file or data validation failed."""

    def __init__(self, reason: str, file_path: Optional[str] = None):
        context = {"reason": reason}
        if file_path:
            context["file_path"] = file_path
        super().__init__(
            message=f"Bpod validation failed: {reason}",
            context=context,
            hint="Check file path, size, extension, and data structure",
        )
        self.error_code = "BPOD_VALIDATION_ERROR"


# Transcode Errors


class TranscodeError(W2TError):
    """Video transcoding errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None, hint: Optional[str] = None):
        super().__init__(error_code="TRANSCODE_ERROR", message=message, context=context, hint=hint, stage="transcode")


# Pose Errors


class PoseError(W2TError):
    """Pose estimation errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None, hint: Optional[str] = None):
        super().__init__(error_code="POSE_ERROR", message=message, context=context, hint=hint, stage="pose")


# Facemap Errors


class FacemapError(W2TError):
    """Facemap processing errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None, hint: Optional[str] = None):
        super().__init__(error_code="FACEMAP_ERROR", message=message, context=context, hint=hint, stage="facemap")


# NWB Errors


class NWBError(W2TError):
    """NWB assembly errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None, hint: Optional[str] = None):
        super().__init__(error_code="NWB_ERROR", message=message, context=context, hint=hint, stage="nwb")


class ExternalToolError(NWBError):
    """External tool execution failed."""

    def __init__(self, tool: str, command: str, return_code: int, stderr: str):
        super().__init__(
            message=f"External tool '{tool}' failed with code {return_code}",
            context={"tool": tool, "command": command, "return_code": return_code, "stderr": stderr},
            hint=f"Check that {tool} is installed and accessible in PATH",
        )
        self.error_code = "EXTERNAL_TOOL_ERROR"


# Validation Errors


class ValidationError(W2TError):
    """NWB validation errors (nwbinspector)."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None, hint: Optional[str] = None):
        super().__init__(error_code="VALIDATION_ERROR", message=message, context=context, hint=hint, stage="validation")


# QC Errors


class QCError(W2TError):
    """QC report generation errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None, hint: Optional[str] = None):
        super().__init__(error_code="QC_ERROR", message=message, context=context, hint=hint, stage="qc")
