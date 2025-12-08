#!/usr/bin/env python3
"""Example: Neuropixels Metadata + Spike Sorting → NWB (Phase 1 + 2).

Demonstrates the complete w2t_bkin.ingest.ecephys pipeline for creating NWB files
with Neuropixels hardware metadata AND spike sorting data.

Goal
----
Show **how to create complete NWB files from SpikeGLX + Kilosort** with:

1. Phase 1: Hardware metadata (devices, electrode groups, electrodes table)
2. Phase 2: Spike sorting data (units table with spike times, waveforms, metrics)

Data flow
---------
1. Generate synthetic SpikeGLX + Kilosort data → realistic recording
2. Parse SpikeGLX metadata → create devices and electrodes
3. Load Kilosort output → extract spike times and quality metrics
4. Filter units by quality → keep only "good" units with sufficient spikes
5. Add units to NWB → populate units table with spike times, waveforms, metrics
6. Write NWB file with complete electrophysiology data

This is **Phase 1 + 2** of ecephys integration: hardware + spike sorting.

Quality Filtering
-----------------
Units are filtered by:
- Quality label: Only "good" units (excludes "noise" and "mua")
- Spike count: Minimum number of spikes (default: 100)
- Optional: Contamination percentage, firing rate, ISI violations

Example usage
-------------
    $ python examples/neuropixels_spikes_nwb.py

With custom parameters:
    $ MIN_SPIKE_COUNT=200 N_UNITS=50 python examples/neuropixels_spikes_nwb.py
"""

from datetime import datetime
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pynwb import NWBHDF5IO, NWBFile

from synthetic import build_ecephys_output
from w2t_bkin.ingest.ecephys import create_device
from w2t_bkin.ingest.kilosort import add_units_from_kilosort
from w2t_bkin.ingest.spikeglx import add_electrodes_from_spikeglx, parse_spikeglx_meta


