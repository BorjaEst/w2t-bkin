#!/usr/bin/env python3
"""Example: Neuropixels Device & Electrodes → NWB (Phase 1).

Demonstrates the modern w2t_bkin.ingest.ecephys API for creating NWB files with
Neuropixels hardware metadata (devices and electrodes).

Goal
----
Show **how to create NWB files from SpikeGLX metadata** with a clear understanding
of the NWB ecephys data model:

1. Device: Hardware information (manufacturer, description)
2. ElectrodeGroup: Logical grouping of electrodes (location, device reference)
3. Electrodes Table: Individual electrode properties (location, filtering, coordinates)

Data flow
---------
1. Generate synthetic SpikeGLX metadata → realistic probe configuration
2. Parse SpikeGLX .meta file → extract sampling rate, channel count, geometry
3. Create Device object → add to NWBFile
4. Create ElectrodeGroup → links electrodes to device and location
5. Populate Electrodes table → one row per channel with spatial coordinates
6. Write NWB file with complete hardware metadata

This is **Phase 1** of ecephys integration: metadata only, no spike data.

Example usage
-------------
    $ python examples/neuropixels_metadata_nwb.py

With custom parameters:
    $ SUBJECT_ID=mouse-123 N_CHANNELS=384 python examples/neuropixels_metadata_nwb.py
"""

from datetime import datetime
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pynwb import NWBHDF5IO, NWBFile

from synthetic import build_raw_folder
from w2t_bkin.ingest.ecephys import create_device, create_electrode_group
from w2t_bkin.ingest.spikeglx import add_electrodes_from_spikeglx, parse_spikeglx_meta


