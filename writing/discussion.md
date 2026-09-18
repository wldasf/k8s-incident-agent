# Discussion

## 5.1 What the results say about the research question

The study asked when an LLM-based agent should be permitted to act on its own
diagnosis, and whether the confidence signal used to make that decision can
bear the weight placed on it. The answer to the second question constrains the
first, and it is not encouraging.

**No threshold in the swept range achieves both substantial automation and an
acceptable error rate.** The most favourable operating point observed was the
verbalised estimator at a threshold of 0.90, which executed 48% of eligible
runs with an error rate of 35%. Raising the threshold further bought almost
nothing: at 0.95 the error rate improved by a single percentage point while
automation fell by two. The evidence-grounded estimator performed worse across
the usable range, and its curve was flat from 0.75 upward. Neither estimator
offers an operating point at which a majority of incidents are resolved
autonomously and unsafe or ineffective actions are rare.

This is a negative result and is reported as one. The gating mechanism itself
behaves as specified — it discriminates between policies, fails closed under
error, and attributes every blocked action to a named rule. The limiting
factor is the quality of the signal available to it.

The second finding is that diagnostic reliability is not a single quantity but
a boundary. Accuracy was 27/27 on configuration drift and 17/18 on resource
exhaustion, against 9/27 on application saturation and 4/27 on dependency
failure. The ordering corresponds to how directly the cause is expressed in
declarative cluster state: an invalid image tag is written in the deployment
specification, whereas a partition between two healthy services is named
nowhere and must be inferred. A policy expressed as one global threshold
therefore applies a uniform rule to a capability that is anything but uniform.

The third finding is that diagnosis and remediation succeed or fail together.
Across the balanced condition, 20 runs produced a correct root cause and 15
selected the reference remediation, with no cases of a correct remediation
under an incorrect diagnosis. This matters for the design: it establishes that
confidence in diagnosis is a legitimate quantity on which to gate action,
which was assumed rather than demonstrated when the gate was specified. Had
action selection proved the more reliable of the two, the gate would have been
thresholding the wrong signal.

## 5.2 Confidence: what can and cannot be thresholded

Confidence-gated escalation is the dominant pattern in deployed agent systems
[Zyl26], and Kirchhof et al. note that numerical uncertainty with a threshold
remains appropriate where an agent's output is consumed by an automated system
rather than a human [Kirchhof25]. What the literature does not supply is
evidence about which estimator best serves that thresholding task in an
operational setting. This study measured it directly.

The result was not the one the design anticipated.

The evidence-grounded estimator (E3) produced better-calibrated numbers. Its
expected calibration error was 0.208 against the verbalised estimator's 0.293,
and its mean confidence of 0.72 sits closer to the observed accuracy of 0.58
than E1's 0.83. This is consistent with the documented overconfidence of model
self-report [Xiong24, Kadavath22].

The verbalised estimator nonetheless discriminated substantially better, with
an area under the ROC curve of 0.876 against E3's 0.736. Presented with one
correct and one incorrect diagnosis, E1 assigned the higher confidence to the
correct one 88% of the time; E3 managed 74%.

Calibration and discrimination are independent properties, and for a gating
decision the second is the operative one. A threshold does not require the
confidence value to be numerically accurate; it requires that correct
diagnoses receive higher values than incorrect ones. On that criterion the
naive estimator outperformed the grounded one, and the threshold sweep
confirms the practical consequence: at comparable automation rates E1's error
rate was consistently lower, and at a threshold of 0.90 it achieved the same
automation as E3 with a ten-point lower error rate.

Two observations qualify that comparison.

**Miscalibration is selective rather than uniform.** E1's distribution is
dominated by two bins holding 80 of 99 runs. The upper bin, spanning 0.9 to
1.0, was perfectly accurate. The bin immediately below it, spanning 0.8 to
0.9, was 24% accurate. A difference of one tenth in stated confidence
separates near-certainty from near-worthlessness. That cliff is not evenly
distributed: 35 of the 37 runs in the lower bin are dependency-failure or
application-saturation scenarios. The model is therefore not uniformly
overconfident but confidently wrong on precisely the fault classes it cannot
diagnose, and an aggregate calibration figure conceals this entirely. E1's
strong ranking is earned on the declarative classes and lost on the
inferential ones.

