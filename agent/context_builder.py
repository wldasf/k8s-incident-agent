"""
Context builder.

Assembles the incident context the model receives: a compact, structured
snapshot of the affected workload. Deliberately scenario-blind -- it is given
a namespace and workload, never a scenario id, so the agent cannot shortcut
diagnosis by recognising the experiment.
"""

from __future__ import annotations

from .cluster_view import ClusterView


def build_context(view: ClusterView, namespace: str, workload: str) -> str:
    pods = view.pods_for_workload(namespace, workload)
    pod_lines = "\n".join(
        f"  {p['name']}: phase={p['phase']} ready={p['ready']} "
        f"restarts={p['restarts']} last_termination={p['last_termination'] or 'none'} "
        f"node={p['node']}"
        for p in pods
    ) or "  (no pods found)"

    return f"""An alert has fired for workload '{workload}' in namespace '{namespace}'.

POD STATUS:
{pod_lines}

DEPLOYMENT SPEC (summary):
{view.deployment_spec_summary(namespace, workload)}

RECENT EVENTS (namespace, oldest first):
{view.get_events(namespace)[-3000:]}

You may use diagnostic tools to gather more evidence (logs, metrics,
rollout history) before giving your final answer."""
