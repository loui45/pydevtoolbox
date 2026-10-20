"""
build_check.py - Builds wheels and source distributions and diagnoses build failures.
"""

import sys
import subprocess
import shutil
from pathlib import Path
from typing import Tuple, List, Optional

from ..models import CheckCategoryResult, Issue, Severity


def run_build_checks(
    project_dir: Path, output_dir: Optional[Path] = None, no_isolation: bool = True
) -> Tuple[CheckCategoryResult, List[Path]]:
    """
    Builds sdist and wheel distributions, captures warnings, and diagnoses errors.
    Returns (CheckCategoryResult, list_of_built_artifact_paths).
    """
    cat = CheckCategoryResult(
        category="Distribution Build",
        description="Builds Python source distributions (sdist) and wheels (bdist_wheel) and checks for errors",
    )
    artifacts: List[Path] = []

    target_dist = output_dir or (project_dir / "dist")
    target_dist.mkdir(parents=True, exist_ok=True)

    # Clean existing dist files in target_dist to guarantee freshness
    for existing in target_dist.glob("*"):
        if existing.is_file() and existing.name.endswith((".whl", ".tar.gz", ".zip")):
            try:
                existing.unlink()
            except Exception:
                pass

    cmd = [sys.executable, "-m", "build", "--outdir", str(target_dist)]
    if no_isolation:
        cmd.append("--no-isolation")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        cat.add_issue(
            Issue(
                code="BLD101",
                severity=Severity.CRITICAL,
                title="Python Interpreter Not Found",
                message="Could not invoke python interpreter to run build tool.",
                suggestion="Ensure Python is in system PATH and virtual environment is activated.",
            )
        )
        return cat, artifacts
    except subprocess.TimeoutExpired:
        cat.add_issue(
            Issue(
                code="BLD102",
                severity=Severity.CRITICAL,
                title="Build Timed Out",
                message="Package build command timed out after 120 seconds.",
                suggestion="Check for long network downloads or infinite loops in setup script.",
            )
        )
        return cat, artifacts

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    combined_log = f"{stdout}\n{stderr}"

    if proc.returncode != 0:
        # Diagnose failure reasons
        if "BackendUnavailable" in combined_log or "No module named" in combined_log:
            cat.add_issue(
                Issue(
                    code="BLD103",
                    severity=Severity.CRITICAL,
                    title="Build Backend Unavailable",
                    message="The specified build backend is not installed in the current environment.",
                    suggestion="Install the required build tools: pip install build setuptools wheel",
                )
            )
        elif "InvalidDistribution" in combined_log or "error: can't find" in combined_log:
            cat.add_issue(
                Issue(
                    code="BLD104",
                    severity=Severity.CRITICAL,
                    title="Package Files Not Found During Build",
                    message="Build backend could not locate specified packages or source files.",
                    suggestion="Check [tool.setuptools.packages.find] where=['src'] or package directory structure.",
                )
            )
        else:
            first_err = "\n".join(
                [line for line in stderr.splitlines() if "error" in line.lower() or "exception" in line.lower()][:3]
            )
            cat.add_issue(
                Issue(
                    code="BLD105",
                    severity=Severity.CRITICAL,
                    title="Package Build Failed",
                    message=f"Build exited with code {proc.returncode}. {first_err}",
                    suggestion="Review build output logs, dependencies, and configuration.",
                )
            )
        return cat, artifacts

    # Check generated files
    wheels = list(target_dist.glob("*.whl"))
    sdists = list(target_dist.glob("*.tar.gz"))

    if not wheels:
        cat.add_issue(
            Issue(
                code="BLD106",
                severity=Severity.CRITICAL,
                title="Wheel Distribution Not Built",
                message="The build succeeded but no .whl wheel package was produced.",
                suggestion="Ensure 'bdist_wheel' is supported by your build backend.",
            )
        )
    else:
        artifacts.extend(wheels)

    if not sdists:
        cat.add_issue(
            Issue(
                code="BLD107",
                severity=Severity.WARNING,
                title="Source Distribution (sdist) Not Built",
                message="No .tar.gz source distribution was created.",
                suggestion="PyPI strongly recommends publishing both a wheel (.whl) and source archive (.tar.gz).",
            )
        )
    else:
        artifacts.extend(sdists)

    # Check for warnings in build log
    if "WARNING" in combined_log or "UserWarning" in combined_log or "DeprecationWarning" in combined_log:
        warning_lines = [
            line.strip()
            for line in combined_log.splitlines()
            if "warning" in line.lower() and not line.strip().startswith("!")
        ][:3]
        if warning_lines:
            cat.add_issue(
                Issue(
                    code="BLD108",
                    severity=Severity.WARNING,
                    title="Warnings During Package Build",
                    message="; ".join(warning_lines),
                    suggestion="Review and resolve build backend warnings prior to PyPI publication.",
                )
            )

    # Optional Twine Check on generated distributions
    try:
        twine_proc = subprocess.run(
            [sys.executable, "-m", "twine", "check"] + [str(p) for p in artifacts],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if twine_proc.returncode != 0:
            twine_err = twine_proc.stderr or twine_proc.stdout or "Twine check failed"
            if "No module named twine" in twine_err:
                cat.add_issue(
                    Issue(
                        code="TWN002",
                        severity=Severity.INFO,
                        title="Twine Not Installed (Skipped twine check)",
                        message="Twine is not installed in the current environment.",
                        suggestion="Run 'pip install twine' to enable distribution validation checks.",
                    )
                )
            else:
                cat.add_issue(
                    Issue(
                        code="TWN001",
                        severity=Severity.CRITICAL,
                        title="Twine Distribution Validation Failed",
                        message=twine_err.strip(),
                        suggestion="Fix package metadata or README formatting so that PyPI can render the project page.",
                    )
                )
        else:
            cat.add_issue(
                Issue(
                    code="TWN000",
                    severity=Severity.PASS,
                    title="Twine Validation Passed",
                    message="All built distributions passed twine package integrity checks.",
                    suggestion="",
                )
            )
    except Exception:
        # Twine execution error
        pass

    return cat, artifacts
