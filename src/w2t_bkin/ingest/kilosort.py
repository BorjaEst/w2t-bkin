"""
Kilosort Spike Sorting Output Ingestion.

This module provides utilities for loading Kilosort output files (.npy, .tsv)
and building data structures for NWB Units tables.

Architecture Layer: Ingest (returns NWB objects, does not attach to NWBFile)
- Returns data structures (dicts, lists) that can be passed to nwbfile.add_unit()
- Pipeline layer is responsible for adding units to NWBFile
- No imports from config, Session, or Manifest
- All functions accept primitives only (file paths, strings, numbers)

Example Usage:
    >>> from pathlib import Path
    >>> from w2t_bkin.ingest.kilosort import load_kilosort_data, load_cluster_labels
    >>>
    >>> # Load spike data
    >>> data = load_kilosort_data(Path("interim/neural/kilosort/imec0"))
    >>> spike_times = data["spike_times"]  # Sample indices
    >>> spike_clusters = data["spike_clusters"]  # Cluster assignments
    >>>
    >>> # Load quality labels
    >>> labels = load_cluster_labels(Path("interim/neural/kilosort/imec0"))
    >>> good_units = labels[labels['KSLabel'] == 'good']
    >>>
    >>> # Build units table data
    >>> units = build_units_table_from_kilosort(
    ...     sorting_dir=Path("interim/neural/kilosort/imec0"),
    ...     probe_id="imec0",
    ...     sampling_rate=30000.0,
    ...     include_labels=["good", "mua"],
    ... )
    >>> # Pipeline layer adds to nwbfile:
    >>> for unit_data in units:
    ...     nwbfile.add_unit(**unit_data)
"""

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def load_kilosort_data(sorting_dir: Path) -> Dict[str, Optional[np.ndarray]]:
    """
    Load core Kilosort output files into memory.

    Args:
        sorting_dir: Path to Kilosort output directory
                     (e.g., interim/neural/kilosort/imec0/)

    Returns:
        Dictionary with numpy arrays:
            {
                "spike_times": np.ndarray[int64],     # Shape: (n_spikes,)
                "spike_clusters": np.ndarray[int32],  # Shape: (n_spikes,)
                "templates": np.ndarray[float32] | None,  # Shape: (n_templates, n_samples, n_channels)
            }

    Raises:
        FileNotFoundError: If required files (spike_times.npy, spike_clusters.npy) are missing

    Example:
        >>> data = load_kilosort_data(Path("interim/neural/kilosort/imec0"))
        >>> data["spike_times"].shape
        (150000,)  # 150k spikes
        >>> data["spike_clusters"].shape
        (150000,)
    """
    sorting_dir = Path(sorting_dir)

    # Load required files
    spike_times_path = sorting_dir / "spike_times.npy"
    spike_clusters_path = sorting_dir / "spike_clusters.npy"

    if not spike_times_path.exists():
        raise FileNotFoundError(f"Required file not found: {spike_times_path}")
    if not spike_clusters_path.exists():
        raise FileNotFoundError(f"Required file not found: {spike_clusters_path}")

    spike_times = np.load(spike_times_path).flatten()  # Ensure 1D
    spike_clusters = np.load(spike_clusters_path).flatten()

    # Load optional templates file
    templates_path = sorting_dir / "templates.npy"
    templates = np.load(templates_path) if templates_path.exists() else None

    return {
        "spike_times": spike_times,
        "spike_clusters": spike_clusters,
        "templates": templates,
    }


def load_cluster_labels(sorting_dir: Path) -> pd.DataFrame:
    """
    Load cluster quality labels from Kilosort/Phy curation files.

    Tries multiple file formats in order of preference:
    1. cluster_info.tsv (newer Kilosort 4)
    2. cluster_KSLabel.tsv (older Kilosort versions)

    Args:
        sorting_dir: Path to Kilosort output directory

    Returns:
        DataFrame with at least columns: ['cluster_id', 'KSLabel']
        Additional columns may include: 'ch', 'Amplitude', 'ContamPct', etc.

    Raises:
        FileNotFoundError: If no cluster label file found

    Example:
        >>> labels = load_cluster_labels(Path("interim/neural/kilosort/imec0"))
        >>> labels[labels['KSLabel'] == 'good'].shape[0]
        85  # 85 good units
    """
    sorting_dir = Path(sorting_dir)

    # Try cluster_info.tsv first (most complete)
    cluster_info_path = sorting_dir / "cluster_info.tsv"
    if cluster_info_path.exists():
        df = pd.read_csv(cluster_info_path, sep="\t")
        # Ensure required columns exist
        if "cluster_id" not in df.columns:
            df["cluster_id"] = df.index if "id" not in df.columns else df["id"]
        if "KSLabel" not in df.columns and "group" in df.columns:
            df["KSLabel"] = df["group"]  # Phy uses 'group' column
        return df

    # Fallback to cluster_KSLabel.tsv
    ks_label_path = sorting_dir / "cluster_KSLabel.tsv"
    if ks_label_path.exists():
        df = pd.read_csv(ks_label_path, sep="\t")
        if "cluster_id" not in df.columns:
            df["cluster_id"] = df.index
        return df

    raise FileNotFoundError(f"No cluster label file found in {sorting_dir}. " f"Looked for: cluster_info.tsv, cluster_KSLabel.tsv")


