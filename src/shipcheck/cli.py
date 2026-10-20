"""
cli.py - Command-line interface for ShipCheck release auditor.
"""

import sys
import argparse
from pathlib import Path

from . import __version__
from .auditor import ShipCheck
from .reporter import render_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shipcheck",
        description="ShipCheck: Python Package Release Auditing Tool for PyPI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  shipcheck                         # Audit current package
  shipcheck /path/to/project        # Audit specific package directory
  shipcheck --json                  # Output structured JSON for CI/CD
  shipcheck --output report.json    # Save report to a file
  shipcheck --skip-install          # Skip isolated environment smoke test
  shipcheck --strict                # Treat warnings as errors (exit code 1)
        """,
    )

    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to the Python project directory (default: current directory).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format for automated pipelines.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Write report output to specified file path.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip distribution build and only audit configuration & metadata.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip testing installation in an isolated virtual environment.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail (exit code 1) if any warnings are detected, even if no critical errors.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Include detailed passing checks and verbose build logs.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit.",
    )

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_path = Path(args.path).resolve()
    if not project_path.is_dir():
        print(f"Error: Directory '{project_path}' does not exist.", file=sys.stderr)
        return 1

    auditor = ShipCheck(
        project_dir=project_path,
        skip_build=args.skip_build,
        skip_install_test=args.skip_install,
    )

    report = auditor.run_audit()

    formatted_output = render_report(
        report=report,
        json_output=args.json,
        verbose=args.verbose,
    )

    if args.output:
        try:
            output_path = Path(args.output)
            output_path.write_text(formatted_output, encoding="utf-8")
            if not args.json:
                print(f"Report written to {output_path}")
        except Exception as e:
            print(f"Error writing report to '{args.output}': {e}", file=sys.stderr)
            return 1
    else:
        print(formatted_output)

    if report.has_critical_issues:
        return 1
    if args.strict and report.total_warnings > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
