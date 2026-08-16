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


