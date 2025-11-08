"""Pytest configuration and shared fixtures for the w2t_bkin project.

Fixtures here are intentionally minimal during the design phase; they will
expand as modules gain implementation. The goal now is to provide a stable
scaffold for future unit and integration tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return repository root path."""
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def src_root(repo_root: Path) -> Path:
    return repo_root / "src" / "w2t_bkin"


@pytest.fixture()
def temp_workdir(tmp_path: Path) -> Path:
    """Provide an isolated temporary working directory for tests."""
    return tmp_path


@pytest.fixture()
def dummy_manifest(tmp_path: Path) -> Path:
    """Create a minimal dummy manifest file for tests that need one.

    This is a placeholder; real fields will appear once ingest implementation exists.
    """
    manifest = {
        "session_id": "test_session",
        "videos": [],
        "sync": [],
        "config_snapshot": {},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path
