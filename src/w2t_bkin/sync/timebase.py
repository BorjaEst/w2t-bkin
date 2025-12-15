"""Timebase providers for temporal synchronization.

Provides nominal rate, TTL, and Neuropixels timebase sources.

Example:
    >>> from w2t_bkin.sync import create_timebase_provider
    >>> provider = create_timebase_provider(source="nominal_rate", rate=30.0)
    >>> timestamps = provider.get_timestamps(n_samples=100)
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional

from w2t_bkin.exceptions import SyncError

# =============================================================================
# Timebase Provider Abstraction
# =============================================================================


class TimebaseProvider(ABC):
    """Base class for timebase providers.

    Subclasses must implement get_timestamps().
    """

    def __init__(self, source: str, offset_s: float = 0.0):
        """Initialize timebase provider.

        Args:
            source: Identifier for timebase source (e.g., "nominal_rate", "ttl")
            offset_s: Time offset to apply to all timestamps
        """
        self.source = source
        self.offset_s = offset_s

    @abstractmethod
    def get_timestamps(self, n_samples: Optional[int] = None) -> List[float]:
        """Get timestamps from this timebase.

        Args:
            n_samples: Number of samples (required for synthetic timebases)

        Returns:
            List of timestamps in seconds
        """
        pass


class NominalRateProvider(TimebaseProvider):
    """Generate timestamps from constant sample rate.

    Example:
        >>> provider = NominalRateProvider(rate=30.0)
        >>> timestamps = provider.get_timestamps(n_samples=100)
    """

    def __init__(self, rate: float, offset_s: float = 0.0):
        """Initialize nominal rate provider.

        Args:
            rate: Sample rate in Hz (e.g., 30.0 for 30 fps video)
            offset_s: Time offset to apply to all timestamps
        """
        super().__init__(source="nominal_rate", offset_s=offset_s)
        self.rate = rate

    def get_timestamps(self, n_samples: Optional[int] = None) -> List[float]:
        """Generate synthetic timestamps from nominal rate.

        Args:
            n_samples: Number of samples to generate (required)

        Returns:
            List of timestamps starting at offset_s

        Raises:
            ValueError: If n_samples is None
        """
        if n_samples is None:
            raise ValueError("n_samples required for NominalRateProvider")

        timestamps = [self.offset_s + i / self.rate for i in range(n_samples)]
        return timestamps


class TTLProvider(TimebaseProvider):
    """Load timestamps from TTL hardware sync files.

    Example:
        >>> provider = TTLProvider(ttl_id="camera_sync", ttl_files=["TTLs/cam0.txt"])
        >>> timestamps = provider.get_timestamps()
    """

    def __init__(self, ttl_id: str, ttl_files: List[str], offset_s: float = 0.0):
        """Initialize TTL provider.

        Args:
            ttl_id: Identifier for this TTL channel
            ttl_files: List of TTL file paths to load
            offset_s: Time offset to apply to all timestamps

        Raises:
            SyncError: If TTL files cannot be loaded or parsed
        """
        super().__init__(source="ttl", offset_s=offset_s)
        self.ttl_id = ttl_id
        self.ttl_files = ttl_files
        self._timestamps = None
        self._load_timestamps()

    def _load_timestamps(self):
        """Load timestamps from TTL files.

        Raises:
            SyncError: If TTL file not found or invalid format
        """
        timestamps = []

        for ttl_file in self.ttl_files:
            path = Path(ttl_file)
            if not path.exists():
                raise SyncError(f"TTL file not found: {ttl_file}")

            try:
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            timestamps.append(float(line))
            except Exception as e:
                raise SyncError(f"Failed to parse TTL file {ttl_file}: {e}")

        # Apply offset and sort
        self._timestamps = [t + self.offset_s for t in sorted(timestamps)]

    def get_timestamps(self, n_samples: Optional[int] = None) -> List[float]:
        """Get timestamps from TTL files.

        Args:
            n_samples: Ignored for TTL provider (returns all loaded timestamps)

        Returns:
            List of timestamps from TTL files (sorted)
        """
        return self._timestamps


class NeuropixelsProvider(TimebaseProvider):
    """Load timestamps from Neuropixels recordings (stub).

    Currently generates synthetic 30 kHz timestamps.
    """

    def __init__(self, stream: str, offset_s: float = 0.0):
        """Initialize Neuropixels provider.

        Args:
            stream: Neuropixels stream identifier
            offset_s: Time offset to apply
        """
        super().__init__(source="neuropixels", offset_s=offset_s)
        self.stream = stream

    def get_timestamps(self, n_samples: Optional[int] = None) -> List[float]:
        """Get timestamps from Neuropixels stream (stub).

        Args:
            n_samples: Number of samples (default: 1000)

        Returns:
            Stub timestamps at 30 kHz sampling rate
        """
        if n_samples is None:
            n_samples = 1000

        # Stub: 30 kHz sampling
        rate = 30000.0
        timestamps = [self.offset_s + i / rate for i in range(n_samples)]
        return timestamps


# =============================================================================
# Factory Function
# =============================================================================


def create_timebase_provider(
    source: str,
    offset_s: float = 0.0,
    rate: Optional[float] = None,
    ttl_id: Optional[str] = None,
    ttl_files: Optional[List[str]] = None,
    neuropixels_stream: Optional[str] = None,
) -> TimebaseProvider:
    """Create timebase provider.

    Args:
        source: "nominal_rate", "ttl", or "neuropixels"
        offset_s: Time offset in seconds
        rate: Sample rate (required for nominal_rate)
        ttl_id: TTL channel ID (required for ttl)
        ttl_files: TTL file paths (required for ttl)
        neuropixels_stream: Stream ID (required for neuropixels)

    Returns:
        TimebaseProvider instance

    Raises:
        SyncError: Invalid source or missing parameters

    Example:
        >>> provider = create_timebase_provider(source="nominal_rate", rate=30.0)
        >>> timestamps = provider.get_timestamps(n_samples=100)
    """
    if source == "nominal_rate":
        if rate is None:
            raise SyncError("rate required when source='nominal_rate'")
        return NominalRateProvider(rate=rate, offset_s=offset_s)

    elif source == "ttl":
        if ttl_id is None:
            raise SyncError("ttl_id required when source='ttl'")
        if ttl_files is None:
            raise SyncError("ttl_files required when source='ttl'")
        return TTLProvider(ttl_id=ttl_id, ttl_files=ttl_files, offset_s=offset_s)

    elif source == "neuropixels":
        if neuropixels_stream is None:
            raise SyncError("neuropixels_stream required when source='neuropixels'")
        return NeuropixelsProvider(stream=neuropixels_stream, offset_s=offset_s)

    else:
        raise SyncError(f"Invalid timebase source: {source}")


def create_timebase_provider_from_config(config, manifest: Optional[Any] = None) -> TimebaseProvider:
    """Create timebase provider from Config and Manifest (high-level wrapper).

    Convenience wrapper that extracts primitive arguments from Config/Manifest
    and delegates to the low-level create_timebase_provider() function.

    Args:
        config: Pipeline configuration with synchronization settings
        manifest: Session manifest (required for hardware_pulse provider)

    Returns:
        TimebaseProvider instance

    Raises:
        SyncError: If invalid strategy or missing required data

    Example:
        >>> from w2t_bkin.config import load_config
        >>> from w2t_bkin.ingest import build_and_count_manifest
        >>>
        >>> config = load_config("config.toml")
        >>> session = load_session("metadata.toml")
        >>> manifest = build_and_count_manifest(config, session)
        >>>
        >>> provider = create_timebase_provider_from_config(config, manifest)
        >>> timestamps = provider.get_timestamps(n_samples=1000)
    """
    strategy = config.synchronization.strategy
    offset_s = config.synchronization.alignment.global_offset_s

    if strategy == "rate_based":
        # Default to 30 Hz for cameras
        rate = 30.0
        return create_timebase_provider(source="nominal_rate", rate=rate, offset_s=offset_s)

    elif strategy == "hardware_pulse":
        if manifest is None:
            raise SyncError("Manifest required for hardware_pulse timebase provider")

        ttl_id = config.synchronization.reference_channel
        if not ttl_id:
            raise SyncError("synchronization.reference_channel required when strategy='hardware_pulse'")

        # Find TTL files in manifest
        ttl_files = None
        for ttl in manifest.ttls:
            if ttl.ttl_id == ttl_id:
                ttl_files = ttl.files
                break

        if not ttl_files:
            raise SyncError(f"TTL {ttl_id} not found in manifest")

        return create_timebase_provider(source="ttl", ttl_id=ttl_id, ttl_files=ttl_files, offset_s=offset_s)

    elif strategy == "network_stream":
        stream = config.synchronization.reference_channel
        if not stream:
            raise SyncError("synchronization.reference_channel required when strategy='network_stream'")

        return create_timebase_provider(source="neuropixels", neuropixels_stream=stream, offset_s=offset_s)

    else:
        raise SyncError(f"Invalid synchronization strategy: {strategy}")
