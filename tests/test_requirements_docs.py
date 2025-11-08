"""Validate presence and basic structure of module design/requirements docs.

These tests ensure that each planned module has both a design.md and
requirements.md file so implementation can proceed in isolation.
"""

from __future__ import annotations

from pathlib import Path

MODULES = [
    "config",
    "ingest",
    "sync",
    "transcode",
    "pose",
    "facemap",
    "events",
    "nwb",
    "qc",
    "cli",
    "utils",
    "domain",
]


def test_module_docs_exist(src_root: Path):
    missing = []
    for mod in MODULES:
        design = src_root / mod / "design.md"
        reqs = src_root / mod / "requirements.md"
        if not design.exists() or not reqs.exists():
            missing.append(mod)
    assert not missing, f"Modules missing docs: {missing}"  # pragma: no cover


def test_front_matter_present(src_root: Path):
    offenders = []
    for mod in MODULES:
        for fname in ("design.md", "requirements.md"):
            path = src_root / mod / fname
            text = path.read_text(encoding="utf-8")
            if not text.lstrip().startswith("---\n"):
                offenders.append(str(path))
    assert not offenders, f"Missing or malformed front matter: {offenders}"  # pragma: no cover
