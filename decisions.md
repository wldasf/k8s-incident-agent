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


