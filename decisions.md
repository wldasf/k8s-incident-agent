# Decisions log

## 2026-08-15 — Agent runs outside the cluster
The agent and harness run on the local machine rather than as pods
inside the cluster under test. If the agent ran inside, a chaos
experiment killing a node could kill the agent mid-run, making it
impossible to distinguish a failure of judgement from a failure of
availability. Running externally also mirrors how an on-call engineer
operates: outside the system they are repairing.

## 2026-08-15 — CX server line over CPX/CCX
Hetzner repriced in 2026; the CPX and CCX lines rose 144-176% while
the cost-optimised CX line rose ~33-38%. CX gives the required
14 vCPU / 28 GB at roughly a quarter of the cost, with no relevant
performance difference for this workload.

## 2026-08-15 — Schema validity does not imply semantic correctness
RES-03 was labelled `disk_pressure` while injecting memory stress and
checking MemoryPressure. The validator passed because the label was a
valid enum member — just the wrong one. Added MEMORY_PRESSURE to the
enum and corrected the scenario. Noted as a limitation of automated
validation: it checks structure, not meaning.

## 2026-08-16 — Private interface detected, not hardcoded
Initial cloud-init hardcoded `ens10` as the private-network interface.
On the provisioned servers it is `enp7s0`, so k3s could not bind flannel
and no nodes registered despite the API server running. Replaced with
runtime detection by subnet (10.10.x), with retry and fallback.
Environment-specific identifiers should be discovered, not assumed.

## 2026-08-17 — Unbounded wait loops hide failure
Two workers hung 17h in cloud-init because the private interface never
came up and the join-wait loop had no timeout. A bounded wait that fails
loudly beats an infinite wait that fails silently — the same principle
the safety gate's fail-closed design encodes.

## 2026-08-17 — Measure from inside the network, not across the WAN
First http_probe baseline showed p99 ≈ 2000ms on a healthy system — the
probe was measuring Jordan→Germany WAN + port-forward overhead, not the
application. Latency thresholds are meaningless unless measured near the
system under test. Probe moved to execute on the control plane; the
harness orchestrates remotely but measures locally.

## 2026-08-18 — Firewall IP rotation automated
Public IP rotated twice in three days, each time silently breaking SSH
and kubectl with connection timeouts. Added `make fixip` to detect the
current address and update the firewall. Access control tied to a dynamic
address needs an automated refresh path, not manual edits.

## 2026-08-18 — Provisioning race with Hetzner private networking
Third occurrence across two sessions: cloud-init runs before Hetzner
attaches the private network, so interface detection falls back to a
guessed name and k3s starts but registers no node — a silent failure.
Replaced with a blocking wait that polls for a 10.10.x address, actively
reapplies network config, and aborts with a logged error rather than
proceeding on a guess. Corrects an earlier hypothesis that servers had
rebooted; uptime was low because they were newly created.

## 2026-08-19 — Race, not failure
Rebuild showed the private network attaching correctly on its own,
disproving the earlier conclusion that DHCP was broken. The true fault is
a race between Hetzner's asynchronous network attachment and cloud-init.
Intermittent success had been misread as a hard failure. Fix: configure
the known address statically rather than waiting on a race.

## 2026-08-19 — CFG-03 occurred naturally during provisioning
emailservice entered CrashLoopBackOff with healthy application logs; the
cause was its own liveness probe timing out at 1s against a slow-starting
Python gRPC server. This is the exact failure mode of scenario CFG-03
(probe misconfiguration removing a healthy process from service),
encountered unintentionally. Supports the claim that the scenario library
reflects failures that occur in practice. Fix baked into provisioning
rather than applied by hand, to preserve reproducibility.

## 2026-08-21 — Validation at the boundary, not repair in the gate
The agent returned namespace and workload in `target` while the gate read
them from `params`, so blast-radius computation received None and raised.
The gate returned ESCALATE rather than EXECUTE, confirming the fail-closed
design works under unhandled error.

Two fixes were possible: have the gate merge `target` into `params`
(interface repair), or require the fields in `params` and reject final
answers lacking them (protocol validation). Chose the latter.

Rationale: a safety-critical component should assume nothing and repair
nothing. Repair in the gate would make its behaviour depend on model output
format, so every future model quirk becomes a gate change — and the
component that most needs to be simple and auditable becomes the one
absorbing malformed input. Validation at the boundary also makes
"how often can the model produce a well-formed actionable decision?"
a measurable result rather than something silently patched over.

Accepted cost: this will report more protocol failures than the repair
approach. That is accurate rather than worse.

