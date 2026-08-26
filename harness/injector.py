"""
Fault injection and teardown.

Applies a scenario's fault, then restores the cluster afterwards. Restoration
correctness is the single most important property of the harness: if run N+1
inherits residue from run N, results are quietly wrong and the contamination
is very hard to detect after the fact.

Two safeguards address this. First, the pre-injection state of any patched
resource is captured BEFORE the fault is applied and replayed verbatim on
teardown, rather than reconstructed from the scenario definition. Second,
teardown is followed by an explicit baseline health check (see runner) --
the harness verifies recovery rather than assuming it.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from dataclasses import dataclass, field


@dataclass
class InjectionState:
    """Everything needed to undo an injection."""
    scenario_id: str
    method: str
    saved_spec: dict | None = None          # pre-injection deployment spec
    chaos_resources: list[tuple] = field(default_factory=list)  # (kind, name, ns)

def _kubectl(args: list[str], stdin: str | None = None,
             truncate: int | None = 1000) -> tuple[bool, str]:
    # Output is truncated by default because most callers want a short error
    # message. Callers that parse JSON must pass truncate=None: a JSON
    # document cut at 1000 characters fails to parse, and the resulting error
    # points at the parser rather than at the truncation.
    out = subprocess.run(["kubectl", *args], capture_output=True, text=True,
                         input=stdin, timeout=180)
    text = (out.stdout or out.stderr).strip()
    return out.returncode == 0, text[:truncate] if truncate else text


def _capture_deployment(ns: str, wl: str) -> dict | None:
    ok, raw = _kubectl(["get", "deployment", wl, "-n", ns, "-o", "json"], truncate=None)
    if not ok:
        return None
    d = json.loads(raw)
    spec = d["spec"]["template"]["spec"]["containers"][0]
    return {
        "namespace": ns,
        "workload": wl,
        "container": spec["name"],
        "image": spec.get("image"),
        "resources": spec.get("resources", {}),
        "env": spec.get("env", []),
        "readinessProbe": spec.get("readinessProbe"),
        "livenessProbe": spec.get("livenessProbe"),
        "replicas": d["spec"].get("replicas", 1),
    }


def _wait_for_injection(kind: str, name: str, namespace: str,
                        timeout_s: int = 90) -> tuple[bool, str]:
    """Block until Chaos Mesh reports the fault injected, or fail loudly.

    Applying a chaos manifest and injecting a fault are different events.
    `kubectl apply` returns success once the custom resource is accepted; the
    controller then attempts injection asynchronously and records the outcome
    in status.conditions. An injector that crashes reports AllInjected=False
    while apply still succeeds, producing a run that appears normal but in
    which no fault was ever present.

    Returns (injected, detail). On failure, detail carries the controller's
    own error message where one is available.
    """
    deadline = time.monotonic() + timeout_s
    last = "no status reported"
    while time.monotonic() < deadline:
        ok, raw = _kubectl(["get", kind.lower(), name, "-n", namespace,
                            "-o", "json"], truncate=None)
        if ok:
            status = json.loads(raw).get("status", {})
            conds = {c["type"]: c["status"] for c in status.get("conditions", [])}
            if conds.get("AllInjected") == "True":
                return True, "injected"
            if conds.get("Selected") == "False":
                last = "selector matched no pods"
            # Surface the controller's own error rather than a generic timeout.
            for rec in status.get("experiment", {}).get("containerRecords", []):
                for ev in rec.get("events", []):
                    msg = ev.get("message", "")
                    if msg and "error" in msg.lower():
                        last = msg[:300]
        time.sleep(3)
    return False, f"fault not injected within {timeout_s}s: {last}"


def inject(scenario) -> tuple[bool, str, InjectionState]:
    """Apply the scenario's fault. Returns (ok, detail, state_for_teardown)."""
    ns = scenario.target.namespace
    wl = scenario.target.workload
    state = InjectionState(scenario_id=scenario.id, method=scenario.injection.method)

    if scenario.injection.method == "kubectl_patch":
        # Capture first: teardown replays this, not the scenario's guess.
        state.saved_spec = _capture_deployment(ns, wl)
        if state.saved_spec is None:
            return False, f"could not capture pre-injection state for {wl}", state
        ok, detail = _kubectl(["patch", "deployment", wl, "-n", ns,
                               "--type=strategic", "-p", json.dumps(scenario.injection.patch)])
        return ok, detail, state

    if scenario.injection.method == "chaos_mesh":
        manifest = scenario.injection.manifest
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            json.dump(manifest, fh)      # kubectl accepts JSON for -f
            path = fh.name
        ok, detail = _kubectl(["apply", "-f", path])
        if not ok:
            return False, detail, state
        kind = manifest["kind"]
        name = manifest["metadata"]["name"]
        cns = manifest["metadata"].get("namespace", "chaos-mesh")
        # Record for teardown before verifying: a partially injected fault
        # still needs cleaning up.
        state.chaos_resources.append((kind, name, cns))
        injected, idetail = _wait_for_injection(kind, name, cns)
        if not injected:
            return False, f"chaos applied but not injected: {idetail}", state
        return True, "injected", state

    return False, f"unsupported injection method: {scenario.injection.method}", state


