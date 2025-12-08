"""
SpikeGLX Hardware Metadata Parsing and NWB Object Creation.

This module provides utilities for parsing SpikeGLX .meta files and
creating NWB objects (Device, ElectrodeGroup, ElectricalSeries) for
Neuropixels probes.

Architecture Layer: Low-Level Tools
- No imports from config, Session, or Manifest
- All functions accept primitives only
- Returns NWB objects (not attached to NWBFile)
- Pipeline layer is responsible for attachment

Example Usage:
    >>> from pathlib import Path
    >>> from pynwb import NWBFile
    >>> from w2t_bkin.ingest.spikeglx import (
    ...     parse_spikeglx_meta,
    ...     build_device_from_meta,
    ...     build_electrode_group_from_meta,
    ...     build_electrodes_table_from_meta,
    ... )
    >>>
    >>> # Parse metadata
    >>> meta = parse_spikeglx_meta(Path("recording.imec0.ap.meta"))
    >>>
    >>> # Create NWB objects (not attached yet)
    >>> device = build_device_from_meta(meta, "imec0")
    >>> electrode_group = build_electrode_group_from_meta(
    ...     name="probe_imec0",
    ...     device=device,
    ...     location="Motor Cortex, M1",
    ...     meta=meta,
    ... )
    >>> electrode_rows = build_electrodes_table_from_meta(
    ...     meta, electrode_group, "Motor Cortex, M1"
    ... )
    >>>
    >>> # Pipeline attaches to NWBFile
    >>> nwbfile = NWBFile(...)
    >>> nwbfile.add_device(device)
    >>> nwbfile.create_electrode_group(
    ...     name=electrode_group.name,
    ...     description=electrode_group.description,
    ...     location=electrode_group.location,
    ...     device=electrode_group.device,
    ... )
    >>> for row in electrode_rows:
    ...     nwbfile.add_electrode(**row)
"""

import functools
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from pynwb.device import Device
from pynwb.ecephys import ElectricalSeries, ElectrodeGroup


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


def build_device_from_meta(meta: Dict[str, Any], probe_id: str) -> Device:
    """
    Create Device object from parsed SpikeGLX metadata.

    Args:
        meta: Parsed metadata dict from parse_spikeglx_meta()
        probe_id: Probe identifier (e.g., "imec0")

    Returns:
        Device object (not attached to NWBFile)

    Example:
        >>> meta = parse_spikeglx_meta(Path("recording.imec0.ap.meta"))
        >>> device = build_device_from_meta(meta, "imec0")
        >>> device.name
        'neuropixels_imec0'
    """
    # Map probe type codes to descriptive names
    probe_type_map = {
        "0": "Neuropixels 1.0",
        "21": "Neuropixels 2.0 (single-shank)",
        "24": "Neuropixels 2.0 (four-shank)",
        "1100": "Neuropixels 1.0 (commercial)",
        "1110": "Neuropixels 1.0 (phase 3A)",
        "1120": "Neuropixels 1.0 (phase 3B1)",
        "1121": "Neuropixels 1.0 (phase 3B2)",
        "1122": "Neuropixels 1.0 (NHP short)",
        "1123": "Neuropixels 1.0 (NHP medium)",
        "1300": "Neuropixels Ultra",
    }
    probe_type_str = probe_type_map.get(meta["probe_type"], f"Neuropixels (type {meta['probe_type']})")

    return Device(
        name=f"neuropixels_{probe_id}",
        manufacturer="IMEC",
        description=f"{probe_type_str} probe ({probe_id})",
    )


def build_electrode_group_from_meta(
    name: str,
    device: Device,
    location: str,
    meta: Dict[str, Any],
) -> ElectrodeGroup:
    """
    Create ElectrodeGroup object from metadata.

    Args:
        name: Unique group identifier (e.g., "probe_imec0")
        device: Device object (from build_device_from_meta)
        location: Brain region (e.g., "Motor Cortex, M1")
        meta: Parsed metadata dict from parse_spikeglx_meta()

    Returns:
        ElectrodeGroup object (not attached to NWBFile)

    Example:
        >>> device = build_device_from_meta(meta, "imec0")
        >>> group = build_electrode_group_from_meta(
        ...     name="probe_imec0",
        ...     device=device,
        ...     location="Motor Cortex, M1",
        ...     meta=meta,
        ... )
    """
    return ElectrodeGroup(
        name=name,
        description=f"Electrodes from {device.name} ({meta['n_channels']} channels)",
        location=location,
        device=device,
    )


