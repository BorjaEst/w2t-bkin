"""Synthetic data generation package for W2T-BKIN testing.

This package provides tools to generate synthetic data for testing the W2T-BKIN
pipeline without requiring real experimental data. It creates minimal, deterministic,
and valid data files that conform to the pipeline's expectations.

Key Features:
-------------
- **Deterministic Generation**: Same seed produces identical outputs
- **Minimal Size**: Small files optimized for fast test execution
- **Valid by Design**: Outputs conform to domain model contracts
- **Modular**: Generate individual modalities or complete sessions
- **Scenario Support**: Pre-built scenarios for common test patterns

Package Structure:
------------------
- models: Data models for synthetic generation parameters
- config_synth: Generate Config and Session TOML files
- session_synth: Orchestrate complete synthetic session trees
- video_synth: Create synthetic video files
- ttl_synth: Create synthetic TTL pulse files
- bpod_synth: Create synthetic Bpod .mat files
- pose_synth: Create synthetic pose estimation outputs
- facemap_synth: Create synthetic facemap outputs
- scenarios: Pre-built test scenarios (happy_path, mismatch, etc.)

Usage Example:
--------------
>>> from synthetic.scenarios import happy_path
>>> from pathlib import Path
>>>
>>> # Generate complete synthetic session
>>> session_paths = happy_path.make_session(
...     root=Path("temp/test_sessions"),
...     session_id="test-001",
...     seed=42
... )
>>>
>>> # Use in tests
>>> from w2t_bkin.config import load_config, load_session
>>> config = load_config(session_paths.config_path)
>>> session = load_session(session_paths.session_path)

Design Principles:
------------------
1. **Test-Only**: This package is for testing, not production use
2. **Fast Generation**: Optimize for speed over realism
3. **Deterministic**: Same inputs always produce same outputs
4. **Composable**: Mix and match modalities as needed
5. **Self-Contained**: No dependencies on real data

Requirements Coverage:
----------------------
Supports testing of:
- FR-1/2/3: Config/session loading and file discovery
- FR-13/15/16: Frame/TTL counting and verification
- FR-TB-*: Timebase alignment scenarios
- NFR-1/2: Deterministic processing validation
- NFR-4: Fast verification testing
"""

from synthetic.models import SyntheticCamera, SyntheticSession, SyntheticSessionParams, SyntheticTTL
from synthetic.video_synth import check_ffmpeg_available, count_stub_frames, is_synthetic_stub

__all__ = [
    "SyntheticCamera",
    "SyntheticSession",
    "SyntheticSessionParams",
    "SyntheticTTL",
    "is_synthetic_stub",
    "count_stub_frames",
    "check_ffmpeg_available",
]

__version__ = "0.1.0"
