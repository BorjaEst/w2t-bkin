"""Timebase provider abstraction and implementations.

Provides multiple timebase sources for temporal synchronization:
- **Nominal Rate**: Synthetic timestamps from constant frame rate
- **TTL**: Hardware sync signals from acquisition system
- **Neuropixels**: Neural recording stream timestamps

Example:
    >>> from w2t_bkin.sync import create_timebase_provider
    >>> from w2t_bkin.config import load_config
    >>>
    >>> config = load_config("config.toml")
    >>> provider = create_timebase_provider(config, manifest=None)
    >>> timestamps = provider.get_timestamps(n_samples=1000)
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from ..domain import Config, Manifest
from .exceptions import SyncError

__all__ = [
    "TimebaseProvider",
    "NominalRateProvider",
    "TTLProvider",
    "NeuropixelsProvider",
    "create_timebase_provider",
]


# =============================================================================
# Timebase Provider Abstraction
# =============================================================================


class TimebaseProvider(ABC):
    """Abstract base class for timebase providers.

    All timebase providers must implement get_timestamps() to return
    a list of timestamps in seconds.
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
    """Nominal rate timebase provider (synthetic timestamps).

    Generates evenly-spaced timestamps assuming a constant sample rate.
    Useful for video cameras with stable frame rates or as a fallback.

    Example:
        >>> provider = NominalRateProvider(rate=30.0, offset_s=0.0)
        >>> timestamps = provider.get_timestamps(n_samples=100)
        >>> print(f"First frame: {timestamps[0]:.3f}s")
        >>> print(f"100th frame: {timestamps[99]:.3f}s")
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
    """TTL-based timebase provider (load from hardware sync files).

    Loads actual hardware synchronization pulses from TTL files.
    Each TTL file should contain one timestamp per line.

    Example:
        >>> provider = TTLProvider(
        ...     ttl_id="camera_sync",
        ...     ttl_files=["session/TTLs/cam0.txt"],
        ...     offset_s=0.0
        ... )
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
    """Neuropixels timebase provider (stub for Phase 2).

    Future: Will load timestamps from Neuropixels neural recording streams.
    Currently generates synthetic 30 kHz timestamps as a placeholder.
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


def create_timebase_provider(config: Config, manifest: Optional[Manifest] = None) -> TimebaseProvider:
    """Create timebase provider from configuration.

    Factory function that instantiates the appropriate TimebaseProvider
    subclass based on config.timebase.source.

    Args:
        config: Pipeline configuration with timebase settings
        manifest: Session manifest (required for TTL provider)

    Returns:
        TimebaseProvider instance (NominalRateProvider, TTLProvider, or NeuropixelsProvider)

    Raises:
        SyncError: If invalid source or missing required data

    Example:
        >>> from w2t_bkin.config import load_config
        >>> config = load_config("config.toml")
        >>> provider = create_timebase_provider(config, manifest=None)
        >>> timestamps = provider.get_timestamps(n_samples=1000)
    """
    source = config.timebase.source
    offset_s = config.timebase.offset_s

    if source == "nominal_rate":
        # Default to 30 Hz for cameras
        rate = 30.0
        return NominalRateProvider(rate=rate, offset_s=offset_s)

    elif source == "ttl":
        if manifest is None:
            raise SyncError("Manifest required for TTL timebase provider")

        ttl_id = config.timebase.ttl_id
        if not ttl_id:
            raise SyncError("timebase.ttl_id required when source='ttl'")

        # Find TTL files in manifest
        ttl_files = None
        for ttl in manifest.ttls:
            if ttl.ttl_id == ttl_id:
                ttl_files = ttl.files
                break

        if not ttl_files:
            raise SyncError(f"TTL {ttl_id} not found in manifest")

        return TTLProvider(ttl_id=ttl_id, ttl_files=ttl_files, offset_s=offset_s)

    elif source == "neuropixels":
        stream = config.timebase.neuropixels_stream
        if not stream:
            raise SyncError("timebase.neuropixels_stream required when source='neuropixels'")

        return NeuropixelsProvider(stream=stream, offset_s=offset_s)

    else:
        raise SyncError(f"Invalid timebase source: {source}")