def build_electrodes_table_from_meta(
    meta: Dict[str, Any],
    electrode_group: ElectrodeGroup,
    location: str,
) -> List[Dict[str, Any]]:
    """
    Build electrode table rows from parsed metadata.

    Returns list of dictionaries that can be passed to nwbfile.add_electrode(**row).
    Does not modify NWBFile - pipeline layer is responsible for adding electrodes.

    Args:
        meta: Parsed metadata dict from parse_spikeglx_meta()
        electrode_group: ElectrodeGroup object (from build_electrode_group_from_meta)
        location: Brain region (e.g., "Motor Cortex, M1")

    Returns:
        List of electrode row dictionaries with keys:
            - group: ElectrodeGroup reference
            - location: str
            - x, y, z: float (coordinates in μm)
            - filtering: str
            - imp: float (impedance, typically NaN)

    Example:
        >>> electrode_rows = build_electrodes_table_from_meta(meta, group, "M1")
        >>> len(electrode_rows)
        384
        >>> electrode_rows[0]['x']
        0.0
    """
    electrodes = []
    geometry = meta["geometry"]
    n_channels = meta["n_channels"]

    for ch_idx in range(n_channels):
        # Get coordinates if available
        if ch_idx < len(geometry):
            x, y = geometry[ch_idx]
        else:
            x, y = float("nan"), float("nan")

        electrodes.append(
            {
                "group": electrode_group,
                "location": location,
                "x": x,
                "y": y,
                "z": 0.0,  # Neuropixels probes are planar (2D layout)
                "filtering": meta["filtering"],
                "imp": float("nan"),  # Impedance not typically in .meta files
            }
        )

    return electrodes


def build_electrical_series_from_bin(
    name: str,
    bin_file_path: Path,
    meta: Dict[str, Any],
    electrode_region,
    starting_time: float = 0.0,
    comments: str = "",
) -> ElectricalSeries:
    """
    Create ElectricalSeries with external link to SpikeGLX .bin file.

    Creates an ElectricalSeries that references the raw binary data file without
    copying it into the NWB file. This is critical for large recordings (100s of GB).

    The .bin file must exist alongside the NWB file for the link to work.

    Args:
        name: Series name (e.g., "probe_imec0_ap")
        bin_file_path: Path to .ap.bin or .lf.bin file
        meta: Parsed metadata dict from parse_spikeglx_meta()
        electrode_region: DynamicTableRegion from nwbfile.create_electrode_table_region()
        starting_time: Start time in seconds (default: 0.0)
        comments: Optional comments about the recording

    Returns:
        ElectricalSeries object with external file link

    Raises:
        FileNotFoundError: If bin_file_path does not exist

    Example:
        >>> # After adding device, group, and electrodes to nwbfile:
        >>> electrode_indices = list(range(384))
        >>> electrode_region = nwbfile.create_electrode_table_region(
        ...     region=electrode_indices,
        ...     description="All electrodes from probe_imec0",
        ... )
        >>> electrical_series = build_electrical_series_from_bin(
        ...     name="probe_imec0_ap",
        ...     bin_file_path=Path("recording.imec0.ap.bin"),
        ...     meta=meta,
        ...     electrode_region=electrode_region,
        ... )
        >>> nwbfile.add_acquisition(electrical_series)
    """
    from hdmf.backends.hdf5 import H5DataIO

    bin_file_path = Path(bin_file_path)
    if not bin_file_path.exists():
        raise FileNotFoundError(f"SpikeGLX .bin file not found: {bin_file_path}")

    # Use absolute path for external link
    absolute_path = str(bin_file_path.absolute())

    return ElectricalSeries(
        name=name,
        description=f"Neuropixels recording from {bin_file_path.name} (external link)",
        data=H5DataIO(data=[], link_data=True),  # Empty placeholder, links externally
        external_file=[absolute_path],
        starting_time=starting_time,
        rate=meta["sampling_rate"],
        electrodes=electrode_region,
        conversion=1e-6,  # SpikeGLX stores in microvolts, NWB expects volts
        unit="volts",
        comments=comments,
    )


__all__ = [
    "parse_spikeglx_meta",
    "build_device_from_meta",
    "build_electrode_group_from_meta",
    "build_electrodes_table_from_meta",
    "build_electrical_series_from_bin",
]
