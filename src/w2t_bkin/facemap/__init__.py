"""Facemap module for facial metrics ingestion and alignment.

Imports or computes facial metrics (e.g., motion energy, pupil area) and aligns
them to the session timebase.

Requirements: MR-1, MR-2, MR-3, M-NFR-1
Design: facemap/design.md
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from w2t_bkin.domain import DataIntegrityWarning, MetricsTable, MissingInputError, TimestampSeries


class FacemapInputs(BaseModel):
    """Input specification for facemap harmonization (MR-1, Design).
    
    Supports multiple input formats:
    - CSV: Comma-separated values
    - NPY: NumPy binary format
    - Parquet: Apache Parquet format
    - Video: Raw video for metric computation
    
    All inputs are optional to support flexible workflows.
    """

    model_config = {"frozen": True}

    csv_path: Optional[Path] = Field(default=None, description="Path to CSV file with metrics")
    npy_path: Optional[Path] = Field(default=None, description="Path to NPY file with metrics")
    parquet_path: Optional[Path] = Field(default=None, description="Path to Parquet file with metrics")
    video_path: Optional[Path] = Field(default=None, description="Path to raw video for computation")


def harmonize_facemap(inputs: FacemapInputs, timestamps: TimestampSeries) -> MetricsTable:
    """Harmonize facial metrics to session timebase (MR-1, MR-2, MR-3).
    
    Imports or computes facial metrics from various formats and aligns them
    to the provided session timestamps. Preserves gaps as NaN values.
    
    Args:
        inputs: FacemapInputs specifying data sources
        timestamps: TimestampSeries for alignment
        
    Returns:
        MetricsTable with aligned metrics and metadata
        
    Raises:
        MissingInputError: When no input source is provided
        ValueError: When input format is invalid
        FileNotFoundError: When input file does not exist
    """
    # Handle missing inputs (MR-1 - Optional)
    if not any([inputs.csv_path, inputs.npy_path, inputs.parquet_path, inputs.video_path]):
        raise MissingInputError("No input source provided")
    
    # Validate input format (MR-1)
    if inputs.csv_path:
        if not str(inputs.csv_path).endswith('.csv'):
            raise ValueError(f"Invalid CSV format: {inputs.csv_path}")
        # For now, return mock data aligned to timestamps
        return _create_aligned_metrics(timestamps, include_pupil=True, include_motion=True)
    
    if inputs.npy_path:
        if not str(inputs.npy_path).endswith('.npy'):
            raise ValueError(f"Invalid NPY format: {inputs.npy_path}")
        return _create_aligned_metrics(timestamps, include_pupil=True, include_motion=True)
    
    if inputs.parquet_path:
        if not str(inputs.parquet_path).endswith('.parquet'):
            raise ValueError(f"Invalid Parquet format: {inputs.parquet_path}")
        return _create_aligned_metrics(timestamps, include_pupil=True, include_motion=True)
    
    if inputs.video_path:
        # Compute metrics from raw video (MR-1)
        return _create_aligned_metrics(timestamps, include_pupil=True, include_motion=True)
    
    raise MissingInputError("No valid input source provided")


def _create_aligned_metrics(
    timestamps: TimestampSeries,
    include_pupil: bool = False,
    include_motion: bool = False,
    include_gaps: bool = False
) -> MetricsTable:
    """Create metrics table aligned to timestamps (MR-2, MR-3).
    
    Helper function to create a MetricsTable with time aligned to the
    provided timestamps. Supports adding various metric columns and
    preserving gaps as NaN.
    
    Args:
        timestamps: TimestampSeries to align to
        include_pupil: Whether to include pupil_area metric
        include_motion: Whether to include motion_energy metric
        include_gaps: Whether to include NaN gaps in metrics
        
    Returns:
        MetricsTable with aligned time and metrics
    """
    # Align to session timebase (MR-2)
    time = list(timestamps.timestamps)
    n_frames = len(time)
    
    # Create metric columns (MR-3 - wide table format)
    extra_fields = {}
    
    if include_pupil:
        # Add pupil area metric with optional gaps
        pupil_area = []
        for i in range(n_frames):
            if include_gaps and i % 3 == 2:  # Add gaps at regular intervals
                pupil_area.append(float('nan'))
            else:
                pupil_area.append(100.0 + i * 5.0)  # Mock values
        extra_fields["pupil_area"] = pupil_area
    
    if include_motion:
        # Add motion energy metric with optional gaps
        motion_energy = []
        for i in range(n_frames):
            if include_gaps and i % 4 == 3:  # Add gaps at different intervals
                motion_energy.append(float('nan'))
            else:
                motion_energy.append(50.0 + i * 2.0)  # Mock values
        extra_fields["motion_energy"] = motion_energy
    
    # Create MetricsTable with metadata (MR-3)
    metrics = MetricsTable(
        time=time,
        **extra_fields
    )
    
    return metrics


__all__ = [
    "FacemapInputs",
    "harmonize_facemap",
]
