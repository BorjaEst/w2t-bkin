from pathlib import Path


def test_scaffold_has_module_packages():
    """Smoke-check that planned module directories exist under src/w2t_bkin."""
    root = Path(__file__).resolve().parents[1]
    src = root / "src" / "w2t_bkin"
    expected = {
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
    }
    existing = {p.name for p in src.iterdir() if p.is_dir()}
    missing = expected - existing
    assert not missing, f"Missing module directories: {sorted(missing)}"
