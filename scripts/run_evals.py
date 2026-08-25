#!/usr/bin/env python3
"""Eval runner for Business Decision OS — runs golden cases against the live dev API."""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime
from pathlib import Path

import httpx

from packages.agent.evals.runner import EvalRunner

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
_log = logging.getLogger(__name__)


def build_report(results: list, cases_path: Path, api_url: str) -> str:
    """Build a markdown report from EvalResult list."""
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    lines = [
        "# Eval Run Report",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Cases:** {cases_path}",
        f"**API:** {api_url}",
        f"**Result:** {passed}/{total} PASS",
        "",
        "## Per-Case Results",
        "",
        "| Case | Passed | Tools Called | Failure Type | Notes |",
        "|---|---|---|---|---|",
    ]

    for r in results:
        passed_str = "✓ PASS" if r.passed else "✗ FAIL"
        tools_str = ", ".join(r.tools_called) if r.tools_called else "(none)"
        failure = r.failure_type or ""
        notes = ""
        if r.missing_required_tools:
            notes += f"missing: {', '.join(r.missing_required_tools)}; "
        if r.prohibited_tools_called:
            notes += f"prohibited: {', '.join(r.prohibited_tools_called)}; "
        if r.assertion_misses:
            notes += f"assertion misses: {', '.join(r.assertion_misses[:2])}; "
        lines.append(
            f"| {r.case_id} | {passed_str} | {tools_str[:50]} | {failure} | {notes.strip('; ')} |"
        )

    # Failure breakdown
    failure_counts: dict[str, int] = {}
    for r in results:
        if r.failure_type:
            failure_counts[r.failure_type] = failure_counts.get(r.failure_type, 0) + 1

    lines += [
        "",
        "## Failure Breakdown",
        "",
        "| Type | Count |",
        "|---|---|",
    ]
    for ftype, count in sorted(failure_counts.items()):
        lines.append(f"| {ftype} | {count} |")

    if not failure_counts:
        lines.append("| (none) | — |")

    return "\n".join(lines) + "\n"


async def main(args: argparse.Namespace) -> int:
    cases_path = Path(args.cases_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    runner = EvalRunner(api_base_url=args.api_url)
    cases = runner.load_cases(cases_path)
    _log.info("Loaded %d eval cases from %s", len(cases), cases_path)

    if args.dry_run:
        _log.info("Dry run — printing cases without running")
        for case in cases:
            print(f"  {case.id}: {case.spec_question[:60]}... required_tools={case.required_tools}")
        return 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        results = await runner.run_all(cases, client)

    for r in results:
        status = "PASS" if r.passed else f"FAIL ({r.failure_type})"
        _log.info("  %s: %s tools=%s", r.case_id, status, r.tools_called)

    passed = sum(1 for r in results if r.passed)
    _log.info("Result: %d/%d PASS", passed, len(results))

    report = build_report(results, cases_path, args.api_url)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    report_path = output_dir / f"{timestamp}-eval-run.md"
    report_path.write_text(report)
    _log.info("Report written to %s", report_path)

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run BDOS eval suite")
    parser.add_argument("--api-url", default="http://localhost:8002", help="API base URL")
    parser.add_argument(
        "--cases-path",
        default="data/evals/spec10_golden_cases.yaml",
        help="Path to golden cases YAML",
    )
    parser.add_argument(
        "--output-dir",
        default="docs/eval-reports",
        help="Output directory for reports",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print cases without running")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args)))
