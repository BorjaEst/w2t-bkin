#!/usr/bin/env python3
"""DeepLabCut Pose to TTL Signal Converter

Converts DeepLabCut pose estimation data to mock TTL synchronization signals
by tracking body part movements and detecting events based on likelihood thresholds.

This script generates TTL timestamp files compatible with w2t_bkin.sync modules,
enabling synchronization workflows when hardware TTL signals are unavailable.

Purpose
-------
Generate mock TTL signals from DLC H5 pose files for:
- Trial light detection (LED markers)
- Behavioral event timestamps
- Camera synchronization signal generation
- Testing and validation of sync pipelines

Requirements
------------
- DLC H5 file with 3-level MultiIndex format (scorer, bodypart, coords)
- Specified body part must exist in the pose data
- Valid likelihood threshold and minimum duration parameters

Usage
-----
Basic usage:
    $ python scripts/pose2ttl.py --input-file path/to/pose.h5

With parameters:
    $ python scripts/pose2ttl.py \\
        --input-file path/to/pose.h5 \\
        --output-file path/to/output.txt \\
        --bodypart trial_light \\
        --threshold 0.99 \\
        --min-duration 301 \\
        --fps 150.0 \\
        --transition-type rising

Process multiple files with shell loop:
    $ for f in data/*.h5; do \\
        python scripts/pose2ttl.py --input-file "$f"; \\
      done

See Also
--------
- w2t_bkin.sync.ttl_mock: Core TTL generation functions
- w2t_bkin.sync: TTL synchronization utilities
- scripts/mat2json.py: Similar script structure pattern
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Add project root to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from w2t_bkin.figures.pose import plot_ttl_detection_from_pose
from w2t_bkin.sync.ttl_mock import TTLMockOptions, generate_ttl_from_dlc_likelihood, write_ttl_timestamps


class TTLConverterSettings(BaseSettings):
    """Configuration settings for DLC pose to TTL conversion.

    Attributes:
        input_file: Path to the input DLC H5 pose file
        output_file: Path to the output TTL file (default: same name with _ttl.txt suffix)
        bodypart: DLC body part name to track for event detection
        threshold: Minimum likelihood threshold for signal detection (0-1)
        min_duration: Minimum duration in frames for valid signal phase
        fps: Camera frame rate in Hz for timestamp conversion
        transition_type: Type of transition to detect ('rising', 'falling', or 'both')
        time_offset: Time offset in seconds to add to all timestamps
        plot: Display visualization plot of detection results
        verbose: Enable detailed output during conversion
    """

    model_config = SettingsConfigDict(cli_parse_args=True)

    input_file: Path = Field(..., description="Path to the input DLC H5 pose file")
    output_file: Path | None = Field(None, description="Path to the output TTL file")
    bodypart: str = Field(default="trial_light", description="DLC body part name to track")
    threshold: float = Field(default=0.99, ge=0.0, le=1.0, description="Likelihood threshold (0-1)")
    min_duration: int = Field(default=1, ge=1, description="Minimum duration in frames")
    fps: float = Field(default=150.0, gt=0.0, description="Camera frame rate in Hz")
    transition_type: str = Field(default="rising", description="Transition type: rising, falling, or both")
    time_offset: float = Field(default=0.0, description="Time offset in seconds")
    plot: bool = Field(default=False, description="Display visualization plot of detection")
    verbose: bool = Field(default=False, description="Enable verbose output")

    @field_validator("input_file")
    @classmethod
    def validate_input_file(cls, v: Path) -> Path:
        """Validate that the input file exists and has .h5 extension."""
        if not v.exists():
            raise ValueError(f"Input file does not exist: {v}")
        if not v.is_file():
            raise ValueError(f"Input path is not a file: {v}")
        if v.suffix.lower() != ".h5":
            raise ValueError(f"Input file must have .h5 extension, got: {v.suffix}")
        return v

    @field_validator("transition_type")
    @classmethod
    def validate_transition_type(cls, v: str) -> str:
        """Validate transition type is one of allowed values."""
        allowed = {"rising", "falling", "both"}
        if v not in allowed:
            raise ValueError(f"transition_type must be one of {allowed}, got '{v}'")
        return v

    @model_validator(mode="after")
    def set_default_output(self) -> TTLConverterSettings:
        """Set default output filename based on input filename if not provided."""
        if self.output_file is None:
            self.output_file = self.input_file.with_name(f"{self.input_file.stem}_ttl.txt")
        return self


class TTLGenerator:
    """Generates TTL timestamps from DLC pose likelihood data.

    This class encapsulates the core logic for converting DLC pose estimation
    likelihood values into TTL synchronization timestamps using configurable
    detection parameters.
    """

    def __init__(self, settings: TTLConverterSettings):
        """Initialize the generator with settings.

        Args:
            settings: Configuration settings for TTL generation
        """
        self.settings = settings

    def generate(self) -> List[float]:
        """Generate TTL timestamps from the input H5 file.

        Returns:
            List of TTL timestamps in seconds

        Raises:
            PoseError: If H5 file is invalid, body part not found, or generation fails
        """
        # Create TTL generation options from settings
        options = TTLMockOptions(
            bodypart=self.settings.bodypart,
            likelihood_threshold=self.settings.threshold,
            min_duration_frames=self.settings.min_duration,
            fps=self.settings.fps,
            transition_type=self.settings.transition_type,
            start_time_offset_s=self.settings.time_offset,
        )

        # Generate timestamps using w2t_bkin API
        timestamps = generate_ttl_from_dlc_likelihood(self.settings.input_file, options)

        return timestamps


class TTLProcessor:
    """High-level processor orchestrating DLC pose to TTL conversion."""

    def __init__(self, settings: TTLConverterSettings):
        """Initialize the processor with settings.

        Args:
            settings: Configuration settings for the conversion
        """
        self.settings = settings
        self.generator = TTLGenerator(settings)

    def process(self) -> None:
        """Execute the conversion from DLC pose to TTL file.

        Raises:
            PoseError: If conversion fails at any stage
            IOError: If file writing fails
        """
        if self.settings.verbose:
            print(f"Processing: {self.settings.input_file}")
            print(f"  Bodypart:        {self.settings.bodypart}")
            print(f"  Threshold:       {self.settings.threshold}")
            print(f"  Min duration:    {self.settings.min_duration} frames")
            print(f"  FPS:             {self.settings.fps} Hz")
            print(f"  Transition type: {self.settings.transition_type}")

        # Generate TTL timestamps
        timestamps = self.generator.generate()

        if self.settings.verbose:
            print(f"\nDetection results:")
            print(f"  Events detected: {len(timestamps)}")
            if timestamps:
                print(f"  First event:     {timestamps[0]:.6f} s")
                print(f"  Last event:      {timestamps[-1]:.6f} s")
                if len(timestamps) > 1:
                    span = timestamps[-1] - timestamps[0]
                    print(f"  Time span:       {span:.3f} s")

        # Write TTL file
        write_ttl_timestamps(timestamps, self.settings.output_file)

        print(f"✓ Converted {len(timestamps)} events to {self.settings.output_file}")

        # Display plot if requested
        if self.settings.plot:
            self._display_plot(timestamps)

    def _display_plot(self, timestamps: List[float]) -> None:
        """Display visualization plot of TTL detection results.

        Args:
            timestamps: List of detected TTL timestamps
        """
        if not timestamps:
            print("⚠ No events to plot")
            return

        plot_ttl_detection_from_pose(
            h5_path=self.settings.input_file,
            bodypart=self.settings.bodypart,
            threshold=self.settings.threshold,
            timestamps=timestamps,
            fps=self.settings.fps,
            transition_type=self.settings.transition_type,
            min_duration=self.settings.min_duration,
            display=True,
        )


def main() -> int:
    """Main entry point for the converter.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        settings = TTLConverterSettings()
        processor = TTLProcessor(settings)
        processor.process()
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
