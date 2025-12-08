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

from synthetic import build_interim_folder, build_raw_folder
from w2t_bkin.figures.ecephys import plot_electrode_locations, plot_firing_rate_distribution, plot_spike_raster, plot_unit_quality_metrics
from w2t_bkin.ingest.kilosort import build_units_table_from_kilosort
from w2t_bkin.ingest.spikeglx import build_device_from_meta, build_electrode_group_from_meta, build_electrodes_table_from_meta, parse_spikeglx_meta


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

    # Generate synthetic raw session with SpikeGLX metadata
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

    # Generate synthetic interim folder with Kilosort output
    interim_result = build_interim_folder(
        interim_root=settings.output_root / "interim",
        subject_id=settings.subject_id,
        session_id=settings.session_id,
        pose_camera_ids=[],  # No pose data for this example
        kilosort_probe_ids=[settings.probe_id],
        n_units=settings.n_units,
        n_channels=settings.n_channels,
        sampling_rate=settings.sampling_rate,
        recording_duration_s=settings.recording_duration_s,
        firing_rate_mean=5.0,
        firing_rate_std=3.0,
        good_unit_fraction=0.70,
        noise_unit_fraction=0.15,
        seed=settings.seed,
    )

    meta_path = raw_result.ecephys_meta_paths[0]
    kilosort_dir = interim_result.kilosort_paths[settings.probe_id]

    print(f"\n✓ Synthetic artifacts:")
    print(f"  - SpikeGLX metadata: {meta_path}")
    print(f"  - Kilosort directory: {kilosort_dir}")
    print(f"  - Spike times:       {kilosort_dir / 'spike_times.npy'}")
    print(f"  - Cluster info:      {kilosort_dir / 'cluster_info.tsv'}")
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
    device = build_device_from_meta(meta, settings.probe_id)
    nwbfile.add_device(device)
    print(f"\n✓ Created Device: {device.name}")

    # Create electrode group
    group_name = f"probe_{settings.probe_id}"
    electrode_group = build_electrode_group_from_meta(
        name=group_name,
        device=device,
        location=settings.location,
        meta=meta,
    )
    nwbfile.add_electrode_group(electrode_group)

    # Build and add electrodes
    electrode_rows = build_electrodes_table_from_meta(
        meta=meta,
        electrode_group=electrode_group,
        location=settings.location,
    )
    for row in electrode_rows:
        nwbfile.add_electrode(**row)

    n_electrodes = len(electrode_rows)
    print(f"\n✓ Added {n_electrodes} electrodes to table")

    # ---------------------------------------------------------------------
    # PHASE 2: Add Spike Sorting Data
    # ---------------------------------------------------------------------
    print_section("PHASE 2: Add Spike Sorting Data")

    print(f"\nAdding units from Kilosort:")
    print(f"  - Directory:        {kilosort_dir}")
    print(f"  - Quality filter:   {settings.quality_labels}")
    print(f"  - Min spike count:  {settings.min_spike_count}")

    # Build units table data
    units_list = build_units_table_from_kilosort(
        sorting_dir=kilosort_dir,
        probe_id=settings.probe_id,
        sampling_rate=meta["sampling_rate"],
        include_labels=settings.quality_labels,
        min_spike_count=settings.min_spike_count,
        include_waveforms=True,
        include_metrics=True,
    )

    # Extract stats (last element with __stats__ key) and remove it from list
    result = units_list[-1].pop("__stats__")
    units_list = units_list[:-1]  # Remove the now-empty last element

    # Determine which custom columns to add by checking what's available in ALL units
    if units_list:
        # Check first unit to see what optional columns are available
        sample_keys = set(units_list[0].keys())

        # Verify all units have the same optional columns
        for unit_data in units_list:
            sample_keys &= set(unit_data.keys())

        # Add columns that are present in all units
        if "contamination_pct" in sample_keys:
            nwbfile.add_unit_column(name="contamination_pct", description="Contamination percentage from Kilosort")
        if "amplitude" in sample_keys:
            nwbfile.add_unit_column(name="amplitude", description="Spike amplitude (μV)")
        if "probe_id" in sample_keys:
            nwbfile.add_unit_column(name="probe_id", description="Probe identifier (e.g., imec0)")

    # Add units to NWBFile
    for unit_data in units_list:
        nwbfile.add_unit(**unit_data)

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
    # PHASE 5: Generate Figures
    # ---------------------------------------------------------------------
    print_section("PHASE 5: Generate Figures")

    figures_dir = settings.output_root / "figures"
    figures_dir.mkdir(exist_ok=True)

    # Read NWB and extract data for plotting
    with NWBHDF5IO(str(output_file), mode="r") as io:
        read_nwb = io.read()
        electrodes_df = read_nwb.electrodes.to_dataframe()
        units_df = read_nwb.units.to_dataframe() if read_nwb.units is not None else None

    print("\nGenerating figures...")

    # Plot 1: Electrode locations
    electrode_map_path = figures_dir / "electrode_locations.png"
    result = plot_electrode_locations(electrodes_df, out_path=electrode_map_path)
    if result:
        print(f"  ✓ Saved: {electrode_map_path}")
    else:
        print("  ⚠ Skipped electrode locations plot (matplotlib not available)")

    # Plot 2-4: Unit-related plots (only if units exist)
    if units_df is not None and len(units_df) > 0:
        # Plot 2: Spike raster (first 10 seconds)
        raster_path = figures_dir / "spike_raster.png"
        result = plot_spike_raster(
            units_df,
            out_path=raster_path,
            time_range=(0, min(10.0, settings.recording_duration_s)),
            max_units=20,
        )
        if result:
            print(f"  ✓ Saved: {raster_path}")
        else:
            print("  ⚠ Skipped spike raster plot (matplotlib not available)")

        # Plot 3: Firing rate distribution
        firing_rate_path = figures_dir / "firing_rate_distribution.png"
        result = plot_firing_rate_distribution(
            units_df,
            out_path=firing_rate_path,
            recording_duration=settings.recording_duration_s,
        )
        if result:
            print(f"  ✓ Saved: {firing_rate_path}")
        else:
            print("  ⚠ Skipped firing rate plot (matplotlib not available)")

        # Plot 4: Quality metrics (if columns exist)
        quality_metrics_path = figures_dir / "unit_quality_metrics.png"
        result = plot_unit_quality_metrics(units_df, out_path=quality_metrics_path)
        if result:
            print(f"  ✓ Saved: {quality_metrics_path}")
        else:
            print("  ⚠ Skipped quality metrics plot (missing columns or matplotlib)")
    else:
        print("  ⚠ Skipping unit plots (no units in file)")

    # List all generated figures
    figures_written = [p for p in [electrode_map_path, raster_path, firing_rate_path, quality_metrics_path] if p.exists()]
    if figures_written:
        print(f"\n✓ Generated {len(figures_written)} figure(s):")
        for p in figures_written:
            print(f"  - {p}")

    # ---------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------
    print_section("Summary")

    print("\n✓ Successfully created NWB file with complete ecephys data:")
    print(f"  1. Device: {device.name}")
    print(f"  2. Electrode Group: {group_name}")
    print(f"  3. Electrodes: {n_electrodes} channels")
    print(f"  4. Units: {n_units} sorted units (quality-filtered)")
    print(f"\n✓ Output: {output_file}")
    if figures_written:
        print(f"\n✓ Figures: {len(figures_written)} plot(s) in {figures_dir}")
    print("\nNext steps:")
    print("  - Analyze spike times and firing patterns")
    print("  - Visualize waveforms and unit locations")
    print("  - Add raw data links (Phase 3): link to .ap.bin files")
    print("  - Add LFP data (Phase 4): downsample and store LFP")

    print("\n" + "=" * 80)
    print("Example complete!")
    print("=" * 80)
