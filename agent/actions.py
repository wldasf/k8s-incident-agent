"""
Action catalogue and risk classification.

Every action the agent may propose is declared here with an explicit risk tier
and a blast-radius function. This module is the formal basis of the safety gate:
the gate's decisions are defined entirely in terms of the tier and blast radius
declared here, so "how risky is this action?" is answered by a versioned
artifact rather than by the model's own judgement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Callable


class RiskTier(IntEnum):
    """Ordered risk classification. Higher is more dangerous.

    R0  Read-only. No cluster state is modified. Always permitted.
    R1  Reversible, narrow. Affects a single pod; recovers automatically.
    R2  Reversible, wide. Affects a whole workload or node scheduling.
    R3  Irreversible or destructive. Data loss or unrecoverable state change.
    """

    R0_READ_ONLY = 0
    R1_REVERSIBLE_NARROW = 1
    R2_REVERSIBLE_WIDE = 2
    R3_DESTRUCTIVE = 3


@dataclass(frozen=True)
class ActionSpec:
    """Declarative specification of one action.

    name          stable identifier used in agent output and policy files
    tier          risk classification, used by the safety gate
    reversible    whether the cluster returns to its prior state unaided
    describes     one-line human-readable summary for the audit log
    blast_radius  callable mapping (cluster_view, params) -> int pods affected
    """

    name: str
    tier: RiskTier
    reversible: bool
    describes: str
    blast_radius: Callable[..., int]


def _single_pod(_view, _params) -> int:
    return 1


def _pods_in_workload(view, params) -> int:
    """Number of pods belonging to the target workload."""
    return max(1, view.pod_count(params.get("namespace"), params.get("workload")))


def _pods_on_node(view, params) -> int:
    return max(1, view.pods_on_node(params.get("node")))


def _replica_delta(view, params) -> int:
    current = view.replica_count(params.get("namespace"), params.get("workload"))
    return abs(int(params.get("replicas", current)) - current)


# --- Catalogue -------------------------------------------------------------
# Read-only diagnostics (R0) are always available to the reasoning loop and are
# never gated; they are listed here so the audit log can record them uniformly.

CATALOGUE: dict[str, ActionSpec] = {
    # ---- R0: diagnostics -------------------------------------------------
    "describe_pod": ActionSpec(
        "describe_pod", RiskTier.R0_READ_ONLY, True,
        "Read pod spec and status", _single_pod),
    "get_logs": ActionSpec(
        "get_logs", RiskTier.R0_READ_ONLY, True,
        "Read recent container logs", _single_pod),
    "query_metrics": ActionSpec(
        "query_metrics", RiskTier.R0_READ_ONLY, True,
        "Execute a PromQL range query", lambda v, p: 0),
    "get_events": ActionSpec(
        "get_events", RiskTier.R0_READ_ONLY, True,
        "Read namespace events", lambda v, p: 0),
    "rollout_history": ActionSpec(
        "rollout_history", RiskTier.R0_READ_ONLY, True,
        "Read deployment revision history", lambda v, p: 0),

    # ---- R1: narrow, self-healing ----------------------------------------
    "delete_pod": ActionSpec(
        "delete_pod", RiskTier.R1_REVERSIBLE_NARROW, True,
        "Delete one pod; controller recreates it", _single_pod),
    "scale_up_one": ActionSpec(
        "scale_up_one", RiskTier.R1_REVERSIBLE_NARROW, True,
        "Increase replica count by one", lambda v, p: 1),

    # ---- R2: wide but recoverable ----------------------------------------
    "rollout_restart": ActionSpec(
        "rollout_restart", RiskTier.R2_REVERSIBLE_WIDE, True,
        "Restart every pod in a deployment", _pods_in_workload),
    "scale_workload": ActionSpec(
        "scale_workload", RiskTier.R2_REVERSIBLE_WIDE, True,
        "Set replica count to an arbitrary value", _replica_delta),
    "rollback_deployment": ActionSpec(
        "rollback_deployment", RiskTier.R2_REVERSIBLE_WIDE, True,
        "Roll deployment back to previous revision", _pods_in_workload),
    "patch_resource_limits": ActionSpec(
        "patch_resource_limits", RiskTier.R2_REVERSIBLE_WIDE, True,
        "Modify container resource requests or limits", _pods_in_workload),
    "cordon_node": ActionSpec(
        "cordon_node", RiskTier.R2_REVERSIBLE_WIDE, True,
        "Mark node unschedulable", lambda v, p: 0),

    # ---- R3: destructive --------------------------------------------------
    "drain_node": ActionSpec(
        "drain_node", RiskTier.R3_DESTRUCTIVE, False,
        "Evict all pods from a node", _pods_on_node),
    "scale_to_zero": ActionSpec(
        "scale_to_zero", RiskTier.R3_DESTRUCTIVE, False,
        "Scale a workload to zero replicas", _pods_in_workload),
    "delete_deployment": ActionSpec(
        "delete_deployment", RiskTier.R3_DESTRUCTIVE, False,
        "Delete a deployment entirely", _pods_in_workload),
    "delete_pvc": ActionSpec(
        "delete_pvc", RiskTier.R3_DESTRUCTIVE, False,
        "Delete a persistent volume claim (data loss)", lambda v, p: 1),
}


def spec_for(action_name: str) -> ActionSpec | None:
    return CATALOGUE.get(action_name)


def tier_of(action_name: str) -> RiskTier | None:
    spec = CATALOGUE.get(action_name)
    return spec.tier if spec else None
