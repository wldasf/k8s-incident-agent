# Discussion

*Outline with argument developed. Passages marked ⟨…⟩ depend on results not
yet collected; the surrounding argument is written so that the shape of each
claim is fixed before the numbers arrive.*

## 5.1 What the results say about the research question

The study asked when an LLM-based agent should be permitted to act on its own
diagnosis, and whether the confidence signal used to make that decision can
bear the weight placed on it. Three findings bear on this.

⟨The threshold sweep (§4.6) is the primary result and this section leads with
it: the operating point, whether one exists that combines majority autonomous
resolution with zero unsafe actions, and whether that point differs by
estimator. State the answer plainly before qualifying it.⟩

The second finding is that diagnostic reliability is not a single quantity.
It varies systematically with how directly the cause is expressed in
declarative cluster state, from complete accuracy on configuration faults to
none on dependency failures in the balanced condition. Any policy expressed
as a single global threshold therefore applies a uniform rule to a
non-uniform capability. ⟨If the per-class calibration figures support it,
argue that thresholds should be conditioned on fault class, and note what
that would require operationally — a classifier for fault class that is
itself reliable, which is not obviously easier than the diagnosis problem.⟩

The third is that diagnosis and remediation succeed or fail together. Across
the balanced corpus there were no cases of a correct remediation under an
incorrect diagnosis. This matters for the design: it means confidence in
diagnosis is a legitimate quantity to gate action on, which was assumed
rather than established when the gate was specified. Had action selection
proved more reliable than labelling, the gate would have been thresholding
the wrong signal.

## 5.2 Confidence: what can and cannot be thresholded

Confidence-gated escalation is the dominant pattern in deployed agent
systems, and the reviewed literature treats the confidence signal itself as
largely unexamined in operational settings [Zyl26]. This study measured it
directly.

The verbalised estimator (E1) exceeded the evidence-grounded estimator (E3)
by 0.21 on average, consistent with the reported overconfidence of model
self-report [Xiong24, Kadavath22]. But the mean gap is the less interesting
observation. Two others matter more.

First, **miscalibration is selective rather than uniform**. In the
dependency-failure scenarios, where no diagnosis was exactly correct,
verbalised confidence spanned both 0.85–0.90 and 0.30–0.40. The model is not
consistently overconfident; it is overconfident on some failures and
appropriately uncertain on others, and an aggregate calibration figure
averages these into an uninformative middle. ⟨Report expected calibration
error per fault class alongside the overall figure and argue that the
disaggregated view is the one with operational meaning.⟩

Second, **separation matters more than calibration**. A confidence score need
not be numerically accurate to be useful for gating; it needs to rank correct
diagnoses above incorrect ones. These are independent properties [Gal26]. ⟨If
E3 shows better separation than E1 despite both being poorly calibrated in
absolute terms, that is the practically significant result, and it should be
stated in those terms rather than as a claim about calibration.⟩

The construction of E3 is what makes this comparison possible. Because its
predicates are selected by the root cause the agent *claims* rather than the
true one, a confident incorrect diagnosis scores low: the estimator asks
whether the world looks the way the agent says it does. ⟨If E3 outperforms
E1 on separation, the mechanism to credit is grounding in observable state
rather than any property of the model. That generalises: an operational agent
has access to the system it is diagnosing, and can therefore check its own
hypotheses in a way a question-answering system cannot.⟩

## 5.3 The cost of caution

⟨Once the three policy conditions are complete, the escalation-resolution
trade-off is quantified here.⟩

The framing to resist is that escalation is free. It is not: every escalated
incident is transferred to a human, and oversight capacity is finite.
Research on oversight under load finds that realised safety peaks at an
escalation rate below full escalation, because a reviewer saturated with
low-value escalations attends less carefully to the ones that matter [Cap26].
The conservative policy in this study is therefore not the safe baseline it
appears to be — it is a different allocation of risk, moving it from
incorrect autonomous action to reviewer fatigue and delayed response.

⟨Report mean time to resolution alongside escalation rate. If conservative
policies resolve fewer incidents and resolve them more slowly, state the
combined cost rather than treating escalation as costless caution.⟩

## 5.4 Harmful success, and what its absence means

The outcome taxonomy separates resolution from proportionality specifically
to make visible a category that a single success rate conceals: an incident
resolved by disproportionate means.

⟨In the balanced condition no harmful successes were recorded across 26
executed actions. Whether this survives the permissive condition — the only
one admitting destructive actions — is the interesting question, and the
answer determines how this section is written.⟩

Two readings should be distinguished carefully, and the data can separate
them. If the agent proposes no destructive action even where policy permits
it, then the model self-restricts and the gate's tier restrictions are
largely redundant for this model — a finding that qualifies how much safety
the gate is actually contributing. If the agent does propose destructive
actions and the gate blocks them, the gate is doing load-bearing work. These
have very different implications for whether such a gate is necessary, and
the permissive condition is the only place the question can be answered.

⟨Whichever holds, note that it is a claim about one model on one workload,
and that a model more willing to reach for destructive remediation would
change the answer without changing anything about the gate.⟩