class ExampleSettings(BaseSettings):
    """Settings for Neuropixels Metadata NWB Example."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    output_root: Path = Field(
        default=Path("output/neuropixels_metadata_nwb"),
        description="Root directory for output files",
    )
    subject_id: str = Field(default="subject-001", description="Subject identifier")
    session_id: str = Field(default="session-001", description="Session identifier")

    # Probe configuration
    probe_id: str = Field(default="imec0", description="Probe identifier (e.g., imec0, imec1)")
    location: str = Field(
        default="Motor Cortex, M1, left hemisphere",
        description="Brain region where probe is inserted",
    )

    # Synthetic data generation
    n_channels: int = Field(default=384, description="Number of recording channels")
    sampling_rate: float = Field(default=30000.0, description="Sampling rate (Hz)")
    recording_duration_s: float = Field(default=60.0, description="Recording duration (seconds)")
    seed: int = Field(default=42, description="Random seed for reproducible generation")


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


if __name__ == "__main__":
    """Run the Neuropixels Metadata → NWB demo."""
    settings = ExampleSettings()

    print("=" * 80)
    print("Example: Neuropixels Device & Electrodes → NWB (Phase 1)")
    print("=" * 80)
    print(f"\nSubject: {settings.subject_id}")
    print(f"Session: {settings.session_id}")
    print(f"Probe: {settings.probe_id}")
    print(f"Location: {settings.location}")
    print(f"Channels: {settings.n_channels}")

    # Create output directory
    settings.output_root.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------------
    # PHASE 0: Generate Synthetic Session with SpikeGLX Metadata
    # ---------------------------------------------------------------------
    print_section("PHASE 0: Generate Synthetic Session with SpikeGLX Metadata")

    print(f"\nGenerating synthetic raw session:")
    print(f"  - Channels:         {settings.n_channels}")
    print(f"  - Sampling rate:    {settings.sampling_rate:,.0f} Hz")
    print(f"  - Duration:         {settings.recording_duration_s} seconds")
    print(f"  - Seed:             {settings.seed}")

    # Generate synthetic session with SpikeGLX metadata
    raw_result = build_raw_folder(
        out_root=settings.output_root / "raw",
        subject_id=settings.subject_id,
        session_id=settings.session_id,
        camera_ids=[],  # No cameras for this example
        ttl_ids=[],  # No TTLs for this example
        ecephys_probe_ids=[settings.probe_id],
        ecephys_n_channels=settings.n_channels,
        ecephys_sampling_rate=settings.sampling_rate,
        ecephys_recording_duration_s=settings.recording_duration_s,
        seed=settings.seed,
    )

    meta_path = raw_result.ecephys_meta_paths[0]
    print(f"\n✓ Synthetic artifacts:")
    print(f"  - SpikeGLX metadata: {meta_path}")

    # ---------------------------------------------------------------------
    # PHASE 1: Parse SpikeGLX Metadata
    # ---------------------------------------------------------------------
    print_section("PHASE 1: Parse SpikeGLX Metadata")

    print(f"\nParsing metadata from: {meta_path}")

    meta = parse_spikeglx_meta(meta_path)
    print(f"\n✓ Parsed metadata:")
    print(f"  - Sampling rate: {meta['sampling_rate']:,.0f} Hz")
    print(f"  - Number of channels: {meta['n_channels']}")
    print(f"  - Probe type: {meta['probe_type']}")
    if meta.get("geometry"):
        print(f"  - Electrode geometry: {len(meta['geometry'])} electrodes with coordinates")

    # ---------------------------------------------------------------------
    # PHASE 2: Create NWBFile
    # ---------------------------------------------------------------------
    print_section("PHASE 2: Create NWBFile")

    nwbfile = NWBFile(
        session_description=f"Neuropixels recording from {settings.location}",
        identifier=f"{settings.subject_id}_{settings.session_id}_neuropixels",
        session_start_time=datetime.now().astimezone(),
        experimenter=["Demo User"],
        lab="Demo Lab",
        institution="Demo Institution",
        subject=None,  # Optional: add pynwb.file.Subject for detailed subject metadata
    )

    print(f"\n✓ Created NWBFile:")
    print(f"  - Identifier: {nwbfile.identifier}")
    print(f"  - Session: {nwbfile.session_description}")

    # ---------------------------------------------------------------------
    # PHASE 3: Create Device
    # ---------------------------------------------------------------------
    print_section("PHASE 3: Create Device")

    device_name = f"neuropixels_{settings.probe_id}"
    device = create_device(
        nwbfile=nwbfile,
        name=device_name,
        manufacturer="IMEC",
        description=f"Neuropixels 2.0 probe ({settings.probe_id})",
    )

    print(f"\n✓ Created Device:")
    print(f"  - Name: {device.name}")
    print(f"  - Manufacturer: {device.manufacturer}")
    print(f"  - Description: {device.description}")

    # ---------------------------------------------------------------------
    # PHASE 4: Add Electrodes
    # ---------------------------------------------------------------------
    print_section("PHASE 4: Add Electrodes")

    n_electrodes = add_electrodes_from_spikeglx(
        nwbfile=nwbfile,
        meta_path=meta_path,
        device=device,
        probe_id=settings.probe_id,
        location=settings.location,
    )

    print(f"\n✓ Added {n_electrodes} electrodes:")
    print(f"  - Electrode group: probe_{settings.probe_id}")
    print(f"  - Location: {settings.location}")
    print(f"  - Device: {device_name}")

    # Show sample electrodes
    print(f"\n  Sample electrodes (first 3):")
    electrodes_df = nwbfile.electrodes.to_dataframe()
    for idx in range(min(3, len(electrodes_df))):
        row = electrodes_df.iloc[idx]
        print(f"    [{idx}] x={row['x']:.1f}, y={row['y']:.1f}, " f"location={row['location']}, filtering={row['filtering']}")

    # ---------------------------------------------------------------------
    # PHASE 5: Write NWB File
    # ---------------------------------------------------------------------
    print_section("PHASE 5: Write NWB File")

    output_dir = settings.output_root / "output"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "neuropixels_metadata.nwb"
    with NWBHDF5IO(str(output_file), mode="w") as io:
        io.write(nwbfile)

    print(f"\n✓ Wrote NWB file: {output_file}")
    print(f"  - File size: {output_file.stat().st_size / 1024:.1f} KB")

    # ---------------------------------------------------------------------
    # PHASE 6: Read Back and Verify
    # ---------------------------------------------------------------------
    print_section("PHASE 6: Read Back and Verify")

    with NWBHDF5IO(str(output_file), mode="r") as io:
        read_nwb = io.read()

        # Verify devices
        print(f"\n✓ Devices ({len(read_nwb.devices)}):")
        for device_name, device in read_nwb.devices.items():
            print(f"  - {device_name}: {device.manufacturer}")

        # Verify electrode groups
        print(f"\n✓ Electrode Groups ({len(read_nwb.electrode_groups)}):")
        for group_name, group in read_nwb.electrode_groups.items():
            print(f"  - {group_name}: {group.location}")

        # Verify electrodes table
        print(f"\n✓ Electrodes Table:")
        print(f"  - Total electrodes: {len(read_nwb.electrodes)}")
        electrodes_df = read_nwb.electrodes.to_dataframe()
        print(f"  - Columns: {list(electrodes_df.columns)}")

        # Spatial extent
        x_range = (electrodes_df["x"].min(), electrodes_df["x"].max())
        y_range = (electrodes_df["y"].min(), electrodes_df["y"].max())
        print(f"  - X range: {x_range[0]:.1f} to {x_range[1]:.1f} μm")
        print(f"  - Y range: {y_range[0]:.1f} to {y_range[1]:.1f} μm")

    # ---------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------
    print_section("Summary")

    print("\n✓ Successfully created NWB file with Neuropixels metadata:")
    print(f"  1. Device: {device_name}")
    print(f"  2. Electrode Group: probe_{settings.probe_id}")
    print(f"  3. Electrodes: {n_electrodes} channels")
    print(f"\n✓ Output: {output_file}")
    print("\nNext steps:")
    print("  - Add spike sorting data (Phase 2): see neuropixels_spikes_nwb.py")
    print("  - Add raw data links (Phase 3): link to .ap.bin files")
    print("  - Add LFP data (Phase 4): downsample and store LFP")

    print("\n" + "=" * 80)
    print("Example complete!")
    print("=" * 80)
