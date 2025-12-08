"""
Neuropixels Extracellular Electrophysiology Ingestion Module.

This module provides low-level tools for ingesting Neuropixels data into NWB files.
It follows the NWB-First architecture, accepting only primitives (file paths, strings, numbers)
and returning NWB-native objects (Device, ElectricalSeries, Units).

Architecture Layer: Low-Level Tools
- No imports from config, Session, or Manifest
- All functions accept primitives only
- Returns NWB objects directly

Modules:
    parsers: SpikeGLX .meta and Kilosort file parsers
    device: Device and electrode creation
    sorting: Spike sorting ingestion (Kilosort → Units table)
    raw_data: Raw AP band data handling (external links)

Example Usage:
    >>> from pynwb import NWBFile
    >>> from w2t_bkin.ingest.ecephys import (
    ...     create_neuropixels_device,
    ...     add_electrodes_from_meta,
    ...     add_spike_sorting,
    ... )
    >>>
    >>> nwbfile = NWBFile(...)
    >>> device = create_neuropixels_device(
    ...     nwbfile=nwbfile,
    ...     device_name="neuropixels_imec0",
    ...     manufacturer="IMEC",
    ...     model_name="Neuropixels 2.0",
    ... )
    >>>
    >>> n_electrodes = add_electrodes_from_meta(
    ...     nwbfile=nwbfile,
    ...     meta_path=Path("interim/neural/catgt/recording_tcat.imec0.ap.meta"),
    ...     device=device,
    ...     probe_id="imec0",
    ...     location="Motor Cortex, M1",
    ... )
    >>>
    >>> stats = add_spike_sorting(
    ...     nwbfile=nwbfile,
    ...     sorting_dir=Path("interim/neural/kilosort/imec0"),
    ...     probe_id="imec0",
    ...     include_labels=["good", "mua"],
    ...     min_spike_count=100,
    ... )
"""

from .device import add_electrodes_from_meta, create_neuropixels_device
from .parsers import parse_spikeglx_meta

__all__ = [
    "create_neuropixels_device",
    "add_electrodes_from_meta",
    "parse_spikeglx_meta",
]
