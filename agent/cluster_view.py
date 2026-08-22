"""
Cluster view.

A strictly read-only interface over the cluster: kubectl (via subprocess,
using the operator's own kubeconfig and RBAC), Prometheus, and pod logs.

Read-only by construction -- nothing in this module can mutate cluster state.
Every mutating action lives behind the safety gate, so the reasoning loop can
be handed this view with no risk of side effects. It also supplies the pod
and replica counts the gate needs for blast-radius calculation.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
import urllib.request


class ClusterView:
    def __init__(self, prometheus_url: str | None = None, kubectl: str = "kubectl"):
        # Endpoint comes from the environment so the same code runs
        # against a local port-forward or an in-cluster service IP.
        url = prometheus_url or os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
        self.prom = url.rstrip("/")
        self.kubectl = kubectl

    # ---- kubectl (read-only verbs only) ------------------------------------

    def _run(self, *args: str) -> str:
        out = subprocess.run(
            [self.kubectl, *args],
            capture_output=True, text=True, timeout=60,
        )
        if out.returncode != 0:
            return f"ERROR: {out.stderr.strip()[:800]}"
        return out.stdout

    def describe_pod(self, namespace: str, pod: str) -> str:
        return self._run("describe", "pod", pod, "-n", namespace)[:8000]

    def pods_for_workload(self, namespace: str, workload: str) -> list[dict]:
        raw = self._run("get", "pods", "-n", namespace, "-o", "json")
        if raw.startswith("ERROR"):
            return []
        items = json.loads(raw).get("items", [])
        return [
            {
                "name": p["metadata"]["name"],
                "phase": p["status"].get("phase"),
                "ready": all(c.get("ready", False)
                             for c in p["status"].get("containerStatuses", [])) or False,
                "restarts": sum(c.get("restartCount", 0)
                                for c in p["status"].get("containerStatuses", [])),
                "last_termination": [
                    c.get("lastState", {}).get("terminated", {}).get("reason")
                    for c in p["status"].get("containerStatuses", [])
                    if c.get("lastState", {}).get("terminated")
                ],
                "node": p["spec"].get("nodeName"),
            }
            for p in items
            if p["metadata"]["name"].startswith(workload)
        ]

    def get_logs(self, namespace: str, workload: str, lines: int = 200) -> str:
        pods = self.pods_for_workload(namespace, workload)
        if not pods:
            return f"no pods found for workload {workload}"
        pod = next((p for p in pods if p["restarts"] > 0), pods[0])["name"]
        cur = self._run("logs", pod, "-n", namespace, f"--tail={lines}")
        prev = self._run("logs", pod, "-n", namespace, f"--tail={lines // 2}", "--previous")
        text = cur[:6000]
        if not prev.startswith("ERROR"):
            text += "\n--- previous container instance ---\n" + prev[:3000]
        return text

    def get_events(self, namespace: str) -> str:
        return self._run("get", "events", "-n", namespace,
                         "--sort-by=.lastTimestamp")[-6000:]

    def rollout_history(self, namespace: str, workload: str) -> str:
        return self._run("rollout", "history", f"deployment/{workload}", "-n", namespace)[:2000]

    def deployment_spec_summary(self, namespace: str, workload: str) -> str:
        raw = self._run("get", "deployment", workload, "-n", namespace, "-o", "json")
        if raw.startswith("ERROR"):
            return raw
        d = json.loads(raw)
        c = d["spec"]["template"]["spec"]["containers"][0]
        return json.dumps({
            "replicas": d["spec"].get("replicas"),
            "image": c.get("image"),
            "resources": c.get("resources", {}),
            "env_count": len(c.get("env", [])),
            "readiness_probe": c.get("readinessProbe"),
        }, indent=2)

    # ---- counts for the safety gate ----------------------------------------

    def pod_count(self, namespace: str, workload: str) -> int:
        return len(self.pods_for_workload(namespace, workload))

    def pods_on_node(self, node: str) -> int:
        raw = self._run("get", "pods", "-A", "-o", "json")
        if raw.startswith("ERROR"):
            return 0
        return sum(1 for p in json.loads(raw).get("items", [])
                   if p["spec"].get("nodeName") == node)

    def replica_count(self, namespace: str, workload: str) -> int:
        raw = self._run("get", "deployment", workload, "-n", namespace, "-o", "json")
        if raw.startswith("ERROR"):
            return 0
        return json.loads(raw)["spec"].get("replicas", 0)

    # ---- Prometheus ---------------------------------------------------------

    def query_metrics(self, promql: str) -> str:
        url = f"{self.prom}/api/v1/query?" + urllib.parse.urlencode({"query": promql})
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                data = json.load(resp)
        except Exception as exc:  # noqa: BLE001
            return f"ERROR: prometheus unreachable: {exc}"
        if data.get("status") != "success":
            return f"ERROR: {data.get('error', 'query failed')}"
        results = data["data"]["result"][:20]
        if not results:
            return "no series returned"
        lines = []
        for r in results:
            labels = {k: v for k, v in r.get("metric", {}).items()
                      if k in ("pod", "container", "node", "deployment", "condition", "reason")}
            lines.append(f"{labels or r.get('metric', {})}: {r['value'][1]}")
        return "\n".join(lines)
