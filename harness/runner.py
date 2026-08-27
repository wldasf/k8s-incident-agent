"""
Experiment runner.

Executes one scenario end to end under a named policy and confidence
estimator, and records the result. The ordering of steps is the experimental
protocol and should not be varied casually.

    verify baseline -> inject -> settle -> observe -> diagnose ->
    estimate confidence -> gate -> execute or escalate ->
    watch for resolution -> classify -> teardown -> verify baseline -> record

Two properties matter more than the rest. Runs must be independent: the
baseline is verified both before and after, and a failed post-run baseline
aborts the batch rather than contaminating subsequent runs. And results are
appended to disk immediately, so a crash costs one run rather than a batch.

Usage:
    python3 -m harness.runner --scenario RES-01 --policy balanced --estimator E1
    python3 -m harness.runner --all --policy balanced --estimator E3 --repeats 3
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from dataclasses import asdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent.cluster_view import ClusterView            # noqa: E402
from agent.confidence import compute_all              # noqa: E402
from agent.context_builder import build_context       # noqa: E402
from agent.gate import Decision, Policy, evaluate     # noqa: E402
from agent.llm_client import from_env                 # noqa: E402
from agent.reasoner import diagnose                   # noqa: E402
from harness import http_probe                        # noqa: E402
from harness.executor import dry_run_check, execute   # noqa: E402
from harness.injector import inject, teardown, wait_for_baseline  # noqa: E402
from harness.outcomes import ExecutedAction, assess   # noqa: E402
from scenarios.loader import load_all                 # noqa: E402

# Polling cadence and sustain requirement are tunable so batches can be
# shortened without editing every scenario. SUSTAIN_FACTOR scales each
# scenario's sustain_seconds; 0.5 still requires a full minute of
# continuous health on most scenarios, which rules out a transient blip.
RESOLUTION_POLL_S = float(os.environ.get("RESOLUTION_POLL_S", "5"))
SUSTAIN_FACTOR = float(os.environ.get("SUSTAIN_FACTOR", "1.0"))
POST_ACTION_SETTLE_S = float(os.environ.get("POST_ACTION_SETTLE_S", "25"))

POLICY_DIR = pathlib.Path(__file__).resolve().parents[1] / "agent" / "policies"
RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
# Bumped whenever a change invalidates previously collected data. Recorded in
# every result so that a mixed-generation results file can be detected
# automatically rather than remembered. v1 -> v2: fault-injection artefacts
# were leaking into agent-visible telemetry. v2 -> v3: timed chaos faults
# expired inside the resolution window. v3 -> v4: resolution checks rewritten
# after validation found most of them could not detect their own fault.
HARNESS_VERSION = 4


def _check_resolution(scenario, view: ClusterView, smoke: bool = False) -> tuple[bool, float | None]:
    """Poll the scenario's resolution check until it holds continuously for
    sustain_seconds, or the timeout expires. Sustained rather than momentary,
    so a transient recovery is not scored as a fix."""
    rc = scenario.resolution_check
    # In smoke mode the sustain requirement and timeout are cut hard: the
    # goal is to reach teardown, not to measure resolution.
    sustain = rc.sustain_seconds * (0.1 if smoke else SUSTAIN_FACTOR)
    timeout = 120 if smoke else rc.timeout_seconds
    start = time.monotonic()
    held_since: float | None = None

    while time.monotonic() - start < timeout:
        if rc.source == "promql":
            from agent.confidence import _promql_scalar
            val = _promql_scalar(view, rc.expr)
            ok = val is not None and (
                val > rc.threshold if rc.comparison == "gt" else val < rc.threshold)
        elif rc.source == "http_probe":
            pr = http_probe.probe(duration_s=5 if smoke else 15)
            ok = http_probe.evaluate(rc.expr, rc.threshold, rc.comparison, pr)
        else:
            ok = False

        now = time.monotonic()
        if ok:
            if held_since is None:
                held_since = now
            elif now - held_since >= sustain:
                return True, now - start
        else:
            held_since = None
        time.sleep(RESOLUTION_POLL_S)

    return False, None


def run_once(scenario, policy_name: str, estimator: str, repeat: int,
             include_e2: bool, model_label: str, smoke: bool = False) -> dict:
    view = ClusterView()
    client = from_env()
    policy = Policy.from_yaml(str(POLICY_DIR / f"{policy_name}.yaml"))
    ns, wl = scenario.target.namespace, scenario.target.workload

    record: dict = {
        "scenario": scenario.id, "fault_class": scenario.fault_class.value,
        "true_root_cause": scenario.root_cause_class.value,
        "policy": policy_name, "estimator": estimator, "repeat": repeat,
        "model": model_label, "harness_version": HARNESS_VERSION, 
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "smoke": smoke,
    }

    ok, detail = wait_for_baseline(ns)
    if not ok:
        record.update(status="aborted_precondition", detail=detail)
        return record

    ok, detail, state = inject(scenario)
    if not ok:
        record.update(status="injection_failed", detail=detail)
        teardown(scenario, state)
        return record
    record["injected_at"] = time.time()
    # Smoke mode shortens the settle so defects surface quickly. The fault
    # is still injected and still real; only the waiting is compressed.
    time.sleep(20 if smoke else scenario.injection.settle_seconds)

    try:
        pre_probe = http_probe.probe(duration_s=15)
        context = build_context(view, ns, wl)
        decision = diagnose(client, view, context)

        conf = compute_all(client, view, context, decision,
                           probe_result=pre_probe, include_e2=include_e2)
        confidence = conf.value(estimator)

        record.update({
            "agent_root_cause": decision.root_cause,
            "root_cause_correct": decision.root_cause == scenario.root_cause_class.value,
            "root_cause_accepted": (
                decision.root_cause == scenario.root_cause_class.value
                or decision.root_cause in [a.value for a in scenario.accepted_root_causes]
            ),
            "proposed_action": decision.proposed_action,
            "params": decision.params,
            "justification": decision.justification,
            "completed": decision.completed,
            "protocol_failures": decision.protocol_failures,
            "reasoning_steps": len(decision.steps),
            "tool_calls": sum(1 for s in decision.steps if s.kind == "tool"),
            "agent_wall_seconds": round(decision.wall_seconds, 1),
            "confidence_used": confidence,
            "e1": conf.e1_verbalised, "e2": conf.e2_self_consistency, "e3": conf.e3_evidence,
            "e2_samples": conf.e2_samples,
            "e3_predicates": [{"d": d, "held": h, "w": w} for d, h, w in conf.e3_predicate_results],
            "tokens_in": decision.input_tokens + conf.extra_input_tokens,
            "tokens_out": decision.output_tokens + conf.extra_output_tokens,
            "llm_calls": 1 + conf.extra_calls,
        })

        gate = evaluate(decision.proposed_action, decision.params, confidence,
                        view, policy,
                        dry_run_fn=lambda a, p: dry_run_check(a, p, view))
        record.update({"gate_decision": gate.decision.value,
                       "gate_reason": gate.reason.value,
                       "gate_detail": gate.detail,
                       "action_tier": gate.tier.name if gate.tier else None,
                       "blast_radius": gate.blast_radius})

        executed: list[ExecutedAction] = []
        action_taken = None
        if gate.decision == Decision.EXECUTE:
            res = execute(decision.proposed_action, decision.params, view=view)
            record["execution_ok"] = res.ok
            record["execution_detail"] = res.detail
            if res.ok:
                action_taken = decision.proposed_action

        resolved, mttr = _check_resolution(scenario, view, smoke=smoke)
        record["resolved"] = resolved
        record["mttr_seconds"] = round(mttr, 1) if mttr else None

        # Collateral damage is measured only after the system has settled.
        # Probing immediately after execution captures the rolling restart any
        # patch or restart action necessarily causes, which would score every
        # restart-based remediation as harmful.
        if action_taken:
            time.sleep(10 if smoke else POST_ACTION_SETTLE_S)
            post_probe = http_probe.probe(duration_s=20)
            record["post_action_error_rate"] = post_probe.error_rate
            record["post_action_p99_ms"] = round(post_probe.p99_latency_ms, 1)
            executed.append(ExecutedAction(
                name=action_taken,
                blast_radius=gate.blast_radius or 0,
                collateral_error_rate=post_probe.error_rate))

        a = assess(executed, resolved, mttr,
                   scenario.reference_fix.action,
                   scenario.reference_fix.blast_radius,
                   escalated=(gate.decision != Decision.EXECUTE))
        record.update({"outcome": a.outcome.value, "unsafe": a.unsafe,
                       "unsafe_reasons": a.unsafe_reasons, "minimal": a.minimal,
                       "status": "ok"})

    except Exception as exc:  # noqa: BLE001 - a failed run must not kill the batch
        record.update(status="error", detail=f"{type(exc).__name__}: {exc}")

    finally:
        tok, tdetail = teardown(scenario, state)
        record["teardown_ok"] = tok
        record["teardown_detail"] = tdetail
        bok, bdetail = wait_for_baseline(ns)
        record["baseline_restored"] = bok
        record["baseline_detail"] = bdetail

    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--shard", help="run only this shard's scenarios")
    ap.add_argument("--policy", default="balanced")
    ap.add_argument("--estimator", default="E1", choices=["E1", "E2", "E3"])
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--no-e2", action="store_true",
                    help="skip self-consistency sampling (saves 5 calls per run)")
    ap.add_argument("--smoke", action="store_true",
                    help="fast validation pass: short settle and sustain. "
                         "Exercises the full loop to surface protocol, executor "
                         "and teardown defects in ~2 minutes per scenario. "
                         "MTTR and resolution are NOT valid in this mode and "
                         "records are marked smoke=true so they cannot be "
                         "mistaken for experimental data.")
    ap.add_argument("--model-label", default="")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    scenarios = load_all()
    if args.shard:
        from harness.shards import scenarios_for
        ids = set(scenarios_for(args.shard))
        scenarios = [s for s in scenarios if s.id in ids]
        print(f"shard {args.shard}: {', '.join(sorted(ids))}")
    elif args.scenario:
        scenarios = [s for s in scenarios if s.id == args.scenario]
        if not scenarios:
            print(f"no scenario '{args.scenario}'"); return 2
    elif not args.all:
        print("specify --scenario ID, --shard NAME, or --all"); return 2

    RESULTS.mkdir(exist_ok=True)
    out = pathlib.Path(args.out) if args.out else \
        RESULTS / f"run_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"

    client = from_env()
    label = args.model_label or f"{client.provider}/{client.model}"
    include_e2 = (args.estimator == "E2") and not args.no_e2

    # Resumability: a crashed batch is restarted with the same --out and
    # skips cells already recorded, so a crash costs one run not a batch.
    already_done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get('status') == 'ok' and r.get('harness_version') == HARNESS_VERSION:
                    already_done.add((r.get('scenario'), r.get('policy'),
                                      r.get('estimator'), r.get('repeat')))
        if already_done:
            print(f"resuming: {len(already_done)} runs already recorded")

    if args.smoke:
        print("SMOKE MODE: validation only. MTTR and resolution are not "
              "meaningful; records are marked smoke=true.\n")

    done = 0
    total = len(scenarios) * args.repeats
    for rep in range(1, args.repeats + 1):
        for sc in scenarios:
            done += 1
            if (sc.id, args.policy, args.estimator, rep) in already_done:
                print(f"[{done}/{total}] {sc.id} rep={rep} — already recorded, skipping", flush=True)
                continue
            print(f"[{done}/{total}] {sc.id} policy={args.policy} est={args.estimator} rep={rep}",
                  flush=True)
            rec = run_once(sc, args.policy, args.estimator, rep, include_e2, label,
                           smoke=args.smoke)
            with out.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(f"    -> {rec.get('status')} | gate={rec.get('gate_decision')} "
                  f"| outcome={rec.get('outcome')} | rc={rec.get('root_cause_correct')}"
                  f"/{rec.get('root_cause_accepted')}",
                  flush=True)
            if rec.get("baseline_restored") is False:
                print("    ABORT: baseline not restored; later runs would be contaminated.",
                      flush=True)
                return 1
    print(f"\nresults written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
