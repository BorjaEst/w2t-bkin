"""Phase 6: Finalization."""

import logging
from typing import Optional

from rich.progress import Progress, TaskID

from ... import session, validate
from .... import utils
from ..models import PipelineContext

logger = logging.getLogger(__name__)


def run_phase_6(context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
    """Write NWB, validate, and create sidecars."""
    logger.info("Writing NWB file and creating sidecars...")

    total_steps = 3
    if progress and task_id is not None:
        progress.update(task_id, total=total_steps)

    _write_nwb(context, progress, task_id)
    _write_sidecars(context, progress, task_id)
    _validate_nwb(context, progress, task_id)


def _write_nwb(context: PipelineContext, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    # Prepare provenance
    provenance = {
        "pipeline": "w2t_bkin",
        "version": "v2",
        "config_hash": utils.compute_hash(context.config.model_dump(mode="json")),
        "alignment_stats": context.alignment_stats,
    }
    logger.debug(f"Provenance data prepared: {list(provenance.keys())}")

    # Write NWB file
    output_dir = context.config.paths.output_root / context.subject_id / context.session_id
    output_dir.mkdir(parents=True, exist_ok=True)
    nwb_path = output_dir / f"{context.session_id}.nwb"

    logger.debug(f"Writing NWB file to: {nwb_path}")
    session.write_nwb_file(context.nwbfile, nwb_path)
    context.nwb_path = nwb_path
    nwb_size_mb = nwb_path.stat().st_size / (1024 * 1024)
    logger.info(f"  NWB file: {nwb_path.name} ({nwb_size_mb:.1f} MB)")

    if progress and task_id is not None:
        progress.advance(task_id)


def _write_sidecars(context: PipelineContext, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    output_dir = context.config.paths.output_root / context.subject_id / context.session_id

    if context.alignment_stats:
        stats_path = output_dir / "alignment_stats.json"
        utils.write_json(context.alignment_stats, stats_path)
        logger.info(f"  Alignment stats: {stats_path.name}")
    else:
        logger.debug("Skipping alignment stats sidecar (empty stats)")

    provenance = {
        "pipeline": "w2t_bkin",
        "version": "v2",
        "config_hash": utils.compute_hash(context.config.model_dump(mode="json")),
        "alignment_stats": context.alignment_stats,
    }
    provenance_path = output_dir / "provenance.json"
    utils.write_json(provenance, provenance_path)
    logger.info(f"  Provenance: {provenance_path.name}")

    if progress and task_id is not None:
        progress.advance(task_id)


def _validate_nwb(context: PipelineContext, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    validation_results = None
    if not context.options.skip_nwb_validation:
        logger.info("Validating NWB file with nwbinspector...")
        validation_results = validate.validate_nwb_file(context.nwb_path)

        # Summary of validation
        if validation_results:
            critical = sum(1 for r in validation_results if r.get("severity") == "CRITICAL")
            errors = sum(1 for r in validation_results if r.get("severity") == "ERROR")
            warnings = sum(1 for r in validation_results if r.get("severity") == "WARNING")

            if critical > 0 or errors > 0:
                logger.warning(f"  Validation issues: {critical} critical, {errors} errors, {warnings} warnings")
                for r in validation_results:
                    if r.get("severity") in ["CRITICAL", "ERROR"]:
                        logger.debug(f"    {r.get('severity')}: {r.get('message')}")
            else:
                logger.info(f"  Validation passed ({warnings} warnings)")
                if warnings > 0:
                    logger.debug(f"    {warnings} warnings found (check validation report)")
        else:
            logger.info("  Validation passed (no issues)")
    else:
        logger.info("Skipping NWB validation (requested by options)")

    context.validation_results = validation_results

    if progress and task_id is not None:
        progress.advance(task_id)
