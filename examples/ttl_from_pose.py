#!/usr/bin/env python3
"""Example: Generate TTL Signals from DeepLabCut Pose Data.

Demonstrates how to generate mock TTL signals from DLC pose estimation data
by tracking body part movements (e.g., trial light LED) and detecting events
based on likelihood thresholds and duration constraints.

Goal
----
Show how to extract TTL timestamps from pose tracking data for:
- Trial light detection (LED markers)
- Behavioral event timestamps
- Synchronization signal generation
- Testing and validation pipelines

The generated TTL files are compatible with w2t_bkin.sync.ttl loader and can
be used as alternative sync signals when hardware TTL is unavailable.

Usage
-----
    # Generate TTL from pose H5 file
    $ python examples/ttl_from_pose.py --h5-path path/to/pose.h5

    # With custom parameters
    $ python examples/ttl_from_pose.py \
        --h5-path path/to/pose.h5 \
        --bodypart trial_light \
        --threshold 0.99 \
        --min-duration 301 \
        --fps 150.0

    # Generate for multiple cameras
    $ python examples/ttl_from_pose.py \
        --h5-path Session-001/pose_cam0.h5 \
        --h5-path Session-001/pose_cam1.h5 \
        --output-dir Session-001/TTLs

    # Using environment variables
    $ BODYPART=trial_light THRESHOLD=0.995 python examples/ttl_from_pose.py --h5-path pose.h5

Algorithm
---------
1. Load DLC H5 file and extract likelihood series for specified body part
2. Apply likelihood threshold to create boolean signal (ON/OFF)
3. Detect signal transitions (rising, falling, or both edges)
4. Filter phases by minimum duration to remove false positives
5. Convert frame indices to timestamps using camera FPS
6. Write TTL timestamps to file (one timestamp per line)

Example Scenario
----------------
Trial light tracking:
- DLC tracks LED position with high confidence when ON
- Likelihood drops below threshold when LED is OFF
- Generate TTL pulse at each LED ON event (rising edge)
- Filter brief flickers by requiring minimum ON duration (e.g., 2 seconds)
"""

from pathlib import Path
import sys
from typing import List, Optional

import pandas as pd
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, CliSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict

# Add project root to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from figures.pose import plot_ttl_detection_from_pose
from w2t_bkin.pose import TTLMockOptions, generate_ttl_from_dlc_likelihood, load_dlc_likelihood_series


