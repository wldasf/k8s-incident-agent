# Decisions log

Running notes on choices made and why, kept as I go. Rough by design — this
is working material for the design and limitations chapters, not prose.

---

## 2026-08-15

**Agent runs outside the cluster.** If it ran as a pod inside, a chaos
experiment killing a node could kill the agent mid-run, and I'd have no way
to tell a failure of judgement from a failure of availability. Also closer to
how on-call actually works — you're not inside the thing you're fixing.

**CX servers, not CPX/CCX.** Hetzner repriced this year: CPX and CCX up
144–176%, CX only ~33–38%. CX gives me the 14 vCPU / 28 GB I need at roughly
a quarter of the cost and there's no performance difference that matters for
this workload.

**RES-03 was mislabelled and the validator didn't care.** It said
`disk_pressure` while injecting memory stress and checking MemoryPressure.
Passed validation because `disk_pressure` is a valid enum member — just the
wrong one. Added MEMORY_PRESSURE and fixed the scenario. Schema validity
isn't semantic correctness; worth a line in limitations.

## 2026-08-16

Cloud-init hardcoded `ens10` as the private interface. It's actually
`enp7s0`, so flannel couldn't bind and no nodes registered even though the
API server was up. Switched to detecting the interface by its subnet.
Shouldn't have assumed the name.

## 2026-08-17

**Two workers hung for 17 hours.** The private interface never came up and
the join-wait loop had no timeout, so they sat there silently instead of
failing. Bounded the wait. Same principle as the gate failing closed — loud
failure beats quiet nothing.

**Latency measurement was measuring the wrong thing.** First http_probe
baseline showed p99 ≈ 2000ms on a healthy system. That's Jordan→Germany plus
port-forward overhead, not the application. Thresholds are meaningless if
you're measuring the distance to the datacentre.

## 2026-08-18

**IP rotated twice in three days**, each time breaking SSH and kubectl with
timeouts that look like something worse. Added `make fixip`. If access
control depends on a dynamic address it needs an automated refresh, not me
editing tfvars.

**The networking problem is a race.** Third time now: cloud-init runs before
Hetzner has attached the private network, interface detection falls back to a
guess, and k3s starts but registers nothing. Also: I'd assumed the servers
had rebooted, but uptime was low because they were newly created. Wrong
hypothesis, corrected.

## 2026-08-19

**Confirmed it's a race, not a failure.** A rebuild brought the network up
fine on its own, which kills my earlier theory that DHCP was broken. It
works sometimes. Intermittent success reads as hard failure if you only see
the failures. Fix: assign the address statically from what Terraform already
knows, rather than trying to win a race I don't control.

**CFG-03 happened to me for real.** emailservice went into CrashLoopBackOff
with completely healthy logs — its own liveness probe was timing out at 1s
against a slow-starting Python gRPC server. That's exactly scenario CFG-03,
encountered by accident. Good evidence the scenario library reflects things
that actually happen. Baked the fix into provisioning rather than patching by
hand, so the environment stays reproducible.

## 2026-08-21

**Validation at the boundary, not repair in the gate.**

The agent put namespace and workload in `target`; the gate reads `params`.
Blast-radius computation got None and raised. Notably the gate escalated
rather than executed — fail-closed working under an unhandled error.

Two options: have the gate merge `target` into `params`, or require the
fields in `params` and reject decisions without them. Went with the second.

A safety-critical component should assume nothing and repair nothing. If the
gate patches up malformed input, its behaviour starts depending on model
output format, and every future quirk becomes a gate change — the one
component that most needs to stay simple and auditable ends up absorbing
everyone else's mess. Validating at the boundary also turns "how often can
the model produce a well-formed decision?" into something measurable rather
than something quietly papered over.

Cost: more reported protocol failures than the repair approach would give.
That's accurate, not worse.

## 2026-08-22

**Collateral damage has to be measured after things settle.** First full run
scored RES-01 as harmful_success on a 100% post-action error rate — because
the probe ran during the rolling restart that patch_resource_limits
necessarily causes. Every restart-based fix would have been mislabelled.
Moved the probe to after resolution is confirmed. The distinction is between
a momentary interruption *during* an action and persistent degradation
*caused by* it.

**Moved the harness into the cluster.** Running from the laptop put a WAN
link and two port-forwards on the critical path of every measurement. The
tunnels dropped under probe load, and worse, a dropped Prometheus tunnel
returns "no series" — which the harness read as *evidence absent* rather than
*measurement failed*. Latency went from 2000ms to 60ms once measured
in-cluster.

**Parallel clusters, not parallel scenarios.** Can't run scenarios
concurrently on one cluster — node-stress and partition faults are
cluster-wide and the baseline check is namespace-wide. Terraform workspaces
give independent clusters instead. ~4x throughput for about €0.20/hour.

## 2026-08-23

