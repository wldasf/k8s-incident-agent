"""
Action executor.

Translates a gated decision into kubectl commands. Reached only after the
safety gate returns EXECUTE -- this module performs no checks of its own and
must never be called directly.

Supports a dry-run mode used by the gate's precondition check (rule 5): the
same command is issued with --dry-run=server, so the API server validates it
without applying it. A failing dry run causes the gate to escalate.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class ExecResult:
    ok: bool
    detail: str
    command: str


def _kubectl(args: list[str], dry_run: bool = False) -> ExecResult:
    cmd = ["kubectl", *args]
    if dry_run:
        cmd.append("--dry-run=server")
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return ExecResult(out.returncode == 0,
                      (out.stdout or out.stderr).strip()[:500],
                      " ".join(cmd))


def execute(action: str, params: dict, view=None, dry_run: bool = False) -> ExecResult:
    ns = params.get("namespace", "")
    wl = params.get("workload", "")

    if action == "delete_pod":
        pods = view.pods_for_workload(ns, wl) if view else []
        if not pods:
            return ExecResult(False, f"no pods found for {wl}", "")
        # Prefer the unhealthy pod: deleting a healthy one is a wider action
        # than the incident warrants.
        target = next((p for p in pods if p["restarts"] > 0 or not p["ready"]), pods[0])
        return _kubectl(["delete", "pod", target["name"], "-n", ns], dry_run)

    if action == "scale_up_one":
        current = view.replica_count(ns, wl) if view else 1
        return _kubectl(["scale", f"deployment/{wl}", "-n", ns,
                         f"--replicas={current + 1}"], dry_run)

    if action == "scale_workload":
        replicas = int(params.get("replicas", 2))
        return _kubectl(["scale", f"deployment/{wl}", "-n", ns,
                         f"--replicas={replicas}"], dry_run)

    if action == "rollout_restart":
        return _kubectl(["rollout", "restart", f"deployment/{wl}", "-n", ns], dry_run)

    if action == "rollback_deployment":
        # --dry-run is not supported by rollout undo; validate existence instead.
        if dry_run:
            return _kubectl(["get", "deployment", wl, "-n", ns], dry_run=False)
        return _kubectl(["rollout", "undo", f"deployment/{wl}", "-n", ns])

    if action == "patch_resource_limits":
        container = params.get("container_name") or params.get("container") or "server"
        limits, requests = {}, {}
        if params.get("memory_limit"):
            limits["memory"] = params["memory_limit"]
        if params.get("cpu_limit"):
            limits["cpu"] = params["cpu_limit"]
        if params.get("memory_request"):
            requests["memory"] = params["memory_request"]
        if params.get("cpu_request"):
            requests["cpu"] = params["cpu_request"]
        if not limits and not requests:
            return ExecResult(False, "no resource values supplied in params", "")
        resources = {}
        if limits:
            resources["limits"] = limits
        if requests:
            resources["requests"] = requests
        patch = {"spec": {"template": {"spec": {"containers":
                 [{"name": container, "resources": resources}]}}}}
        return _kubectl(["patch", "deployment", wl, "-n", ns,
                         "--type=strategic", "-p", json.dumps(patch)], dry_run)

    if action == "cordon_node":
        node = params.get("node", "")
        if not node or node.startswith("auto"):
            # Resolve "the affected node" to where the workload actually runs.
            pods = view.pods_for_workload(ns, wl) if view else []
            node = pods[0]["node"] if pods else ""
        if not node:
            return ExecResult(False, "could not resolve target node", "")
        return _kubectl(["cordon", node], dry_run)

    # ---- R3 destructive actions -------------------------------------------
    if action == "scale_to_zero":
        return _kubectl(["scale", f"deployment/{wl}", "-n", ns, "--replicas=0"], dry_run)

    if action == "delete_deployment":
        return _kubectl(["delete", "deployment", wl, "-n", ns], dry_run)

    if action == "drain_node":
        node = params.get("node", "")
        if not node:
            pods = view.pods_for_workload(ns, wl) if view else []
            node = pods[0]["node"] if pods else ""
        if not node:
            return ExecResult(False, "could not resolve target node", "")
        return _kubectl(["drain", node, "--ignore-daemonsets",
                         "--delete-emptydir-data", "--force", "--timeout=60s"], dry_run)

    if action == "delete_pvc":
        pvc = params.get("pvc", "")
        if not pvc:
            return ExecResult(False, "no pvc named in params", "")
        return _kubectl(["delete", "pvc", pvc, "-n", ns], dry_run)

    return ExecResult(False, f"executor has no implementation for '{action}'", "")


def dry_run_check(action: str, params: dict, view=None):
    """Adapter matching the signature the safety gate expects."""
    r = execute(action, params, view=view, dry_run=True)
    return r.ok, r.detail
