# Decisions log
 
Running notes on choices made and why, kept as I go. Rough by design — working
material for the design and limitations chapters, not prose.
 
---
 
## 2026-08-15
 
- **Agent runs outside the cluster.** Inside, a chaos experiment could kill it
  mid-run and I couldn't tell bad judgement from unavailability. Also closer to
  how on-call works — you're not inside the thing you're fixing.
- **CX servers, not CPX/CCX.** Hetzner repriced this year: CPX/CCX up 144–176%,
  CX only ~33–38%. Same 14 vCPU / 28 GB at a quarter of the cost.
- **RES-03 was mislabelled and the validator passed it anyway.** Said
  `disk_pressure` while injecting memory stress. Valid enum member, wrong one.
  Schema validity isn't semantic correctness.
## 2026-08-16
 
Cloud-init hardcoded `ens10`; it's actually `enp7s0`, so flannel couldn't bind
and no nodes registered despite the API server being up. Detect by subnet
instead. Shouldn't have assumed the name.
 
## 2026-08-17
 
- **Two workers hung 17 hours.** Private interface never came up, join-wait
  loop had no timeout. Bounded it. Loud failure beats quiet nothing.
- **Latency measurement was measuring the WAN.** p99 ≈ 2000ms on a healthy
  system — that's Jordan→Germany plus port-forward, not the application.
## 2026-08-18
 
- **IP rotated twice in three days**, each time breaking SSH and kubectl with
  timeouts that look like something worse. Added `make fixip`.
- **The networking problem is a race**, not a failure — cloud-init runs before
  Hetzner attaches the private network. Also: I'd assumed the servers rebooted;
  uptime was low because they were newly created. Wrong hypothesis.
## 2026-08-19
 
- **Confirmed the race.** A rebuild brought the network up fine on its own, so
  DHCP isn't broken — it just sometimes loses. Fix: assign the address
  statically from what Terraform already knows rather than racing for it.
- **CFG-03 happened to me for real.** emailservice crash-looping with healthy
  logs — its own 1s liveness probe killing a slow-starting Python gRPC server.
  Exactly the scenario, encountered by accident. Baked the fix into
  provisioning so the environment stays reproducible.
## 2026-08-21
 
**Validation at the boundary, not repair in the gate.** Agent put namespace and
workload in `target`; the gate reads `params`, got None, raised. It escalated
rather than executed — fail-closed working.
 
Could have had the gate merge the fields, or required them in `params` and
rejected decisions without. Chose the second: a safety-critical component
should assume nothing and repair nothing. If the gate patches malformed input,
its behaviour depends on model output format and every future quirk becomes a
gate change. Also makes "how often can the model produce a well-formed
decision?" measurable instead of silently patched over. Costs more reported
protocol failures — accurate, not worse.
 
## 2026-08-22
 
- **Collateral damage must be measured after settling.** RES-01 scored
  harmful_success on a 100% error rate because the probe ran during the rolling
  restart the fix itself causes. Every restart-based remediation would have been
  mislabelled.
- **Moved the harness into the cluster.** Tunnels dropped under probe load, and
  a dropped Prometheus tunnel returns "no series" — read as evidence absent
  rather than measurement failed. Latency 2000ms → 60ms.
- **Parallel clusters, not parallel scenarios.** Node-stress and partition
  faults are cluster-wide and the baseline check is namespace-wide. Terraform
  workspaces instead. ~4x throughput for €0.20/hour.
## 2026-08-23
 
Long day. Six defects had each taken ~15 min to surface through full runs —
the feedback loop was the real cost, not the bugs. Added smoke mode and a
one-second executor dry-run test; the first smoke pass found four more defects
in twenty minutes, one of which would have killed an overnight batch at run 2.
 
- **Probe timings, namespace-wide this time.** Patched emailservice
  individually last week; recurred on recommendationservice and went unnoticed
  for three days. Per-service was the wrong granularity.
- **Baseline check was too weak.** Tested availableReplicas only, so a
  crash-looping pod beside an available one passed. A health check that misses a
  dead service for three days isn't a health check.
- **kubectl dry-run isn't uniform.** `rollout restart` rejects the flag;
  `drain` ignores it and starts evicting. Both now just check the resource
  exists. Limitation: weaker precondition check for those actions.
