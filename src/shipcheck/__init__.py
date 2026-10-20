"""
ShipCheck - Python Package Release Auditing Tool for PyPI.

Audits project configuration, builds wheels/sdist, inspects archives for missing files,
and verifies clean isolated installation and importing before publishing to PyPI.
"""

__version__ = "0.2.0"
__author__ = "Izere Louise"

from .models import AuditReport, CheckCategoryResult, Issue, Severity
from .auditor import ShipCheck, audit
from .reporter import render_report

__all__ = [
    "__version__",
    "ShipCheck",
    "audit",
    "AuditReport",
    "CheckCategoryResult",
    "Issue",
    "Severity",
    "render_report",
]