**E3's weakness is a construction problem rather than a property of the
approach.** Forty of its 99 scores sit at exactly 1.0. Its predicate sets are
small and weighted, so a diagnosis whose evidence all holds receives a maximal
score irrespective of how much evidence there was. This compresses the upper
range and leaves no threshold above 0.75 capable of separating anything, which
is why its sweep curve is flat across that interval. An estimator whose values
concentrate at the extremes cannot be tuned, however well calibrated it is.

The construction of E3 is nonetheless what makes the comparison meaningful.
Because its predicates are selected by the root cause the agent *claims*
rather than the true one, a confident incorrect diagnosis scores low: the
estimator asks whether the world looks the way the agent says it does. That
property is available to an operational agent in a way it is not to a
question-answering system, and an estimator that combined it with a wider
score distribution would be a material improvement over self-report.

## 5.3 The cost of caution

The three policy conditions quantify the trade-off the study exists to
characterise, and they do not sit on a single axis.

The permissive policy executed 30 of 33 proposals and resolved 23 of 30
scoreable incidents. The balanced policy executed 24 and resolved 20 — 87% of
the permissive policy's resolutions while acting 20% less often. That is a
genuine trade: fewer actions, slightly fewer resolutions, and in this corpus
one compound failure rather than none.

The conservative policy executed nothing. All 33 proposals were denied, 32 of
them on tier grounds, and no incident resolved. The reason is structural
rather than a matter of degree: the agent proposed R2 actions in 95 of 97
classified runs, and the conservative policy permits only R0 and R1. It did
not require the agent to be more certain — its confidence thresholds were
never consulted — it forbade the only class of action the agent ever
proposes.

The condition is therefore degenerate rather than cautious. It surrendered
every resolution and prevented no unsafe action, because in this corpus there
was none to prevent. It also escalated 100% of incidents, which is the maximal
load a policy can impose on a human reviewer.

The framing to resist is that escalation is free. Research on oversight under
load finds that realised safety peaks at an escalation rate below full
escalation, because a reviewer saturated with low-value escalations attends
less carefully to the ones that matter [Cap26]. The conservative policy is not
the safe baseline it appears to be; it relocates risk from incorrect
autonomous action to reviewer fatigue and unresolved incidents.

One comparison requires care. Mean time to resolution was higher under the
permissive policy (319 s) than the balanced one (237 s), which appears
counter-intuitive. The explanation is compositional: the permissive policy
resolves three incidents that the balanced policy escalates, and those
additional cases are the slower ones. The balanced policy's faster mean
reflects an easier subset rather than faster remediation.

## 5.4 Harmful success, and what its absence means

The outcome taxonomy separates resolution from proportionality specifically to
expose a category a single success rate conceals: an incident resolved by
disproportionate means.

No harmful successes were recorded across 54 executed actions. When the agent
acted and resolved an incident, it did so proportionately. This is a genuine
negative rather than an absence of measurement: an earlier corpus, collected
before the collateral-damage timing correction described in §3.7, reported
nine harmful successes, so the detector is known to fire when its conditions
are met. One compound failure occurred — the taxonomy's worst cell, damage
without benefit — in which `scale_workload` neither resolved the incident nor
left unrelated services undisturbed.

The destructive-action finding is more interesting than its frequency
suggests. Across 99 runs the agent proposed an R3 action exactly once: in
DEP-03 under the conservative policy, it proposed draining a node — evicting
every pod from a machine — in response to a network partition between two
otherwise healthy services. The gate denied it on tier grounds.

Two readings were available before the data arrived, and the single
observation separates them. Zero proposals under the permissive policy, which
admits R3 at a confidence threshold of 0.90, would on its own suggest that the
model self-restricts to reversible remediation and that the gate's tier rules
are largely redundant. The conservative-condition proposal refutes that
reading. The agent will reach for a disproportionate destructive action,
rarely and unpredictably, which is precisely the profile a categorical
restriction suits. Tier restriction is therefore insurance against a
low-probability, high-cost event rather than a constant restraint — a
materially different justification, and one that could not have been
established from aggregate rates.

It is worth noting that the proposal arose under the one policy that forbade
it. Had the same diagnosis occurred under the permissive policy, the action
would have been evaluated on confidence alone.

This is a claim about one model's disposition on one workload. A model more
willing to reach for destructive remediation would change the answer without
changing anything about the gate.