- **Two scenarios invalid against a live cluster** despite passing schema
  validation — CFG-03's duplicate probe handler, RES-02's request above its
  limit. Neither detectable without applying the patch.
- **Failed runs must not count as done.** Resume treated any recorded run as
  complete, so a permanently failing scenario would be skipped forever.
- **Moved to gemini-3.7-flash.** 2.5 retires 16 Oct, four days after
  submission. 3.x deprecates temperature, which E2 needs, so tested diversity
  first: five samples gave four distinct answers. Still stochastic.
- **Free tier was sized for validation, not experimentation** — 20 requests/day
  against a design needing 216. Billing on before collection.
- **Accepted root causes.** Agent keeps calling RES-01
  `resource_limit_misconfig` where truth says `oom_kill`. Both right — one names
  the mechanism, one the cause. Ten scenarios now declare alternatives with a
  rationale; CFG-01 and DEP-02 stay strict. Recording both figures.
## 2026-08-24
 
**The fault injector was leaking the answer.** 8 of 9 APP runs said
`network_partition` against true causes of pool exhaustion, thread starvation
and cascading latency. The justifications showed why — the agent was citing
Chaos Mesh directly: *"Events show a PodNetworkChaos resource targeting
redis-cart"*. Those resources appear in namespace events and pod descriptions,
both of which I was handing it. It wasn't diagnosing, it was reading the answer
key. Seven of twelve scenarios use chaos injection, so the batch was void.
 
Fix: strip injector references from events, descriptions and logs, dropping the
lines rather than marking them — a redaction marker would itself announce a
fault. Context construction aborts if anything survives.
 
What bothers me is how invisible it was. Tool use was genuine, confidence
moderate, accuracy poor in exactly the classes where poor accuracy is expected.
Only the free text gave it away. Generalises: any benchmark injecting faults
through an in-cluster framework must treat that framework's resources as ground
truth and withhold them.
 
- **Harness versioning.** Resume couldn't tell a contaminated generation from a
  current one. Records now carry a version; bumping it invalidates old data
  automatically.
- **First clean batch — 36 runs, balanced/E1.** 47% strict / 56% lenient, 83%
  resolved, mean MTTR 474s, zero harmful successes across 26 actions.
  By class: config drift 9/9, resource 6/9, app saturation 2/9, dependency 0/9.
  That ordering tracks how directly the cause is stated in cluster state. The
  finding isn't "47% accurate" — it's that capability degrades as evidence moves
  from declarative to inferential. That's the headline.
- **Token cost up 23x**, ~1,700 → ~39,800 per run now the agent actually
  investigates. The old figure came from runs where it was reading leaked
  artefacts instead of working.
- **Separate estimator arms may be unnecessary.** E1 and E3 are recorded on
  every run regardless of which gates, so calibration is already collected. I
  can sweep the threshold offline.
- **Confidence isn't uniformly miscalibrated.** E1 mean 0.80, E3 0.59. DEP
  scenarios (0/9) show it sharpest: wrong answers at 0.85–0.90 *and* 0.30–0.40.
  Same runs, different answers depending on estimator. That's the thesis.
## 2026-08-25
 
- **Diagnosis and remediation succeed together.** 17 correct labels, 15 correct
  fixes, zero cases of right fix under wrong label. Action selection isn't more
  reliable than diagnosis. Confirms confidence-in-diagnosis is the right thing
  to threshold on — assumed, now checked.
- **The reference fix is *a* correct answer, not *the* one.** Two runs
  diagnosed correctly and chose differently, both resolving cleanly; one chose
  something *less* invasive than the reference. Not changing the references —
  moving them after seeing results would be fitting the rubric to the data — but
  reference-fix match is a lower bound, and minimality is conservative.
- **Chaos faults expire before the window closes.** All 10 non-executed runs
  scored "resolved", MTTRs clustering at 1136–1203s against a 20m duration. The
  fault lifts itself. Inflates resolution rate and corrupts `minimal`. Fix:
  longer durations, plus a distinct outcome for resolution without action.
  Running the no-op baseline next — this is exactly what it exists to catch and
  I should have run it first.
## 2026-08-26
 
Validation day. Only 4/12 scenarios usable when I started.
 
