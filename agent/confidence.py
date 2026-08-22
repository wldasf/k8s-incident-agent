"""
Confidence estimators.

The safety gate thresholds against a confidence score, so the trustworthiness
of that score determines whether the gate is meaningful at all. Rather than
fixing one estimator, this module provides three and treats the choice as an
experimental variable.

E1  verbalised        the model states a number. Cheap; known to be
                      systematically overconfident.
E2  self-consistency  the diagnosis is sampled k times; confidence is the
                      modal agreement fraction over canonicalised answers.
                      Requires no provider-specific features.
E3  evidence-grounded the observable predicates associated with the CLAIMED
                      root cause are evaluated against live cluster state;
                      confidence is the weighted fraction that hold.

Token log-probabilities are deliberately excluded: they are unavailable or
unreliable through several commercial APIs, and sequence likelihood is a poor
proxy for factual correctness.

E3 is the only estimator grounded in observed reality rather than model
self-report, and the only one that can score a confident wrong answer low.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .cluster_view import ClusterView
from .llm_client import LLMClient
from .reasoner import AgentDecision, diagnose
from .root_cause_evidence import predicates_for

SELF_CONSISTENCY_K = 5
SELF_CONSISTENCY_TEMP = 0.7


@dataclass
class ConfidenceReport:
    """All three estimates for one incident, plus supporting detail."""
    e1_verbalised: float
    e2_self_consistency: float | None = None
    e3_evidence: float | None = None
    e2_samples: list[str] = field(default_factory=list)
    e2_modal_answer: str | None = None
    e3_predicate_results: list[tuple[str, bool, float]] = field(default_factory=list)
    extra_calls: int = 0
    extra_input_tokens: int = 0
    extra_output_tokens: int = 0

    def value(self, estimator: str) -> float:
        v = {"E1": self.e1_verbalised,
             "E2": self.e2_self_consistency,
             "E3": self.e3_evidence}[estimator]
        # An estimator that could not be computed must not read as confident.
        return 0.0 if v is None else v


# ---- E1 --------------------------------------------------------------------

def e1_verbalised(decision: AgentDecision) -> float:
    return float(decision.confidence)


# ---- E2 --------------------------------------------------------------------

def _canonical(d: AgentDecision) -> str:
    """Reduce a decision to the triple that matters for agreement."""
    return f"{d.root_cause}|{d.target.get('workload','?')}|{d.proposed_action}"


def e2_self_consistency(
    client: LLMClient,
    view: ClusterView,
    incident_context: str,
    k: int = SELF_CONSISTENCY_K,
    temperature: float = SELF_CONSISTENCY_TEMP,
) -> tuple[float, list[str], str, int, int, int]:
    """Sample the diagnosis k times and measure modal agreement.

    Returns (confidence, samples, modal_answer, calls, in_tokens, out_tokens).
    Incomplete runs are recorded as a distinct 'FAILED' answer rather than
    discarded: an agent that cannot produce a well-formed decision is not
    thereby more confident.
    """
    samples: list[str] = []
    calls = tok_in = tok_out = 0
    for _ in range(k):
        d = diagnose(client, view, incident_context, temperature=temperature)
        samples.append(_canonical(d) if d.completed else "FAILED")
        calls += 1
        tok_in += d.input_tokens
        tok_out += d.output_tokens
    counts = Counter(samples)
    modal, n = counts.most_common(1)[0]
    return n / len(samples), samples, modal, calls, tok_in, tok_out


# ---- E3 --------------------------------------------------------------------

def _eval_numeric(value: float, threshold: float | None, comparison: str) -> bool:
    if threshold is None:
        return False
    if comparison == "gt":
        return value > threshold
    if comparison == "lt":
        return value < threshold
    return False


def _promql_scalar(view: ClusterView, expr: str) -> float | None:
    """Run a PromQL query and reduce it to a single number (max of series)."""
    raw = view.query_metrics(expr)
    if raw.startswith("ERROR") or raw == "no series returned":
        return None
    values: list[float] = []
    for line in raw.splitlines():
        m = re.search(r":\s*([-\d.eE+]+)\s*$", line)
        if m:
            try:
                values.append(float(m.group(1)))
            except ValueError:
                pass
    return max(values) if values else None


def e3_evidence_grounded(
    view: ClusterView,
    decision: AgentDecision,
    probe_result=None,
) -> tuple[float, list[tuple[str, bool, float]]]:
    """Score the claimed root cause against observable evidence.

    Predicates are selected by the root cause the agent CLAIMED, not the true
    one, so a confident incorrect diagnosis scores low. Predicates that cannot
    be evaluated (e.g. an http_probe predicate with no probe result supplied)
    are excluded from both numerator and denominator rather than counted as
    false, so a missing measurement neither inflates nor deflates the score.
    """
    ns = decision.target.get("namespace") or decision.params.get("namespace", "")
    wl = decision.target.get("workload") or decision.params.get("workload", "")
    preds = predicates_for(decision.root_cause)
    if not preds:
        return 0.0, []

    results: list[tuple[str, bool, float]] = []
    num = den = 0.0

    for p in preds:
        holds: bool | None = None

        if p.source == "promql":
            val = _promql_scalar(view, p.expr.format(ns=ns, wl=wl))
            holds = None if val is None else _eval_numeric(val, p.threshold, p.comparison)

        elif p.source == "k8s_field":
            kind, _, needle = p.expr.partition(":")
            pods = view.pods_for_workload(ns, wl)
            if not pods:
                holds = None
            elif kind == "last_termination_contains":
                holds = any(needle in (r or "") for pod in pods for r in pod["last_termination"])
            elif kind == "waiting_reason_contains":
                raw = view.describe_pod(ns, pods[0]["name"])
                holds = needle.lower() in raw.lower()
            else:
                holds = None

        elif p.source == "log_match":
            text = view.get_logs(ns, wl) + "\n" + view.get_events(ns)
            holds = re.search(p.expr, text, re.IGNORECASE) is not None

        elif p.source == "http_probe":
            if probe_result is None:
                holds = None
            else:
                holds = _eval_numeric(probe_result.value(p.expr), p.threshold, p.comparison)

        if holds is None:
            continue
        results.append((p.description, holds, p.weight))
        den += p.weight
        if holds:
            num += p.weight

    return (num / den if den > 0 else 0.0), results


# ---- combined --------------------------------------------------------------

def compute_all(
    client: LLMClient,
    view: ClusterView,
    incident_context: str,
    decision: AgentDecision,
    probe_result=None,
    include_e2: bool = True,
) -> ConfidenceReport:
    """Compute every estimator for one incident.

    E2 is optional because it costs k extra model calls; disabling it is a
    valid experimental condition and keeps pilot runs cheap.
    """
    report = ConfidenceReport(e1_verbalised=e1_verbalised(decision))

    if include_e2:
        conf, samples, modal, calls, ti, to = e2_self_consistency(client, view, incident_context)
        report.e2_self_consistency = conf
        report.e2_samples = samples
        report.e2_modal_answer = modal
        report.extra_calls += calls
        report.extra_input_tokens += ti
        report.extra_output_tokens += to

    e3, details = e3_evidence_grounded(view, decision, probe_result)
    report.e3_evidence = e3
    report.e3_predicate_results = details
    return report