A methodological caveat belongs here. Every service in the workload runs a
single replica, so deleting a pod removes the service entirely until its
replacement is ready. Whether that constitutes collateral damage is a
substantive judgement rather than a measurement artefact: in a single-replica
deployment it plainly is, and in a replicated one it plainly is not. The
metric reports something real about this deployment topology rather than
something general about the action.

## 5.5 Benchmark construction: two contamination modes

Two problems arose during collection that are worth reporting as findings
rather than as incidents, because both are properties of how such benchmarks
are built rather than of this implementation. Meas26 makes a related argument:
that empirical claims about agentic Kubernetes operations are largely
unfalsifiable for want of agent-disabled controls, and reports confounds its
own instrumentation caught that would otherwise have produced incorrect
published claims [Meas26].

### Shared observability planes leak ground truth

The fault-injection framework created resources in the namespace it was
targeting, and those resources appeared in the events and pod descriptions
supplied to the agent. In an initial corpus of 36 runs, eight of nine
application-saturation runs diagnosed `network_partition` against true causes
of connection pool exhaustion, thread starvation and cascading latency. The
justifications cited the framework directly, reporting that events showed a
`PodNetworkChaos` resource targeting the affected service. The agent was not
diagnosing; it was reading the answer, and concluding correctly that a network
fault had been injected.

The general form of the problem is that the harness and the system under test
shared an observability plane. Any evaluation with that property must treat
the harness's own artefacts as part of the ground truth and withhold them.
This is not specific to Chaos Mesh, and it applies with more force as agents
are given broader access to cluster state: an agent permitted to read custom
resources or the control-plane audit log has more channels through which the
experiment can leak.

What makes it worth reporting is that it was invisible in the aggregate
record. Tool use was genuine at three to eight diagnostic calls per run,
confidence spanned 0.4 to 0.95 with no anomalous concentration, and accuracy
was poor in exactly the classes where poor accuracy is expected. Only the
free-text justifications revealed the mechanism. A review confined to summary
statistics would have accepted the corpus and reported a plausible and
entirely spurious finding about model behaviour on saturation faults.

### Measurement instruments that cannot detect their own fault

The second defect was independent and equally invisible. Five of the twelve
resolution checks could not detect the fault they were written to observe,
because their thresholds were satisfied by a healthy system. The healthy
baseline measured p95 latency of 100 ms, p99 of 231 ms and an error rate of
0.000, while the checks required, variously, p99 below 800 ms, p95 below
1000 ms, and an error rate below 0.01. Each returned "resolved" on its first
evaluation, in every run, regardless of what the agent did.

The signature was a mean time to resolution identical to the decisecond across
repetitions — 175.2 seconds three times — where genuine recovery varies. A
related defect compounded it: injected faults were configured with a duration
shorter than the resolution window, so faults expired unaided and every run in
which the gate declined to act was scored as resolved. That effect is not
random. It inflates resolution rates in proportion to how often a policy
escalates, which flatters conservative policies most — precisely the
comparison the study exists to make.

Both were found by running a no-op baseline in which the gate denied every
action, and by subsequently building a validation procedure that injects each
fault and confirms the resolution check passes at baseline and fails under
fault. Of twelve scenarios, four passed that check on first attempt. The
remainder required correction, one was reframed around the failure Kubernetes
actually produces rather than the one intended, one was retained for diagnosis
only because it produces no client-observable failure, and one was excluded.

The general lesson is that a measurement instrument must be shown to respond
to the phenomenon before it is used to measure it, and that an evaluation
measuring whether an intervention resolved an incident must ensure the
incident cannot resolve itself within the measurement window.

Both problems shared a signature: they produced results that were wrong but
not implausible. That is an argument for qualitative inspection of individual
runs as a routine part of analysis rather than as a debugging measure of last
resort.

## 5.6 Relation to prior work

The reviewed literature establishes that LLM agents diagnose cloud faults
competently, and recent work has extended evaluation to remediation with
execution-based verification [Chen25]. This study does not attempt to advance
either capability, and its diagnostic accuracy figures should not be read as
competitive with work optimised for that purpose.

Its contribution is to the governance question those benchmarks leave open.
Existing frameworks measure whether an agent *can* remediate. STRATUS is the
partial exception, formalising a safety specification termed Transactional
No-Regression that constrains an agent's exploration so that iteration does
not degrade the system under repair [Stratus25]. That governs how safely an
agent may search for a fix; it does not measure the cost of applying a
disproportionate one, nor evaluate the confidence signal on which deployed
systems gate autonomous action.

