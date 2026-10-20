# ShipCheck 🚀

> **Python Package Release Auditing Tool for PyPI**  
> Identify and fix packaging, configuration, and build problems *before* publishing to PyPI.

[![PyPI Version](https://img.shields.io/pypi/v/pydevtoolbox.svg)](https://pypi.org/project/pydevtoolbox/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/badge/python-3.8+-brightgreen.svg)](https://pypi.org/project/pydevtoolbox/)

---

## 🔍 What is ShipCheck?

Publishing a Python package to PyPI is permanent—once a release version number is uploaded, it cannot be modified or re-uploaded. A broken build, missing source file, or unverified import can break user installations and force immediate patch releases.

**ShipCheck** runs a comprehensive pre-flight audit of your Python project:
1. **Checks project configuration & metadata**: Validates `pyproject.toml`, PEP 621 fields, SPDX licenses, and detects unreplaced placeholders (e.g., `YOUR_USERNAME`, `TODO`).
2. **Builds distribution packages**: Compiles source distributions (`.tar.gz`) and wheels (`.whl`), intercepting build backend warnings and syntax errors.
3. **Inspects package contents**: Ensures all Python modules from disk are bundled inside the wheel, verifies `LICENSE` and `README` inclusion, and blocks accidental leaks of `.env` files, secrets, or temporary caches.
4. **Smoke-tests in clean environments**: Creates an isolated temporary virtual environment, installs the freshly built wheel, tests importing the module, and verifies CLI entrypoints.
5. **Provides clear explanations & fixes**: Translates obscure packaging errors into actionable, copy-pasteable remedies.
6. **Integrates with CI/CD**: Delivers styled terminal reports or structured JSON output with standard exit codes (`0` for ready, `1` for blocked).

---

## 📦 Installation

```bash
pip install pydevtoolbox
```

*(ShipCheck is bundled in `pydevtoolbox` and exposes both `shipcheck` and `pydevtoolbox` CLI commands).*

---

## ⚡ Quick Start

Run ShipCheck in your project root:

```bash
shipcheck
```

Or audit a specific path:

```bash
shipcheck /path/to/your/project
```

### Command Options

```text
usage: shipcheck [path] [options]

Arguments:
  path                  Path to the Python project directory (default: .)

Options:
  --json                Output results in JSON format for automated pipelines
  -o, --output FILE     Write report output to specified file path
  --skip-build          Skip distribution build and only audit configuration
  --skip-install        Skip isolated virtual environment install & smoke test
  --strict              Fail (exit code 1) on warnings as well as critical errors
  -v, --verbose         Display detailed passing checks and debug logs
  --version             Show tool version
```

---

## 📊 Sample Terminal Output

```text
╔═══════════════════════════════════════════════════════════════════╗
║                  ShipCheck Package Release Audit                  ║
╚═══════════════════════════════════════════════════════════════════╝
  Target: pydevtoolbox v0.2.0
  Path:   c:\projects\my-package
  Time:   3.42s

─── Configuration & Metadata [✓ PASS] ───
    Inspects pyproject.toml, build-backend, and package metadata

    ✓ PEP 621 compliant configuration detected
    ✓ Valid package name and version (0.2.0)
    ✓ License and README verified

─── Distribution Build [✓ PASS] ───
    Builds Python source distributions (sdist) and wheels (bdist_wheel)

    ✓ Successfully built pydevtoolbox-0.2.0.tar.gz
    ✓ Successfully built pydevtoolbox-0.2.0-py3-none-any.whl
    ✓ All built distributions passed twine package integrity checks.

─── Package Contents & Artifact Inspection [✓ PASS] ───
    Inspects files inside .whl and .tar.gz for missing modules & secrets

    ✓ Verified 4 module(s) bundled in wheel
    ✓ No leaked credentials or unwanted cache files

─── Installation & Import Smoke Test [✓ PASS] ───
    Installs built wheel in a clean isolated virtual environment

    ✓ Wheel installed cleanly in isolated environment
    ✓ Module Import Passed: 'shipcheck' (version: 0.2.0)
    ✓ CLI Script Verified: 'shipcheck'

═══════════════════════════════════════════════════════════════════
  AUDIT SUMMARY
═══════════════════════════════════════════════════════════════════
  Issues Found:  0 Critical | 0 Warnings | 6 Passed/Info
  Distributions Built:
    • pydevtoolbox-0.2.0-py3-none-any.whl
    • pydevtoolbox-0.2.0.tar.gz

  🚀 VERDICT: READY FOR PYPI RELEASE
═══════════════════════════════════════════════════════════════════
```

---

## 🤖 CI/CD Integration (GitHub Actions)

Catch release issues automatically on every Pull Request or push:

```yaml
name: Release Preflight Audit

on:
  push:
    branches: [main]
  pull_request:

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install ShipCheck
        run: pip install pydevtoolbox

      - name: Run ShipCheck Audit
        run: shipcheck --strict --json -o audit-report.json

      - name: Upload Audit Artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: shipcheck-report
          path: audit-report.json
```

---

## 🐍 Python API Usage

You can also run ShipCheck programmatically inside Python test suites or build scripts:

```python
from shipcheck import audit, render_report

# Run audit on current directory
report = audit(".")

# Check if release is ready
if report.has_critical_issues:
    print(f"Audit failed with {report.total_critical} critical issues!")
    print(render_report(report))
else:
    print("Package is ready for PyPI!")
    print(f"Built artifacts: {report.build_artifacts}")
```

---

## 🛡️ Checks Performed

| Code | Category | Check Description | Severity |
| :--- | :--- | :--- | :--- |
| **CFG001** | Configuration | Missing `pyproject.toml` or setup configuration | `CRITICAL` |
| **BLD001** | Configuration | Missing `[build-system]` table | `CRITICAL` |
| **META002** | Metadata | Missing or invalid package name | `CRITICAL` |
| **META005** | Metadata | Missing or non-PEP 440 compliant version | `CRITICAL` |
| **META010** | Metadata | Referenced `README` does not exist on disk | `CRITICAL` |
| **META016** | Metadata | Unreplaced placeholders (`YOUR_USERNAME`, `TODO`) | `CRITICAL` |
| **META012** | Metadata | Missing license declaration or LICENSE file | `WARNING` |
| **BLD105** | Build | Wheel or sdist build failure diagnosis | `CRITICAL` |
| **TWN001** | Build | Twine distribution metadata check failure | `CRITICAL` |
| **CNT002** | Contents | Source modules on disk missing from built wheel | `CRITICAL` |
| **CNT006** | Contents | Leaked credentials (`.env`, private keys) in wheel | `CRITICAL` |
| **INS004** | Install Test | Wheel fails installation in clean virtual environment | `CRITICAL` |
| **IMP001** | Install Test | Package fails to import after clean installation | `CRITICAL` |
| **CLI001** | Install Test | Defined CLI entrypoints fail execution | `WARNING` |

---

## 📄 License

MIT © [Izere Louise](https://github.com/loui45)