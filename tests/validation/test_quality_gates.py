"""Quality gate validation tests.

Enforces design constraints: all modules importable, linters pass, type checks
pass, NWB outputs pass inspection.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.validation


class TestBuildGate:
    """Test build quality gate (Design §13)."""

    def test_Should_ImportAllModules_When_PackageBuilt_Design13(self, src_root: Path):
        """All w2t_bkin.* modules SHALL be importable without error.

        Requirements: Design §13 - Build gate
        Issue: Design phase - Module importability
        """
        # Arrange
        expected_modules = [
            "w2t_bkin.config",
            "w2t_bkin.ingest",
            "w2t_bkin.sync",
            "w2t_bkin.transcode",
            "w2t_bkin.pose",
            "w2t_bkin.facemap",
            "w2t_bkin.events",
            "w2t_bkin.nwb",
            "w2t_bkin.qc",
            "w2t_bkin.cli",
            "w2t_bkin.utils",
        ]

        # Act & Assert
        for module_name in expected_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")

    def test_Should_HaveValidPackageStructure_When_Checked_Design2(self, src_root: Path):
        """Package structure SHALL match modular design specification.

        Requirements: Design §2 - Module Breakdown
        Issue: Design phase - Package structure validation
        """
        # Arrange
        expected_subpackages = [
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
        ]

        # Act & Assert
        for subpackage in expected_subpackages:
            subpackage_path = src_root / subpackage
            assert subpackage_path.exists(), f"Subpackage {subpackage} directory must exist"
            # Should have __init__.py for Python package
            init_file = subpackage_path / "__init__.py"
            assert init_file.exists(), f"Subpackage {subpackage} must have __init__.py"


class TestLintGate:
    """Test linting quality gate (Design §13)."""

    def test_Should_PassRuff_When_LintingSourceCode_Design13(self, repo_root: Path):
        """Ruff linting SHALL pass on src/ directory.

        Requirements: Design §13 - Lint gate
        Issue: Design phase - Code style compliance
        """
        # Arrange
        src_dir = repo_root / "src"

        # Act
        result = subprocess.run(
            ["ruff", "check", str(src_dir)],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Ruff linting failed:\n{result.stdout}\n{result.stderr}"

    def test_Should_PassRuffFormat_When_CheckingCodeFormat_Design13(self, repo_root: Path):
        """Ruff format check SHALL pass on src/ directory.

        Requirements: Design §13 - Lint gate
        Issue: Design phase - Code formatting compliance
        """
        # Arrange
        src_dir = repo_root / "src"

        # Act
        result = subprocess.run(
            ["ruff", "format", "--check", str(src_dir)],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Ruff format check failed:\n{result.stdout}\n{result.stderr}"


class TestTypeCheckGate:
    """Test type checking quality gate (Design §13, NFR-10)."""

    def test_Should_PassMypy_When_TypeCheckingCoreModules_Design13_NFR10(self, repo_root: Path):
        """MyPy static type checking SHALL pass with strict optional checks.

        Requirements: Design §13 - Type check gate, NFR-10 (Type safety)
        Issue: Design phase - Type safety enforcement
        """
        # Arrange
        src_dir = repo_root / "src"

        # Act
        result = subprocess.run(
            [
                "mypy",
                str(src_dir),
                "--strict",
                "--ignore-missing-imports",  # For external dependencies
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"MyPy type checking failed:\n{result.stdout}\n{result.stderr}"


class TestUnitTestGate:
    """Test unit test quality gate (Design §13, NFR-12)."""

    def test_Should_PassUnitTests_When_Running_Design13_NFR12(self, repo_root: Path):
        """Pytest unit tests SHALL run successfully.

        Requirements: Design §13 - Unit test gate, NFR-12 (Testability)
        Issue: Design phase - Unit test execution
        """
        # Arrange
        tests_dir = repo_root / "tests"

        # Act
        result = subprocess.run(
            ["pytest", "-m", "unit", str(tests_dir), "-v"],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Unit tests failed:\n{result.stdout}\n{result.stderr}"

    def test_Should_HaveAdequateCoverage_When_RunningTests_NFR12(self, repo_root: Path):
        """Test coverage SHALL meet minimum threshold.

        Requirements: NFR-12 (Testability)
        Issue: Design phase - Test coverage validation
        """
        # Arrange
        src_dir = repo_root / "src"
        min_coverage = 80.0  # 80% coverage threshold

        # Act
        result = subprocess.run(
            [
                "pytest",
                "--cov=w2t_bkin",
                "--cov-report=term",
                f"--cov-fail-under={min_coverage}",
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Coverage below {min_coverage}%:\n{result.stdout}"


class TestNWBValidationGate:
    """Test NWB validation quality gate (FR-9, NFR-6, A2)."""

    def test_Should_PassNWBInspector_When_ValidatingOutput_FR9_NFR6_A2(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Generated NWB files SHALL pass nwbinspector with no critical issues.

        Requirements: FR-9, NFR-6 (Compatibility), Acceptance Criterion A2
        Issue: Design phase - NWB compliance validation
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.nwb import assemble_nwb
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)
        timestamps_dir, _ = compute_timestamps(manifest_path, temp_workdir / "sync")
        nwb_path = assemble_nwb(manifest_path, timestamps_dir, temp_workdir / "processed")

        # Act
        result = subprocess.run(
            ["nwbinspector", str(nwb_path), "--output", str(temp_workdir / "inspector_report.json")],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"nwbinspector failed:\n{result.stdout}\n{result.stderr}"

        # Check for critical issues
        import json

        report_path = temp_workdir / "inspector_report.json"
        if report_path.exists():
            report = json.loads(report_path.read_text())
            critical_issues = [issue for issue in report.get("issues", []) if issue.get("severity") == "CRITICAL"]
            assert len(critical_issues) == 0, f"Found {len(critical_issues)} critical issues (violates A2)"

    def test_Should_BeReadableByPyNWB_When_FileCreated_NFR6(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """NWB output SHALL be readable by pynwb.

        Requirements: NFR-6 (Compatibility)
        Issue: Design phase - PyNWB compatibility
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.nwb import assemble_nwb
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)
        timestamps_dir, _ = compute_timestamps(manifest_path, temp_workdir / "sync")
        nwb_path = assemble_nwb(manifest_path, timestamps_dir, temp_workdir / "processed")

        # Act & Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            assert nwb_file is not None, "NWB file must be readable"
            assert nwb_file.session_id is not None, "Session ID must be present"