## 2026-08-22 — Collateral damage must be measured after settling
First full harness run scored RES-01 as harmful_success on a 100% post-action
error rate. Cause: the probe ran during the rolling restart that
patch_resource_limits necessarily triggers. Every restart-based remediation
would have been mislabelled. Probe moved to after resolution is confirmed,
with a settling delay. Distinguishes momentary interruption during an action
from persistent degradation caused by it.

## 2026-08-22 — Harness moved into the cluster
Running from a laptop placed a WAN link and two port-forwards on the
critical path of every measurement. Tunnels dropped under the probe's
connection churn, and a dropped Prometheus tunnel returned "no series",
which the harness read as evidence absent rather than measurement failed.
Latency was also distorted: healthy p99 measured 2000ms from Jordan,
60ms in-cluster. Measurement must sit near the system under test.

## 2026-08-22 — Parallel clusters, not parallel scenarios
Scenarios cannot share a cluster: node-stress and partition faults are
cluster-wide and the baseline check is namespace-wide. Terraform
workspaces give four independent clusters instead, ~4x throughput for
about EUR 0.20/hour.

## 2026-08-23 — Smoke mode added after repeated slow bug discovery
Six defects had each cost ~15 minutes to surface via full runs. Added a
compressed validation mode and a one-second executor dry-run test. The
first smoke pass found four further defects in twenty minutes, one of
which would have aborted an overnight batch at run 2.

## 2026-08-23 — Probe timings patched namespace-wide
Online Boutique ships probes with timeoutSeconds 1 and no initial delay.
Python gRPC services calling dependencies at startup are killed before
becoming ready (exit 137) with healthy application logs. Patched per
service on emailservice; recurred on recommendationservice, undetected
for three days. Per-service patching was the wrong granularity.

## 2026-08-23 — Baseline check strengthened
wait_for_baseline tested availableReplicas only, so a crash-looping pod
alongside an available one passed. Now also rejects any pod not Running
or in CrashLoopBackOff. A weak health check silently degraded the
test-bed for three days.

## 2026-08-23 — Dry-run support is not uniform across kubectl verbs
rollout restart rejects --dry-run outright; drain ignores it and begins
evicting. Both now validate resource existence instead. Note for
limitations: the gate's precondition check is weaker for these actions
than for those supporting server-side dry run.

## 2026-08-23 — Free tier sized for validation, not experimentation
Gemini free tier caps at 20 requests/day. With E2 self-consistency
sampling at 6 calls per run, that is ~3 runs/day against an experimental
design needing 216. The free tier was adequate to prove the pipeline and
measure real token cost (~1,700/run), which is what it was used for.
Billing enabled before data collection. Cost estimate from measured
usage: under $2 for the full experiment on Flash pricing.

## 2026-08-23 — Dry-run support is not uniform across kubectl verbs
The gate's precondition check issues each action with --dry-run=server. An
executor dry-run test found that `rollout restart` rejects the flag outright,
causing every restart proposal to escalate on dry_run_failed, and that
`drain` ignores it and begins evicting pods — a supposedly side-effect-free
check with real side effects. Both now validate resource existence instead.
Limitation: the precondition check is weaker for these actions than for
those supporting server-side dry run, and this asymmetry is a property of
kubectl rather than of the design.

## 2026-08-23 — Scenario defects found by validation, not by inspection
Two scenarios were invalid against a live cluster despite passing schema
validation. CFG-03 added a tcpSocket probe to a service already carrying a
grpc probe; Kubernetes permits only one handler type and a strategic merge
adds rather than replaces. RES-02 set a CPU limit of 20m while leaving the
request at 100m, which Kubernetes rejects. Neither is detectable without
applying the patch. Reinforces the earlier finding that schema validity does
not imply semantic correctness.

## 2026-08-23 — Failed runs must not count as completed
Resumability initially treated any recorded run as done, so a permanently
failing scenario would be skipped on every retry and the batch would
silently under-collect. Only runs with status ok are now treated as
complete. A resume mechanism that cannot distinguish success from failure
converts a loud failure into a quiet gap in the data.

## 2026-08-23 — Migrated to gemini-3.7-flash
Gemini 2.5 Flash retires on 16 October 2026, four days after submission —
no margin if anything slips. 3.7 Flash is generally available with lower
cost and improved token efficiency. The 3.x line deprecates the temperature
parameter, which E2 self-consistency depends on, so sampling diversity was
tested empirically before migrating: five samples of an open-ended prompt
produced four distinct answers on both 2.5 and 3.7, confirming the models
remain stochastic. Migration performed before data collection so that no
results span two models.

## 2026-08-23 — Accepted root causes: strict and lenient accuracy
The agent consistently labelled RES-01 `resource_limit_misconfig` where
ground truth said `oom_kill`. Both are correct: one names the mechanism, the
other the cause. Scoring strictly would report a substantively correct
diagnosis as an error on a vocabulary technicality. Ten of twelve scenarios
now declare accepted alternatives with a written rationale; CFG-01 and
DEP-02 remain strict, having no defensible alternative reading. Every run
records both exact and accepted correctness, and the gap between the two
measures how much apparent error is really disagreement over labelling.

