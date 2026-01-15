"""Pose processing phase helpers."""

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple

from w2t_bkin.models import SessionInfo


@dataclass(frozen=True)
class PosePlan:
    """Pose processing execution plan (single source of truth).

    Resolved once from config+metadata, then used by both Phase 2 and Phase 3
    to prevent mode resolution drift.

    Attributes:
        dlc_mode: DLC effective mode ("off", "discover", "generate")
        sleap_mode: SLEAP effective mode ("off", "discover", "generate")
        ingestion_strategy: How to ingest poses ("metadata_stem", "artifact_list", "none")
        should_generate_dlc: Whether Phase 2 should run DLC generation
        should_generate_sleap: Whether Phase 2 should run SLEAP generation (future)
        has_pose_metadata: Whether metadata.pose section exists
        reasons: Human-readable decision reasoning for logging
    """

    dlc_mode: Literal["off", "discover", "generate"]
    sleap_mode: Literal["off", "discover", "generate"]
    ingestion_strategy: Literal["metadata_stem", "artifact_list", "none"]
    should_generate_dlc: bool
    should_generate_sleap: bool
    has_pose_metadata: bool
    reasons: Dict[str, str]


def resolve_pose_plan(session_info: SessionInfo) -> PosePlan:
    """Resolve pose processing execution plan.

    Single source of truth for mode resolution and ingestion strategy.
    Prevents drift between artifact generation (Phase 2) and ingestion (Phase 3).

    Args:
        session_info: Session configuration with metadata

    Returns:
        PosePlan with effective modes, ingestion strategy, and reasons
    """
    dlc_config = session_info.config.preprocessing.dlc
    sleap_config = session_info.config.preprocessing.sleap
    pose_metadata = session_info.metadata.get("pose", {})
    has_models = bool(pose_metadata.get("models", {}))
    has_cameras = bool(pose_metadata.get("cameras", {}))
    has_pose_section = bool(pose_metadata)

    # Resolve DLC effective mode
    dlc_mode = dlc_config.mode
    if not dlc_config.enabled:
        dlc_effective, dlc_reason = "off", "disabled in config"
    elif dlc_mode == "off":
        dlc_effective, dlc_reason = "off", "mode='off'"
    elif dlc_mode == "auto":
        if has_models:
            dlc_effective, dlc_reason = "generate", "mode='auto' → 'generate' (metadata.pose.models present)"
        else:
            dlc_effective, dlc_reason = "discover", "mode='auto' → 'discover' (no metadata.pose.models)"
    else:
        dlc_effective, dlc_reason = dlc_mode, f"mode='{dlc_mode}' (explicit)"

    # Resolve SLEAP effective mode
    sleap_mode = sleap_config.mode
    if not sleap_config.enabled:
        sleap_effective, sleap_reason = "off", "disabled in config"
    elif sleap_mode == "off":
        sleap_effective, sleap_reason = "off", "mode='off'"
    elif sleap_mode == "auto":
        sleap_effective, sleap_reason = "discover", "mode='auto' → 'discover' (generate not implemented)"
    elif sleap_mode == "generate":
        sleap_effective, sleap_reason = "discover", "mode='generate' → 'discover' (not implemented)"
    else:
        sleap_effective, sleap_reason = sleap_mode, f"mode='{sleap_mode}' (explicit)"

    # Determine ingestion strategy
    if dlc_effective == "off" and sleap_effective == "off":
        ingestion_strategy, strategy_reason = "none", "both DLC and SLEAP disabled"
    elif has_cameras and (dlc_effective == "discover" or sleap_effective == "discover"):
        ingestion_strategy, strategy_reason = "metadata_stem", "metadata.pose.cameras exists + discover mode active"
    elif dlc_effective == "generate" or sleap_effective == "generate":
        ingestion_strategy, strategy_reason = "artifact_list", "generation mode active (consume Phase 2 artifacts)"
    else:
        ingestion_strategy, strategy_reason = "artifact_list", "discover mode without metadata.pose.cameras (legacy path)"

    plan = PosePlan(
        dlc_mode=dlc_effective,
        sleap_mode=sleap_effective,
        ingestion_strategy=ingestion_strategy,
        should_generate_dlc=(dlc_effective == "generate"),
        should_generate_sleap=(sleap_effective == "generate"),
        has_pose_metadata=has_pose_section,
        reasons={"dlc": dlc_reason, "sleap": sleap_reason, "ingestion_strategy": strategy_reason},
    )

    return plan
