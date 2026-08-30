# Results

All figures are from 99 completed runs at harness version 4: eleven
scenarios, three repetitions, three policy conditions. Runs collected at
earlier harness versions are excluded, and are discussed separately in §4.8.

## 4.1 Collected data

| Condition | Policy | Estimator | Runs | Scored | Diagnosis-only |
|---|---|---|---|---|---|
| A | Permissive | E1 | 33 | 30 | 3 |
| B | Balanced | E1 | 33 | 30 | 3 |
| C | Conservative | E1 | 33 | 30 | 3 |

All 99 runs completed with a valid record; none aborted on a failed baseline
check. The nine diagnosis-only runs are APP-02, which is scored for diagnosis
but excluded from resolution and outcome statistics for the reason given in
§3.3.

Every run records all three confidence estimators regardless of which one
gated the decision, so the calibration analysis in §4.5 and the threshold
sweep in §4.6 draw on the full corpus rather than on condition-specific arms.

## 4.2 Diagnostic accuracy

**Table 4.1 — Accuracy by fault class and condition (strict, lenient in
parentheses)**

| Fault class | Permissive | Balanced | Conservative | All |
|---|---|---|---|---|
| Configuration drift | 9/9 (9/9) | 9/9 (9/9) | 9/9 (9/9) | **27/27 (100%)** |
| Resource exhaustion | 5/6 (6/6) | 6/6 (6/6) | 6/6 (6/6) | **17/18 (94%)** |
| Application saturation | 4/9 (7/9) | 4/9 (7/9) | 1/9 (4/9) | **9/27 (33%)** |
| Dependency failure | 0/9 (3/9) | 1/9 (3/9) | 3/9 (5/9) | **4/27 (15%)** |
| **All** | 18/33 (25/33) | 20/33 (25/33) | 19/33 (24/33) | **57/99 (58%)** |

Aggregate accuracy is 58% strict and 75% lenient. That figure is the least
informative number in the table.

The class-wise breakdown is sharply bimodal rather than merely graded.
Configuration drift and resource exhaustion together account for 44 of the 45
correct strict diagnoses in those two classes — 98% — while application
saturation and dependency failure together achieve 13 of 54, or 24%. The
ordering corresponds to how directly the cause is expressed in declarative
cluster state.

A configuration fault is *stated*. An invalid image tag appears verbatim in
the deployment specification; a misconfigured probe is visible in the
container spec; an incorrect dependency address is an environment variable the
agent can read. Resource exhaustion is *adjacent*: a memory limit below the
working set sits beside an `OOMKilled` termination reason, and relating the
two requires no inference beyond noticing they concern the same container.

Application saturation and dependency failure must be *inferred* from
behaviour distributed across services — elevated latency together with
unremarkable processor utilisation, or errors in one service whose cause lies
in another that reports itself healthy. Nothing in the cluster state names the
fault.

The result is therefore better stated as a boundary than as a percentage:
diagnostic reliability collapses when evidence stops being declarative.

**Table 4.2 — Accuracy by condition**

| Condition | n | Strict | Lenient | Gap |
|---|---|---|---|---|
| Permissive | 33 | 18 (55%) | 25 (76%) | 7 |
| Balanced | 33 | 20 (61%) | 25 (76%) | 5 |
| Conservative | 33 | 19 (58%) | 24 (73%) | 5 |

Accuracy is near-constant across conditions, as the design requires: the agent
receives no information about which policy is active, so its diagnosis cannot
depend on one. The three-point spread is within what three repetitions per
cell would produce by chance. This constancy also licenses the threshold sweep
in §4.6, which holds diagnosis fixed while varying the gate.

The strict–lenient gap accounts for 17 of the 42 strict errors: roughly two
fifths of apparent misdiagnosis is disagreement over labelling rather than
misreading of the fault.

### 4.2.1 Error structure

Errors are neither uniform nor random.

In the dependency-failure class the agent's incorrect labels are scattered
across `thread_starvation`, `cpu_throttling`, `resource_limit_misconfig` and
`cascading_latency`, with no single confusion dominating. This is consistent
with genuine diagnostic difficulty rather than a systematic misreading of one
signal.

