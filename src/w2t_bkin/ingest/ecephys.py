"""
Generic Extracellular Electrophysiology Utilities.

This module provides hardware-agnostic utilities for working with ecephys data
in NWB files. It handles common operations like device creation and electrode
table management that apply across different acquisition systems.

For hardware-specific functionality, see:
- spikeglx: SpikeGLX/Neuropixels metadata parsing
- kilosort: Kilosort spike sorting ingestion

Architecture Layer: Low-Level Tools
- No imports from config, Session, or Manifest
- All functions accept primitives only
- Returns NWB objects directly

Example Usage:
    >>> from pynwb import NWBFile
    >>> from w2t_bkin.ingest.ecephys import create_device, create_electrode_group
    >>> from w2t_bkin.ingest.spikeglx import parse_spikeglx_meta, add_electrodes_from_spikeglx
    >>>
    >>> nwbfile = NWBFile(...)
    >>> device = create_device(
    ...     nwbfile=nwbfile,
    ...     name="neuropixels_imec0",
    ...     manufacturer="IMEC",
    ...     description="Neuropixels 2.0 probe in Motor Cortex"
    ... )
    >>>
    >>> electrode_group = create_electrode_group(
    ...     nwbfile=nwbfile,
    ...     name="probe_imec0",
    ...     description="Motor cortex electrodes",
    ...     location="Motor Cortex, M1",
    ...     device=device
    ... )
"""

from typing import Optional

from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup


def create_device(
    nwbfile: NWBFile,
    name: str,
    manufacturer: str = "",
    description: str = "",
) -> Device:
    """
    Create a generic Device object for ecephys hardware.

    Args:
        nwbfile: NWBFile to add device to
        name: Unique device identifier (e.g., "neuropixels_imec0")
        manufacturer: Device manufacturer (e.g., "IMEC")
        description: Human-readable description

    Returns:
        Device object added to nwbfile

    Raises:
        ValueError: If device name already exists in nwbfile

    Example:
        >>> device = create_device(
        ...     nwbfile=nwbfile,
        ...     name="neuropixels_imec0",
        ...     manufacturer="IMEC",
        ...     description="Neuropixels 2.0 probe"
        ... )
    """
    if name in nwbfile.devices:
        raise ValueError(
            f"Device '{name}' already exists in NWBFile. "
            f"Device names must be unique."
        )

    device = nwbfile.create_device(
        name=name,
        manufacturer=manufacturer,
        description=description,
    )

    return device


def create_electrode_group(
    nwbfile: NWBFile,
    name: str,
    description: str,
    location: str,
    device: Device,
) -> ElectrodeGroup:
    """
    Create an ElectrodeGroup for organizing electrodes.

    Args:
        nwbfile: NWBFile to add electrode group to
        name: Unique group identifier (e.g., "probe_imec0")
        description: Human-readable description
        location: Brain region or anatomical location
        device: Device object that these electrodes belong to

    Returns:
        ElectrodeGroup object added to nwbfile

    Raises:
        ValueError: If electrode group name already exists

    Example:
        >>> group = create_electrode_group(
        ...     nwbfile=nwbfile,
        ...     name="probe_imec0",
        ...     description="Motor cortex recording site",
        ...     location="Motor Cortex, M1",
        ...     device=device
        ... )
    """
    if name in nwbfile.electrode_groups:
        raise ValueError(
            f"ElectrodeGroup '{name}' already exists in NWBFile. "
            f"Group names must be unique."
        )

    electrode_group = nwbfile.create_electrode_group(
        name=name,
        description=description,
        location=location,
        device=device,
    )

    return electrode_group


__all__ = [
    "create_device",
    "create_electrode_group",
]
