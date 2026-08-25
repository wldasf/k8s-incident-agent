# Results

*Scaffolding — figures from the balanced/E1 batch (36 runs, 24 August 2026).
Cells marked ⟨…⟩ await the permissive, conservative and E2 batches.*

## 4.1 Overview of collected data

| Condition | Policy | Estimator | Runs | Status |
|---|---|---|---|---|
| A | Balanced | E1 | 36 | complete |
| B | Permissive | E1 | 36 | ⟨running⟩ |
| C | Conservative | E1 | 36 | ⟨pending⟩ |
| D | Balanced | E2 | ⟨n⟩ | ⟨pending⟩ |

All runs at harness version 2. Runs collected before that version are
excluded: they were contaminated by fault-injection artefacts visible to the
agent (§3.4) and are reported here only as a methodological finding (§4.7).

Every run records all three confidence estimators regardless of which one
gated the decision, so calibration analysis (§4.5) and the threshold sweep
(§4.6) draw on the full corpus rather than on condition-specific arms.

## 4.2 Diagnostic accuracy

Accuracy is reported under two rules. *Strict* requires exact agreement with
the scenario's ground-truth label; *lenient* additionally admits the
accepted alternatives declared per scenario (§3.3).

**Table 4.1 — Accuracy by fault class, balanced policy, E1**

| Fault class | n | Strict | Lenient |
|---|---|---|---|
| Configuration drift | 9 | 9 (100%) | 9 (100%) |
| Resource exhaustion | 9 | 6 (67%) | 6 (67%) |
| Application saturation | 9 | 2 (22%) | 4 (44%) |
| Dependency failure | 9 | 0 (0%) | 1 (11%) |
| **All** | **36** | **17 (47%)** | **20 (56%)** |

The aggregate figure is the least informative number in the table. The
class-wise breakdown is monotonic, and the ordering corresponds to how
directly the cause is expressed in declarative cluster state.

A configuration fault is *stated*: an invalid image tag appears verbatim in
the deployment specification, and a misconfigured probe is visible in the
container spec. Resource exhaustion is *adjacent*: a memory limit below the
working set sits beside an `OOMKilled` termination reason, requiring the two
to be related but not inferred. Application saturation and dependency
failure must be *inferred* from behaviour distributed across services —
elevated latency together with unremarkable CPU, or errors in one service
whose cause lies in another.

The result is therefore better stated as a gradient than as a percentage:
diagnostic reliability degrades as evidence moves from declarative to
inferential. ⟨Confirm the gradient holds across policies once B and C are
in; policy should not affect diagnosis, so a departure would indicate an
uncontrolled variable.⟩

**Table 4.2 — Accuracy by condition**

| Condition | Strict | Lenient | Δ |
|---|---|---|---|
| A (balanced, E1) | 47% | 56% | 9pp |
| B (permissive, E1) | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| C (conservative, E1) | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |

The strict–lenient gap measures how much apparent error is disagreement over
labelling rather than misdiagnosis. In condition A it accounts for 3 of 19
errors.

### 4.2.1 Error structure

Errors are not uniformly distributed and are not random.

⟨Table 4.3 — confusion matrix, claimed against true root cause, all runs.⟩

Two patterns in the dependency-failure class are worth separating. In
condition A the agent produced no exact matches across nine runs, but the
claimed labels were scattered — `thread_starvation`, `cpu_throttling`,
`resource_limit_misconfig`, `cascading_latency` — rather than converging on
a single confusion. This is consistent with genuine diagnostic difficulty
rather than a systematic misreading.

By contrast, application-saturation errors cluster: the agent repeatedly
identifies the correct *family* (latency under normal resource utilisation)
while naming the wrong mechanism within it. In one representative run it
reported elevated frontend latency of 700–1500 ms with CPU and memory below
limits and the backing store responding normally, and proposed the
scenario's reference fix — while labelling the cause `cascading_latency`
rather than `connection_pool_exhaustion`.

⟨Report how often the proposed action matched the reference fix
independently of whether the label was correct. A correct remedy under an
incorrect label is a materially different result from a wrong remedy, and
the two are currently collapsed.⟩

## 4.3 Gate behaviour

**Table 4.4 — Gate decisions by policy**

| Policy | EXECUTE | ESCALATE | DENY | n |
|---|---|---|---|---|
| Balanced | 26 (72%) | 8 (22%) | 2 (6%) | 36 |
| Permissive | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨36⟩ |
| Conservative | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨36⟩ |

