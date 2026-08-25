# Methodology

*Draft — MSc final project. Figures from the balanced/E1 batch of 24 August 2026.*

## 3.1 Overview

The study measures where the boundary between autonomous action and human
escalation should be drawn for an LLM-based incident-response agent, and
whether the confidence signal used to draw that boundary can bear the weight
placed on it. It comprises three artefacts: a fault benchmark, an agent, and
an evaluation harness. The agent is deliberately the least novel of the
three. It is assembled largely from existing services, and the study's
contribution lies in the benchmark and the measurement apparatus around it.

## 3.2 Test environment

Experiments run on a four-node Kubernetes cluster provisioned on Hetzner
Cloud via Terraform: one control-plane node (2 vCPU, 4 GB) and three workers
(4 vCPU, 8 GB each), running k3s v1.31.4 on Ubuntu 24.04. Workers are
labelled by tier. Application workloads are pinned to two nodes and the
observability stack to the third, so that a fault injected into the
application cannot disable the measurement system.

The workload is Google's Online Boutique, an eleven-service reference
application with a built-in load generator. Observability is provided by
Prometheus for metrics and Loki with Promtail for logs. Faults are injected
using Chaos Mesh.

A real multi-node cluster is a methodological requirement rather than a
convenience. Network partitions and node-level resource pressure cannot be
faithfully reproduced on a single-host container-based cluster, where
"nodes" share a kernel and a network namespace.

Two environment properties required correction before data collection.
Online Boutique ships probe timings tuned for a fast local cluster
(timeoutSeconds 1, no initial delay); several Python gRPC services in the
suite call dependencies during startup and are killed by their own liveness
probes before becoming ready, producing crash loops with entirely healthy
application logs. Probe timings are therefore relaxed namespace-wide as part
of provisioning. Second, Hetzner attaches private networking asynchronously,
racing cloud-init; private addresses are consequently assigned statically
from values Terraform already holds rather than obtained by DHCP.

## 3.3 Fault benchmark

Twelve scenarios span four fault classes, three per class: resource
exhaustion, configuration drift, dependency failure, and application
saturation. Classes are grounded in published empirical studies of
microservice failure rather than assembled ad hoc; each scenario records the
literature establishing its fault as a recognised class.

Each scenario definition specifies:

- a **reversible injection**, applied either as a strategic merge patch or a
  Chaos Mesh manifest, with a settling period before the incident is
  considered live;
- a **root cause** drawn from a closed vocabulary of thirteen labels, so
  that diagnostic accuracy is scored against a fixed set rather than by
  string comparison;
- **accepted alternatives** where a second label describes the same fault at
  a different level of description, each with a written rationale;
- a **reference fix**: the minimal known-correct remediation, with its blast
  radius, used as the yardstick for proportionality;
- a **resolution check** that must hold continuously for a sustain period,
  so that transient recovery is not scored as a fix;
- **known distractors**: the plausible but incorrect diagnoses the scenario
  is designed to elicit, recorded so that analysis can report how an agent
  was wrong rather than only that it was.

Definitions are validated against a schema and cross-checked before any run:
reference fixes must exist in the action catalogue and must be neither
read-only nor destructive, since a destructive yardstick would make
disproportionate remediation unscoreable.

Not every scenario is repairable from the action catalogue. Several
dependency-failure faults are injected outside the application, where no
available action resolves the incident. This is deliberate: an agent that
localises such a fault and escalates should score well, and one that takes
destructive action in pursuit of a fix should not.

## 3.4 Agent

The agent runs outside the cluster and reaches it through the Kubernetes
API, Prometheus, and pod logs. Running externally is deliberate: an agent
resident in the cluster could be killed by the very fault it is diagnosing,
making a failure of availability indistinguishable from a failure of
judgement.

Diagnosis proceeds as a ReAct-style loop capped at eight steps. Each turn
must be a JSON object that is either a call to a read-only diagnostic tool
or a final structured decision comprising root cause, target, proposed
action, parameters, confidence, and justification. A JSON protocol is used
in preference to provider-native function calling so that the loop is
identical across model providers, and so that a malformed reply is a
measurable event rather than an exception. Malformed turns are corrected
once and then recorded as protocol failures.

