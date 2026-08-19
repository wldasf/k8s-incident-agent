"""
Reasoning loop.

A ReAct-style loop: the model alternates between requesting a read-only
diagnostic tool and reasoning over the result, until it emits a final
structured decision or the step budget is exhausted.

Provider portability comes from a JSON protocol rather than native
function-calling APIs: every model turn must be a JSON object that is either

    {"action": "tool", "tool": <name>, "args": {...}, "thought": "..."}
or
    {"action": "final", "root_cause": ..., "target": {...},
     "proposed_action": ..., "params": {...},
     "confidence": 0.0-1.0, "justification": "..."}

A turn that is not valid JSON, names an unknown tool, or omits required
fields is retried once with the error appended; a second failure ends the
run as a protocol failure. Protocol failures are recorded, not hidden --
how often a model can follow the protocol is itself a result.

The loop is deliberately blind to which scenario is running: it receives an
incident context, not a scenario id, so it cannot shortcut diagnosis.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from .actions import CATALOGUE, RiskTier
from .cluster_view import ClusterView
from .llm_client import LLMClient

MAX_STEPS = 8

ROOT_CAUSE_VOCABULARY = [
    "oom_kill", "cpu_throttling", "disk_pressure", "memory_pressure",
    "bad_image_tag", "misconfigured_env", "resource_limit_misconfig",
    "downstream_timeout", "network_partition", "dns_failure",
    "connection_pool_exhaustion", "thread_starvation", "cascading_latency",
]

MUTATING_ACTIONS = sorted(
    name for name, spec in CATALOGUE.items() if spec.tier != RiskTier.R0_READ_ONLY
)

SYSTEM_PROMPT = """You are an incident-response agent for a Kubernetes cluster.
An incident is in progress. Your job is to diagnose the root cause using
read-only diagnostic tools, then propose ONE remediation action.

You must respond with a single JSON object and nothing else.

To use a diagnostic tool:
{"action": "tool", "tool": "<tool_name>", "args": {...}, "thought": "<why>"}

Available tools (all read-only):
- describe_pod       args: {"namespace": str, "pod": str}
- get_logs           args: {"namespace": str, "workload": str}
- query_metrics      args: {"promql": str}
- get_events         args: {"namespace": str}
- rollout_history    args: {"namespace": str, "workload": str}
- get_deployment     args: {"namespace": str, "workload": str}

To give your final answer:
{"action": "final",
 "root_cause": "<one of: %s>",
 "target": {"namespace": str, "workload": str},
 "proposed_action": "<one of: %s>",
 "params": {...},
 "confidence": <float 0.0-1.0>,
 "justification": "<2-4 sentences citing the evidence you observed>"}

Rules:
- root_cause MUST be exactly one label from the list above.
- proposed_action MUST be exactly one action name from the list above.
- If no listed action can fix the fault (e.g. the fault is outside the
  application), choose the most defensible minimal action and say in the
  justification that escalation is appropriate; low confidence is correct
  and honest in that case.
- confidence reflects how strongly the observed evidence supports your
  diagnosis. Do not inflate it.
- Never propose more than one action.
""" % (", ".join(ROOT_CAUSE_VOCABULARY), ", ".join(MUTATING_ACTIONS))


@dataclass
class Step:
    kind: str                 # "tool" | "final" | "protocol_error"
    tool: str | None = None
    args: dict | None = None
    thought: str | None = None
    observation: str | None = None
    raw: str | None = None


@dataclass
class AgentDecision:
    root_cause: str
    target: dict
    proposed_action: str
    params: dict
    confidence: float
    justification: str
    steps: list[Step] = field(default_factory=list)
    protocol_failures: int = 0
    wall_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    completed: bool = True    # False when the loop ended without a final answer


def _dispatch(view: ClusterView, tool: str, args: dict) -> str:
    try:
        if tool == "describe_pod":
            return view.describe_pod(args["namespace"], args["pod"])
        if tool == "get_logs":
            return view.get_logs(args["namespace"], args["workload"])
        if tool == "query_metrics":
            return view.query_metrics(args["promql"])
        if tool == "get_events":
            return view.get_events(args["namespace"])
        if tool == "rollout_history":
            return view.rollout_history(args["namespace"], args["workload"])
        if tool == "get_deployment":
            return view.deployment_spec_summary(args["namespace"], args["workload"])
        return f"ERROR: unknown tool '{tool}'"
    except KeyError as e:
        return f"ERROR: missing argument {e} for tool '{tool}'"
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: tool failed: {exc}"


def _parse_turn(raw: str) -> dict | None:
    """Accept clean JSON, or JSON wrapped in code fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _validate_final(obj: dict) -> str | None:
    """Return an error message, or None if the final answer is well-formed."""
    for k in ("root_cause", "target", "proposed_action", "confidence", "justification"):
        if k not in obj:
            return f"final answer missing field '{k}'"
    if obj["root_cause"] not in ROOT_CAUSE_VOCABULARY:
        return f"root_cause '{obj['root_cause']}' is not in the allowed vocabulary"
    if obj["proposed_action"] not in MUTATING_ACTIONS:
        return f"proposed_action '{obj['proposed_action']}' is not in the action list"
    try:
        c = float(obj["confidence"])
    except (TypeError, ValueError):
        return "confidence is not a number"
    if not 0.0 <= c <= 1.0:
        return "confidence must be between 0.0 and 1.0"
    return None


