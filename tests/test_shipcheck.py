"""
test_shipcheck.py - Comprehensive tests for ShipCheck package auditor.
"""

import sys
import json
import tempfile
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shipcheck import ShipCheck, audit, Severity, Issue, AuditReport, render_report
from shipcheck.checks.config_check import run_config_checks
from shipcheck.checks.contents_check import run_contents_checks


def test_models_and_json_serialization():
    """Verify AuditReport and Issue serialization to JSON."""
    report = AuditReport(
        project_name="demo-pkg",
        version="1.0.0",
        project_path="/demo",
    )
    issue = Issue(
        code="TEST01",
        severity=Severity.CRITICAL,
        title="Sample Test Issue",
        message="This is a test failure.",
        suggestion="Fix the test issue.",
    )
    from shipcheck.models import CheckCategoryResult
    cat = CheckCategoryResult(category="TestCat", description="Test Category")
    cat.add_issue(issue)
    report.categories.append(cat)

    assert report.has_critical_issues is True
    assert report.total_critical == 1
    assert report.total_warnings == 0

    json_str = report.to_json()
    data = json.loads(json_str)
    assert data["project_name"] == "demo-pkg"
    assert data["summary"]["critical"] == 1
    assert data["summary"]["success"] is False


def test_config_check_missing_config():
    """Verify detection of missing pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cat = run_config_checks(Path(tmp_dir))
        assert cat.passed is False
        assert any(issue.code == "CFG001" for issue in cat.issues)


def test_config_check_placeholder_detection():
    """Verify detection of placeholders like YOUR_USERNAME."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        p = Path(tmp_dir) / "pyproject.toml"
        p.write_text(
            """
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "test-pkg"
version = "0.1.0"
description = "TODO: add description"
readme = "README.md"

[project.urls]
Homepage = "https://github.com/YOUR_USERNAME/test-pkg"
            """,
            encoding="utf-8",
        )
        cat = run_config_checks(Path(tmp_dir))
        codes = [i.code for i in cat.issues]
        assert "META016" in codes  # Placeholder found


def test_shipcheck_on_current_project():
    """Run ShipCheck directly on the updated devhelper / pydevtoolbox project."""
    project_root = Path(__file__).parent.parent
    checker = ShipCheck(project_dir=project_root, skip_install_test=True)
    report = checker.run_audit()

    # The current project should have zero critical errors!
    crit_issues = [
        f"{i.code}: {i.title} - {i.message}"
        for cat in report.categories
        for i in cat.issues
        if i.severity == Severity.CRITICAL
    ]
    assert len(crit_issues) == 0, f"Unexpected critical issues: {crit_issues}"
    assert len(report.build_artifacts) > 0

    output = render_report(report)
    assert "READY FOR PYPI RELEASE" in output


if __name__ == "__main__":
    print("Running ShipCheck tests...")
    test_models_and_json_serialization()
    print("[PASS] Model and JSON serialization passed.")
    test_config_check_missing_config()
    print("[PASS] Missing config detection passed.")
    test_config_check_placeholder_detection()
    print("[PASS] Placeholder detection passed.")
    test_shipcheck_on_current_project()
    print("[PASS] ShipCheck audit on current project passed!")
    print("\nAll ShipCheck unit tests passed successfully!")