**Table 4.5 — Escalation and denial reasons**

| Reason | Balanced | Permissive | Conservative |
|---|---|---|---|
| `confidence_below_threshold` | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| `tier_not_allowed` | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| `blast_radius_exceeded` | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| `dry_run_failed` | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| `budget_exhausted` | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |

Recording the first rule to block an action allows escalations to be
attributed to a specific mechanism rather than reported in aggregate. This
matters for interpreting the policy comparison: two policies producing the
same escalation rate for different reasons are not equivalent.

### 4.3.1 Action selection

**Table 4.6 — Proposed action by risk tier**

| Tier | Balanced | Permissive | Conservative |
|---|---|---|---|
| R1 (reversible, narrow) | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| R2 (reversible, wide) | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| R3 (destructive) | 0 (barred) | ⟨…⟩ | 0 (barred) |

The permissive condition is the only one admitting destructive actions, at a
confidence threshold of 0.90. ⟨If the agent proposes no R3 action across 36
permitted runs, that is a substantive finding: it would indicate the model
self-restricts to reversible remediation, and would qualify how much
constraint the gate is contributing over and above the model's own
disposition. If it does propose R3 actions, report the scenarios and whether
the reference fix was reversible.⟩

## 4.4 Remediation outcomes

**Table 4.7 — Outcome distribution, balanced policy, E1**

| | Action safe | Action unsafe |
|---|---|---|
| **Resolved** | 30 clean resolution | 0 harmful success |
| **Unresolved** | 6 benign failure | 0 compound failure |

Resolution rate 30/36 (83%). Mean time to resolution 474 s (min 95, max
1299).

No harmful successes were recorded across 26 executed actions. The result is
a genuine negative rather than an absence of measurement: an earlier batch,
before the collateral-damage timing correction (§3.7), reported nine harmful
successes, so the detector is known to fire when its conditions are met. In
this corpus, when the agent acted it acted proportionately.

⟨Two qualifications to resolve. First, every service in the workload runs a
single replica, so `delete_pod` briefly removes the service entirely; whether
that should count as collateral damage is a substantive question, not a
measurement artefact, and the answer should be stated explicitly. Second,
harmful success can only be observed where destructive actions are
permitted; condition B is the only opportunity for it to arise.⟩

**Table 4.8 — Outcomes by policy**

| Policy | Clean | Harmful success | Benign failure | Compound failure |
|---|---|---|---|---|
| Balanced | 30 | 0 | 6 | 0 |
| Permissive | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| Conservative | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |

The escalation-versus-resolution relationship is the practical trade-off the
study exists to characterise: a policy that escalates more should resolve
fewer incidents autonomously while incurring fewer unsafe actions. ⟨Quantify
across the three policies.⟩

## 4.5 Confidence calibration

**Table 4.9 — Confidence by estimator**

| Estimator | Mean | SD | Mean when correct | Mean when incorrect | Separation |
|---|---|---|---|---|---|
| E1 verbalised | 0.80 | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| E2 self-consistency | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| E3 evidence-grounded | 0.59 | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |

The 0.21 gap between mean E1 and mean E3 is consistent with the reported
overconfidence of verbalised self-report. The more consequential quantity,
however, is not the mean but the *separation*: the difference in confidence
between correct and incorrect diagnoses. A threshold is only useful if the
score it acts on separates the two.

**Table 4.10 — Calibration metrics**

| Estimator | ECE | Brier | AUROC (action success) |
|---|---|---|---|
| E1 | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| E2 | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| E3 | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |

⟨Figure 4.1 — reliability diagrams, ten bins, one panel per estimator, with
the identity line. Caption should state bin counts, since small-sample bins
are unstable and the diagram will mislead without them.⟩

Miscalibration is not uniform across fault classes. In the
dependency-failure scenarios, where strict accuracy was 0/9, incorrect
diagnoses carried E1 confidences in both the 0.85–0.90 and 0.30–0.40 ranges.
The agent is therefore not uniformly overconfident but *selectively* so, and
an aggregate calibration figure conceals this. ⟨Report ECE per fault class
as well as overall.⟩

## 4.6 The escalation threshold

**Figure 4.2 — Automation rate against error rate, θ swept from 0.50 to 0.95
in steps of 0.05, one curve per estimator.**