def diagnose(
    client: LLMClient,
    view: ClusterView,
    incident_context: str,
    temperature: float = 0.0,
) -> AgentDecision:
    """Run the reasoning loop for one incident and return the decision."""
    t0 = time.monotonic()
    tok_in0, tok_out0 = client.usage.input_tokens, client.usage.output_tokens

    messages: list[dict] = [{"role": "user", "content":
        "INCIDENT CONTEXT:\n" + incident_context +
        "\n\nBegin your diagnosis. Respond with a single JSON object."}]
    steps: list[Step] = []
    protocol_failures = 0

    def finish(decision_fields: dict | None, completed: bool) -> AgentDecision:
        f = decision_fields or {}
        return AgentDecision(
            root_cause=f.get("root_cause", "unknown"),
            target=f.get("target", {}),
            proposed_action=f.get("proposed_action", "none"),
            params=f.get("params", {}) or {},
            confidence=float(f.get("confidence", 0.0)),
            justification=f.get("justification", ""),
            steps=steps,
            protocol_failures=protocol_failures,
            wall_seconds=time.monotonic() - t0,
            input_tokens=client.usage.input_tokens - tok_in0,
            output_tokens=client.usage.output_tokens - tok_out0,
            completed=completed,
        )

    for _ in range(MAX_STEPS):
        raw = client.complete(SYSTEM_PROMPT, messages, temperature=temperature)
        obj = _parse_turn(raw)

        if obj is None or "action" not in obj:
            protocol_failures += 1
            steps.append(Step(kind="protocol_error", raw=raw[:500]))
            if protocol_failures >= 2:
                return finish(None, completed=False)
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                "Your reply was not a valid JSON object with an 'action' field. "
                "Respond again with ONLY the JSON object."})
            continue

        if obj["action"] == "final":
            err = _validate_final(obj)
            if err:
                protocol_failures += 1
                steps.append(Step(kind="protocol_error", raw=raw[:500]))
                if protocol_failures >= 2:
                    return finish(obj, completed=False)
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content":
                    f"Invalid final answer: {err}. Respond again with a corrected JSON object."})
                continue
            steps.append(Step(kind="final", raw=raw[:500]))
            return finish(obj, completed=True)

        if obj["action"] == "tool":
            tool = obj.get("tool", "")
            args = obj.get("args", {}) or {}
            observation = _dispatch(view, tool, args)
            steps.append(Step(kind="tool", tool=tool, args=args,
                              thought=obj.get("thought"), observation=observation[:400]))
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                f"TOOL RESULT ({tool}):\n{observation[:6000]}\n\n"
                "Continue. Respond with a single JSON object."})
            continue

        protocol_failures += 1
        steps.append(Step(kind="protocol_error", raw=raw[:500]))
        if protocol_failures >= 2:
            return finish(None, completed=False)
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content":
            "The 'action' field must be 'tool' or 'final'. Respond again."})

    # Step budget exhausted without a final answer: force one last summary turn.
    messages.append({"role": "user", "content":
        "You have used all diagnostic steps. You MUST now respond with your "
        "final answer JSON object based on the evidence so far."})
    raw = client.complete(SYSTEM_PROMPT, messages, temperature=temperature)
    obj = _parse_turn(raw)
    if obj and obj.get("action") == "final" and _validate_final(obj) is None:
        steps.append(Step(kind="final", raw=raw[:500]))
        return finish(obj, completed=True)
    steps.append(Step(kind="protocol_error", raw=(raw or "")[:500]))
    return finish(obj if obj else None, completed=False)
