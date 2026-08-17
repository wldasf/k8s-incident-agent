"""
Metric availability probe.

Every scenario declares PromQL predicates and a resolution check. If those
series do not exist in the deployed stack, the scenario cannot be scored — and
discovering that during the experimental runs would invalidate them.

This script extracts every PromQL expression in the library, queries live
Prometheus, and reports which return data. Run it immediately after the
environment is provisioned, before building anything on top.

Usage:
    kubectl port-forward -n observability svc/kube-prom-kube-prometheus-prometheus 9090:9090 &
    python3 harness/probe_metrics.py
"""

from __future__ import annotations

import sys
import urllib.parse
import urllib.request
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scenarios.loader import load_all  # noqa: E402

PROM = "http://localhost:9090"
TIMEOUT = 20


def query(expr: str) -> tuple[bool, str]:
    """Run an instant query. Returns (has_data, note)."""
    url = f"{PROM}/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            payload = json.load(resp)
    except Exception as exc:  # noqa: BLE001
        return False, f"request failed: {exc}"

    if payload.get("status") != "success":
        return False, f"query error: {payload.get('error', 'unknown')}"

    result = payload.get("data", {}).get("result", [])
    if not result:
        return False, "no series returned"
    return True, f"{len(result)} series"


def collect_expressions():
    """Yield (scenario_id, kind, identifier, expression) for every PromQL used."""
    for s in load_all():
        for p in s.predicates:
            if p.source == "promql":
                yield s.id, "predicate", p.id, p.expr
            # http_probe predicates are measured by the harness directly and
            # are validated by harness/http_probe.py, not by Prometheus.
        if s.resolution_check.source == "promql":
            yield s.id, "resolution", "-", s.resolution_check.expr


def main() -> int:
    rows = list(collect_expressions())
    print(f"Probing {len(rows)} PromQL expressions against {PROM}\n")

    ok_count = 0
    failures: list[tuple[str, str, str, str, str]] = []

    header = f"{'scenario':9} {'kind':11} {'id':5} {'status':6} {'note':22} expression"
    print(header)
    print("-" * len(header))

    for sid, kind, pid, expr in rows:
        has_data, note = query(expr)
        status = "OK" if has_data else "EMPTY"
        if has_data:
            ok_count += 1
        else:
            failures.append((sid, kind, pid, note, expr))
        short = expr if len(expr) <= 60 else expr[:57] + "..."
        print(f"{sid:9} {kind:11} {pid:5} {status:6} {note:22} {short}")

    print(f"\n{ok_count}/{len(rows)} expressions returned data")

    if failures:
        print("\nEXPRESSIONS RETURNING NO DATA")
        print("These must be corrected before the harness is built. Common causes:")
        print("  - the metric is not exposed by the service (check /metrics on the pod)")
        print("  - label names differ from those assumed (container, job, namespace)")
        print("  - the exporter is not installed (kube-state-metrics, cadvisor)")
        print("  - the workload has not yet generated traffic for the series to appear\n")
        for sid, kind, pid, note, expr in failures:
            print(f"  {sid} [{kind} {pid}] - {note}")
            print(f"      {expr}\n")
        return 1

    print("\nAll scenario metrics are available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