This is the study's central result. Because all three estimators are
recorded on every run, the curve is derived by re-evaluating the gate
decision against stored confidence values rather than by additional data
collection.

Automation rate is the proportion of runs the gate would execute. Error rate
is the proportion of executed actions that were unsafe or that failed to
resolve. The curve is expected to trade one against the other; the question
is where it bends, and whether the bend occurs at a usable operating point.

⟨Report, for each estimator: the θ maximising clean resolutions; the θ at
which unsafe actions first appear; and whether any θ achieves both a
majority of incidents resolved autonomously and zero unsafe actions. If no
such point exists for E1 but one exists for E3, that is the argument for
grounding confidence in observed evidence rather than self-report — and it
is the finding the project was designed to produce.⟩

⟨Report also the escalation rate at the recommended operating point, and
relate it to the finding that realised safety peaks below full escalation:
escalating everything is not the safe default it appears to be, since it
transfers all load to a human reviewer.⟩

## 4.7 Operational cost

**Table 4.11 — Cost per run**

| Condition | Tokens in | Tokens out | LLM calls | Agent wall time |
|---|---|---|---|---|
| A (E1) | 39,300 | 508 | 1 | ⟨…⟩ |
| D (E2) | ⟨…⟩ | ⟨…⟩ | 6 | ⟨…⟩ |

Token consumption rose approximately twenty-three-fold between early
development runs (~1,700 per run) and the corpus reported here (~39,800).
The increase is attributable to the injector-redaction correction: before
it, the agent could resolve a diagnosis from a single leaked event line and
terminated after one step; afterwards it issues three to eight diagnostic
tool calls, each result appended to the conversation.

This is worth stating explicitly because it inverts the naive reading. The
cheaper configuration was not more efficient — it was not diagnosing.

E2 multiplies calls by the sample count and is the dominant cost of the
design. ⟨State whether its calibration advantage, if any, justifies that
multiple.⟩

## 4.8 Baselines

**Table 4.12 — Agent against baselines**

| | Resolution rate | Mean MTTR | Unsafe actions |
|---|---|---|---|
| No-op | ⟨…⟩ | ⟨…⟩ | 0 |
| Rule-based | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| Human (timed) | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| Agent (balanced, E1) | 83% | 474 s | 0 |

⟨The no-op baseline establishes which scenarios self-recover; any scenario
resolving without intervention cannot discriminate between conditions and
should be flagged. The human baseline is self-administered by the author,
who designed the scenarios, and is biased toward faster diagnosis than an
unfamiliar operator would achieve; report it with that caveat and do not
rest any claim on it alone.⟩

## 4.9 A contaminated corpus, reported as a finding

An initial batch of 36 runs was discarded. In it, eight of nine
application-saturation runs diagnosed `network_partition` against true
causes of connection pool exhaustion, thread starvation and cascading
latency.

The cause was visible only in the free-text justifications, which cited the
fault-injection framework directly — for example, that events showed a
`PodNetworkChaos` resource targeting the backing store. Chaos Mesh creates
its resources alongside the pods it targets, and those resources appeared in
the namespace events and pod descriptions supplied to the agent. The agent
was not diagnosing from symptoms; it was reading the experiment's ground
truth, and concluding correctly that a network fault had been injected.

The episode is reported rather than merely corrected because of how it
presented. Tool use was genuine, at three to eight diagnostic calls per run.
Confidence spanned 0.4 to 0.95, with no anomalous concentration. Accuracy
was poor, but poor accuracy on the hardest fault classes is exactly what a
plausible result looks like. Nothing in the quantitative record indicated a
problem, and a review confined to the summary statistics would have accepted
the corpus.

The generalisation is not specific to Chaos Mesh: any evaluation in which
the harness and the system under test share an observability plane must
treat the harness's own artefacts as part of the ground truth and withhold
them. ⟨Return to this in the discussion as a recommendation for benchmark
construction.⟩

## 4.10 Threats to validity

⟨Assemble once the corpus is complete. Minimally: small per-cell samples
(n = 3) and the consequent instability of per-scenario figures; a single
workload with one replica per service, which affects both blast-radius
measurement and the interpretation of `delete_pod`; frontend-only latency
measurement with no per-service attribution; a self-administered human
baseline; accepted-alternative labels fixed before collection but chosen by
the author; and a single model family, so results characterise this model's
behaviour rather than LLM agents generally.⟩
