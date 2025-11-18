"""Synthetic video generation utilities.

Creates small synthetic video files matching session camera glob
patterns to enable end-to-end pipeline tests (ingest, sync, QC) without
real data. Keeps dependencies light by relying only on `ffmpeg-python`
and the system ffmpeg binary; falls back to dummy placeholder files if
ffmpeg is unavailable.

Features:
- `VideoGenerationOptions` Pydantic model for generation knobs.
- Pattern-aware filename derivation (handles `*` wildcard).
- Deterministic color selection per camera (seed + camera id hash).
- Graceful fallback to text placeholder if ffmpeg run fails.

Example:
    from synthetic.session_synth import build_session
    from synthetic.video_synth import VideoGenerationOptions, generate_video_files_for_session

    session = build_session()
    opts = VideoGenerationOptions(frames_per_segment=30, fps=30.0)
    mapping = generate_video_files_for_session(session, 'temp/Session-SYNTH-VID', options=opts)
    print(mapping['cam0'])  # list of generated file paths

CLI:
    python -m synthetic.video_synth --out temp/Session-SYNTH-VID
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field

from synthetic.utils import derive_sequenced_paths

try:
    import ffmpeg  # type: ignore
except Exception:  # pragma: no cover - fallback if import fails
    ffmpeg = None  # type: ignore

from w2t_bkin.domain.session import Session as SessionModel


class VideoGenerationOptions(BaseModel):
    """Options controlling synthetic video generation.

    frames_per_segment: Number of frames per generated video file.
    segments_per_camera: How many files to generate per camera.
    fps: Frame rate.
    width/height: Frame dimensions.
    base_color: Base RGB hex (e.g. '336699'); varied per camera.
    seed: Seed used for deterministic color variation.
    codec: ffmpeg codec (must match pipeline expectations; often 'libx264').
    pix_fmt: Pixel format (defaults to yuv420p for broad compatibility).
    extension: Container extension if pattern lacks one (e.g. 'mp4').
    overwrite: Overwrite existing files.
    """

    frames_per_segment: int = Field(30, ge=1)
    segments_per_camera: int = Field(1, ge=1)
    fps: float = Field(30.0, gt=0)
    width: int = Field(320, ge=16)
    height: int = Field(240, ge=16)
    base_color: str = Field("336699", pattern=r"^[0-9A-Fa-f]{6}$")
    seed: int = Field(2025)
    codec: str = Field("libx264")
    pix_fmt: str = Field("yuv420p")
    extension: str = Field("avi")
    overwrite: bool = Field(True)


def _derive_video_paths(pattern: str, segments: int, extension: str) -> List[Path]:
    """Derive concrete video file paths from a glob pattern with `*`.

    Delegates to shared utility for consistent sequencing behavior.
    """
    return derive_sequenced_paths(
        pattern,
        segments,
        default_ext=extension,
        pad=4,
        dash_when_no_wildcard=True,
        single_when_no_wildcard=False,
    )


def _camera_color(base_hex: str, camera_id: str, seed: int) -> str:
    """Derive a deterministic hex color per camera by hashing id + seed."""
    h = hashlib.sha256(f"{seed}:{camera_id}".encode()).hexdigest()[:6]

    # Simple mix: average each channel with base
    def mix(comp_base: int, comp_hash: int) -> int:
        return int((comp_base + comp_hash) / 2)

    base_r = int(base_hex[0:2], 16)
    base_g = int(base_hex[2:4], 16)
    base_b = int(base_hex[4:6], 16)
    hash_r = int(h[0:2], 16)
    hash_g = int(h[2:4], 16)
    hash_b = int(h[4:6], 16)
    r = f"{mix(base_r, hash_r):02x}"
    g = f"{mix(base_g, hash_g):02x}"
    b = f"{mix(base_b, hash_b):02x}"
    return r + g + b


def _write_video_file(path: Path, *, fps: float, frames: int, width: int, height: int, color_hex: str, codec: str, pix_fmt: str, overwrite: bool) -> None:
    """Write a synthetic solid-color video using ffmpeg or create dummy file.

    Solid color uses lavfi `color` source for efficiency.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return
    duration = frames / fps
    if ffmpeg is None:
        path.write_text("DUMMY_VIDEO\n", encoding="utf-8")
        return
    color_arg = f"#{color_hex}"
    try:
        (
            ffmpeg.input(f"color=c={color_arg}:s={width}x{height}:r={fps}:d={duration}", f="lavfi")
            .output(str(path), vcodec=codec, pix_fmt=pix_fmt, r=fps, loglevel="error")
            .overwrite_output()
            .run()
        )
    except Exception:
        # Fallback if ffmpeg execution fails
        path.write_text("DUMMY_VIDEO_FALLBACK\n", encoding="utf-8")


def generate_video_files_for_session(
    session: SessionModel,
    base_dir: Union[str, Path],
    *,
    options: Optional[VideoGenerationOptions] = None,
    **overrides,
) -> Dict[str, List[Path]]:
    """Generate synthetic video files for each camera defined in `session`.

    Returns mapping camera_id -> list[Path].
    """
    base = options or VideoGenerationOptions()
    if overrides:
        base = base.model_copy(update=overrides)

    out_base = Path(base_dir)
    mapping: Dict[str, List[Path]] = {}
    for cam in session.cameras:
        paths = _derive_video_paths(cam.paths, base.segments_per_camera, base.extension)
        color = _camera_color(base.base_color, cam.id, base.seed)
        concrete: List[Path] = []
        for p in paths:
            full = out_base / p
            _write_video_file(
                full,
                fps=base.fps,
                frames=base.frames_per_segment,
                width=base.width,
                height=base.height,
                color_hex=color,
                codec=base.codec,
                pix_fmt=base.pix_fmt,
                overwrite=base.overwrite,
            )
            concrete.append(full.resolve())
        mapping[cam.id] = concrete
    return mapping


def generate_and_write_videos(session: SessionModel, base_dir: Union[str, Path], **kwargs) -> Dict[str, List[Path]]:
    """Convenience wrapper around `generate_video_files_for_session`."""
    return generate_video_files_for_session(session, base_dir, **kwargs)


if __name__ == "__main__":  # pragma: no cover
    import argparse

    from synthetic.session_synth import build_session

    parser = argparse.ArgumentParser(description="Generate synthetic videos for a synthetic session")
    parser.add_argument("--out", type=str, default="temp/Session-SYNTH-VID", help="Output base directory")
    parser.add_argument("--frames", type=int, default=30, help="Frames per segment")
    parser.add_argument("--segments", type=int, default=1, help="Segments per camera")
    parser.add_argument("--fps", type=float, default=30.0, help="Frames per second")
    parser.add_argument("--width", type=int, default=320, help="Frame width")
    parser.add_argument("--height", type=int, default=240, help="Frame height")
    args = parser.parse_args()

    session = build_session()
    opts = VideoGenerationOptions(
        frames_per_segment=args.frames,
        segments_per_camera=args.segments,
        fps=args.fps,
        width=args.width,
        height=args.height,
    )
    mapping = generate_video_files_for_session(session, args.out, options=opts)
    for cid, files in mapping.items():
        print(f"Camera {cid} -> {', '.join(str(f) for f in files)}")
