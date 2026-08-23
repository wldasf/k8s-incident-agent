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


