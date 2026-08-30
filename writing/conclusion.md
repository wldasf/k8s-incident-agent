# Conclusion

This project asked when an LLM-based incident-response agent should be
permitted to act on its own diagnosis, and whether the confidence signal used
to make that decision can bear the weight placed on it. It answered those
questions by building a validated benchmark of eleven Kubernetes fault
scenarios, a formally specified safety gate, three confidence estimators and
an evaluation harness, and by collecting ninety-nine runs across three policy
conditions on a live cluster.

## 6.1 What was found

**Diagnostic reliability has a boundary.** Accuracy was 98% on faults whose
cause is expressed directly in cluster state — an invalid image tag written in
a deployment specification, a memory limit sitting beside an out-of-memory
termination — and 24% on faults requiring inference across services. This is
not a gradient with a middle. It suggests that an agent's usefulness in
incident response depends less on its general capability than on whether the
particular fault leaves a declarative trace.

**The confidence signal is usable but not by the route expected.** The
evidence-grounded estimator, constructed to check whether the world looks as
the agent claims, produced better-calibrated numbers: its expected calibration
error was 29% lower. Yet the model's own stated confidence discriminated
substantially better, separating correct from incorrect diagnoses with an
AUROC of 0.876 against 0.736. For gating, discrimination is the operative
property — a threshold needs correct diagnoses ranked above incorrect ones,
not numerically accurate probabilities. The naive estimator therefore
outperformed the designed one on the criterion that matters, which was not the
anticipated result.

Two qualifications attach to that. Stated confidence is *selectively*
miscalibrated: its high-confidence band is perfectly accurate while the band
immediately below it is 24% accurate, and 35 of the 37 runs in that lower band
are the inferential fault classes. And the evidence-grounded estimator's
scores are concentrated at the extremes, which makes it untunable above a
threshold of 0.75 regardless of how well calibrated it is.

**No threshold delivers both automation and safety.** The most favourable
operating point automated 48% of eligible incidents at a 35% error rate.
Raising the threshold further bought almost nothing. On this workload,
confidence gating cannot produce near-autonomous operation at an error rate an
operator would accept, and reporting otherwise would require ignoring the
data.

**Policy comparison shows caution is not free, and can be degenerate.** The
balanced policy achieved 87% of the permissive policy's resolutions while
acting 20% less often — a genuine trade. The conservative policy achieved
nothing at all: it denied every proposal on tier grounds, resolved no
incidents, and escalated 100% of them to a human. It did not make the agent
careful; it made it inert, while imposing the maximal possible reviewer load.

**Tier restriction is insurance, not restraint.** A destructive action was
proposed once in ninety-nine runs, and under the one policy that forbade it.
Aggregate rates would have supported the conclusion that the model
self-restricts and the gate's tier rules are redundant. The single observation
refutes that: the agent will occasionally reach for a disproportionate action,
rarely and unpredictably, which is precisely the profile a categorical
restriction is suited to.

## 6.2 A methodological finding

Two contamination modes were discovered during collection, and both are
properties of how such benchmarks are built rather than of this
implementation.

The fault-injection framework created resources in the namespace it targeted,
and those resources appeared in the telemetry supplied to the agent. The agent
read them and concluded, correctly, that a fault had been injected — it was
not diagnosing but reading the experiment's answer. Separately, five of the
twelve resolution checks could not detect their own fault, because their
thresholds were satisfied by a healthy system; each returned "resolved" on its
first evaluation in every run.

Both produced results that were wrong but not implausible. Tool use was
genuine, confidence values unremarkable, and accuracy poor in exactly the
classes where poor accuracy is expected. Neither was visible in summary
statistics; both were found only by reading individual runs and by measuring
whether each instrument could detect the condition it was meant to measure.

The general form is that an evaluation sharing an observability plane with its
subject must treat its own artefacts as ground truth and withhold them, and
that a measurement instrument must be shown to respond to the phenomenon
before it is used to measure it. Neither is specific to the tooling used here.

## 6.3 What this does not show

The findings are bounded. They come from one model, one workload with a single
replica per service, three repetitions per cell, and measurement taken at the
frontend rather than per service. The claim that the agent rarely proposes
destructive action is a property of this model's disposition and would not
transfer without testing. Two scenarios produce no client-observable failure
and are scored for diagnosis only, so nine of the ninety-nine runs contribute
to accuracy but not to resolution.

The study also does not show that agents are better or worse at incident
response than previously reported. It was not designed to advance diagnostic
capability and its accuracy figures should not be read as competitive with
work optimised for that purpose.

## 6.4 Further work

The most direct extension follows from the boundary in §6.1: if accuracy and
calibration vary systematically by fault class, a single global threshold
applies a uniform rule to a non-uniform capability. Conditioning thresholds on
fault class would be an improvement, though it requires a reliable classifier
for fault class, which may not be easier than the diagnosis problem itself.

The evidence-grounded estimator's concentration at the extremes is a
construction problem rather than a property of the approach. More predicates,
finer weighting, or partial credit for partially-satisfied evidence would
spread the distribution and make it tunable — and given that it is already
better calibrated, an estimator that also discriminated well would be a
material improvement over stated confidence.

Two further directions are worth noting. The present design permits one action
per incident, which excludes the sequential diagnose-act-reassess behaviour
real operators exhibit; extending the outcome taxonomy to multi-action
remediation would test a more realistic setting. And replicating on a workload
with replicated services would separate findings about actions from findings
about topology, since pod deletion is a materially different act when a
service has one replica rather than three.

## 6.5 Closing

The question this project set out to answer was where the boundary between
autonomous action and human escalation should be drawn. The honest answer, on
this evidence, is that it cannot yet be drawn anywhere comfortable. The
gating mechanism works as specified, fails closed, and discriminates between
policies in measurable ways. The limiting factor is the confidence signal
available to it: usable enough to be better than nothing, not good enough to
support the autonomy its users would want.

That is a less satisfying conclusion than a recommended threshold would have
been, but it is the one the data supports, and identifying the limiting factor
is a more useful contribution than an operating point that would not survive
contact with a different workload.
