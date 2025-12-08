"""
Device and Electrode Table Management for Neuropixels.

This module provides functions to create Device objects and populate
the electrodes table from SpikeGLX metadata.
"""

from pathlib import Path
from typing import Optional

from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup

from .parsers import parse_spikeglx_meta


def create_neuropixels_device(
    nwbfile: NWBFile,
    device_name: str,
    manufacturer: str = "IMEC",
    model_name: str = "Neuropixels 2.0",
    description: str = "",
) -> Device:
    """
    Create a Device object for a Neuropixels probe.

    Args:
        nwbfile: NWBFile to add device to
        device_name: Unique device identifier (e.g., "neuropixels_imec0")
        manufacturer: Device manufacturer (default: "IMEC")
        model_name: Probe model (e.g., "Neuropixels 1.0", "Neuropixels 2.0")
        description: Human-readable description

    Returns:
        Device object added to nwbfile

    Raises:
        ValueError: If device_name already exists in nwbfile

    Example:
        >>> from pynwb import NWBFile
        >>> from datetime import datetime
        >>> from dateutil.tz import tzlocal
        >>>
        >>> nwbfile = NWBFile(
        ...     session_description="test",
        ...     identifier="test-001",
        ...     session_start_time=datetime.now(tzlocal()),
        ... )
        >>> device = create_neuropixels_device(
        ...     nwbfile=nwbfile,
        ...     device_name="neuropixels_imec0",
        ...     manufacturer="IMEC",
        ...     model_name="Neuropixels 2.0",
        ...     description="Motor cortex probe",
        ... )
        >>> device.name
        'neuropixels_imec0'
        >>> device.manufacturer
        'IMEC'
    """
    # Check if device already exists
    if device_name in nwbfile.devices:
        raise ValueError(f"Device '{device_name}' already exists in NWBFile. " f"Device names must be unique.")

    # Create device
    device = nwbfile.create_device(
        name=device_name,
        manufacturer=manufacturer,
        description=description or f"{model_name} probe",
        # Note: pynwb Device doesn't have model_name parameter directly
        # We include it in description
    )

    return device


def add_electrodes_from_meta(
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
        device: Device object created by create_neuropixels_device()
        probe_id: Probe identifier (e.g., "imec0")
        location: Brain region (e.g., "Motor Cortex, M1")
        group_name: ElectrodeGroup name (defaults to f"probe_{probe_id}")

    Returns:
        Number of electrodes added

    Raises:
        FileNotFoundError: If meta_path does not exist
        ValueError: If .meta file is malformed

    Example:
        >>> n_added = add_electrodes_from_meta(
        ...     nwbfile=nwbfile,
        ...     meta_path=Path("interim/neural/catgt/rec_tcat.imec0.ap.meta"),
        ...     device=device,
        ...     probe_id="imec0",
        ...     location="Motor Cortex, M1",
        ... )
        >>> n_added
        384
        >>> len(nwbfile.electrodes)
        384
    """
    # Parse .meta file
    meta = parse_spikeglx_meta(meta_path)

    # Create electrode group
    if group_name is None:
        group_name = f"probe_{probe_id}"

    electrode_group = nwbfile.create_electrode_group(
        name=group_name,
        description=f"Neuropixels probe {probe_id}",
        location=location,
        device=device,
    )

    # Add electrodes
    n_channels = meta["n_channels"]
    geometry = meta.get("geometry", [])
    filtering = meta.get("filtering", "unknown")

    for ch_idx in range(n_channels):
        # Get coordinates if available
        if ch_idx < len(geometry):
            x, y = geometry[ch_idx]
            z = 0.0  # Neuropixels are planar
        else:
            x, y, z = float("nan"), float("nan"), float("nan")

        # Add electrode to table
        nwbfile.add_electrode(
            group=electrode_group,
            location=location,
            filtering=filtering,
            x=x,
            y=y,
            z=z,
            imp=float("nan"),  # Impedance not typically available
            # Add custom column for probe_id if needed
        )

    return n_channels