## 2026-08-24 — Fault injector leaked ground truth into agent-visible telemetry
The first real batch produced a systematic error: 8 of 9 APP runs diagnosed
`network_partition` against true causes of connection pool exhaustion,
thread starvation and cascading latency. Inspection of the justifications
showed why — the agent was citing the injector directly: "Events show a
PodNetworkChaos resource targeting redis-cart", "Chaos Mesh PodNetworkChaos
resource active".

Chaos Mesh creates PodNetworkChaos and similar resources alongside the pods
it targets. These appear in namespace events and in `kubectl describe`
output, both of which were passed to the agent. The agent was therefore not
diagnosing from symptoms but reading the experiment's answer key, and
reasonably concluding that a network fault had been injected.

Seven of twelve scenarios use chaos injection (all APP, all DEP, RES-03), so
those results were invalid. The affected batch was discarded rather than
analysed.

Fix: all injector-related lines are removed from events, pod descriptions and
logs before the agent sees them. Lines are dropped rather than marked,
because a redaction marker would itself signal that a fault was injected.
A post-construction assertion aborts the run if any injector reference
survives into the context, so contamination becomes a crash rather than a
plausible-looking wrong answer. Verified under live injection: context built
with zero artefact references.

Note the failure mode. The agent's tool use was genuine — 3 to 8 diagnostic
calls per run — and its confidence was moderate (0.4–0.95), so nothing in
the numbers looked anomalous. Only reading the free-text justifications
revealed it. A quantitative-only review would have accepted these results.

Generalisable: benchmarks that inject faults through an in-cluster framework
must treat the framework's own resources as part of the ground truth and
withhold them from the system under test. This is not specific to Chaos Mesh
and applies to any evaluation where the harness shares an observability
plane with the agent.

## 2026-08-24 — Harness version recorded in every result
Resumability skipped runs that had completed successfully but were
scientifically invalid, because it could not distinguish a contaminated
generation from a current one. Every record now carries a harness_version,
and resume treats only runs at the current version as done. Bumping the
version therefore invalidates prior data automatically rather than relying
on remembering which file is which.
 
## 2026-08-24 — First clean batch: 36 runs, balanced policy, E1
All 36 runs completed with no injection failures and no aborted batches.
Headline figures: 47% strict accuracy, 56% lenient, 83% resolution rate,
mean MTTR 474s, zero harmful successes across 26 executed actions.
 
The aggregate accuracy figure is the least informative number in the set.
Broken down by fault class it is monotonic: configuration drift 9/9,
resource exhaustion 6/9, application saturation 2/9, dependency failure
0/9. The ordering tracks how directly the cause is stated in declarative
cluster state. An invalid image tag is written in the deployment spec; a
memory limit below the working set is visible alongside an OOMKilled
status; connection pool exhaustion and dependency failures must be inferred
from behaviour distributed across services. The finding is therefore not
that the agent is 47% accurate but that diagnostic capability degrades as
evidence moves from declarative to inferential.
 
## 2026-08-24 — Token cost rose 23x once tool use engaged
Early single-step runs consumed ~1,700 tokens. With redaction in place the
agent investigates properly (3-8 tool calls) and consumes ~39,800 tokens per
run, since each tool result is appended to the conversation. Budget revised
from ~2M to ~10M tokens for the full design. Still a few dollars at Flash
pricing, but the earlier estimate was taken from runs where the agent was
answering from leaked artefacts rather than investigating.
 
## 2026-08-24 — Estimator arms are unnecessary for calibration analysis
E1 and E3 are computed and recorded on every run regardless of which
estimator gates the decision. The calibration comparison is therefore
already collected and does not require separate experimental arms. Separate
arms would only establish whether the gate decision differs, and that can be
derived offline by sweeping the threshold against stored confidence values.
Remaining collection reduced to the policy dimension (permissive,
conservative) plus one E2 arm, since self-consistency genuinely requires
additional sampling.
 
## 2026-08-24 — Confidence is not uniformly miscalibrated
Mean confidence was 0.80 under E1 and 0.59 under E3, a systematic gap
consistent with the reported overconfidence of verbalised self-report. The
dependency-failure scenarios, where strict accuracy was 0/9, show the
pattern most sharply: incorrect diagnoses carried confidences of both
0.85-0.90 and 0.30-0.40. Miscalibration is therefore not uniform, and the
question of whether a confidence signal can be safely thresholded is
answered differently by different estimators on the same runs.