The tool set is strictly read-only: pod description, logs, metric queries,
namespace events, rollout history, and deployment specification. No
mutating capability is reachable from the reasoning loop; every state change
passes through the safety gate.

### Isolation of the injection framework

Chaos Mesh creates resources alongside the pods it targets, and these appear
in namespace events and pod descriptions. In an initial batch the agent
cited them directly and concluded that a network fault had been injected —
reading the experiment's answer key rather than diagnosing from symptoms.
All references to the injection framework are therefore removed from events,
logs, and descriptions before the agent sees them, and context construction
aborts the run if any reference survives. Lines are dropped rather than
marked, since a redaction marker would itself signal that a fault was
injected. Results collected before this correction were discarded.

## 3.5 Safety gate

The gate is the component under study. It implements a total function over
the proposed action, its confidence, and a named policy, returning exactly
one of EXECUTE, ESCALATE, or DENY, with a machine-readable reason recorded
for every invocation.

Every action in the catalogue carries a declared risk tier and a
blast-radius function:

| Tier | Description | Examples |
|---|---|---|
| R0 | Read-only | describe pod, query metrics |
| R1 | Reversible, narrow | delete a single pod |
| R2 | Reversible, wide | rollout restart, rollback, patch limits |
| R3 | Irreversible | drain node, delete deployment, delete claim |

Risk is declared in a versioned artefact rather than judged by the model, so
an agent cannot argue its way into a higher tier.

Rules are applied in a fixed order, and the recorded reason identifies the
first rule that blocked the action: the action must exist in the catalogue;
read-only actions bypass the gate; the tier must be permitted by policy; an
explicit allow-list is honoured where configured; a per-incident action
budget must not be exhausted; a server-side dry run must succeed; blast
radius must be within the tier's cap; and confidence must meet the tier's
threshold.

The gate **fails closed**: any condition it cannot evaluate yields ESCALATE.
This was exercised unintentionally during development, when an interface
mismatch caused blast-radius computation to raise; the gate escalated rather
than executing.

A limitation of the precondition check should be noted. Server-side dry run
is not uniformly supported across kubectl verbs: `rollout restart` rejects
the flag, and `drain` ignores it and begins evicting. For these actions the
check validates resource existence only, and is correspondingly weaker.

### Policies as experimental conditions

Because a policy is a set of numeric thresholds and an allowed action set,
"tightening the policy" denotes a measurable change:

| Policy | θ(R1) | θ(R2) | θ(R3) | Allowed tiers | Budget |
|---|---|---|---|---|---|
| Permissive | 0.50 | 0.70 | 0.90 | R0–R3 | 5 |
| Balanced | 0.70 | 0.85 | — | R0–R2 | 3 |
| Conservative | 0.90 | — | — | R0–R1 | 2 |

## 3.6 Confidence estimation

Three estimators are computed on every run, independently of which one gates
the decision.

**E1, verbalised.** The model emits a scalar in its structured output. Cheap
and the naive baseline; verbalised confidence is known to be systematically
overconfident.

**E2, self-consistency.** The diagnosis is sampled five times and reduced to a canonical (root cause, target, action) triple; confidence is the modal agreement fraction. The Gemini 3.x line deprecates the temperature parameter, so sampling diversity was verified empirically before adoption: five samples of an open-ended prompt produced four distinct responses, confirming the model remains stochastic without explicit temperature control.

**E3, evidence-grounded.** Each root-cause label carries a set of weighted,
observable predicates; confidence is the weighted fraction that hold against
live cluster state. Predicates are selected by the root cause the agent
*claims*, not the true one. Using the scenario's own predicates would make
confidence circular, rising merely because the agent happened to be correct.
Under this construction a confident incorrect diagnosis scores low, which is
the property that makes E3 informative.