Application-saturation errors cluster differently: the agent repeatedly
identifies the correct *family* — latency under normal resource utilisation —
while naming the wrong mechanism within it. In one representative run it
reported frontend latency of 700–1500 ms with processor and memory below
limits and the backing store responding normally, correctly proposed the
scenario's reference remediation, and labelled the cause `cascading_latency`
rather than `connection_pool_exhaustion`.

Diagnosis and remediation are tightly coupled. Across the balanced condition,
17 runs produced a correct label and 15 selected the reference fix, with **no
cases of a correct remediation under an incorrect diagnosis**. This matters
for the design: it establishes that confidence in diagnosis is a legitimate
quantity on which to gate action, which was assumed rather than demonstrated
when the gate was specified. Had action selection proved more reliable than
labelling, the gate would have been thresholding the wrong signal.

The converse case did occur twice, both resolving cleanly: an agent diagnosed
correctly and chose an action other than the reference. In APP-02 it selected
`rollout_restart` where the reference specifies `scale_workload`, and in
APP-03 it selected `scale_workload` where the reference specifies
`delete_pod` — the latter strictly less invasive than the reference. Agreement
with the reference fix is therefore a lower bound on remediation quality.

## 4.3 Gate behaviour

**Table 4.4 — Gate decisions by policy**

| Policy | EXECUTE | ESCALATE | DENY | n |
|---|---|---|---|---|
| Permissive | 30 (91%) | 2 (6%) | 1 (3%) | 33 |
| Balanced | 24 (73%) | 9 (27%) | 0 | 33 |
| Conservative | 0 | 0 | 33 (100%) | 33 |

**Table 4.5 — First rule to block the action**

| Reason | Permissive | Balanced | Conservative |
|---|---|---|---|
| `within_policy` (executed) | 30 | 24 | 0 |
| `confidence_below_threshold` | 2 | 9 | 0 |
| `tier_not_allowed` | 0 | 0 | 32 |
| `unknown_action` | 1 | 0 | 1 |

Recording the first rule to fire allows each blocked action to be attributed
to a specific mechanism. The three conditions do not merely escalate at
different rates; they escalate for different reasons, and are therefore not
points on a single axis of caution.

Under the balanced policy every escalation is a confidence judgement. Under
the conservative policy every denial is a categorical tier prohibition, and no
confidence value is ever consulted. The conservative condition is thus not a
stricter version of the balanced one but a qualitatively different mechanism:
it does not require the agent to be more certain, it forbids the class of
action the agent almost always proposes.

The two `unknown_action` denials are protocol failures rather than
inappropriate proposals: the reasoning loop exhausted its retry budget without
producing a well-formed decision, and the gate denied an empty action. This is
the fail-closed path operating as specified, and it occurred in 2 of 99 runs
(2.0%).

### 4.3.1 Action selection and the destructive tier

**Table 4.6 — Proposed action by risk tier**

| Policy | R1 | R2 | R3 |
|---|---|---|---|
| Permissive | 1 | 31 | 0 |
| Balanced | 0 | 33 | 0 |
| Conservative | 0 | 31 | 1 |

The agent proposes wide but reversible remediation almost exclusively: 95 of
the 97 classified proposals are R2. This concentration explains the
conservative condition's behaviour entirely. That policy permits only R0 and
R1, so it denies essentially every proposal the agent makes, regardless of
confidence.

Destructive R3 actions were proposed **once in 99 runs**. In DEP-03 under the
conservative policy, the agent proposed `drain_node` — evicting every pod from
a machine — in response to a network partition between two otherwise healthy
services. The gate denied it on tier grounds.

This single observation carries more weight than its frequency suggests, for
two reasons.

First, it refutes the simpler reading of Table 4.6. Zero R3 proposals under
the permissive policy might suggest the model reliably self-restricts to
reversible remediation, which would make tier restriction redundant. The
conservative-condition proposal shows it does not: the agent will reach for a
disproportionate destructive action, rarely and unpredictably. Tier
restriction is therefore not a redundant constraint but insurance against a
low-probability, high-cost event — a materially different justification, and
one that cannot be established from aggregate rates.

