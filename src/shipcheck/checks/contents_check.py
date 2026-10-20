"""
contents_check.py - Inspects built distribution archives (wheel and sdist) for missing or unwanted files.
"""

import tarfile
import zipfile
from pathlib import Path
from typing import List, Set

from ..models import CheckCategoryResult, Issue, Severity

SENSITIVE_PATTERNS = [
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    ".pem",
    ".key",
    ".pypirc",
    "credentials",
    "secrets.json",
    "token",
]

JUNK_PATTERNS = [
    "__pycache__",
    ".pyc",
    ".pyo",
    ".DS_Store",
    "Thumbs.db",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
]


def get_wheel_members(wheel_path: Path) -> List[str]:
    """List all file paths inside a wheel archive."""
    with zipfile.ZipFile(wheel_path, "r") as zf:
        return zf.namelist()


def get_sdist_members(sdist_path: Path) -> List[str]:
    """List all file paths inside a source distribution archive."""
    with tarfile.open(sdist_path, "r:*") as tf:
        return tf.getnames()


def run_contents_checks(project_dir: Path, artifacts: List[Path]) -> CheckCategoryResult:
    """Inspects contents of built wheels and source archives."""
    cat = CheckCategoryResult(
        category="Package Contents & Artifact Inspection",
        description="Inspects files inside .whl and .tar.gz for missing modules, documentation, and accidental secrets",
    )

    if not artifacts:
        cat.add_issue(
            Issue(
                code="CNT001",
                severity=Severity.CRITICAL,
                title="No Distribution Artifacts To Inspect",
                message="Cannot inspect contents because no wheel or sdist was built.",
                suggestion="Fix build errors to allow package content inspection.",
            )
        )
        return cat

    # Collect source files on disk to compare
    disk_py_files: Set[str] = set()
    src_dir = project_dir / "src"
    root_to_scan = src_dir if src_dir.is_dir() else project_dir

    for p in root_to_scan.rglob("*.py"):
        # Ignore virtual environments, tests, build dirs
        rel = str(p.relative_to(project_dir)).replace("\\", "/")
        if any(ignored in rel for ignored in ["test_env", "venv", ".venv", "build", "dist", ".egg-info"]):
            continue
        # Extract relative module path (e.g. pydevtoolbox/operations.py)
        if src_dir.is_dir() and p.is_relative_to(src_dir):
            rel_module = str(p.relative_to(src_dir)).replace("\\", "/")
        else:
            rel_module = rel
        disk_py_files.add(rel_module)

    # 1. Inspect Wheel(s)
    wheels = [p for p in artifacts if p.name.endswith(".whl")]
    for wheel in wheels:
        try:
            members = get_wheel_members(wheel)
            normalized_members = [m.replace("\\", "/") for m in members]

            # Check that python files from source are included in the wheel
            missing_in_wheel = []
            for src_file in disk_py_files:
                if not any(m.endswith(src_file) or m == src_file for m in normalized_members):
                    missing_in_wheel.append(src_file)

            if missing_in_wheel:
                cat.add_issue(
                    Issue(
                        code="CNT002",
                        severity=Severity.CRITICAL,
                        title=f"Source Files Missing From Wheel ({wheel.name})",
                        message=f"{len(missing_in_wheel)} Python source file(s) on disk are missing from the built wheel: {', '.join(missing_in_wheel[:5])}",
                        suggestion="Check [tool.setuptools.packages.find] or package discovery in pyproject.toml to ensure all modules are packaged.",
                        file=wheel.name,
                    )
                )
            else:
                cat.add_issue(
                    Issue(
                        code="CNT000",
                        severity=Severity.PASS,
                        title=f"All Python Source Files Present in Wheel ({wheel.name})",
                        message=f"Verified {len(disk_py_files)} module(s) bundled in wheel.",
                        suggestion="",
                        file=wheel.name,
                    )
                )

            # Check for METADATA and RECORD
            has_dist_info = any(".dist-info" in m for m in normalized_members)
            has_metadata = any(m.endswith(".dist-info/METADATA") for m in normalized_members)
            has_record = any(m.endswith(".dist-info/RECORD") for m in normalized_members)

            if not has_dist_info or not has_metadata or not has_record:
                cat.add_issue(
                    Issue(
                        code="CNT003",
                        severity=Severity.CRITICAL,
                        title="Corrupted or Non-compliant Wheel Structure",
                        message=f"Wheel {wheel.name} is missing essential dist-info, METADATA, or RECORD files.",
                        suggestion="Ensure a standard wheel builder is used to build distribution packages.",
                        file=wheel.name,
                    )
                )

            # Check for license file inside wheel
            has_license_in_wheel = any("license" in m.lower() or "copying" in m.lower() for m in normalized_members)
            has_license_on_disk = any((project_dir / l).exists() for l in ["LICENSE", "LICENSE.txt", "COPYING"])
            if has_license_on_disk and not has_license_in_wheel:
                cat.add_issue(
                    Issue(
                        code="CNT004",
                        severity=Severity.WARNING,
                        title="LICENSE File Missing in Wheel",
                        message="LICENSE exists in the project root but was not bundled into the wheel archive.",
                        suggestion="Add license-files = ['LICENSE'] under [project] in pyproject.toml.",
                        file="pyproject.toml",
                    )
                )

            # Check for leaked secrets or junk files in wheel
            for m in normalized_members:
                m_lower = m.lower()
                for junk in JUNK_PATTERNS:
                    if junk in m_lower:
                        cat.add_issue(
                            Issue(
                                code="CNT005",
                                severity=Severity.WARNING,
                                title=f"Junk File Bundled in Wheel: {m}",
                                message=f"Found artifact matching '{junk}' inside the wheel.",
                                suggestion="Add unwanted build and cache files to .gitignore and package excludes.",
                                file=m,
                            )
                        )
                for secret in SENSITIVE_PATTERNS:
                    if m_lower.endswith(secret) or f"/{secret}" in m_lower:
                        cat.add_issue(
                            Issue(
                                code="CNT006",
                                severity=Severity.CRITICAL,
                                title=f"Potentially Sensitive File Bundled in Wheel: {m}",
                                message=f"File {m} matches sensitive credential pattern '{secret}'.",
                                suggestion="Remove this sensitive file immediately before publishing to PyPI!",
                                file=m,
                            )
                        )

            # Check wheel size
            wheel_size_mb = wheel.stat().st_size / (1024 * 1024)
            if wheel_size_mb > 50:
                cat.add_issue(
                    Issue(
                        code="CNT007",
                        severity=Severity.WARNING,
                        title=f"Large Wheel Size ({wheel_size_mb:.1f} MB)",
                        message="Wheel file exceeds 50 MB, which may fail PyPI upload limits or cause slow installs.",
                        suggestion="Exclude heavy media, test fixtures, or datasets from package distributions.",
                        file=wheel.name,
                    )
                )

        except Exception as e:
            cat.add_issue(
                Issue(
                    code="CNT008",
                    severity=Severity.CRITICAL,
                    title=f"Could Not Read Wheel Archive: {wheel.name}",
                    message=f"Error inspecting wheel: {str(e)}",
                    suggestion="Verify that the wheel file was generated cleanly.",
                    file=wheel.name,
                )
            )

    # 2. Inspect Source Distribution(s)
    sdists = [p for p in artifacts if p.name.endswith(".tar.gz")]
    for sdist in sdists:
        try:
            members = get_sdist_members(sdist)
            norm = [m.replace("\\", "/") for m in members]

            has_readme = any("readme" in m.lower() for m in norm)
            if not has_readme and (project_dir / "README.md").exists():
                cat.add_issue(
                    Issue(
                        code="CNT009",
                        severity=Severity.WARNING,
                        title="README Missing in Source Distribution",
                        message=f"README was not found inside {sdist.name}.",
                        suggestion="Ensure README.md is declared in pyproject.toml or included in MANIFEST.in.",
                        file=sdist.name,
                    )
                )

            has_pyproject = any(m.endswith("pyproject.toml") for m in norm)
            if not has_pyproject:
                cat.add_issue(
                    Issue(
                        code="CNT010",
                        severity=Severity.WARNING,
                        title="pyproject.toml Missing in Source Distribution",
                        message=f"pyproject.toml was not found inside {sdist.name}.",
                        suggestion="Include pyproject.toml so users installing from source get proper build metadata.",
                        file=sdist.name,
                    )
                )

        except Exception as e:
            cat.add_issue(
                Issue(
                    code="CNT011",
                    severity=Severity.CRITICAL,
                    title=f"Could Not Read Source Distribution: {sdist.name}",
                    message=f"Error inspecting sdist: {str(e)}",
                    suggestion="Verify that tar.gz archive is not corrupted.",
                    file=sdist.name,
                )
            )

    return cat