def load_cluster_metrics(sorting_dir: Path) -> Optional[pd.DataFrame]:
    """
    Load cluster quality metrics from Kilosort output.

    Loads ContamPct, Amplitude, and other quality metrics if available.
    This is optional data that enriches the Units table.

    Args:
        sorting_dir: Path to Kilosort output directory

    Returns:
        DataFrame with columns: ['cluster_id', 'ContamPct', 'Amplitude', ...]
        Returns None if no metric files found.

    Example:
        >>> metrics = load_cluster_metrics(Path("interim/neural/kilosort/imec0"))
        >>> if metrics is not None:
        ...     low_contamination = metrics[metrics['ContamPct'] < 0.1]
    """
    sorting_dir = Path(sorting_dir)

    # Try loading from cluster_info.tsv first (contains most metrics)
    cluster_info_path = sorting_dir / "cluster_info.tsv"
    if cluster_info_path.exists():
        df = pd.read_csv(cluster_info_path, sep="\t")
        metric_cols = ["ContamPct", "Amplitude", "amp", "contamination"]
        available_cols = [col for col in metric_cols if col in df.columns]
        if available_cols:
            result = df[["cluster_id"] + available_cols] if "cluster_id" in df.columns else df
            return result

    # Try individual metric files
    contam_path = sorting_dir / "cluster_ContamPct.tsv"
    amp_path = sorting_dir / "cluster_Amplitude.tsv"

    dfs = []
    if contam_path.exists():
        contam_df = pd.read_csv(contam_path, sep="\t")
        if "cluster_id" not in contam_df.columns:
            contam_df["cluster_id"] = contam_df.index
        dfs.append(contam_df)

    if amp_path.exists():
        amp_df = pd.read_csv(amp_path, sep="\t")
        if "cluster_id" not in amp_df.columns:
            amp_df["cluster_id"] = amp_df.index
        dfs.append(amp_df)

    if dfs:
        # Merge all metric dataframes on cluster_id
        result = dfs[0]
        for df in dfs[1:]:
            result = result.merge(df, on="cluster_id", how="outer")
        return result

    return None