class TTLFromPoseSettings(BaseSettings):
    """Settings for TTL generation from DLC pose data.

    All settings can be overridden via:
    1. Command-line arguments (highest priority)
    2. Environment variables (prefix with TTL_FROM_POSE_)
    3. Default values (lowest priority)
    """

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # Input/Output paths
    h5_path: List[Path] = Field(default_factory=list, description="Path(s) to DLC H5 pose file(s). Can specify multiple files.")
    output_dir: Optional[Path] = Field(default=None, description="Output directory for TTL files. If not specified, writes to same directory as H5 file.")
    output_suffix: str = Field(default="_ttl.txt", description="Suffix for output TTL files (e.g., 'pose.h5' -> 'pose_ttl.txt')")

    # Detection parameters
    bodypart: str = Field(default="trial_light", description="DLC body part name to track (must match keypoint in H5 file)")
    threshold: float = Field(default=0.75, ge=0.0, le=1.0, description="Minimum likelihood threshold for signal detection (0-1)")
    min_duration: int = Field(default=1, ge=1, description="Minimum duration in frames for valid signal phase (filters brief flickers)")
    fps: float = Field(default=150.0, gt=0.0, description="Camera frame rate in Hz (for converting frames to timestamps)")
    transition_type: str = Field(default="rising", description="Transition type to detect: 'rising' (ON events), 'falling' (OFF events), or 'both'")
    time_offset: float = Field(default=0.0, description="Time offset in seconds to add to all timestamps")

    # Visualization and reporting
    plot: bool = Field(default=True, description="Generate visualization plots of likelihood and detected events")
    verbose: bool = Field(default=True, description="Print detailed progress and statistics")
    dry_run: bool = Field(default=False, description="Preview detection without writing files")

    @field_validator("h5_path", mode="before")
    @classmethod
    def parse_h5_paths(cls, v):
        """Convert single path or list of paths to list."""
        if isinstance(v, (str, Path)):
            return [Path(v)]
        elif isinstance(v, list):
            return [Path(p) for p in v]
        return v

    @field_validator("transition_type")
    @classmethod
    def validate_transition_type(cls, v: str) -> str:
        """Validate transition type is one of allowed values."""
        allowed = {"rising", "falling", "both"}
        if v not in allowed:
            raise ValueError(f"transition_type must be one of {allowed}, got '{v}'")
        return v

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources to include CLI arguments."""
        return (
            init_settings,
            CliSettingsSource(settings_cls, cli_parse_args=True),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


def analyze_likelihood_statistics(h5_path: Path, bodypart: str) -> dict:
    """Analyze likelihood distribution for a body part.

    Helps determine appropriate threshold values.
    """
    likelihood = load_dlc_likelihood_series(h5_path, bodypart)

    return {
        "n_frames": len(likelihood),
        "mean": float(likelihood.mean()),
        "std": float(likelihood.std()),
        "min": float(likelihood.min()),
        "max": float(likelihood.max()),
        "median": float(likelihood.median()),
        "q25": float(likelihood.quantile(0.25)),
        "q75": float(likelihood.quantile(0.75)),
        "q95": float(likelihood.quantile(0.95)),
    }


def process_single_file(h5_path: Path, settings: TTLFromPoseSettings) -> dict:
    """Process a single DLC H5 file to generate TTL timestamps.

    Returns summary dictionary with statistics.
    """
    if not h5_path.exists():
        raise FileNotFoundError(f"H5 file not found: {h5_path}")

    print(f"\nProcessing: {h5_path}")
    print("-" * 80)

    # Create TTL generation options
    options = TTLMockOptions(
        bodypart=settings.bodypart,
        likelihood_threshold=settings.threshold,
        min_duration_frames=settings.min_duration,
        fps=settings.fps,
        transition_type=settings.transition_type,
        start_time_offset_s=settings.time_offset,
    )

    # Analyze likelihood statistics if verbose
    if settings.verbose:
        print(f"\n[Likelihood Statistics for '{settings.bodypart}']")
        try:
            stats = analyze_likelihood_statistics(h5_path, settings.bodypart)
            print(f"  Frames:      {stats['n_frames']}")
            print(f"  Mean ± Std:  {stats['mean']:.3f} ± {stats['std']:.3f}")
            print(f"  Range:       {stats['min']:.3f} - {stats['max']:.3f}")
            print(f"  Median:      {stats['median']:.3f}")
            print(f"  Q25/Q75:     {stats['q25']:.3f} / {stats['q75']:.3f}")
            print(f"  Q95:         {stats['q95']:.3f}")
            if stats["q95"] < settings.threshold:
                print(f"  ⚠ Warning: 95th percentile ({stats['q95']:.3f}) below threshold ({settings.threshold})")
                print(f"           Consider lowering threshold or checking tracking quality")
        except Exception as e:
            print(f"  ⚠ Error computing statistics: {e}")

    # Generate TTL timestamps
    print(f"\n[Generating TTL Signals]")
    print(f"  Bodypart:        {settings.bodypart}")
    print(f"  Threshold:       {settings.threshold}")
    print(f"  Min duration:    {settings.min_duration} frames ({settings.min_duration/settings.fps:.3f}s)")
    print(f"  FPS:             {settings.fps} Hz")
    print(f"  Transition type: {settings.transition_type}")

    timestamps = generate_ttl_from_dlc_likelihood(h5_path, options)

    print(f"\n[Detection Results]")
    print(f"  Events detected: {len(timestamps)}")
    if timestamps:
        print(f"  First event:     {timestamps[0]:.6f} s")
        print(f"  Last event:      {timestamps[-1]:.6f} s")
        print(f"  Time span:       {timestamps[-1] - timestamps[0]:.3f} s")
        if len(timestamps) > 1:
            intervals = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
            print(f"  Mean interval:   {sum(intervals)/len(intervals):.3f} s")
            print(f"  Interval range:  {min(intervals):.3f} - {max(intervals):.3f} s")

    # Determine output path
    if settings.output_dir:
        output_dir = settings.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{h5_path.stem}{settings.output_suffix}"
    else:
        output_path = h5_path.parent / f"{h5_path.stem}{settings.output_suffix}"

    # Write TTL file (unless dry run)
    if not settings.dry_run:
        from w2t_bkin.pose.ttl_mock import write_ttl_timestamps

        write_ttl_timestamps(timestamps, output_path)
        print(f"\n[Output]")
        print(f"  ✓ TTL file written: {output_path}")
        print(f"  Size: {output_path.stat().st_size} bytes")
    else:
        print(f"\n[Dry Run]")
        print(f"  Would write to: {output_path}")

    # Generate plots if requested
    if settings.plot and timestamps:
        print(f"\n[Visualization]")
        plot_path = h5_path.parent / f"{h5_path.stem}_ttl_detection.png"
        result_path = plot_ttl_detection_from_pose(
            h5_path=h5_path,
            bodypart=settings.bodypart,
            threshold=settings.threshold,
            timestamps=timestamps,
            fps=settings.fps,
            transition_type=settings.transition_type,
            min_duration=settings.min_duration,
            out_path=plot_path,
        )
        if result_path:
            print(f"  ✓ Saved plot: {result_path}")
        else:
            print("  ⚠ matplotlib not available, skipping plots")

    # Return summary
    return {
        "h5_path": str(h5_path),
        "output_path": str(output_path),
        "n_events": len(timestamps),
        "time_span_s": timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 0.0,
        "settings": {
            "bodypart": settings.bodypart,
            "threshold": settings.threshold,
            "min_duration_frames": settings.min_duration,
            "fps": settings.fps,
            "transition_type": settings.transition_type,
        },
    }


def main():
    """Run TTL generation from pose data."""
    # Load settings from CLI and environment via pydantic-settings
    settings = TTLFromPoseSettings()

    # Validate inputs
    if not settings.h5_path:
        print("Error: At least one --h5-path must be specified")
        return 1

    # Print header
    print("=" * 80)
    print("TTL Generation from DeepLabCut Pose Data")
    print("=" * 80)
    print(f"\nFiles to process: {len(settings.h5_path)}")
    for h5_path in settings.h5_path:
        print(f"  - {h5_path}")

    # Process each file
    results = []
    for h5_path in settings.h5_path:
        try:
            result = process_single_file(h5_path, settings)
            results.append(result)
        except Exception as e:
            print(f"\n✗ Error processing {h5_path}: {e}")
            if settings.verbose:
                import traceback

                traceback.print_exc()
            continue

    # Print summary
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"\nProcessed {len(results)} / {len(settings.h5_path)} files successfully")

    if results:
        total_events = sum(r["n_events"] for r in results)
        print(f"Total events detected: {total_events}")
        print("\nPer-file results:")
        for r in results:
            print(f"  {Path(r['h5_path']).name}: {r['n_events']} events")

        if not settings.dry_run:
            print(f"\n✓ TTL files written to:")
            for r in results:
                print(f"  {r['output_path']}")

    print("\nDone!")
    return 0


if __name__ == "__main__":
    main()
