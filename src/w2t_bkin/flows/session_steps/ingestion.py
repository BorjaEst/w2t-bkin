"""Ingestion parameter resolution helpers."""

from typing import Dict, Tuple

from w2t_bkin.models import SessionInfo


def resolve_bpod_ingest_params(session_info: SessionInfo) -> Tuple[str, str, bool]:
    """Resolve Bpod ingestion parameters from metadata and config.

    Prefers per-session metadata configuration, falls back to deployment config.

    Args:
        session_info: Session configuration

    Returns:
        Tuple of (pattern, order, continuous_time)
    """
    bpod_meta = session_info.metadata.get("bpod") or {}
    pattern = bpod_meta.get("path") or bpod_meta.get("paths") or bpod_meta.get("pattern") or session_info.config.bpod.pattern
    order = bpod_meta.get("order") or session_info.config.bpod.order
    continuous_time = bpod_meta.get("continuous_time", session_info.config.bpod.continuous_time)

    return pattern, order, continuous_time


def resolve_ttl_patterns(session_info: SessionInfo) -> Dict[str, str]:
    """Resolve TTL patterns from metadata.

    Args:
        session_info: Session configuration

    Returns:
        Dictionary mapping ttl_id to file pattern
    """
    ttl_configs = session_info.metadata.get("TTLs", [])
    return {ttl["id"]: ttl["paths"] for ttl in ttl_configs}
