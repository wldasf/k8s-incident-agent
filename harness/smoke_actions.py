"""
Executor smoke test.

Dry-runs every mutating action in the catalogue against the live cluster and
reports which succeed. Because it uses --dry-run=server, the API server
validates each command without applying it: this exercises the executor's
parameter handling and command construction with no risk and no waiting.

Rationale: bugs in executor parameter handling have so far been discovered by
full experimental runs costing ~15 minutes each, when a server-side dry run
finds the same class of defect in under a second. Every action type is
exercised here, rather than only the one an agent happened to propose.

Usage (on the control plane):
    python3 -m harness.smoke_actions
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent.actions import CATALOGUE, RiskTier      # noqa: E402
from agent.cluster_view import ClusterView          # noqa: E402
from harness.executor import execute                # noqa: E402

NS = "boutique"
WL = "cartservice"

# Representative parameters per action, including the shape variants models
# have actually emitted, so the executor is tested against real inputs.
CASES: list[tuple[str, dict]] = [
    ("delete_pod",            {"namespace": NS, "workload": WL}),
    ("scale_up_one",          {"namespace": NS, "workload": WL}),
    ("scale_workload",        {"namespace": NS, "workload": WL, "replicas": 2}),
    ("rollout_restart",       {"namespace": NS, "workload": WL}),
    ("rollback_deployment",   {"namespace": NS, "workload": WL}),
    ("patch_resource_limits", {"namespace": NS, "workload": WL,
                               "container_name": "server", "memory_limit": "128Mi"}),
    ("patch_resource_limits", {"namespace": NS, "workload": WL,
                               "container_name": "server",
                               "limits": {"memory": "128Mi"},
                               "requests": {"memory": "64Mi"}}),
    ("patch_resource_limits", {"namespace": NS, "workload": WL,
                               "container_name": "server",
                               "resources": {"limits": {"cpu": "200m"}}}),
    ("cordon_node",           {"namespace": NS, "workload": WL}),
    ("cordon_node",           {"namespace": NS, "workload": WL, "node": "auto:affected"}),
    ("scale_to_zero",         {"namespace": NS, "workload": WL}),
    ("delete_deployment",     {"namespace": NS, "workload": WL}),
    ("drain_node",            {"namespace": NS, "workload": WL}),
]


def main() -> int:
    view = ClusterView()
    print(f"Dry-running {len(CASES)} action cases against {NS}/{WL}\n")
    print(f"{'action':24} {'tier':6} {'result':8} detail")
    print("-" * 100)

    failures = 0
    for action, params in CASES:
        spec = CATALOGUE.get(action)
        tier = spec.tier.name.split("_")[0] if spec else "?"
        shape = ""
        if action == "patch_resource_limits":
            shape = ("flat" if "memory_limit" in params
                     else "nested" if "limits" in params else "resources")
        res = execute(action, params, view=view, dry_run=True)
        status = "OK" if res.ok else "FAIL"
        if not res.ok:
            failures += 1
        label = f"{action}{'/' + shape if shape else ''}"
        print(f"{label:24} {tier:6} {status:8} {res.detail[:60]}")

    # Actions never proposed by the agent are still worth validating: a policy
    # change could admit them later, and a broken executor path should not be
    # discovered at that point.
    uncovered = sorted(
        n for n, s in CATALOGUE.items()
        if s.tier != RiskTier.R0_READ_ONLY and n not in {a for a, _ in CASES}
    )
    if uncovered:
        print(f"\nnot covered by this smoke test: {', '.join(uncovered)}")

    print(f"\n{len(CASES) - failures}/{len(CASES)} action cases valid")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