Long day. Six defects had each taken ~15 minutes to surface through full
runs, which is the real cost — not the bugs, the feedback loop. Added a
compressed smoke mode plus a one-second executor dry-run test. First smoke
pass found four more defects in twenty minutes, one of which would have
killed an overnight batch at run 2.

**Probe timings, again, namespace-wide this time.** Online Boutique ships
probes with timeoutSeconds 1 and no initial delay. Python gRPC services that
call dependencies on startup get killed before they're ready (exit 137) with
healthy logs. I patched emailservice individually last week; it recurred on
recommendationservice and went unnoticed for three days. Per-service was the
wrong granularity.

**Which means the baseline check was too weak.** It tested availableReplicas
only, so a crash-looping pod sitting alongside an available one passed. Now
rejects any pod not Running. A health check that misses a dead service for
three days isn't a health check.

**kubectl dry-run support isn't uniform.** `rollout restart` rejects
`--dry-run` outright, so every restart proposal was escalating on
dry_run_failed. `drain` ignores it and starts evicting — a supposedly
side-effect-free check with real side effects. Both now just validate that
the resource exists. Limitation: the gate's precondition check is weaker for
these actions, and that's a property of kubectl, not of my design.

**Two scenarios were invalid against a live cluster** despite passing schema
validation. CFG-03 added a tcpSocket probe to a service that already has a
grpc one — Kubernetes allows only one handler type, and strategic merge adds
rather than replaces. RES-02 set a CPU limit of 20m while leaving the request
at 100m, which is rejected. Neither is detectable without actually applying
the patch. Same lesson as RES-03 on the 15th.

**Failed runs must not count as done.** Resume treated any recorded run as
complete, so a permanently failing scenario would be skipped forever and the
batch would silently under-collect. Only `status: ok` counts now.

**Moved to gemini-3.7-flash.** 2.5 retires 16 October — four days after
submission, no margin. 3.7 is cheaper and more token-efficient. The 3.x line
deprecates the temperature parameter which E2 depends on, so I tested
sampling diversity first: five samples of an open-ended prompt gave four
distinct answers on both models. Still stochastic. Migrated before
collection so no results span two models.

**Free tier was sized for validation, not experimentation.** 20 requests/day.
With E2 at 6 calls per run that's ~3 runs/day against a design needing 216.
It did its job — proved the pipeline and gave me a real token figure — but
billing had to go on before collection.

**Accepted root causes.** The agent keeps calling RES-01
`resource_limit_misconfig` where ground truth says `oom_kill`. Both are
right: one names the mechanism, the other the cause. Scoring strictly reports
a correct diagnosis as an error over vocabulary. Ten of twelve scenarios now
declare accepted alternatives with a written rationale; CFG-01 and DEP-02
stay strict since there's no defensible alternative reading. Recording both
exact and accepted correctness — the gap between them is itself a number
worth reporting.

## 2026-08-24

**The fault injector was leaking the answer.**

First real batch: 8 of 9 APP runs said `network_partition` against true
causes of pool exhaustion, thread starvation and cascading latency. Reading
the justifications showed why — the agent was citing Chaos Mesh directly:
*"Events show a PodNetworkChaos resource targeting redis-cart"*.

Chaos Mesh creates its resources next to the pods it targets, and those show
up in namespace events and `kubectl describe`, both of which I was handing
straight to the agent. It wasn't diagnosing. It was reading the answer key,
and concluding quite reasonably that a network fault had been injected.

Seven of twelve scenarios use chaos injection, so those results were void.
Discarded the batch.

Fix: strip every injector reference from events, descriptions and logs
before the agent sees them, and drop the lines rather than marking them —
a redaction marker would itself announce that a fault was injected. Context
construction now aborts the run if anything survives, so contamination
becomes a crash instead of a plausible wrong answer. Verified under live
injection: zero references.

What bothers me most is how invisible this was. Tool use was genuine (3–8
calls per run), confidence was moderate (0.4–0.95), nothing in the numbers
looked off. Only the free-text justifications gave it away. A
quantitative-only review would have accepted these results and I'd have
built a chapter on them.

Generalises beyond Chaos Mesh: any benchmark injecting faults through an
in-cluster framework has to treat that framework's own resources as part of
the ground truth and withhold them from the system under test.

**Harness versioning.** Resume couldn't tell a contaminated generation from a
current one — it only knew the run had finished. Every record now carries a
harness_version and resume only counts the current one, so bumping the
version invalidates old data automatically instead of me having to remember
which file is which.

**First clean batch — 36 runs, balanced policy, E1.** All completed, no
injection failures, no aborts. 47% strict / 56% lenient accuracy, 83%
resolved, mean MTTR 474s, zero harmful successes across 26 executed actions.

