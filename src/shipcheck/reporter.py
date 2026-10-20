"""
reporter.py - Terminal and JSON reporters with rich explanations and practical suggestions.
"""

import sys
import os
from .models import AuditReport, Severity, Issue


class TerminalColors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"


def supports_color() -> bool:
    """Check whether the current output environment supports ANSI color codes."""
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    return True


def _safe_glyph(char: str, fallback: str) -> str:
    try:
        enc = sys.stdout.encoding or "utf-8"
        char.encode(enc)
        return char
    except Exception:
        return fallback

GLYPH_PASS = _safe_glyph("✓", "[PASS]")
GLYPH_FAIL = _safe_glyph("✗", "[FAIL]")
GLYPH_WARN = _safe_glyph("⚠", "[WARN]")
GLYPH_INFO = _safe_glyph("ℹ", "[INFO]")
GLYPH_CRIT = _safe_glyph("✖", "[CRIT]")


class TerminalReporter:
    """Renders human-friendly, colorized audit reports with practical suggestions."""

    def __init__(self, color: bool = True, verbose: bool = False):
        self.use_color = color and supports_color()
        self.verbose = verbose

    def _c(self, text: str, color_code: str) -> str:
        if not self.use_color:
            return text
        return f"{color_code}{text}{TerminalColors.RESET}"

    def render(self, report: AuditReport) -> str:
        lines = []

        # Banner
        lines.append("")
        lines.append(self._c("===================================================================", TerminalColors.CYAN))
        lines.append(self._c("                  ShipCheck Package Release Audit                  ", TerminalColors.CYAN + TerminalColors.BOLD))
        lines.append(self._c("===================================================================", TerminalColors.CYAN))
        lines.append(f"  {self._c('Target:', TerminalColors.BOLD)} {report.project_name} v{report.version}")
        lines.append(f"  {self._c('Path:', TerminalColors.BOLD)}   {report.project_path}")
        lines.append(f"  {self._c('Time:', TerminalColors.BOLD)}   {report.duration_seconds:.2f}s")
        lines.append("")

        for cat in report.categories:
            status_icon = self._c(f"{GLYPH_PASS} PASS", TerminalColors.GREEN + TerminalColors.BOLD) if cat.passed else self._c(f"{GLYPH_FAIL} FAIL", TerminalColors.RED + TerminalColors.BOLD)
            lines.append(f"--- {self._c(cat.category, TerminalColors.BOLD)} [{status_icon}] ---")
            lines.append(self._c(f"    {cat.description}", TerminalColors.DIM))
            lines.append("")

            if not cat.issues:
                lines.append(f"    {self._c(GLYPH_PASS, TerminalColors.GREEN)} No issues detected in this phase.")
                lines.append("")
                continue

            for issue in cat.issues:
                if issue.severity == Severity.PASS:
                    lines.append(f"    {self._c(GLYPH_PASS, TerminalColors.GREEN)} {issue.title}")
                    if self.verbose and issue.message:
                        lines.append(self._c(f"      {issue.message}", TerminalColors.DIM))
                elif issue.severity == Severity.INFO:
                    lines.append(f"    {self._c(GLYPH_INFO, TerminalColors.CYAN)} [{issue.code}] {self._c(issue.title, TerminalColors.BOLD)}")
                    lines.append(f"      {issue.message}")
                    if issue.suggestion:
                        lines.append(self._c(f"      * Suggestion: {issue.suggestion}", TerminalColors.CYAN))
                elif issue.severity == Severity.WARNING:
                    lines.append(f"    {self._c(GLYPH_WARN, TerminalColors.YELLOW)} [{issue.code}] {self._c(issue.title, TerminalColors.YELLOW + TerminalColors.BOLD)}")
                    lines.append(f"      {issue.message}")
                    if issue.suggestion:
                        lines.append(self._c(f"      * Suggestion: {issue.suggestion}", TerminalColors.YELLOW))
                elif issue.severity == Severity.CRITICAL:
                    lines.append(f"    {self._c(GLYPH_CRIT, TerminalColors.RED)} [{issue.code}] {self._c(issue.title, TerminalColors.RED + TerminalColors.BOLD)}")
                    lines.append(f"      {self._c(issue.message, TerminalColors.RED)}")
                    if issue.suggestion:
                        lines.append(self._c(f"      * Fix: {issue.suggestion}", TerminalColors.GREEN + TerminalColors.BOLD))

                if issue.file:
                    loc = f"{issue.file}:{issue.line}" if issue.line else issue.file
                    lines.append(self._c(f"      File: {loc}", TerminalColors.DIM))
                lines.append("")

        # Summary box
        lines.append("=" * 67)
        lines.append(self._c("  AUDIT SUMMARY", TerminalColors.BOLD))
        lines.append("=" * 67)
        crit_str = self._c(f"{report.total_critical} Critical", TerminalColors.RED + TerminalColors.BOLD if report.total_critical else TerminalColors.GREEN)
        warn_str = self._c(f"{report.total_warnings} Warnings", TerminalColors.YELLOW if report.total_warnings else TerminalColors.GREEN)
        info_str = self._c(f"{report.total_info} Passed/Info", TerminalColors.CYAN)
        lines.append(f"  Issues Found:  {crit_str} | {warn_str} | {info_str}")

        if report.build_artifacts:
            lines.append("  Distributions Built:")
            for art in report.build_artifacts:
                lines.append(f"    * {os.path.basename(art)}")

        lines.append("")
        if not report.has_critical_issues:
            ready_icon = _safe_glyph("🚀", "[OK]")
            lines.append(
                self._c(f"  {ready_icon} VERDICT: READY FOR PYPI RELEASE", TerminalColors.GREEN + TerminalColors.BOLD)
            )
            if report.total_warnings > 0:
                lines.append(self._c("     (Review non-blocking warnings above for best packaging practices)", TerminalColors.YELLOW))
        else:
            block_icon = _safe_glyph("⛔", "[BLOCKED]")
            lines.append(
                self._c(f"  {block_icon} VERDICT: RELEASE BLOCKED", TerminalColors.RED + TerminalColors.BOLD)
            )
            lines.append(self._c(f"     Resolve {report.total_critical} critical issue(s) before uploading to PyPI.", TerminalColors.RED))
        lines.append("=" * 67)
        lines.append("")

        return "\n".join(lines)


def render_report(report: AuditReport, json_output: bool = False, verbose: bool = False) -> str:
    """Format and return audit report as JSON or styled terminal output."""
    if json_output:
        return report.to_json(indent=2)
    reporter = TerminalReporter(verbose=verbose)
    return reporter.render(report)