- **Five resolution checks were never detecting anything.** MTTRs gave it away
  — 175.2s three times running, identical to the decisecond. Real recovery has
  variance. In every case MTTR ≈ sustain + one poll, so the check passed on its
  first evaluation. Healthy baseline is p95=100ms, p99=231ms, err=0.000; DEP-01
  wanted p99 < 800ms, APP-02 p95 < 1000ms, DEP-03 err < 0.01 — all satisfied by
  a healthy system. I set those by guessing plausible values, never checked they
  could fail.
- **Every fault has a different signature**, which is why one threshold shape
  didn't work. currencyservice delay → err=1.000 with latency *dropping* to 7ms
  (frontend fails fast). redis-cart → p99=3338ms, throughput 5.0→0.4 rps.
  recommendationservice at 2.5s → nothing at all.
- **13 PromQL selectors matched the whole namespace.** Every service names its
  container "server", so `container="server"` with no pod filter matched all of
  them, and `_promql_scalar` takes the max. RES-02 was reading the frontend's
  0.113 throttling as its own and could never register resolution. Also affects
  E3 predicates in seven scenarios.
- **DEP-03 has never worked.** Chaos Mesh reports AllInjected=False with a Rust
  panic in the DNS injector. `kubectl apply` returned success throughout —
  apply only means the CRD was accepted; injection reports separately in
  status.conditions, which the harness never read. Excluded.
- **CFG-03 and RES-02 had silently reverted** to old broken versions, a stale
  patch file overwriting my fixes. Only caught by the validator.
- **CFG-03 was testing something Kubernetes prevents.** A broken readiness
  probe on a rolling update doesn't cause an outage — the new pod never becomes
  ready so the orchestrator keeps the old one serving. Confirmed by hand.
  Reframed around the stalled rollout, which is what actually pages someone.
Built two tools: the injector now polls status.conditions and fails loudly, and
a validator that checks each scenario's resolution check passes at baseline and
fails under fault. Should have existed before any data was collected.
 
## 2026-08-27
 
- **APP-02 is real but invisible.** 8s delay on recommendationservice,
  AllInjected=True, frontend p99 82–97ms against a 231ms baseline — faster than
  healthy. The frontend doesn't block on recommendations, it renders without
  them. Yesterday's 4222ms reading was a fluke I built on. Marked
  diagnosis-only: scored for diagnosis, excluded from resolution stats.
- Worth keeping for the discussion: a fault can be real, correctly injected and
  correctly diagnosed while producing no client-observable failure. Resolution
  metrics miss that class entirely.
- **RES-03** threshold was below the background restart noise. Raised it.
Pattern across both days: metrics returning plausible numbers for a slightly
different question than the one I was asking.
- **Replaced DEP-03** rather than dropping it. Same fault class — dependency
  unreachable — but via network partition to redis-cart instead of DNS
  poisoning, since partition injection is proven working in DEP-02 and the DNS
  component isn't. Validates clean: error_rate 0 → 1.
- **RES-03 marked diagnosis-only.** StressChaos `mode: one` runs the stressor
  inside a single pod's cgroup, and `size` is against that container's limit,
  not the node's. Node never reports pressure, pod never OOM-killed, 0 restarts
  under fault. Raising the stress until the container dies would just reproduce
  RES-01.
- Decided against replacing APP-02 and RES-03 with detectable alternatives.
  Two independent cases of "real fault, correctly diagnosable, no observable
  impact" is a finding worth keeping — a benchmark where every fault happens to
  be visible would be tidier and less honest.
- **Harness v4.** Resolution checks were rewritten across most scenarios, so
  everything collected earlier is invalid.
- Benchmark: 10 fully usable, 2 diagnosis-only, 0 excluded.


## 2026-08-29

- **Balanced condition complete** — 33 runs, all ok. 63% strict / 73% lenient,
  20/30 resolved, MTTR 237s. Class gradient held for the third time: config
  drift 9/9, resource 6/6, app saturation 3/6, dependency 1/9.
- **Excluded RES-03.** Events showed the real failure was a liveness probe
  timing out at 5s under stressor CPU contention (exit 137), not node memory
  pressure — memory limit is 4Gi and nowhere near exhausted. So it duplicates
  CFG-03's failure mode, and the crash-looping pod was blocking subsequent
  runs' baseline checks. Four aborted runs traced to it. Moved to
  scenarios/excluded/ rather than deleted.