class TestDocumentationGate:
    """Test documentation quality gate (Design §13, NFR-3)."""

    def test_Should_HaveDocstrings_When_CheckingPublicAPI_Design13(self, src_root: Path):
        """All public functions SHALL have docstrings.

        Requirements: Design §13 - Documentation coverage
        Issue: Design phase - API documentation validation
        """
        # Arrange
        import ast

        missing_docstrings = []

        # Act - Walk through all Python files
        for py_file in src_root.rglob("*.py"):
            if py_file.name.startswith("_") and py_file.name != "__init__.py":
                continue  # Skip private modules

            with open(py_file) as f:
                try:
                    tree = ast.parse(f.read())
                except SyntaxError:
                    continue  # Skip files with syntax errors (will be caught by linting)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if not node.name.startswith("_"):  # Public API
                        docstring = ast.get_docstring(node)
                        if not docstring:
                            missing_docstrings.append(f"{py_file.relative_to(src_root)}::{node.name}")

        # Assert
        assert len(missing_docstrings) == 0, f"Missing docstrings in:\n" + "\n".join(missing_docstrings)

    def test_Should_HaveREADME_When_CheckingRepository_NFR3(self, repo_root: Path):
        """Repository SHALL have comprehensive README documentation.

        Requirements: NFR-3 (Observability), Design §13
        Issue: Design phase - Repository documentation
        """
        # Arrange
        readme_path = repo_root / "README.md"

        # Act & Assert
        assert readme_path.exists(), "README.md must exist"

        readme_content = readme_path.read_text()
        required_sections = ["installation", "usage", "configuration", "testing"]

        for section in required_sections:
            assert section.lower() in readme_content.lower(), f"README must include '{section}' section"


