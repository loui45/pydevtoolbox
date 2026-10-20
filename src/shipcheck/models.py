"""
models.py - Core data structures and severity levels for ShipCheck.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
import json


class Severity(Enum):
    PASS = "PASS"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Issue:
    code: str
    severity: Severity
    title: str
    message: str
    suggestion: str
    file: Optional[str] = None
    line: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "suggestion": self.suggestion,
            "file": self.file,
            "line": self.line,
        }


@dataclass
class CheckCategoryResult:
    category: str
    description: str
    issues: List[Issue] = field(default_factory=list)
    passed: bool = True

    def add_issue(self, issue: Issue) -> None:
        self.issues.append(issue)
        if issue.severity == Severity.CRITICAL:
            self.passed = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "description": self.description,
            "passed": self.passed,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass
class AuditReport:
    project_name: str
    version: str
    project_path: str
    categories: List[CheckCategoryResult] = field(default_factory=list)
    build_artifacts: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def has_critical_issues(self) -> bool:
        return any(
            issue.severity == Severity.CRITICAL
            for cat in self.categories
            for issue in cat.issues
        )

    @property
    def total_critical(self) -> int:
        return sum(
            1 for cat in self.categories for issue in cat.issues if issue.severity == Severity.CRITICAL
        )

    @property
    def total_warnings(self) -> int:
        return sum(
            1 for cat in self.categories for issue in cat.issues if issue.severity == Severity.WARNING
        )

    @property
    def total_info(self) -> int:
        return sum(
            1 for cat in self.categories for issue in cat.issues if issue.severity in (Severity.INFO, Severity.PASS)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "version": self.version,
            "project_path": self.project_path,
            "duration_seconds": round(self.duration_seconds, 2),
            "summary": {
                "success": not self.has_critical_issues,
                "critical": self.total_critical,
                "warnings": self.total_warnings,
                "info": self.total_info,
            },
            "categories": [cat.to_dict() for cat in self.categories],
            "build_artifacts": self.build_artifacts,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
