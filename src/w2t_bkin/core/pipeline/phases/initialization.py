"""Phase 0: Initialization."""

import logging
from typing import Optional

from rich.progress import Progress, TaskID

from .... import config as config_pkg
from .... import utils
from ..models import PipelineContext

logger = logging.getLogger(__name__)


def run_phase_0(context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
    """Load configuration and create NWBFile."""
    logger.info("Loading configuration and creating NWBFile...")
    logger.debug(f"Config path: {context.config_path}")

    # Load configuration (paths now auto-resolved by Pydantic validators)
    context.config = config_pkg.load_config(context.config_path)

    # Apply CLI overrides
    if context.options.verification_tolerance is not None:
        context.config.verification.mismatch_tolerance_frames = context.options.verification_tolerance
        logger.info(f"  Overriding verification tolerance: {context.options.verification_tolerance}")

    if context.options.warn_on_mismatch is not None:
        context.config.verification.warn_on_mismatch = context.options.warn_on_mismatch
        logger.info(f"  Overriding warn_on_mismatch: {context.options.warn_on_mismatch}")

    logger.info(f"  Project: {context.config.project.name}")
    logger.info(f"  Raw root: {context.config.paths.raw_root}")
    logger.info(f"  Interim root: {context.config.paths.intermediate_root}")
    logger.info(f"  Output root: {context.config.paths.output_root}")
    logger.info(f"  Preprocessing: DLC={context.config.preprocessing.dlc.enabled}, force_rerun={context.config.preprocessing.force_rerun}")
    logger.debug(f"  Full config: {context.config.model_dump_json(indent=2)}")

    # Load metadata and create NWBFile
    context.metadata, context.nwbfile = utils.load_session_metadata_and_nwb(
        config=context.config,
        subject_id=context.subject_id,
        session_id=context.session_id,
    )
    context.session_dir = context.config.paths.raw_root / context.subject_id / context.session_id
    logger.debug(f"  Session directory: {context.session_dir}")

    logger.info(f"  NWBFile: identifier='{context.nwbfile.identifier}'")
    if context.nwbfile.subject:
        logger.info(f"  Subject: {context.nwbfile.subject.subject_id}")
        logger.debug(f"  Subject metadata: {context.nwbfile.subject}")