Log-probability-based confidence is excluded: token log-probabilities are
unavailable or unreliable through several commercial APIs, and sequence
likelihood is a poor proxy for factual correctness.

## 3.7 Outcome classification

Reporting a single success rate conflates two materially different
failures: an agent that fails to resolve an incident without causing harm,
and an agent that resolves one by destructive means. Resolution and safety
are therefore assessed independently:

| | Action safe | Action unsafe |
|---|---|---|
| **Resolved** | Clean resolution | **Harmful success** |
| **Unresolved** | Benign failure | Compound failure |

An action is unsafe if it is destructive where the reference fix was not, if
it exceeds twice the reference fix's blast radius, or if it produces a
collateral error rate above 1% in services unrelated to the incident.

Collateral damage is measured only after resolution has been confirmed and
the system allowed to settle. Measuring immediately after execution captures
the rolling restart that any patch or restart action necessarily causes, and
would classify every restart-based remediation as harmful. An early batch
did exactly this, reporting nine harmful successes that the corrected timing
reduced to zero.

## 3.8 Experimental procedure

Each run follows a fixed sequence: verify baseline, inject, settle, build
context, diagnose, estimate confidence, gate, execute or escalate, watch for
sustained resolution, classify, tear down, verify baseline, record.

Run independence is the harness's most important property. The baseline is
verified both before and after every run, and a failed post-run baseline
aborts the batch rather than allowing contamination to propagate silently.
The baseline check requires every deployment to be fully available and no
pod to be outside the Running phase; an earlier check tested replica counts
alone and allowed a crash-looping service to persist undetected for three
days.

Teardown restores state captured before injection rather than reconstructed
from the scenario definition, and additionally uncordons any node, since
cordoning is a permitted agent action that would otherwise persist.

Results are appended to disk after every run, so an interruption costs one
run rather than a batch. Each record carries a harness version; resumption
treats only runs at the current version as complete, so a change that
invalidates earlier data does so automatically.

## 3.9 Measurement position

The harness executes on the cluster's control plane rather than on a
workstation. Initially it ran remotely over port-forwarded tunnels, which
proved unsuitable in two respects: the tunnels dropped under the load
generated by HTTP probing, and a dropped metrics tunnel returned an empty
result set that was indistinguishable from evidence being absent. Latency
measurement was also dominated by the wide-area link — a healthy 99th
percentile measured 2,000 ms remotely and 60 ms from within the cluster.
Measurement is therefore taken adjacent to the system under test.

Application-level latency and error rate are measured by the harness
probing the frontend directly, rather than from application metrics, because
Online Boutique does not expose Prometheus-format request histograms. This
measures what a client experiences rather than what the application reports
of itself, at the cost of visibility only at the frontend rather than per
service.

## 3.10 Metrics

Diagnostic accuracy is reported both strictly (exact match against ground
truth) and leniently (exact or accepted alternative); the difference
measures how much apparent error is disagreement over labelling.
Remediation is reported as resolution rate and mean time to resolution.
Safety is reported as the four-way outcome distribution, with harmful
successes reported separately. Operational cost is reported as tokens and
wall-clock time per run.

Calibration of each estimator is assessed by reliability diagram, expected
calibration error, Brier score, and area under the ROC curve for action
success. Because confidence is recorded for all three estimators on every
run, the automation-rate against error-rate trade-off is derived by sweeping
the threshold against stored values rather than by separate experimental
arms.

## 3.11 Scope and design limitations

The design is deliberately narrow. Twelve scenarios with three repetitions
give small per-cell samples, so effect sizes are reported alongside
significance and no strong claims are made from individual cells. A single
workload is used, so results may not transfer to applications with
different failure characteristics. The human baseline is self-administered
by the author, who also designed the scenarios, and is therefore biased
toward faster diagnosis than an unfamiliar operator would achieve. Frontend
probing gives no per-service latency attribution. Finally, the accepted
alternatives were fixed before collection, but the decision of which labels
to accept is a judgement that affects reported accuracy and is documented
per scenario for that reason.
