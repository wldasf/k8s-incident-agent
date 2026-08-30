"""
Analysis of the policy conditions.

Produces the figures and tables reported in the results chapter:
accuracy by fault class and condition, gate behaviour, outcome distribution,
confidence calibration per estimator, and the threshold sweep that is the
study's central result.

The threshold sweep is derived rather than collected. Every run records all
three confidence estimators regardless of which one gated the decision, so
the gate's behaviour under a different threshold can be recomputed from
stored values. This avoids running a separate experimental arm per threshold,
which would have been prohibitive, but it carries an assumption worth
stating: it holds the agent's diagnosis fixed and varies only the gate. That
is sound here because the agent is not told which policy is running --
confirmed by strict accuracy being near-constant across the three conditions
(17, 19, 19 of 30).

Usage:
    python3 analyse.py results/*.jsonl
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RISK_TIER_ORDER = {"R0_READ_ONLY": 0, "R1_REVERSIBLE_NARROW": 1,
                   "R2_REVERSIBLE_WIDE": 2, "R3_DESTRUCTIVE": 3}

# Tier permissions per policy, mirroring agent/policies/*.yaml. Needed to
# recompute gate decisions under swept thresholds.
POLICY_TIERS = {
    "permissive":   {0, 1, 2, 3},
    "balanced":     {0, 1, 2},
    "conservative": {0, 1},
}


def load(paths: list[str]) -> list[dict]:
    rows: list[dict] = []
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return [r for r in rows if r.get("status") == "ok"]


def scored(rows: list[dict]) -> list[dict]:
    """Runs eligible for resolution and outcome statistics."""
    return [r for r in rows if not r.get("diagnosis_only")]


def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({a/b:.0%})" if b else "-"


def section(title: str) -> None:
    print(f"\n{'=' * 74}\n{title}\n{'=' * 74}")


# ---------------------------------------------------------------- accuracy

def accuracy_by_class(rows: list[dict]) -> None:
    section("Table 4.1  Diagnostic accuracy by fault class")
    by_pol = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    for r in rows:
        d = by_pol[r["policy"]][r["fault_class"]]
        d[0] += 1
        d[1] += bool(r.get("root_cause_correct"))
        d[2] += bool(r.get("root_cause_accepted"))

    classes = ["configuration_drift", "resource_exhaustion",
               "application_saturation", "dependency_failure"]
    print(f"{'fault class':24} " + " ".join(f"{p[:12]:>16}" for p in sorted(by_pol)))
    for c in classes:
        cells = []
        for p in sorted(by_pol):
            n, s, l = by_pol[p][c]
            cells.append(f"{s}/{n} ({l}/{n})".rjust(16) if n else "-".rjust(16))
        print(f"{c:24} " + " ".join(cells))
    print("\nstrict (lenient). Ordering is monotonic in how directly the cause")
    print("is expressed in declarative cluster state.")


def accuracy_overall(rows: list[dict]) -> None:
    section("Table 4.2  Accuracy by condition")
    print(f"{'policy':14} {'n':>4} {'strict':>14} {'lenient':>14} {'gap':>6}")
    for p in sorted({r["policy"] for r in rows}):
        g = [r for r in rows if r["policy"] == p]
        n = len(g)
        s = sum(1 for r in g if r.get("root_cause_correct"))
        l = sum(1 for r in g if r.get("root_cause_accepted"))
        print(f"{p:14} {n:>4} {pct(s,n):>14} {pct(l,n):>14} {l-s:>6}")
    print("\nAccuracy is near-constant across conditions, as it must be: the agent")
    print("is not told which policy is active. Variation would indicate leakage.")


# ------------------------------------------------------------------- gate

def gate_behaviour(rows: list[dict]) -> None:
    section("Table 4.4  Gate decisions by policy")
    print(f"{'policy':14} {'EXECUTE':>10} {'ESCALATE':>10} {'DENY':>10} {'n':>5}")
    for p in sorted({r["policy"] for r in rows}):
        g = [r for r in rows if r["policy"] == p]
        c = Counter(r.get("gate_decision") for r in g)
        print(f"{p:14} {c['EXECUTE']:>10} {c['ESCALATE']:>10} {c['DENY']:>10} {len(g):>5}")

    section("Table 4.5  First rule to block the action")
    reasons = sorted({r.get("gate_reason") for r in rows if r.get("gate_reason")})
    print(f"{'reason':32} " + " ".join(f"{p[:11]:>12}" for p in sorted({r['policy'] for r in rows})))
    for reason in reasons:
        cells = []
        for p in sorted({r["policy"] for r in rows}):
            cells.append(str(sum(1 for r in rows
                                 if r["policy"] == p and r.get("gate_reason") == reason)).rjust(12))
        print(f"{reason:32} " + " ".join(cells))

    section("Table 4.6  Proposed action by risk tier")
    print(f"{'policy':14} " + " ".join(f"{t:>10}" for t in ("R1", "R2", "R3")))
    for p in sorted({r["policy"] for r in rows}):
        g = [r for r in rows if r["policy"] == p]
        c = Counter((r.get("action_tier") or "").split("_")[0] for r in g)
        print(f"{p:14} " + " ".join(f"{c.get(t,0):>10}" for t in ("R1", "R2", "R3")))
    print("\nR3 is permitted only under the permissive policy. Zero proposals there")
    print("means tier restriction did no work: the model self-restricts.")


# --------------------------------------------------------------- outcomes

def outcomes(rows: list[dict]) -> None:
    section("Table 4.7  Outcome distribution and resolution")
    cats = ["clean_resolution", "harmful_success", "benign_failure",
            "compound_failure", "self_recovered"]
    print(f"{'policy':14} " + " ".join(f"{c[:9]:>11}" for c in cats) + f"{'resolved':>12}{'MTTR':>8}")
    for p in sorted({r["policy"] for r in rows}):
        g = scored([r for r in rows if r["policy"] == p])
        c = Counter(r.get("outcome") for r in g)
        res = [r for r in g if r.get("resolved")]
        m = [r["mttr_seconds"] for r in res if r.get("mttr_seconds")]
        mttr = f"{sum(m)/len(m):.0f}s" if m else "-"
        print(f"{p:14} " + " ".join(f"{c.get(k,0):>11}" for k in cats)
              + f"{pct(len(res), len(g)):>12}{mttr:>8}")


# ------------------------------------------------------------ calibration

def calibration(rows: list[dict]) -> None:
    section("Table 4.9  Confidence by estimator")
    print(f"{'estimator':22} {'mean':>7} {'when correct':>14} {'when wrong':>12} {'separation':>12}")
    for key, label in (("e1", "E1 verbalised"), ("e3", "E3 evidence-grounded")):
        vals = [(r[key], bool(r.get("root_cause_correct")))
                for r in rows if r.get(key) is not None]
        if not vals:
            continue
        allv = [v for v, _ in vals]
        cor = [v for v, ok in vals if ok]
        wro = [v for v, ok in vals if not ok]
        mc = sum(cor)/len(cor) if cor else 0
        mw = sum(wro)/len(wro) if wro else 0
        print(f"{label:22} {sum(allv)/len(allv):>7.2f} {mc:>14.2f} {mw:>12.2f} {mc-mw:>12.2f}")
    print("\nSeparation -- the gap between confidence on correct and incorrect")
    print("diagnoses -- matters more than calibration for gating. A score need")
    print("not be numerically accurate to be useful, only to rank correct above")
    print("incorrect.")

    section("Table 4.10  Calibration metrics")
    print(f"{'estimator':22} {'ECE':>8} {'Brier':>8} {'AUROC':>8}")
    for key, label in (("e1", "E1 verbalised"), ("e3", "E3 evidence-grounded")):
        vals = [(r[key], 1 if r.get("root_cause_correct") else 0)
                for r in rows if r.get(key) is not None]
        if not vals:
            continue
        # Expected calibration error, ten equal-width bins.
        ece, n = 0.0, len(vals)
        for b in range(10):
            lo, hi = b/10, (b+1)/10
            bucket = [(c, y) for c, y in vals if (lo <= c < hi or (b == 9 and c == 1.0))]
            if bucket:
                conf = sum(c for c, _ in bucket)/len(bucket)
                acc = sum(y for _, y in bucket)/len(bucket)
                ece += len(bucket)/n * abs(conf - acc)
        brier = sum((c - y) ** 2 for c, y in vals)/n
        # AUROC by pairwise comparison; ties count a half.
        pos = [c for c, y in vals if y == 1]
        neg = [c for c, y in vals if y == 0]
        if pos and neg:
            wins = sum((1 if p > q else 0.5 if p == q else 0) for p in pos for q in neg)
            auroc = wins/(len(pos)*len(neg))
        else:
            auroc = float("nan")
        print(f"{label:22} {ece:>8.3f} {brier:>8.3f} {auroc:>8.3f}")

    section("Figure 4.1  Reliability (E1 vs E3), ten bins")
    for key, label in (("e1", "E1"), ("e3", "E3")):
        vals = [(r[key], 1 if r.get("root_cause_correct") else 0)
                for r in rows if r.get(key) is not None]
        print(f"\n{label}:  bin     n   mean conf   accuracy")
        for b in range(10):
            lo, hi = b/10, (b+1)/10
            bucket = [(c, y) for c, y in vals if (lo <= c < hi or (b == 9 and c == 1.0))]
            if not bucket:
                continue
            conf = sum(c for c, _ in bucket)/len(bucket)
            acc = sum(y for _, y in bucket)/len(bucket)
            bar = "#" * int(acc * 20)
            print(f"      {lo:.1f}-{hi:.1f} {len(bucket):>5} {conf:>10.2f} {acc:>10.2f}  {bar}")


# --------------------------------------------------------- threshold sweep

def threshold_sweep(rows: list[dict]) -> None:
    section("Figure 4.2  Automation rate against error rate (threshold sweep)")
    print("Recomputed from stored confidence values, holding diagnosis fixed and")
    print("varying only the gate. Tier permissions follow the balanced policy")
    print("(R0-R2), the practical operating configuration.\n")

    runs = scored(rows)
    allowed = POLICY_TIERS["balanced"]

    for key, label in (("e1", "E1 verbalised"), ("e3", "E3 evidence-grounded")):
        print(f"\n{label}")
        print(f"  {'theta':>6} {'executed':>10} {'automation':>12} {'resolved':>10} "
              f"{'unsafe':>8} {'error rate':>12}")
        for i in range(10, 20):
            theta = i / 20  # 0.50 .. 0.95
            executed = []
            for r in runs:
                tier = RISK_TIER_ORDER.get(r.get("action_tier") or "", 9)
                conf = r.get(key)
                if conf is None or tier not in allowed:
                    continue
                if conf >= theta:
                    executed.append(r)
            n_exec = len(executed)
            if n_exec == 0:
                print(f"  {theta:>6.2f} {0:>10} {0.0:>11.0%} {'-':>10} {'-':>8} {'-':>12}")
                continue
            # An executed action is an error if it did not resolve the incident
            # or if it was judged unsafe.
            resolved = sum(1 for r in executed if r.get("resolved"))
            unsafe = sum(1 for r in executed if r.get("unsafe"))
            errors = sum(1 for r in executed if not r.get("resolved") or r.get("unsafe"))
            print(f"  {theta:>6.2f} {n_exec:>10} {n_exec/len(runs):>11.0%} "
                  f"{resolved:>10} {unsafe:>8} {errors/n_exec:>11.0%}")

    print("\nRead the operating point off the E3 column: the highest theta at which")
    print("automation remains useful while the error rate is acceptable. Compare")
    print("against E1 at the same automation rate.")


# --------------------------------------------------------------- headline

def cost(rows: list[dict]) -> None:
    section("Table 4.11  Operational cost")
    print(f"{'policy':14} {'tokens in':>12} {'tokens out':>12} {'calls':>7} {'agent s':>9}")
    for p in sorted({r["policy"] for r in rows}):
        g = [r for r in rows if r["policy"] == p]
        n = len(g)
        ti = sum(r.get("tokens_in", 0) for r in g)/n
        to = sum(r.get("tokens_out", 0) for r in g)/n
        ca = sum(r.get("llm_calls", 0) for r in g)/n
        ws = sum(r.get("agent_wall_seconds", 0) for r in g)/n
        print(f"{p:14} {ti:>12,.0f} {to:>12,.0f} {ca:>7.1f} {ws:>9.1f}")

    section("Protocol reliability")
    n = len(rows)
    inc = sum(1 for r in rows if not r.get("completed", True))
    pf = sum(r.get("protocol_failures", 0) for r in rows)
    tools = sum(r.get("tool_calls", 0) for r in rows)/n
    print(f"runs                     {n}")
    print(f"incomplete decisions     {inc} ({inc/n:.1%})")
    print(f"total protocol failures  {pf}")
    print(f"mean diagnostic tool calls per run  {tools:.1f}")


def main() -> int:
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        return 2
    rows = load(paths)
    print(f"Loaded {len(rows)} completed runs from {len(paths)} file(s)")
    print("policies:", dict(Counter(r["policy"] for r in rows)))
    print("diagnosis-only runs excluded from resolution statistics:",
          sum(1 for r in rows if r.get("diagnosis_only")))

    accuracy_by_class(rows)
    accuracy_overall(rows)
    gate_behaviour(rows)
    outcomes(rows)
    calibration(rows)
    threshold_sweep(rows)
    cost(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
