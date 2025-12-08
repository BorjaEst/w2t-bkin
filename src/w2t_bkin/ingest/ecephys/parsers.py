"""
SpikeGLX and Kilosort File Parsers.

This module provides utilities for parsing SpikeGLX .meta files and
Kilosort output files (.npy, .tsv) into structured Python data types.

All parsing functions are pure and cacheable for performance.
"""

import functools
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


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