def teardown(scenario, state: InjectionState) -> tuple[bool, str]:
    """Undo the injection. Restores from captured state, not from the YAML."""
    ns = scenario.target.namespace
    wl = scenario.target.workload
    problems: list[str] = []

    for kind, name, cns in state.chaos_resources:
        ok, detail = _kubectl(["delete", kind.lower(), name, "-n", cns, "--ignore-not-found"])
        if not ok:
            problems.append(f"chaos cleanup {kind}/{name}: {detail}")

    if state.saved_spec:
        s = state.saved_spec
        container = {"name": s["container"], "resources": s["resources"]}
        if s.get("image"):
            container["image"] = s["image"]
        if s.get("env"):
            container["env"] = s["env"]
        if s.get("readinessProbe"):
            container["readinessProbe"] = s["readinessProbe"]
        if s.get("livenessProbe"):
            container["livenessProbe"] = s["livenessProbe"]
        patch = {"spec": {"replicas": s["replicas"],
                          "template": {"spec": {"containers": [container]}}}}
        ok, detail = _kubectl(["patch", "deployment", wl, "-n", ns,
                               "--type=strategic", "-p", json.dumps(patch)])
        if not ok:
            problems.append(f"spec restore: {detail}")

    # The agent may also have acted on the workload; restore replica count
    # even for chaos-injected scenarios where no spec was captured.
    if not state.saved_spec:
        _kubectl(["scale", f"deployment/{wl}", "-n", ns, "--replicas=1"])

    # Uncordon every node: cordon_node is a legal agent action and would
    # otherwise persist across runs.
    ok, raw = _kubectl(["get", "nodes", "-o", "json"], truncate=None)
    if ok:
        for node in json.loads(raw).get("items", []):
            if node["spec"].get("unschedulable"):
                _kubectl(["uncordon", node["metadata"]["name"]])

    return (not problems), "; ".join(problems) if problems else "clean"


def wait_for_baseline(namespace: str = "boutique", timeout_s: int = 600) -> tuple[bool, str]:
    """Block until every deployment in the namespace is fully available.

    Called after teardown. Treating a failed baseline as a hard stop is what
    keeps runs independent -- without it, contamination is silent.
    """
    deadline = time.monotonic() + timeout_s
    last = "not checked"
    while time.monotonic() < deadline:
        ok, raw = _kubectl(["get", "deployments", "-n", namespace, "-o", "json"], truncate=None)
        if ok:
            items = json.loads(raw).get("items", [])
            unhealthy = [
                i["metadata"]["name"] for i in items
                if i["status"].get("availableReplicas", 0) < i["spec"].get("replicas", 1)
            ]
            # A deployment can report an available replica while a second pod
            # crash-loops, and a pre-existing crash loop went unnoticed for
            # three days because the replica count alone looked satisfied.
            # Any pod not Running in the namespace now blocks baseline.
            pok, praw = _kubectl(["get", "pods", "-n", namespace, "-o", "json"],
                                 truncate=None)
            bad_pods: list[str] = []
            if pok:
                for pod in json.loads(praw).get("items", []):
                    phase = pod["status"].get("phase")
                    waiting = [
                        c.get("state", {}).get("waiting", {}).get("reason")
                        for c in pod["status"].get("containerStatuses", [])
                    ]
                    if phase != "Running" or "CrashLoopBackOff" in waiting:
                        bad_pods.append(pod["metadata"]["name"])
            if items and not unhealthy and not bad_pods:
                return True, "baseline healthy"
            blockers = unhealthy + [f"pod:{p}" for p in bad_pods]
            last = f"waiting on: {', '.join(blockers[:5])}"
        time.sleep(10)
    return False, f"baseline not reached within {timeout_s}s ({last})"