The aggregate accuracy is the least interesting number here. By class:
config drift 9/9, resource 6/9, app saturation 2/9, dependency 0/9. That
ordering tracks how directly the cause is stated in cluster state — a bad
image tag is written in the deployment spec, a memory limit sits right next
to an OOMKilled status, but pool exhaustion has to be inferred from
behaviour spread across services. The finding isn't "47% accurate", it's
that capability degrades as evidence moves from declarative to inferential.
That's the headline.

**Token cost went up 23x.** ~1,700 per run before, ~39,800 now that the
agent actually investigates (3–8 tool calls, each appended to context).
Revised budget to ~10M tokens for the full design. Still only a few dollars,
but the old figure came from runs where it was reading leaked artefacts
instead of working.

**Separate estimator arms may be unnecessary.** E1 and E3 are recorded on
every run regardless of which one gates the decision, so the calibration
comparison is already collected. Separate arms would only show whether the
gate *decision* differs, and I can sweep that offline against stored values.
Cuts remaining collection to the policy dimension plus one E2 arm, since
self-consistency genuinely needs the extra sampling.

**Confidence isn't uniformly miscalibrated.** E1 mean 0.80, E3 mean 0.59 —
the gap you'd expect from verbalised self-report. The DEP scenarios (0/9
strict) show it sharpest: wrong answers at 0.85–0.90 *and* at 0.30–0.40. So
"can you threshold on confidence?" gets different answers from different
estimators on identical runs. That's the thesis in one line.

## 2026-08-25

**Diagnosis and remediation succeed together.** Of 36 balanced/E1 runs, 17
had the correct label and 15 chose the reference fix — but zero cases of
right fix under wrong label. So action selection isn't more reliable than
diagnosis; they're coupled. Good news for the design: confidence-in-diagnosis
is the right thing to threshold on, which I'd assumed but hadn't checked.

**The reference fix is *a* correct answer, not *the* correct answer.** Two
runs diagnosed correctly and chose differently, both resolving cleanly.
APP-02: reference says scale_workload for thread starvation, agent chose
rollout_restart — clears the saturated pool, arguably the more conventional
response. APP-03: reference says delete_pod, agent chose scale_workload,
which is *less* invasive than the reference and still worked.

Not changing the reference fixes — they're the proportionality yardstick and
moving them after seeing results would be fitting the rubric to the data.
But reporting reference-fix match as a strict lower bound on remediation
quality, with these two as evidence that operationally valid alternatives
exist outside it. Also means the minimality metric is conservative: an agent
can be scored non-minimal for choosing a gentler action than the reference.

**Chaos faults expire before the observation window closes.** All 10
non-executed runs scored "resolved" — MTTRs cluster at 1136-1203s against a
20m injection duration. The fault lifts itself. Resolution rate of 83% is
inflated and escalated chaos runs are mislabelled clean_resolution. Also
corrupts `minimal`, which returns True when no action was executed. Fix:
durations longer than the resolution timeout, plus a distinct outcome for
resolution without action. Running the no-op baseline before anything else —
this is exactly what it exists to catch, and I should have run it first.

## 2026-08-26

**Five resolution checks were never detecting anything.** The no-op baseline
showed five scenarios "resolving" with no action taken — but the MTTRs gave
it away: 175.2s three times running, identical to the decisecond. Real
recovery has variance. In every case MTTR ≈ sustain_seconds + one poll, so
the check was passing on its first evaluation. They weren't self-recovering;
the checks never registered the fault at all.

Measured the actual effect of each fault on the frontend. Healthy baseline
is p95=100ms, p99=231ms, err=0.000, rps=5.0. Against that: DEP-01 wanted p99
< 800ms, APP-02 wanted p95 < 1000ms, DEP-03 wanted err < 0.01 — all satisfied
by a healthy system. I set those thresholds by guessing at plausible values
instead of measuring, and never checked they could fail.

Each fault also has a completely different signature, which is why one
threshold shape didn't work: currencyservice delay produces err=1.000 with
latency *dropping* to 7ms (frontend fails fast); redis-cart delay produces
p99=3338ms and throughput collapse to 0.4rps; recommendationservice at 2.5s
produces nothing at all — Online Boutique degrades gracefully on
non-essential services. Had to go to 8s to get a signal (p99 231→4222ms),
and that's the value to use.

**DEP-03 has never worked.** Chaos Mesh reports AllInjected=False with a Rust
panic in the DNS injector. `kubectl apply` returned success the whole time,
because apply only means the CRD was accepted — injection happens
asynchronously and reports separately in status.conditions, which the harness
never read.

Both problems are the same mistake in different clothes: assuming a step
worked because the command that started it returned success. Built two tools
in response. The injector now polls status.conditions and fails loudly if the
fault didn't take. And a validation tool that, per scenario, checks the
resolution check passes at baseline and fails under fault — a scenario where
it passes in both states is measuring nothing. Should have existed before any
data was collected; it would have caught all five in one pass instead of five
separate investigations.