def build_units_table_from_kilosort(
    sorting_dir: Path,
    probe_id: str,
    sampling_rate: float,
    include_labels: Optional[List[str]] = None,
    min_spike_count: int = 0,
    include_waveforms: bool = False,
    include_metrics: bool = True,
) -> List[Dict]:
    """
    Build units table data from Kilosort spike sorting output.

    Loads spike times, cluster labels, and quality metrics from Kilosort output
    directory and returns a list of unit dictionaries ready to be added to NWBFile.

    This function does NOT modify NWBFile - pipeline layer is responsible for:
    1. Adding custom columns (contamination_pct, amplitude, probe_id)
    2. Calling nwbfile.add_unit(**unit_data) for each unit

    Args:
        sorting_dir: Path to Kilosort output directory (e.g., "interim/neural/kilosort/imec0")
        probe_id: Probe identifier for unit naming (e.g., "imec0")
        sampling_rate: Sampling rate in Hz for time conversion (from .meta file)
        include_labels: Quality labels to include (default: ["good", "mua"])
                       Common labels: "good", "mua", "noise"
        min_spike_count: Minimum spike count threshold (default: 0)
        include_waveforms: If True, include mean waveforms from templates.npy
        include_metrics: If True, include quality metrics as custom columns

    Returns:
        List of unit dictionaries, each containing:
            - spike_times: np.ndarray (seconds)
            - probe_id: str
            - electrodes: List[int] (optional, if electrode mapping available)
            - waveform_mean: np.ndarray (optional, if include_waveforms=True)
            - contamination_pct: float (optional, if include_metrics=True)
            - amplitude: float (optional, if include_metrics=True)

        Also returns filtering stats in last dict element with key '__stats__'.

    Raises:
        FileNotFoundError: If required Kilosort files are missing
        ValueError: If sampling_rate <= 0

    Example:
        >>> from pathlib import Path
        >>>
        >>> # Build units table data
        >>> units = build_units_table_from_kilosort(
        ...     sorting_dir=Path("interim/neural/kilosort/imec0"),
        ...     probe_id="imec0",
        ...     sampling_rate=30000.0,
        ...     include_labels=["good", "mua"],
        ...     min_spike_count=100,
        ... )
        >>>
        >>> # Pipeline layer adds custom columns first:
        >>> nwbfile.add_unit_column(name="contamination_pct", description="...")
        >>> nwbfile.add_unit_column(name="amplitude", description="...")
        >>> nwbfile.add_unit_column(name="probe_id", description="...")
        >>>
        >>> # Then adds units:
        >>> stats = units[-1].pop('__stats__')  # Extract stats
        >>> for unit_data in units:
        ...     nwbfile.add_unit(**unit_data)
        >>> print(f"Added {stats['n_units_added']} units")
    """
    # Validate inputs
    if sampling_rate <= 0:
        raise ValueError(f"sampling_rate must be positive, got {sampling_rate}")

    sorting_dir = Path(sorting_dir)
    if include_labels is None:
        include_labels = ["good", "mua"]  # Default: good units and multi-unit activity

    # Load spike data
    spike_data = load_kilosort_data(sorting_dir)
    spike_times = spike_data["spike_times"]  # Sample indices
    spike_clusters = spike_data["spike_clusters"]  # Cluster assignments
    templates = spike_data["templates"]  # Optional waveforms

    # Load cluster labels
    cluster_labels = load_cluster_labels(sorting_dir)

    # Load quality metrics (optional)
    cluster_metrics = None
    if include_metrics:
        cluster_metrics = load_cluster_metrics(sorting_dir)

    # Initialize stats tracking
    stats = {
        "n_units_added": 0,
        "n_units_filtered": 0,
        "n_spikes_total": 0,
        "filter_reasons": {
            "quality_label": 0,
            "spike_count": 0,
            "missing_label": 0,
        },
    }

    # Build list of unit data dictionaries
    units_list = []
    unique_clusters = np.unique(spike_clusters)

    for cluster_id in unique_clusters:
        # Get cluster info
        cluster_row = cluster_labels[cluster_labels["cluster_id"] == cluster_id]

        if cluster_row.empty:
            stats["n_units_filtered"] += 1
            stats["filter_reasons"]["missing_label"] += 1
            continue

        ks_label = cluster_row["KSLabel"].iloc[0]

        # Filter by quality label
        if ks_label not in include_labels:
            stats["n_units_filtered"] += 1
            stats["filter_reasons"]["quality_label"] += 1
            continue

        # Get spike times for this cluster
        cluster_mask = spike_clusters == cluster_id
        cluster_spike_samples = spike_times[cluster_mask]

        # Filter by spike count
        if len(cluster_spike_samples) < min_spike_count:
            stats["n_units_filtered"] += 1
            stats["filter_reasons"]["spike_count"] += 1
            continue

        # Convert spike times from samples to seconds
        cluster_spike_times = cluster_spike_samples / sampling_rate

        # Get electrode mapping (optional, from cluster_info if available)
        electrode_id = None
        if "ch" in cluster_row.columns:
            electrode_id = int(cluster_row["ch"].iloc[0])

        # Prepare unit data dictionary
        unit_data = {
            "spike_times": cluster_spike_times,
            "probe_id": probe_id,
        }

        # Add electrode reference if available
        if electrode_id is not None:
            unit_data["electrodes"] = [electrode_id]

        # Add waveform if requested and available
        if include_waveforms and templates is not None:
            # templates shape: (n_clusters, n_samples, n_channels)
            if cluster_id < templates.shape[0]:
                unit_data["waveform_mean"] = templates[cluster_id]

        # Add quality metrics if available
        if include_metrics and cluster_metrics is not None:
            metric_row = cluster_metrics[cluster_metrics["cluster_id"] == cluster_id]
            if not metric_row.empty:
                if "ContamPct" in cluster_metrics.columns:
                    unit_data["contamination_pct"] = float(metric_row["ContamPct"].iloc[0])
                if "Amplitude" in cluster_metrics.columns:
                    unit_data["amplitude"] = float(metric_row["Amplitude"].iloc[0])
                elif "amp" in cluster_metrics.columns:
                    unit_data["amplitude"] = float(metric_row["amp"].iloc[0])

        # Add to list
        units_list.append(unit_data)

        # Update stats
        stats["n_units_added"] += 1
        stats["n_spikes_total"] += len(cluster_spike_times)

    # Append stats as last element (with special key for identification)
    units_list.append({"__stats__": stats})

    return units_list


__all__ = [
    "load_kilosort_data",
    "load_cluster_labels",
    "load_cluster_metrics",
    "build_units_table_from_kilosort",
]
