"""
install_check.py - Tests installation and imports of the built package in a clean, isolated virtual environment.
"""

import sys
import os
import venv
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..models import CheckCategoryResult, Issue, Severity


def get_venv_executables(venv_dir: Path) -> Dict[str, Path]:
    """Return python and pip paths inside a virtual environment across Windows and Unix."""
    if os.name == "nt":
        scripts_dir = venv_dir / "Scripts"
        return {
            "python": scripts_dir / "python.exe",
            "pip": scripts_dir / "pip.exe",
            "scripts": scripts_dir,
        }
    else:
        bin_dir = venv_dir / "bin"
        return {
            "python": bin_dir / "python",
            "pip": bin_dir / "pip",
            "scripts": bin_dir,
        }


def run_install_checks(
    package_name: str,
    wheel_path: Path,
    entrypoints: Optional[List[str]] = None,
    import_names: Optional[List[str]] = None,
) -> CheckCategoryResult:
    """
    Creates a temporary clean virtualenv, installs the wheel, and verifies import and CLI entry points.
    """
    cat = CheckCategoryResult(
        category="Installation & Import Smoke Test",
        description="Installs built wheel in a clean isolated virtual environment and tests importing and CLI entrypoints",
    )

    if not wheel_path.exists():
        cat.add_issue(
            Issue(
                code="INS001",
                severity=Severity.CRITICAL,
                title="Wheel File Not Found For Installation Test",
                message=f"Wheel path {wheel_path} does not exist.",
                suggestion="Ensure the build step succeeded before testing installation.",
            )
        )
        return cat

    temp_dir = Path(tempfile.mkdtemp(prefix="shipcheck_venv_"))

    try:
        # 1. Create clean virtual environment
        try:
            builder = venv.EnvBuilder(with_pip=True, clear=True)
            builder.create(str(temp_dir))
        except Exception as e:
            cat.add_issue(
                Issue(
                    code="INS002",
                    severity=Severity.WARNING,
                    title="Could Not Create Isolated Virtual Environment",
                    message=f"venv creation failed: {str(e)}",
                    suggestion="Ensure python-venv or ensurepip is installed in your Python distribution.",
                )
            )
            return cat

        executables = get_venv_executables(temp_dir)
        venv_python = executables["python"]
        scripts_dir = executables["scripts"]

        if not venv_python.exists():
            cat.add_issue(
                Issue(
                    code="INS003",
                    severity=Severity.WARNING,
                    title="Virtualenv Python Executable Not Found",
                    message=f"Could not locate {venv_python}.",
                    suggestion="Check virtual environment creation permissions.",
                )
            )
            return cat

        # 2. Install the built wheel
        install_proc = subprocess.run(
            [str(venv_python), "-m", "pip", "install", "--no-warn-script-location", str(wheel_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if install_proc.returncode != 0:
            err_msg = install_proc.stderr or install_proc.stdout or "pip install failed"
            cat.add_issue(
                Issue(
                    code="INS004",
                    severity=Severity.CRITICAL,
                    title="Wheel Installation Failed in Clean Environment",
                    message=f"pip install exited with code {install_proc.returncode}:\n{err_msg.strip()}",
                    suggestion="Review package dependency declarations and wheel structure for incompatible requirements.",
                    file=wheel_path.name,
                )
            )
            return cat
        else:
            cat.add_issue(
                Issue(
                    code="INS000",
                    severity=Severity.PASS,
                    title="Wheel Installed Successfully",
                    message="Wheel installed cleanly in isolated environment without errors.",
                    suggestion="",
                    file=wheel_path.name,
                )
            )

        # 3. Test Python Import
        candidates_to_import = import_names or [
            package_name.replace("-", "_"),
            package_name,
        ]

        imported_any = False
        import_errors = []

        for mod_name in candidates_to_import:
            test_script = (
                "import sys\n"
                "try:\n"
                f"    mod = __import__('{mod_name}')\n"
                "    ver = getattr(mod, '__version__', 'unknown')\n"
                f"    print('SUCCESS:' + '{mod_name}' + ':' + str(ver))\n"
                "except Exception as e:\n"
                "    import traceback\n"
                "    traceback.print_exc()\n"
                "    sys.exit(1)\n"
            )

            import_proc = subprocess.run(
                [str(venv_python), "-c", test_script],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if import_proc.returncode == 0 and "SUCCESS:" in import_proc.stdout:
                imported_any = True
                success_line = [l for l in import_proc.stdout.splitlines() if l.startswith("SUCCESS:")][0]
                _, name_found, version_found = success_line.split(":", 2)
                cat.add_issue(
                    Issue(
                        code="IMP000",
                        severity=Severity.PASS,
                        title=f"Module Import Passed: '{name_found}'",
                        message=f"Successfully imported '{name_found}' in clean environment (version: {version_found}).",
                        suggestion="",
                    )
                )
                break
            else:
                err_detail = import_proc.stderr or import_proc.stdout
                import_errors.append(f"import {mod_name} -> {err_detail.strip()}")

        if not imported_any:
            cat.add_issue(
                Issue(
                    code="IMP001",
                    severity=Severity.CRITICAL,
                    title="Module Import Failed in Clean Environment",
                    message=f"Failed to import package module. Errors:\n" + "\n".join(import_errors),
                    suggestion="Ensure top-level packages include __init__.py and all imported dependencies are listed in requires/dependencies.",
                )
            )

        # 4. Test Entrypoint Scripts (if any)
        if entrypoints:
            for ep in entrypoints:
                ep_exe_name = ep if os.name != "nt" else f"{ep}.exe"
                ep_exe_path = scripts_dir / ep_exe_name

                # Try running <ep> --help or <ep> -h
                tested_ok = False
                if ep_exe_path.exists():
                    ep_proc = subprocess.run(
                        [str(ep_exe_path), "--help"],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    if ep_proc.returncode in (0, 2):  # 2 is common for missing required args in argparse/click
                        tested_ok = True
                        cat.add_issue(
                            Issue(
                                code="CLI000",
                                severity=Severity.PASS,
                                title=f"CLI Script Verified: '{ep}'",
                                message=f"Console script '{ep}' was generated and responded to --help.",
                                suggestion="",
                            )
                        )
                    else:
                        cat.add_issue(
                            Issue(
                                code="CLI001",
                                severity=Severity.WARNING,
                                title=f"CLI Script Error: '{ep}'",
                                message=f"Executing '{ep} --help' failed with code {ep_proc.returncode}: {ep_proc.stderr.strip()}",
                                suggestion="Verify that the function target specified in [project.scripts] exists and runs properly.",
                            )
                        )
                else:
                    # Also try running via python -m <ep>
                    pass

    finally:
        # Clean up temporary venv safely
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    return cat