The comparison in §2.6 shows the pattern: detection, localisation and
root-cause analysis are near-universally addressed, mitigation is addressed by
a recent minority, and the cost of incorrect or disproportionate action by
none of the reviewed work.

What this study adds is a measurement rather than a capability. It does not
show that agents are better or worse at incident response than previously
reported. It shows where the boundary of trustworthy autonomous action falls
for one model under measured conditions, and that the signal used to locate
that boundary in deployed systems is weaker than its use implies.

## 5.7 Limitations

The design is deliberately narrow, and several limitations bound the claims.

**Statistical power.** Eleven scenarios with three repetitions per condition
give three observations per cell. No claim rests on an individual cell; the
class-level findings aggregate between six and twenty-seven observations.

**A single workload and topology.** Online Boutique runs one replica per
service, which affects both blast-radius measurement and the interpretation of
pod deletion as a remediation. The frontend also degrades gracefully when
non-essential dependencies slow, which is what rendered one scenario
unobservable. Results characterise agent behaviour on this deployment shape.

**A single model family.** All results are from one model. The finding that
destructive remediation is proposed once in 99 runs is a property of this
model's disposition, not of LLM agents generally.

**Measurement position.** Application latency and error rate are measured at
the frontend, so per-service attribution is unavailable and a fault degrading
one service is observed only through its effect on the whole path.

**Reference fixes as a proxy for remediation quality.** Five runs diagnosed
correctly and selected a different action. Of the four that were scoreable,
one resolved and three failed, including the corpus's only compound failure.
Departure from the reference action therefore carried a real cost rather than
representing an equally valid alternative, which supports the reference fixes
as specified. The four departures concentrate in a single scenario, however,
so the sample is too small to establish the reference actions as uniquely
correct.

**Accepted alternatives are an author judgement.** The alternative labels were
fixed before collection and each carries a written rationale, but the choice
of which labels to accept affects reported accuracy and was made by the same
person who designed the scenarios.

**No human is in the loop.** Escalation is recorded rather than acted upon.
The study measures how often a human would be called, not what a human would
do when called, and the reviewer-load argument in §5.3 rests on published work
rather than on observation here.

**Two scenarios contribute to diagnosis only.** One produces no
client-observable failure and one was excluded after validation, so nine of
99 runs contribute to diagnostic accuracy but not to resolution statistics.

**Precondition checking is uneven.** Server-side dry run is not supported
uniformly across kubectl verbs; for two actions the check validates only that
the target exists. This is a property of the tooling rather than the design,
but it makes the gate's precondition rule weaker for those actions.

## 5.8 Future work

Four directions follow from the results, in rough order of value.

**Condition thresholds on fault class.** Accuracy and calibration both vary
sharply between declarative and inferential faults, so a single global
threshold applies a uniform rule to a non-uniform capability. A per-class
threshold would be trusting where confidence tracks correctness and strict
where it does not. The obstacle is that applying such a policy requires
knowing the fault class at decision time, and identifying the class is itself
part of the diagnosis the agent performs unreliably on exactly those faults. A
separate, cheaper classifier for fault class — or a coarse declarative-versus-
inferential distinction drawn from the evidence available rather than from the
diagnosis — may be tractable where full diagnosis is not.

**Redesign the evidence-grounded estimator for range.** E3's concentration at
the extremes, rather than its grounding, is what limited it. More predicates
per root cause, finer weighting, and partial credit for partially satisfied
evidence would spread the distribution and make it tunable. Given that it is
already the better-calibrated estimator, one that also discriminated well
would be a material improvement over self-report.

**Extend the outcome taxonomy to multi-action remediation.** The present
design permits one action per incident, which excludes the sequential
diagnose, act, reassess behaviour real operators exhibit and which may be
where the inferential fault classes become tractable.

**Replicate on a workload with replicated services.** Pod deletion is a
materially different act when a service has three replicas rather than one.
Doing so would separate findings about actions from findings about topology,
and would allow the collateral-damage threshold to be set on firmer ground.

A fifth direction is methodological. Both contamination modes documented in
§5.5 are mechanical enough to check for automatically, and a contamination
audit — verifying that harness artefacts are invisible to the agent, and that
each measurement instrument responds to its own fault — would be a reasonable
standard step in constructing benchmarks of this kind.
