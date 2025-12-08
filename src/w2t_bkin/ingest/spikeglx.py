"""
SpikeGLX Hardware Metadata Parsing and Electrode Ingestion.

This module provides utilities for parsing SpikeGLX .meta files and
populating NWB electrode tables for Neuropixels probes.

Architecture Layer: Low-Level Tools
- No imports from config, Session, or Manifest
- All functions accept primitives only
- Returns structured data or NWB objects

Example Usage:
    >>> from pathlib import Path
    >>> from pynwb import NWBFile
    >>> from w2t_bkin.ingest.ecephys import create_device
    >>> from w2t_bkin.ingest.spikeglx import parse_spikeglx_meta, add_electrodes_from_spikeglx
    >>>
    >>> # Parse metadata
    >>> meta = parse_spikeglx_meta(Path("recording.imec0.ap.meta"))
    >>> print(f"Sampling rate: {meta['sampling_rate']} Hz")
    >>>
    >>> # Create device and add electrodes
    >>> nwbfile = NWBFile(...)
    >>> device = create_device(nwbfile, "neuropixels_imec0", "IMEC")
    >>> n_electrodes = add_electrodes_from_spikeglx(
    ...     nwbfile=nwbfile,
    ...     meta_path=Path("recording.imec0.ap.meta"),
    ...     device=device,
    ...     probe_id="imec0",
    ...     location="Motor Cortex, M1"
    ... )
"""

import functools
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from pynwb import NWBFile
from pynwb.device import Device

from .ecephys import create_electrode_group


@functools.lru_cache(maxsize=128)
def parse_spikeglx_meta(meta_path: Path) -> Dict[str, Any]:
    """
    Parse SpikeGLX .meta file into structured dictionary.

    SpikeGLX .meta files are simple key-value text files with format:
        key=value

    This function extracts critical metadata needed for NWB ingestion:
    - Sampling rate
    - Channel count
    - Probe type/generation
    - Electrode geometry (if available)

    Args:
        meta_path: Path to .meta file (e.g., *_tcat.imec0.ap.meta)

    Returns:
        Dictionary with parsed metadata:
            {
                "sampling_rate": float,  # imSampRate in Hz
                "n_channels": int,       # nSavedChans
                "probe_type": str,       # imDatPrb_type (0=NP1.0, 21=NP2.0, etc.)
                "geometry": List[Tuple[float, float]],  # [(x, y), ...] from ~snsGeomMap
                "filtering": str,        # Description of applied filtering
                "file_size_bytes": int,  # fileSizeBytes
            }

    Raises:
        FileNotFoundError: If meta_path does not exist
        ValueError: If required fields are missing or malformed

    Example:
        >>> meta = parse_spikeglx_meta(Path("recording.imec0.ap.meta"))
        >>> meta["sampling_rate"]
        30000.0
        >>> meta["n_channels"]
        384
        >>> meta["probe_type"]
        "21"  # Neuropixels 2.0 single-shank
    """
    # Convert to Path object if string
    meta_path = Path(meta_path)

    if not meta_path.exists():
        raise FileNotFoundError(f"SpikeGLX .meta file not found: {meta_path}")

    # Parse key-value pairs
    meta_dict: Dict[str, str] = {}
    with open(meta_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                meta_dict[key.strip()] = value.strip()

    # Extract required fields
    try:
        sampling_rate = float(meta_dict["imSampRate"])
        n_channels = int(meta_dict["nSavedChans"])
        probe_type = meta_dict.get("imDatPrb_type", "unknown")
        file_size_bytes = int(meta_dict.get("fileSizeBytes", 0))
    except KeyError as e:
        raise ValueError(f"Required field missing in .meta file: {e}")
    except ValueError as e:
        raise ValueError(f"Failed to parse .meta field: {e}")

    # Parse electrode geometry if available
    geometry: List[Tuple[float, float]] = []
    if "~snsGeomMap" in meta_dict:
        # Format: "(x1,y1)(x2,y2)..."
        geom_str = meta_dict["~snsGeomMap"]
        matches = re.findall(r"\(([^,]+),([^)]+)\)", geom_str)
        geometry = [(float(x), float(y)) for x, y in matches]

    # Infer filtering description (standard CatGT settings)
    filtering = "High-pass filtered at 300 Hz (CatGT default)"
    if "~imBandpass" in meta_dict:
        filtering = f"Bandpass: {meta_dict['~imBandpass']} Hz"

    return {
        "sampling_rate": sampling_rate,
        "n_channels": n_channels,
        "probe_type": probe_type,
        "geometry": geometry,
        "filtering": filtering,
        "file_size_bytes": file_size_bytes,
    }


def add_electrodes_from_spikeglx(
    nwbfile: NWBFile,
    meta_path: Path,
    device: Device,
    probe_id: str,
    location: str = "unknown",
    group_name: Optional[str] = None,
) -> int:
    """
    Parse SpikeGLX .meta file and populate electrodes table.

    This function:
    1. Parses the .meta file to extract electrode configuration
    2. Creates an ElectrodeGroup for this probe
    3. Adds electrodes to nwbfile.electrodes table

    Electrode IDs are auto-incremented to ensure uniqueness across multiple probes.

    Args:
        nwbfile: NWBFile to add electrodes to
        meta_path: Path to .meta file (e.g., *_tcat.imec0.ap.meta)
        device: Device object (from ecephys.create_device())
        probe_id: Probe identifier (e.g., "imec0")
        location: Brain region (e.g., "Motor Cortex, M1")
        group_name: ElectrodeGroup name (defaults to f"probe_{probe_id}")

    Returns:
        Number of electrodes added

    Raises:
        FileNotFoundError: If meta_path does not exist
        ValueError: If .meta file is malformed

    Example:
        >>> from w2t_bkin.ingest.ecephys import create_device
        >>> device = create_device(nwbfile, "neuropixels_imec0", "IMEC")
        >>> n_added = add_electrodes_from_spikeglx(
        ...     nwbfile=nwbfile,
        ...     meta_path=Path("recording.imec0.ap.meta"),
        ...     device=device,
        ...     probe_id="imec0",
        ...     location="Motor Cortex, M1"
        ... )
        >>> print(f"Added {n_added} electrodes")
    """
    # Parse metadata
    meta = parse_spikeglx_meta(meta_path)

    # Create electrode group
    group_name = group_name or f"probe_{probe_id}"
    electrode_group = create_electrode_group(
        nwbfile=nwbfile,
        name=group_name,
        description=f"Neuropixels probe {probe_id}",
        location=location,
        device=device,
    )

    # Add electrodes to table
    geometry = meta["geometry"]
    n_channels = meta["n_channels"]

    for ch_idx in range(n_channels):
        # Get coordinates if available
        if ch_idx < len(geometry):
            x, y = geometry[ch_idx]
        else:
            x, y = float("nan"), float("nan")

        nwbfile.add_electrode(
            group=electrode_group,
            location=location,
            x=x,
            y=y,
            z=0.0,  # Neuropixels probes are planar
            filtering=meta["filtering"],
            imp=float("nan"),  # Impedance not typically in .meta
        )

    return n_channels


__all__ = [
    "parse_spikeglx_meta",
    "add_electrodes_from_spikeglx",
]