Second, the proposal arose under the one policy that forbade it. Had the same
diagnosis occurred under the permissive policy, where R3 is permitted at a
confidence threshold of 0.90, the action would have been evaluated on
confidence alone. Whether it would have executed depends on a value the agent
assigns itself.

## 4.4 Remediation outcomes

**Table 4.7 — Outcome distribution**

| Policy | Clean resolution | Harmful success | Benign failure | Compound failure | Resolved | Mean MTTR |
|---|---|---|---|---|---|---|
| Permissive | 23 | 0 | 7 | 0 | 23/30 (77%) | 319 s |
| Balanced | 20 | 0 | 9 | 1 | 20/30 (67%) | 237 s |
| Conservative | 0 | 0 | 30 | 0 | 0/30 (0%) | — |

No harmful successes were recorded across 54 executed actions. When the agent
acted and resolved an incident, it did so proportionately. This is a genuine
negative rather than an absence of measurement: an earlier corpus, collected
before the collateral-damage timing correction described in §3.7, reported
nine harmful successes, so the detector is known to fire when its conditions
are met.

One compound failure occurred, in APP-03 under the balanced policy: the agent
executed `scale_workload`, the incident did not resolve, and a collateral
error rate of 0.250 was measured in services unrelated to the incident after
the system had settled. This is the taxonomy's worst cell — damage without
benefit — and it is the only instance in the corpus.

The policy comparison quantifies the trade-off the study exists to
characterise. Moving from permissive to balanced costs six executed actions
and three resolutions: the balanced policy achieves 87% of the permissive
policy's resolution count while acting 20% less often. Moving from balanced to
conservative costs every remaining resolution and yields nothing, because the
policy's tier restriction excludes the entire class of action the agent
proposes.

The conservative condition is therefore degenerate rather than cautious. It
does not trade resolution for safety at some rate; it eliminates resolution
while having no unsafe action to prevent. Its escalation rate of 100% also
transfers every incident to a human reviewer, which is the maximal load a
policy can impose.

Mean time to resolution is *higher* under the permissive policy (319 s) than
the balanced one (237 s), which is initially counter-intuitive. The
explanation is compositional rather than causal: the permissive policy
resolves three additional incidents that the balanced policy escalates, and
those additional cases are the slower ones. The balanced policy's faster mean
reflects a easier subset, not faster remediation.

## 4.5 Confidence calibration

**Table 4.9 — Confidence by estimator**

| Estimator | Mean | When correct | When incorrect | Separation |
|---|---|---|---|---|
| E1 verbalised | 0.83 | 0.91 | 0.71 | 0.20 |
| E3 evidence-grounded | 0.72 | 0.82 | 0.58 | 0.24 |

**Table 4.10 — Calibration metrics**

| Estimator | ECE | Brier | AUROC |
|---|---|---|---|
| E1 verbalised | 0.293 | 0.247 | **0.876** |
| E3 evidence-grounded | **0.208** | **0.222** | 0.736 |

These two tables point in opposite directions, and the divergence is the most
consequential result in this section.

E3 is better *calibrated*: its expected calibration error is 29% lower than
E1's and its Brier score is lower. Its mean confidence of 0.72 is closer to
the observed accuracy of 0.58 than E1's 0.83, which is consistent with the
documented overconfidence of verbalised self-report.

E1 nonetheless *discriminates* substantially better, with an AUROC of 0.876
against 0.736. Presented with one correct and one incorrect diagnosis, E1
assigns the higher confidence to the correct one 88% of the time; E3 does so
74% of the time.

Calibration and discrimination are independent properties, and for a gating
decision the second is the operative one. A threshold does not require the
confidence value to be numerically accurate; it requires that correct
diagnoses receive higher values than incorrect ones. On that criterion the
naive estimator outperforms the grounded one — the opposite of the result the
design anticipated.

**Figure 4.1 — Reliability, ten bins**

