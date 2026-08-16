"""
The safety gate.

This is the component under study. It implements a total decision function

    gate : (proposed_action, confidence, cluster_view, policy) -> Decision

where Decision is exactly one of EXECUTE, ESCALATE or DENY. Every branch
records a machine-readable reason so that experimental results can be
attributed to a specific rule rather than to the model's behaviour in
aggregate.

Design rationale
----------------
Three properties matter for the experiment:

1.  *Determinism.* Given the same inputs the gate always returns the same
    decision, so any variance across repetitions is attributable to the agent
    rather than to the gate.
2.  *Configurability along measurable axes.* A policy is a set of numeric
    thresholds and an allowed action set. "Tightening the policy" therefore
    means changing a stated number, which makes the automation-rate versus
    error-rate trade-off directly measurable.
3.  *Fail-closed.* Any condition the gate cannot evaluate results in
    ESCALATE, never EXECUTE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import yaml

from .actions import RiskTier, spec_for


class Decision(str, Enum):
    EXECUTE = "EXECUTE"
    ESCALATE = "ESCALATE"
    DENY = "DENY"


class Reason(str, Enum):
    """Machine-readable justification, recorded for every gate invocation."""

    UNKNOWN_ACTION = "unknown_action"
    TIER_NOT_ALLOWED = "tier_not_allowed"
    ACTION_NOT_ALLOWED = "action_not_allowed"
    DRY_RUN_FAILED = "dry_run_failed"
    BLAST_RADIUS_EXCEEDED = "blast_radius_exceeded"
    CONFIDENCE_BELOW_THRESHOLD = "confidence_below_threshold"
    BUDGET_EXHAUSTED = "budget_exhausted"
    WITHIN_POLICY = "within_policy"
    EVALUATION_ERROR = "evaluation_error"


@dataclass
class Policy:
    """A safety policy. Serialised to YAML and versioned with the benchmark."""

    name: str
    # Minimum confidence required to execute autonomously, per risk tier.
    thresholds: dict[RiskTier, float]
    # Maximum number of pods an action may affect, per risk tier.
    blast_caps: dict[RiskTier, int]
    # Tiers the agent may act in at all.
    allowed_tiers: set[RiskTier]
    # Optional explicit allow-list; empty means "any action in an allowed tier".
    allowed_actions: set[str] = field(default_factory=set)
    # Maximum autonomous actions per incident before forced escalation.
    action_budget: int = 3

    @staticmethod
    def from_yaml(path: str) -> "Policy":
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return Policy(
            name=raw["name"],
            thresholds={RiskTier[k]: float(v) for k, v in raw["thresholds"].items()},
            blast_caps={RiskTier[k]: int(v) for k, v in raw["blast_caps"].items()},
            allowed_tiers={RiskTier[t] for t in raw["allowed_tiers"]},
            allowed_actions=set(raw.get("allowed_actions", []) or []),
            action_budget=int(raw.get("action_budget", 3)),
        )


@dataclass
class GateResult:
    decision: Decision
    reason: Reason
    # Everything below is recorded in the audit log for later analysis.
    action: str
    tier: RiskTier | None
    confidence: float
    threshold: float | None
    blast_radius: int | None
    blast_cap: int | None
    detail: str = ""


def evaluate(
    action: str,
    params: dict[str, Any],
    confidence: float,
    cluster_view,
    policy: Policy,
    actions_taken: int = 0,
    dry_run_fn=None,
) -> GateResult:
    """Decide whether a proposed action may be executed autonomously.

    Rules are applied in a fixed order, cheapest and most categorical first,
    so that the recorded reason identifies the *first* rule that blocked the
    action. This ordering is part of the specification and must not change
    between experimental conditions.
    """

    spec = spec_for(action)

    # Rule 1 — the action must exist in the catalogue.
    if spec is None:
        return GateResult(Decision.DENY, Reason.UNKNOWN_ACTION,
                          action, None, confidence, None, None, None,
                          "action not present in catalogue")

    # Read-only diagnostics bypass the gate entirely.
    if spec.tier == RiskTier.R0_READ_ONLY:
        return GateResult(Decision.EXECUTE, Reason.WITHIN_POLICY,
                          action, spec.tier, confidence, 0.0, 0, None,
                          "read-only action")

    # Rule 2 — the tier must be permitted by the policy.
    if spec.tier not in policy.allowed_tiers:
        return GateResult(Decision.DENY, Reason.TIER_NOT_ALLOWED,
                          action, spec.tier, confidence, None, None, None,
                          f"tier {spec.tier.name} disallowed by policy '{policy.name}'")

    # Rule 3 — if an explicit allow-list is configured, honour it.
    if policy.allowed_actions and action not in policy.allowed_actions:
        return GateResult(Decision.DENY, Reason.ACTION_NOT_ALLOWED,
                          action, spec.tier, confidence, None, None, None,
                          "action not in policy allow-list")

    # Rule 4 — per-incident action budget.
    if actions_taken >= policy.action_budget:
        return GateResult(Decision.ESCALATE, Reason.BUDGET_EXHAUSTED,
                          action, spec.tier, confidence, None, None, None,
                          f"budget of {policy.action_budget} actions exhausted")

    # Rule 5 — server-side dry run must succeed (fail closed on error).
    if dry_run_fn is not None:
        try:
            ok, detail = dry_run_fn(action, params)
        except Exception as exc:  # noqa: BLE001 - fail closed by design
            return GateResult(Decision.ESCALATE, Reason.EVALUATION_ERROR,
                              action, spec.tier, confidence, None, None, None,
                              f"dry-run raised: {exc}")
        if not ok:
            return GateResult(Decision.ESCALATE, Reason.DRY_RUN_FAILED,
                              action, spec.tier, confidence, None, None, None,
                              detail)

    # Rule 6 — blast radius must be within the cap for this tier.
    try:
        radius = spec.blast_radius(cluster_view, params)
    except Exception as exc:  # noqa: BLE001 - fail closed by design
        return GateResult(Decision.ESCALATE, Reason.EVALUATION_ERROR,
                          action, spec.tier, confidence, None, None, None,
                          f"blast radius not computable: {exc}")

    cap = policy.blast_caps.get(spec.tier)
    if cap is not None and radius > cap:
        return GateResult(Decision.ESCALATE, Reason.BLAST_RADIUS_EXCEEDED,
                          action, spec.tier, confidence, None, radius, cap,
                          f"{radius} pods affected, cap is {cap}")

    # Rule 7 — confidence must meet the threshold for this tier.
    threshold = policy.thresholds.get(spec.tier, 1.0)
    if confidence < threshold:
        return GateResult(Decision.ESCALATE, Reason.CONFIDENCE_BELOW_THRESHOLD,
                          action, spec.tier, confidence, threshold, radius, cap,
                          f"confidence {confidence:.2f} < threshold {threshold:.2f}")

    return GateResult(Decision.EXECUTE, Reason.WITHIN_POLICY,
                      action, spec.tier, confidence, threshold, radius, cap,
                      "all checks passed")
