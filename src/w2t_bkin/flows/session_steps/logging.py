"""File logging utilities for session flows."""

from contextlib import contextmanager
import logging
from pathlib import Path

from prefect.runtime import flow_run as flow_run_runtime

from w2t_bkin import utils


@contextmanager
def flow_run_file_logger(output_dir: Path, run_logger):
    """Context manager for flow-run-isolated file logging.

    Sets up a file handler bound to the current Prefect flow run to prevent
    cross-session contamination in concurrent execution.

    Args:
        output_dir: Directory to write pipeline.log
        run_logger: Prefect flow logger for status messages

    Yields:
        None (side effect: attaches/detaches file handler)
    """
    log_file = output_dir / "pipeline.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)

    handler_attached = False

    try:
        # Bind handler to current Prefect flow-run context
        flow_run_id = flow_run_runtime.id
        if flow_run_id is None:
            raise RuntimeError("No Prefect flow run context available")

        flow_run_filter = utils.PrefectFlowRunFilter(flow_run_id)
        file_handler.addFilter(flow_run_filter)
        logging.getLogger("w2t_bkin").addHandler(file_handler)
        handler_attached = True
        run_logger.info(f"File logging enabled: {log_file} (bound to flow-run {flow_run_id})")

        yield

    except Exception as e:
        # Skip file logging if no Prefect context isolation available
        run_logger.warning(f"File logging disabled - no Prefect context isolation: {e}")
        if not handler_attached:
            file_handler.close()
        raise

    finally:
        # Clean up file handler to prevent cross-session contamination
        if handler_attached:
            logging.getLogger("w2t_bkin").removeHandler(file_handler)
            file_handler.close()
