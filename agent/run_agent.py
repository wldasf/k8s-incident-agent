"""
Manual agent runner -- Stage 3 smoke test.

Usage:
    python3 -m agent.run_agent <namespace> <workload>

Point it at a workload you have broken by hand, and watch the agent
diagnose it. Prints every reasoning step, the final decision, and what the
safety gate would do under each policy (dry evaluation only -- this runner
never executes anything).
"""

from __future__ import annotations

import json
import pathlib
import sys

from .cluster_view import ClusterView
from .context_builder import build_context
from .gate import Policy, evaluate
from .llm_client import from_env
from .reasoner import diagnose

POLICY_DIR = pathlib.Path(__file__).parent / "policies"


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    namespace, workload = sys.argv[1], sys.argv[2]

    client = from_env()
    view = ClusterView()
    print(f"provider={client.provider} model={client.model}")
    print(f"target: {namespace}/{workload}\n")

    print("== building incident context ==")
    context = build_context(view, namespace, workload)
    print(context[:1200], "\n...\n" if len(context) > 1200 else "")

    print("== reasoning ==")
    decision = diagnose(client, view, context)

    for i, s in enumerate(decision.steps, 1):
        if s.kind == "tool":
            print(f"[step {i}] tool={s.tool} args={s.args}")
            if s.thought:
                print(f"         thought: {s.thought}")
            print(f"         observation: {(s.observation or '')[:200]}")
        elif s.kind == "final":
            print(f"[step {i}] final answer")
        else:
            print(f"[step {i}] PROTOCOL ERROR: {(s.raw or '')[:150]}")

    print("\n== decision ==")
    print(json.dumps({
        "root_cause": decision.root_cause,
        "target": decision.target,
        "proposed_action": decision.proposed_action,
        "params": decision.params,
        "confidence": decision.confidence,
        "justification": decision.justification,
        "completed": decision.completed,
        "protocol_failures": decision.protocol_failures,
        "wall_seconds": round(decision.wall_seconds, 1),
        "tokens": {"in": decision.input_tokens, "out": decision.output_tokens},
    }, indent=2))

    print("\n== safety gate (dry evaluation, nothing executed) ==")
    for name in ("permissive", "balanced", "conservative"):
        policy = Policy.from_yaml(str(POLICY_DIR / f"{name}.yaml"))
        result = evaluate(
            decision.proposed_action, decision.params, decision.confidence,
            view, policy,
        )
        print(f"  {name:13} -> {result.decision.value:9} ({result.reason.value}) {result.detail}")

    print(f"\ncumulative usage this run: {client.usage.calls} calls, "
          f"{client.usage.input_tokens} in / {client.usage.output_tokens} out tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
