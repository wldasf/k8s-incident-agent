# Introduction

## 1.1 The problem

Modern online services are assembled from many small, interconnected software
components running across large fleets of machines, most commonly orchestrated
by Kubernetes. The architecture delivers scalability at the cost of fragility:
a fault in one component can cascade into a service-wide outage, and the
systems emit enormous volumes of diagnostic data while it happens. The
engineers responsible for reliability must interpret those signals in real
time, form a hypothesis about the cause, and act on it under pressure.

Large language models are plausible candidates for parts of this work. They
process unstructured text fluently, which is the form logs and alerts take,
and they can call external tools to gather further evidence. A substantial
literature now demonstrates competent fault diagnosis in cloud systems, and
recent frameworks have extended evaluation to remediation with
execution-based verification on live clusters.

That literature has answered whether an agent can identify a fault. It has
not answered a question that matters more for deployment: **when should the
agent be permitted to act on its own diagnosis, and when must it stop and ask
a human?**

The question is not hypothetical. Confidence-gated escalation — acting
autonomously above a confidence threshold and escalating below it — is the
dominant pattern in deployed agent systems. Yet the confidence signal on which
that pattern depends is known to be poorly calibrated in general, and has not
been evaluated in operational incident response. An ICML position paper on
uncertainty quantification for language-model agents argues that the field
should reason from the practical task — abstention among them — and notes
that numerical thresholds remain appropriate where an agent's output is consumed
by an automated system rather than a human. What it does not supply, and nor
does the wider literature, is evidence about which estimator best serves that task.
The mechanism governing autonomous action in production has not been measured
in the setting where it is used.

## 1.2 Aim and research questions

This project designs, implements and empirically evaluates an autonomous
incident-response agent for Kubernetes, with the explicit purpose of measuring
where the boundary between autonomous action and human escalation should fall,
and whether the confidence signal used to draw it can bear that weight.

Four questions organise the work:

1. **Capability.** For common categories of Kubernetes failure, how reliably
   can an LLM-based agent identify the underlying cause and select an
   appropriate remediation?
2. **Safety.** What safeguards — restricting actions to a pre-approved
   catalogue, bounding blast radius, requiring a minimum confidence, running
   actions in rehearsal first — are sufficient to make autonomous action safe,
   and where does the boundary between automation and escalation fall?
3. **Confidence.** Can the confidence signal on which that boundary depends be
   trusted, and does it matter how confidence is estimated?
4. **Cost.** What are the speed, expense and reliability trade-offs against
   rule-based automation and a human operator?

The second and third are the substantive ones. The first is well covered by
existing work and is measured here principally to characterise the conditions
under which the safety questions are being asked.

## 1.3 Approach

The study comprises three artefacts, of which the agent is deliberately the
least novel.

A **benchmark** of eleven reproducible fault scenarios spans four classes
drawn from published studies of microservice failure: resource exhaustion,
configuration drift, dependency failure, and application saturation. Each
scenario declares a ground-truth cause from a closed vocabulary, a minimal
known-correct remediation, and a resolution condition. Each was validated
against a live cluster to confirm that its resolution check passes on a
healthy system and fails under the injected fault — a step that proved
essential, as §4.8 records.

An **agent** diagnoses incidents through a reasoning loop with access to
read-only diagnostic tools, emitting a structured decision comprising a root
cause, a proposed action, a confidence value and a justification. It is
assembled from existing services and holds no mutating capability; every
state change passes through the safety gate.

A **safety gate** implements a total decision function over the proposed
action, its declared risk tier, its computed blast radius, and its confidence,
returning execute, escalate or deny with a machine-readable reason. Because a
policy is a set of numeric thresholds and an allowed action set, "tightening
the policy" denotes a measurable change rather than a disposition, and three
policies — permissive, balanced and conservative — form the experimental
conditions.

Confidence is treated as an experimental variable rather than a fixed
mechanism. Three estimators are computed on every run: the model's own stated
confidence, agreement across repeated sampling, and the weighted fraction of
observable predicates supporting the *claimed* root cause. The third is
grounded in cluster state rather than model self-report, and is constructed so
that a confident incorrect diagnosis scores low.

Outcomes are classified along two independent axes — whether the incident
resolved, and whether the action taken was proportionate — because a single
success rate conflates an agent that fails harmlessly with one that succeeds
destructively.

## 1.4 Contributions

The contribution is not a more capable agent. It is a measurement, and four
findings follow from it.

**Diagnostic reliability has a boundary rather than a gradient.** Accuracy is
near-perfect on faults whose cause is stated in declarative cluster state and
collapses on faults that must be inferred from behaviour distributed across
services.

**Calibration and discrimination come apart, and the naive estimator wins on
the property that matters.** Evidence-grounded confidence is better calibrated,
but the model's own stated confidence ranks correct diagnoses above incorrect
ones substantially better — and ranking, not numerical accuracy, is what a
threshold requires.

**No threshold delivers both substantial automation and a low error rate.**
The most favourable operating point in the corpus automates just under half of
eligible incidents at an error rate above a third. This is reported as the
negative result it is.

**Tier restriction is insurance against a rare event, not a constant
restraint.** A destructive action was proposed once in ninety-nine runs, and
under the one policy that forbade it. Aggregate rates alone would have
supported the opposite conclusion.

A fifth contribution is methodological. Two independent contamination modes
were discovered during collection — the fault injector leaking ground truth
into agent-visible telemetry, and resolution checks that could not detect
their own faults — and both produced results that were wrong but entirely
plausible. Neither was visible in summary statistics. These are reported in
full, together with the validation procedure developed in response, because
they are properties of how such benchmarks are constructed rather than of this
implementation.

## 1.5 Structure

Chapter 2 reviews the literature and locates the gap this study addresses,
demonstrating through structured comparison that mitigation is addressed by a
recent minority of work and safety evaluation by none of it. Chapter 3
specifies the test environment, benchmark, agent, safety gate, confidence
estimators and experimental procedure. Chapter 4 reports the results across
ninety-nine runs and three policy conditions, including the excluded corpus.
Chapter 5 interprets those results, relates them to prior work, and states the
limitations bounding the claims. Chapter 6 concludes.