A methodological caveat belongs here. Every service in the workload runs a
single replica, so deleting a pod removes the service entirely until its
replacement is ready. Whether that constitutes collateral damage is a
substantive judgement rather than a measurement artefact: in a
single-replica deployment it plainly is, and in a replicated one it plainly
is not. The metric is therefore reporting something real about this
deployment topology rather than something general about the action, and the
threshold should be read with that in mind.

## 5.5 Benchmark construction: two contamination modes

Two problems arose during collection that are worth reporting as findings
rather than as incidents, because both are properties of how such benchmarks
are built rather than of this implementation.

### Shared observability planes leak ground truth

The fault-injection framework created resources in the namespace it was
targeting, and those resources appeared in the events and pod descriptions
supplied to the agent. The agent read them and concluded — correctly — that
a network fault had been injected. It was not diagnosing; it was reading the
answer.

The general form of the problem is that the harness and the system under
test shared an observability plane. Any evaluation with that property must
treat the harness's own artefacts as part of the ground truth and withhold
them. This is not specific to Chaos Mesh, and it applies with more force as
agents are given broader access to cluster state: an agent permitted to read
custom resources or the control-plane audit log has more channels through
which the experiment can leak.

What makes it worth reporting is that it was invisible in the aggregate
record. Tool use was genuine, confidence was unremarkable, and accuracy was
poor in exactly the classes where poor accuracy is expected. Only the
free-text justifications revealed the mechanism. A review confined to summary
statistics would have accepted the corpus, and the resulting paper would have
reported a plausible and entirely spurious finding about model behaviour on
saturation faults.

### Timed faults can outlive their own remediation window

Injected faults were configured with a duration shorter than the window in
which resolution was observed. Faults therefore expired unaided, and every
run in which the gate declined to act was scored as resolved. The effect is
not random: it inflates resolution rates in proportion to how often a policy
escalates, which means it flatters conservative policies most — precisely
the comparison the study exists to make.

The general lesson is that an evaluation measuring whether an intervention
resolved an incident must ensure the incident cannot resolve itself within
the measurement window, and must record resolution-without-action as a
distinct outcome rather than as success. The no-op baseline exists to detect
exactly this and should be run first, not last. ⟨Report the no-op results
here and state which scenarios, if any, self-recover.⟩

Both problems shared a signature: they produced results that were wrong but
not implausible. That is an argument for qualitative inspection of individual
runs as a routine part of analysis rather than as a debugging measure of last
resort.

## 5.6 Relation to prior work

The reviewed literature establishes that LLM agents diagnose cloud faults
competently, and recent work has extended evaluation to remediation with
execution-based verification [Chen25, Oper26]. This study does not attempt to
advance either capability, and its diagnostic accuracy figures should not be
read as competitive with work optimised for that purpose.

Its contribution is to the governance question those benchmarks leave open.
Existing frameworks measure whether an agent *can* remediate; none of the
reviewed work measures the cost of remediating incorrectly or
disproportionately, or evaluates the confidence signal on which deployed
systems gate autonomous action. The comparison in §2.6 shows the pattern:
detection, localisation and root-cause analysis are near-universally
addressed, mitigation is addressed by a recent minority, and safety
evaluation by none of them.

⟨Position the findings against the specific figures reported by AIOpsLab and
OperAID once those have been read in full rather than through secondary
description. State clearly what this study adds and what it does not: it does
not show that agents are better or worse than previously reported, only where
the boundary of trustworthy autonomous action falls for one model under
measured conditions.⟩

## 5.7 Limitations

The design is deliberately narrow, and several limitations bound the claims.

**Statistical power.** Twelve scenarios with three repetitions give three
observations per cell. Per-scenario figures are unstable and no claim rests
on an individual cell; effect sizes are reported alongside significance
throughout.

**A single workload and topology.** Online Boutique runs one replica per
service, which affects both blast-radius measurement and the interpretation
of pod deletion as a remediation. Results characterise agent behaviour on
this deployment shape and should not be assumed to transfer to replicated
production services.

**A single model family.** All results are from one model. The finding that
the agent does not reach for destructive remediation ⟨if confirmed⟩ is a
property of this model, not of LLM agents generally.

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

**The human baseline is self-administered**, by the author, who designed the
faults. It is biased toward faster diagnosis than an unfamiliar operator
would achieve and no claim rests on it alone.

**Precondition checking is uneven.** Server-side dry run is not supported
uniformly across kubectl verbs; for two actions the check validates only that
the target exists. This is a property of the tooling rather than the design,
but it means the gate's rule-5 check is weaker for those actions.

## 5.8 Future work

⟨Develop once results are complete. Candidates, in rough order of value:

Conditioning thresholds on fault class rather than applying one global value,
given the observed variation in accuracy and calibration across classes.

Evaluating whether a second model verifying the first's diagnosis separates
correct from incorrect better than either self-report or evidence grounding.

Extending the outcome taxonomy to multi-action remediation; the present
design permits one action per incident, which excludes the sequential
diagnosis-and-repair behaviour real operators exhibit.

Replicating on a workload with replicated services, where pod deletion is
genuinely low-impact, to separate findings about the action from findings
about the topology.

A contamination audit as a standard step in benchmark construction: the two
modes documented in §5.5 are both mechanical enough to check for
automatically.⟩
