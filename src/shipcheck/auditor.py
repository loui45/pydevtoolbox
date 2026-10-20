"""
auditor.py - Main audit orchestrator for ShipCheck.
"""

import time
from pathlib import Path
from typing import Optional, List

from .models import AuditReport, CheckCategoryResult, Issue, Severity
from .checks.config_check import run_config_checks, load_toml
from .checks.build_check import run_build_checks
from .checks.contents_check import run_contents_checks
from .checks.install_check import run_install_checks


class ShipCheck:
    """Orchestrates comprehensive pre-release auditing of Python packages."""

    def __init__(
        self,
        project_dir: Path,
        skip_build: bool = False,
        skip_install_test: bool = False,
        no_isolation: bool = True,
        output_dir: Optional[Path] = None,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.skip_build = skip_build
        self.skip_install_test = skip_install_test
        self.no_isolation = no_isolation
        self.output_dir = output_dir

    def run_audit(self) -> AuditReport:
        start_time = time.time()

        # Load initial metadata
        pyproject_path = self.project_dir / "pyproject.toml"
        cfg = load_toml(pyproject_path) or {}
        project_table = cfg.get("project", {})

        pkg_name = project_table.get("name", self.project_dir.name)
        pkg_version = project_table.get("version", "0.0.0")

        report = AuditReport(
            project_name=pkg_name,
            version=pkg_version,
            project_path=str(self.project_dir),
        )

        # 1. Configuration & Metadata Checks
        config_cat = run_config_checks(self.project_dir)
        report.categories.append(config_cat)

        # If configuration has critical blocking issues, we can still attempt build or abort
        artifacts: List[Path] = []
        if not self.skip_build:
            # 2. Distribution Build Checks
            build_cat, artifacts = run_build_checks(
                project_dir=self.project_dir,
                output_dir=self.output_dir,
                no_isolation=self.no_isolation,
            )
            report.categories.append(build_cat)
            report.build_artifacts = [str(a) for a in artifacts]

            # 3. Package Contents Inspection
            if artifacts:
                contents_cat = run_contents_checks(self.project_dir, artifacts)
                report.categories.append(contents_cat)

            # 4. Clean Environment Installation & Import Tests
            if not self.skip_install_test and artifacts:
                wheel_artifacts = [a for a in artifacts if a.name.endswith(".whl")]
                if wheel_artifacts:
                    # Detect entrypoints from pyproject.toml
                    scripts_table = project_table.get("scripts", {})
                    entrypoint_names = list(scripts_table.keys()) if isinstance(scripts_table, dict) else []

                    # Detect candidate module names
                    src_dir = self.project_dir / "src"
                    candidate_modules = []
                    if src_dir.is_dir():
                        for child in src_dir.iterdir():
                            if child.is_dir() and (child / "__init__.py").exists():
                                candidate_modules.append(child.name)
                    if not candidate_modules:
                        candidate_modules.append(pkg_name.replace("-", "_"))

                    install_cat = run_install_checks(
                        package_name=pkg_name,
                        wheel_path=wheel_artifacts[0],
                        entrypoints=entrypoint_names,
                        import_names=candidate_modules,
                    )
                    report.categories.append(install_cat)

        report.duration_seconds = time.time() - start_time
        return report


def audit(
    project_dir: str = ".",
    skip_build: bool = False,
    skip_install_test: bool = False,
    no_isolation: bool = True,
) -> AuditReport:
    """Convenience function to audit a Python package project."""
    checker = ShipCheck(
        project_dir=Path(project_dir),
        skip_build=skip_build,
        skip_install_test=skip_install_test,
        no_isolation=no_isolation,
    )
    return checker.run_audit()