- **Honoured diagnosis_only in scoring.** The flag existed but the runner
  never read it, so APP-02 was still being scored on resolution and
  contributing false resolutions.
- **Longer backoff on 503.** Three runs lost to Gemini demand spikes; 2/4/8s
  wasn't enough. Now 30/60/90s on 503 specifically.
- **Permissive condition: zero R3 proposals across 33 runs.** Destructive
  actions were explicitly permitted at 0.90 confidence and the agent never
  proposed one — 31 R2, 1 R1. The gate's tier restrictions did no work here:
  balanced barred R3, permissive allowed it, behaviour was identical. The
  mechanism prevented nothing because there was nothing to prevent.
  Confidence gating did fire twice, so that half is load-bearing. Qualifies
  the contribution — on this model, tier restriction is redundant and
  confidence thresholding is not.
- One protocol failure in 33 (DEP-02 rep3): loop exhausted retries without a
  valid decision, gate denied on unknown_action. Fail-closed working.

## 2026-08-30

- **All three conditions complete**, 99 runs. Permissive 23/30 resolved,
  balanced 20/30, conservative 0/30 — every action denied on tier_not_allowed,
  since the agent proposes R2 almost exclusively and conservative allows only
  R0–R1. Perfect safety, zero benefit.
- **E1 has better AUROC than E3** (0.876 vs 0.736) despite worse calibration
  (ECE 0.293 vs 0.208). Calibration and discrimination come apart. For gating,
  ranking is what matters, so the naive estimator wins on the metric that
  counts — not what I expected.
- **One R3 proposal in 99 runs**: DEP-03 under conservative, `drain_node` to
  fix a network partition between two healthy services. Denied. So the model
  doesn't reliably self-restrict — it reaches for destructive action rarely,
  and the gate is insurance against a low-probability high-cost event rather
  than a constant restraint. Better argument for the gate than "it never
  fires". Note it happened under the one policy that forbade it; under
  permissive at 0.90 it would have executed.
- **E1's 0.8–0.9 bin is 24% accurate** and 35 of its 37 runs are dependency
  failure or application saturation. So the model is confidently wrong
  specifically on inferential faults. Aggregate calibration hides this
  entirely — report ECE per class.
- E3 scores are bimodal (40 runs at 1.0), so its sweep plateaus above 0.75.
  Better calibrated but less useful as a threshold variable.

## 2026-09-02

Wrote up results and drafted the remaining chapters. No new decisions —
analysis followed the plan set out before collection.

## 2026-09-05

Citation verification. Read four sources in full against the claims I'd built
on them.

- **The ICML position paper doesn't say what I claimed it said.** I had
  "calls for a benchmark suite for agentic uncertainty... no such benchmark
  exists in mature form" in three chapters, attributed to Kirchhof et al. via
  a practitioner blog. The paper makes no such claim — that was the blog's
  embellishment. What it does say is useful though: reason from the task
  (abstention) rather than the aleatoric/epistemic labels, and numeric
  thresholds are appropriate when the consumer is an automated system rather
  than a human. That's a direct endorsement of the gate's design. Rewrote the
  claim in abstract, introduction and lit review.
- **Dropped OperAID.** Couldn't access it, and I'd quoted specific figures
  (10.9% → 61.1%, 900 experiments) from a search snippet. Can't verify, can't
  cite.
- **STRATUS partially occupies my space.** It formalises Transactional
  No-Regression, a safety specification for safe exploration. My comparison
  table said safety evaluated: no — that's wrong. Changed to partial. The
  distinction still holds: TNR governs whether iteration degrades the system,
  mine governs whether an action is authorised at all. But I can't say safety
  is unaddressed by everyone.
- Verified Xiong24 (better than expected — it benchmarks exactly my two
  metrics, calibration and failure prediction), Meas26 and MetaKube.

Lesson: three of the four problems came from citing search snippets rather
than papers. Same failure mode as the scenarios — plausible-looking material
I hadn't checked.

## 2026-10-03

- Control plane became unusable after 44 days: k3s datastore grew to 10GB with
  a 15GB WAL, load average 34 on 2 cores, API calls timing out. 100+ runs of
  pod and ReplicaSet churn with no compaction. Rebuilt rather than repaired.
  A long-running experimental cluster needs either periodic rebuilds or
  datastore maintenance; I had assumed it would simply keep working.