class TestQCReportGate:
    """Test QC report generation quality gate (FR-8, A3)."""

    def test_Should_IncludeDriftPlot_When_ReportGenerated_FR8_A3(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """QC report SHALL include drift plot.

        Requirements: FR-8, Acceptance Criterion A3
        Issue: Design phase - QC drift visualization
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.nwb import assemble_nwb
        from w2t_bkin.qc import generate_report
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)
        timestamps_dir, sync_summary = compute_timestamps(manifest_path, temp_workdir / "sync")
        nwb_path = assemble_nwb(manifest_path, timestamps_dir, temp_workdir / "processed")

        # Act
        qc_report_path = generate_report(
            sync_summary=sync_summary,
            nwb_path=nwb_path,
            output_dir=temp_workdir / "qc",
        )

        # Assert
        html_content = qc_report_path.read_text()
        assert "drift" in html_content.lower(), "QC report must include drift plot (A3)"
        # Check for common plot indicators
        assert any(keyword in html_content for keyword in ["<svg", "<canvas", "plotly", "matplotlib"]), "Must contain plot elements"

    def test_Should_IncludePoseConfidence_When_PosePresent_A3(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """QC report SHALL include pose confidence histograms when pose is present.

        Requirements: Acceptance Criterion A3
        Issue: Design phase - QC pose visualization
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.nwb import assemble_nwb
        from w2t_bkin.pose import harmonize_pose
        from w2t_bkin.qc import generate_report
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)
        timestamps_dir, sync_summary = compute_timestamps(manifest_path, temp_workdir / "sync")

        # Add mock pose data
        dlc_output = synthetic_session / "pose_dlc.h5"
        pose_path = harmonize_pose(dlc_output, "dlc", temp_workdir / "pose")

        nwb_path = assemble_nwb(manifest_path, timestamps_dir, temp_workdir / "processed", pose_dir=temp_workdir / "pose")

        # Act
        qc_report_path = generate_report(
            sync_summary=sync_summary,
            nwb_path=nwb_path,
            pose_dir=temp_workdir / "pose",
            output_dir=temp_workdir / "qc",
        )

        # Assert
        html_content = qc_report_path.read_text()
        assert "confidence" in html_content.lower(), "QC report must include confidence histograms (A3)"
        assert "pose" in html_content.lower(), "QC report must reference pose data"


class TestProvenanceGate:
    """Test provenance capture quality gate (NFR-11, Design §11)."""

    def test_Should_EmbedConfigSnapshot_When_AssemblingNWB_NFR11(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """NWB SHALL embed configuration snapshot.

        Requirements: NFR-11 (Provenance), Design §11
        Issue: Design phase - Config provenance
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.nwb import assemble_nwb
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)
        timestamps_dir, _ = compute_timestamps(manifest_path, temp_workdir / "sync")

        # Act
        nwb_path = assemble_nwb(manifest_path, timestamps_dir, temp_workdir / "processed")

        # Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            # Config should be in notes or provenance module
            has_provenance = "config" in (nwb_file.notes or "").lower() or "provenance" in str(nwb_file.processing.keys()).lower()
            assert has_provenance, "NWB must embed configuration snapshot"

    def test_Should_RecordSoftwareVersions_When_AssemblingNWB_NFR11(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """NWB SHALL record software dependency versions.

        Requirements: NFR-11 (Provenance), Design §11
        Issue: Design phase - Software version provenance
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.nwb import assemble_nwb
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)
        timestamps_dir, _ = compute_timestamps(manifest_path, temp_workdir / "sync")

        # Act
        nwb_path = assemble_nwb(manifest_path, timestamps_dir, temp_workdir / "processed")

        # Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            # Software versions should be recorded
            has_versions = "version" in (nwb_file.notes or "").lower() or any("version" in str(mod).lower() for mod in nwb_file.processing.values())
            assert has_versions, "NWB must record software versions"
