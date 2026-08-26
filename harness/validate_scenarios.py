"""
Scenario validation: does each fault actually produce a detectable failure?

Schema validation confirms a scenario is well-formed. It does not confirm
that injecting the fault causes the resolution check to fail -- and five
scenarios in this benchmark passed schema validation while their resolution
checks returned "resolved" from the first poll, because the check was
satisfied by a perfectly healthy system.

For each scenario this tool:

  1. verifies the resolution check PASSES at baseline (healthy cluster)
  2. injects the fault and verifies injection actually took effect
  3. verifies the resolution check now FAILS
  4. tears down and confirms the check passes again

A scenario is only usable if the check flips. One that passes at both
baseline and under fault is measuring nothing; one that fails at baseline is
mis-specified in the other direction.

This is deliberately separate from the experiment: it validates the
instrument, not the agent. Run it after any change to a resolution check.

Usage (on the control plane):
    python3 -m harness.validate_scenarios            # all scenarios
    python3 -m harness.validate_scenarios DEP-01     # one scenario
"""

from __future__ import annotations

import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent.cluster_view import ClusterView                       # noqa: E402
from harness import http_probe                                   # noqa: E402
from harness.injector import inject, teardown, wait_for_baseline  # noqa: E402
from scenarios.loader import load_all                            # noqa: E402


def check_now(scenario, view: ClusterView) -> tuple[bool | None, str]:
    """Evaluate the resolution check once. True means 'looks resolved'."""
    rc = scenario.resolution_check
    if rc.source == "promql":
        from agent.confidence import _promql_scalar
        val = _promql_scalar(view, rc.expr)
        if val is None:
            return None, "no series returned"
        ok = val > rc.threshold if rc.comparison == "gt" else val < rc.threshold
        return ok, f"{val:.4g} {rc.comparison} {rc.threshold}"
    if rc.source == "http_probe":
        pr = http_probe.probe(duration_s=15)
        val = pr.value(rc.expr)
        ok = http_probe.evaluate(rc.expr, rc.threshold, rc.comparison, pr)
        return ok, f"{rc.expr}={val:.4g} {rc.comparison} {rc.threshold}"
    return None, f"unsupported source {rc.source}"


def validate(scenario, view: ClusterView) -> tuple[str, str]:
    ok, detail = wait_for_baseline(scenario.target.namespace)
    if not ok:
        return "SKIP", f"cluster not at baseline: {detail}"

    healthy, hdetail = check_now(scenario, view)
    if healthy is None:
        return "BROKEN", f"check not evaluable at baseline ({hdetail})"
    if not healthy:
        # The check should read "resolved" on a healthy cluster; if it does
        # not, it will never report resolution regardless of what the agent
        # does, and every run of this scenario is a guaranteed failure.
        return "BROKEN", f"check FAILS at baseline ({hdetail})"

    ok, idetail, state = inject(scenario)
    if not ok:
        teardown(scenario, state)
        return "INJECT_FAIL", idetail

    time.sleep(min(scenario.injection.settle_seconds, 90))
    faulted, fdetail = check_now(scenario, view)

    teardown(scenario, state)
    wait_for_baseline(scenario.target.namespace)

    if faulted is None:
        return "BROKEN", f"check not evaluable under fault ({fdetail})"
    if faulted:
        # The defect that motivated this tool: healthy and faulted are
        # indistinguishable, so "resolved" is true from the first poll.
        return "UNDETECTED", f"check still passes under fault ({fdetail})"
    return "OK", f"baseline: {hdetail} | faulted: {fdetail}"


def main() -> int:
    view = ClusterView()
    scenarios = load_all()
    if len(sys.argv) > 1:
        wanted = set(sys.argv[1:])
        scenarios = [s for s in scenarios if s.id in wanted]

    print(f"Validating {len(scenarios)} scenario(s). "
          "A usable scenario's resolution check passes at baseline and fails under fault.\n")
    print(f"{'scenario':10} {'verdict':12} detail")
    print("-" * 100)

    verdicts: dict[str, str] = {}
    for s in scenarios:
        verdict, detail = validate(s, view)
        verdicts[s.id] = verdict
        print(f"{s.id:10} {verdict:12} {detail[:78]}", flush=True)

    usable = sum(1 for v in verdicts.values() if v == "OK")
    print(f"\n{usable}/{len(verdicts)} scenarios usable")
    bad = {k: v for k, v in verdicts.items() if v != "OK"}
    if bad:
        print("\nnot usable:")
        for k, v in bad.items():
            print(f"  {k}: {v}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