class ExampleSettings(BaseSettings):
    """Settings for Neuropixels Spikes NWB Example."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    output_root: Path = Field(
        default=Path("output/neuropixels_spikes_nwb"),
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
    n_units: int = Field(default=30, description="Number of sorted units to generate")
    recording_duration_s: float = Field(default=120.0, description="Recording duration (seconds)")
    seed: int = Field(default=42, description="Random seed for reproducible generation")

    # Quality filtering
    min_spike_count: int = Field(default=100, description="Minimum spikes per unit")
    quality_labels: list = Field(default=["good"], description="Quality labels to include (e.g., ['good', 'mua'])")


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


if __name__ == "__main__":
    """Run the Neuropixels Metadata + Spikes → NWB demo."""
    settings = ExampleSettings()

    print("=" * 80)
    print("Example: Neuropixels Metadata + Spike Sorting → NWB (Phase 1 + 2)")
    print("=" * 80)
    print(f"\nSubject: {settings.subject_id}")
    print(f"Session: {settings.session_id}")
    print(f"Probe: {settings.probe_id}")
    print(f"Location: {settings.location}")
    print(f"Units: {settings.n_units} (before filtering)")
    print(f"Quality filter: {settings.quality_labels}, min_spikes={settings.min_spike_count}")

    # Create output directory
    settings.output_root.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------------
    # PHASE 0: Generate Synthetic Ecephys Data
    # ---------------------------------------------------------------------
    print_section("PHASE 0: Generate Synthetic Ecephys Data")

    print(f"\nGenerating synthetic SpikeGLX + Kilosort data:")
    print(f"  - Channels:         {settings.n_channels}")
    print(f"  - Sampling rate:    {settings.sampling_rate:,.0f} Hz")
    print(f"  - Units:            {settings.n_units}")
    print(f"  - Duration:         {settings.recording_duration_s} seconds")
    print(f"  - Seed:             {settings.seed}")

    # Generate synthetic data in output/raw subdirectory
    raw_dir = settings.output_root / "raw"
    synth_paths = build_ecephys_output(
        raw_dir,
        probe_type="neuropixels2.0",
        probe_id=settings.probe_id,
        n_channels=settings.n_channels,
        sampling_rate=settings.sampling_rate,
        n_units=settings.n_units,
        recording_duration_s=settings.recording_duration_s,
        seed=settings.seed,
    )

    meta_path = synth_paths["meta"]
    kilosort_dir = meta_path.parent.parent / "kilosort"

    print(f"\n✓ Synthetic artifacts:")
    print(f"  - SpikeGLX metadata: {meta_path}")
    print(f"  - Kilosort directory: {kilosort_dir}")
    print(f"  - Spike times:       {kilosort_dir / 'spike_times.npy'}")
    print(f"  - Cluster info:      {kilosort_dir / 'cluster_info.tsv'}")

    # ---------------------------------------------------------------------
    # PHASE 1: Create NWBFile with Metadata + Electrodes
    # ---------------------------------------------------------------------
    print_section("PHASE 1: Create NWBFile with Metadata + Electrodes")

    # Parse metadata
    meta = parse_spikeglx_meta(meta_path)
    print(f"\n✓ Parsed SpikeGLX metadata:")
    print(f"  - Sampling rate: {meta['sampling_rate']:,.0f} Hz")
    print(f"  - Channels:      {meta['n_channels']}")
    print(f"  - Probe type:    {meta['probe_type']}")

    # Create NWBFile
    nwbfile = NWBFile(
        session_description=f"Neuropixels recording with spike sorting from {settings.location}",
        identifier=f"{settings.subject_id}_{settings.session_id}_neuropixels_spikes",
        session_start_time=datetime.now().astimezone(),
        experimenter=["Demo User"],
        lab="Demo Lab",
        institution="Demo Institution",
        subject=None,
    )

    print(f"\n✓ Created NWBFile: {nwbfile.identifier}")

    # Create device
    device_name = f"neuropixels_{settings.probe_id}"
    device = create_device(
        nwbfile=nwbfile,
        name=device_name,
        manufacturer="IMEC",
        description=f"Neuropixels 2.0 probe ({settings.probe_id})",
    )

    print(f"\n✓ Created Device: {device.name}")

    # Add electrodes
    n_electrodes = add_electrodes_from_spikeglx(
        nwbfile=nwbfile,
        meta_path=meta_path,
        device=device,
        probe_id=settings.probe_id,
        location=settings.location,
    )

    print(f"\n✓ Added {n_electrodes} electrodes to table")

    # ---------------------------------------------------------------------
    # PHASE 2: Add Spike Sorting Data
    # ---------------------------------------------------------------------
    print_section("PHASE 2: Add Spike Sorting Data")

    print(f"\nAdding units from Kilosort:")
    print(f"  - Directory:        {kilosort_dir}")
    print(f"  - Quality filter:   {settings.quality_labels}")
    print(f"  - Min spike count:  {settings.min_spike_count}")

    result = add_units_from_kilosort(
        nwbfile=nwbfile,
        sorting_dir=kilosort_dir,
        probe_id=settings.probe_id,
        sampling_rate=meta["sampling_rate"],
        include_labels=settings.quality_labels,
        min_spike_count=settings.min_spike_count,
        include_waveforms=True,
        include_metrics=True,
    )

    n_units = result["n_units_added"]
    print(f"\n✓ Added {n_units} units to table (after filtering)")
    print(f"  - Filtered out: {result['n_units_filtered']} units")
    print(f"  - Total spikes: {result['n_spikes_total']:,}")

    # Show sample units
    if n_units > 0:
        units_df = nwbfile.units.to_dataframe()
        print(f"\n  Sample units (first 3):")
        for idx in range(min(3, len(units_df))):
            row = units_df.iloc[idx]
            n_spikes = len(row["spike_times"])
            firing_rate = n_spikes / settings.recording_duration_s
            amp = row.get("amplitude", "N/A")
            contam = row.get("contamination_pct", "N/A")
            print(
                f"    [unit {idx}] probe={row['probe_id']}, "
                f"spikes={n_spikes}, "
                f"firing_rate={firing_rate:.2f} Hz, "
                f"amplitude={amp:.1f}" + (f", contamination={contam:.2%}" if contam != "N/A" else "")
            )

    # ---------------------------------------------------------------------
    # PHASE 3: Write NWB File
    # ---------------------------------------------------------------------
    print_section("PHASE 3: Write NWB File")

    output_dir = settings.output_root / "output"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "neuropixels_spikes.nwb"

    with NWBHDF5IO(str(output_file), mode="w") as io:
        io.write(nwbfile)

    print(f"\n✓ Wrote NWB file: {output_file}")
    print(f"  - File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")

    # ---------------------------------------------------------------------
    # PHASE 4: Read Back and Verify
    # ---------------------------------------------------------------------
    print_section("PHASE 4: Read Back and Verify")

    with NWBHDF5IO(str(output_file), mode="r") as io:
        read_nwb = io.read()

        # Verify devices
        print(f"\n✓ Devices ({len(read_nwb.devices)}):")
        for dev_name, dev in read_nwb.devices.items():
            print(f"  - {dev_name}: {dev.manufacturer}")

        # Verify electrode groups
        print(f"\n✓ Electrode Groups ({len(read_nwb.electrode_groups)}):")
        for grp_name, grp in read_nwb.electrode_groups.items():
            print(f"  - {grp_name}: {grp.location}")

        # Verify electrodes
        print(f"\n✓ Electrodes Table:")
        print(f"  - Total electrodes: {len(read_nwb.electrodes)}")

        # Verify units
        print(f"\n✓ Units Table:")
        if read_nwb.units is not None and len(read_nwb.units) > 0:
            units_df = read_nwb.units.to_dataframe()
            print(f"  - Total units: {len(units_df)}")
            print(f"  - Columns: {list(units_df.columns)}")

            # Compute statistics
            total_spikes = sum(len(row["spike_times"]) for _, row in units_df.iterrows())
            mean_firing = total_spikes / settings.recording_duration_s / len(units_df)
            print(f"  - Total spikes: {total_spikes:,}")
            print(f"  - Mean firing rate: {mean_firing:.2f} Hz")

            # Quality distribution
            if "contamination_pct" in units_df.columns:
                mean_contam = units_df["contamination_pct"].mean()
                print(f"  - Mean contamination: {mean_contam:.2%}")
            if "amplitude" in units_df.columns:
                mean_amp = units_df["amplitude"].mean()
                print(f"  - Mean amplitude: {mean_amp:.1f} μV")
        else:
            print(f"  - No units found (all filtered out)")

    # ---------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------
    print_section("Summary")

    print("\n✓ Successfully created NWB file with complete ecephys data:")
    print(f"  1. Device: {device_name}")
    print(f"  2. Electrode Group: probe_{settings.probe_id}")
    print(f"  3. Electrodes: {n_electrodes} channels")
    print(f"  4. Units: {n_units} sorted units (quality-filtered)")
    print(f"\n✓ Output: {output_file}")
    print("\nNext steps:")
    print("  - Analyze spike times and firing patterns")
    print("  - Visualize waveforms and unit locations")
    print("  - Add raw data links (Phase 3): link to .ap.bin files")
    print("  - Add LFP data (Phase 4): downsample and store LFP")

    print("\n" + "=" * 80)
    print("Example complete!")
    print("=" * 80)