| Bin | E1 n | E1 accuracy | E3 n | E3 accuracy |
|---|---|---|---|---|
| 0.0–0.1 | 2 | 0.00 | 3 | 0.00 |
| 0.2–0.4 | 6 | 0.00 | 18 | 0.11 |
| 0.5–0.6 | 3 | 0.67 | 14 | 0.64 |
| 0.6–0.7 | 2 | 0.00 | 15 | 0.60 |
| 0.7–0.8 | 6 | 0.50 | 9 | 1.00 |
| 0.8–0.9 | 37 | **0.24** | — | — |
| 0.9–1.0 | 43 | 1.00 | 40 | 0.70 |

E1's distribution is dominated by two bins holding 80 of 99 runs. The upper
bin (0.9–1.0, n = 43) is perfectly accurate; the bin immediately below it
(0.8–0.9, n = 37) is 24% accurate. A difference of one tenth in stated
confidence separates near-certainty from near-worthlessness.

That cliff is not distributed evenly across the benchmark. Of the 37 runs in
the 0.8–0.9 bin, 35 are dependency-failure or application-saturation
scenarios — the two inferential classes. The model is therefore not uniformly
overconfident but *selectively* so: it is well-calibrated on the classes it
diagnoses reliably and confidently wrong on the classes it does not.

This also explains E1's strong AUROC. Its discrimination is earned on the
declarative classes, where high confidence genuinely predicts correctness, and
lost on the inferential ones. An aggregate calibration figure conceals both
effects.

E3's distribution is bimodal in a different way, with 40 of 99 runs at exactly
1.0. Its predicates are few and weighted, so a diagnosis whose evidence all
holds receives a maximal score irrespective of how much evidence there was.
This compresses the upper range and limits E3's usefulness as a threshold
variable, as §4.6 shows.

## 4.6 The escalation threshold

**Figure 4.2 — Automation rate against error rate**

Derived by recomputing the gate decision against stored confidence values,
holding diagnosis fixed and varying only the threshold. Tier permissions
follow the balanced policy (R0–R2). An executed action counts as an error if
it failed to resolve the incident or was judged unsafe.

| θ | E1 automation | E1 error rate | E3 automation | E3 error rate |
|---|---|---|---|---|
| 0.50 | 91% | 48% | 86% | 53% |
| 0.60 | 88% | 46% | 71% | 47% |
| 0.70 | 86% | 44% | 54% | 43% |
| 0.75 | 80% | 43% | 44% | 45% |
| 0.80 | 79% | 42% | 44% | 45% |
| 0.85 | 72% | 37% | 44% | 45% |
| 0.90 | 48% | 35% | 44% | 45% |
| 0.95 | 46% | 34% | 44% | 45% |

Three observations follow.

**No threshold achieves both substantial automation and a low error rate.**
The most favourable operating point in the corpus is E1 at θ = 0.90, which
executes 48% of eligible runs with a 35% error rate. Raising the threshold
further yields almost nothing: θ = 0.95 improves the error rate by one
percentage point while reducing automation by two. This is a negative result
and should be reported as one. On this workload, confidence gating cannot
deliver near-autonomous operation at an error rate an operator would accept.

**E1 dominates E3 across the usable range.** At comparable automation rates
E1's error rate is consistently lower, and at θ = 0.90 E1 achieves the same
automation as E3 with a ten-point lower error rate. This follows directly from
the AUROC difference in §4.5: better ranking produces a better trade-off curve
regardless of calibration.

**E3 plateaus above θ = 0.75.** Its curve is flat from 0.75 to 0.95 —
identical automation, identical error rate — because 40 runs share the maximal
score of 1.0 and no threshold in that range separates them. An estimator whose
values are concentrated at the extremes cannot be tuned, however well
calibrated it is. This is a practical limitation of evidence-grounded
confidence as constructed here, and a candidate for revision rather than a
property of the approach in general.

The escalation rate at the best operating point is 52%. Set against the
finding that realised safety peaks at an escalation rate below full
escalation, because reviewer attention is finite, this suggests the practical
question is not whether to gate on confidence but whether an estimator with
better ranking can be constructed. The gating mechanism is sound; the signal
available to it is the limiting factor.

## 4.7 Operational cost

**Table 4.11 — Mean cost per run**

| Policy | Tokens in | Tokens out | LLM calls | Agent wall time |
|---|---|---|---|---|
| Permissive | 40,420 | 500 | 1.0 | 38.7 s |
| Balanced | 39,110 | 502 | 1.0 | 90.7 s |
| Conservative | 39,101 | 495 | 1.0 | 36.1 s |

Token consumption is effectively constant across conditions, as expected: the
agent's diagnostic work is identical and only the gate's response differs. The
mean of 5.9 diagnostic tool calls per run indicates the agent investigates
rather than answering from the initial context alone.

Protocol reliability was high. Two of 99 runs (2.0%) failed to produce a
well-formed decision within the retry budget, and both were denied by the gate
on `unknown_action`.

## 4.8 An excluded corpus, reported as a finding

An earlier corpus of 36 runs was discarded rather than analysed. In it, eight
of nine application-saturation runs diagnosed `network_partition` against true
causes of connection pool exhaustion, thread starvation and cascading latency.

The cause was visible only in the free-text justifications, which cited the
fault-injection framework directly — reporting, for example, that events
showed a `PodNetworkChaos` resource targeting the backing store. Chaos Mesh
creates its resources alongside the pods it targets, and those resources
appeared in the namespace events and pod descriptions supplied to the agent.
The agent was not diagnosing from symptoms; it was reading the experiment's
ground truth, and concluding correctly that a network fault had been injected.

The episode is reported rather than merely corrected because of how it
presented. Tool use was genuine at three to eight diagnostic calls per run.
Confidence spanned 0.4 to 0.95 with no anomalous concentration. Accuracy was
poor, but poor accuracy on the hardest fault classes is exactly what a
plausible result looks like. Nothing in the quantitative record indicated a
problem, and a review confined to summary statistics would have accepted the
corpus and reported a spurious finding about model behaviour on saturation
faults.

A second and independent defect was found in the same period: five of the
twelve resolution checks could not detect their own fault, because their
thresholds were satisfied by a healthy system. The healthy baseline measured
p95 = 100 ms, p99 = 231 ms and an error rate of 0.000, while the checks
required, variously, p99 below 800 ms, p95 below 1000 ms, and an error rate
below 0.01. Each returned "resolved" on its first evaluation, in every run,
regardless of the agent's action. The signature was a mean time to resolution
identical to the decisecond across repetitions — 175.2 s three times — where
genuine recovery varies.

Both defects produced results that were wrong but not implausible. This is an
argument for qualitative inspection of individual runs as a routine part of
analysis rather than as a debugging measure of last resort, and for validating
that each measurement instrument can detect the condition it is intended to
measure before any data is collected. The validation procedure developed in
response is described in §3.8.

## 4.9 Threats to validity

**Statistical power.** Three repetitions per scenario per condition give small
per-cell samples. No claim rests on an individual cell, and the class-level
findings aggregate nine to twenty-seven observations.

**A single workload and topology.** Online Boutique runs one replica per
service, which affects both blast-radius measurement and the interpretation of
pod deletion as remediation. The frontend also degrades gracefully when
non-essential dependencies slow, which is what rendered APP-02 unobservable.

**A single model family.** All results are from one model. The R3 finding in
particular — one disproportionate proposal in 99 runs — is a property of this
model's disposition, not of LLM agents generally.

**Frontend-only measurement.** Application latency and error rate are measured
at the frontend, so per-service attribution is unavailable.

**Reference fixes are one correct answer.** Two runs selected a defensible
alternative action and resolved cleanly, one of them less invasive than the
reference. Agreement with the reference fix is a lower bound.

**Accepted alternatives are an author judgement**, fixed before collection and
documented per scenario, but chosen by the same person who designed the
scenarios.

**Two scenarios are diagnosis-only.** APP-02 and the excluded RES-03 produce
no client-observable failure, so 9 of 99 runs contribute to diagnostic
accuracy but not to resolution statistics.
