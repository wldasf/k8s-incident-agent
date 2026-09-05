# Critical Review

*Draft — MSc final project. Verify every citation against the primary source before submission.*

## 2.1 Scope and structure

This review examines the use of large language models as autonomous agents in
IT operations, with particular attention to Kubernetes incident response. It
proceeds in four parts: work on diagnosis, where the literature is dense; the
recent turn toward remediation; the treatment of uncertainty and confidence,
which is thin; and the safety mechanisms that govern autonomous action, which
are widely deployed in industry but rarely evaluated in published work. The
review closes by locating this project in the gap the comparison reveals.

## 2.2 Diagnosis: a well-served problem

The application of language models to fault diagnosis in cloud systems is
established and productive. Chen et al. demonstrated automatic root cause
analysis for cloud incidents using LLMs [Chen23], and subsequent work has
elaborated the approach along several dimensions. RCAgent introduced
tool-augmented autonomous agents for cloud root cause analysis [Wang24].
SynergyRCA applied graph-structured retrieval to Kubernetes specifically,
reporting precision of approximately 0.90 [Xiang25]. COCA incorporated code
knowledge into generative root cause analysis for distributed systems
[Li25], and Flow-of-Action encoded standard operating procedures into a
multi-agent system [Pei25].

Two architectural themes recur. The first is tool use: the ReAct pattern of
interleaved reasoning and action [Yao23] has become a de facto baseline, and
agents denied access to diagnostic tools cannot resolve faults that require
observing live system state. The second is retrieval: supplying runbooks or
historical resolutions at inference time [Lewis20] consistently improves
grounding, and MetaKube extends this to memory of past incidents, reporting
that experiential retrieval contributed a 15.3% improvement [Meta26].

Diagnosis, then, is not the open problem. The literature has converged on
tool-augmented, retrieval-grounded agents and reports strong results.

## 2.3 The turn toward remediation

Recent work has begun to close the loop from diagnosis to action, and this is
where the picture becomes more complicated.

AIOpsLab evaluates agents across the full incident lifecycle — detection,
localisation, root cause analysis, and mitigation — on live Kubernetes
deployments [Chen25]. Its results are instructive: agents that performed well
on detection performed markedly worse on mitigation. STRATUS coordinates
specialised agents across detection, diagnosis and mitigation, and formalises
a safety specification termed Transactional No-Regression that constrains an
agent's exploration so that iteration does not degrade the system it is
repairing [Stratus25]. A recovery-aware evaluation of diagnosis-to-action
reasoning asks directly whether models can recover microservice failures
rather than merely explain them [Rec26].

Two observations follow. First, this turn is very recent — the substantive
remediation benchmarks date from 2025 and 2026, where diagnosis work extends
back several years. Second, and more importantly for this project, these
benchmarks measure *whether* an agent can remediate. They do not
systematically measure *whether it should have been permitted to*. Success is
scored as resolution; the manner of resolution is not decomposed.

The distinction matters because remediation actions are not interchangeable.
An agent that resolves a failing pod by deleting the deployment has succeeded
by a resolution metric and failed by any operational standard. Conversely, an
agent that correctly diagnoses a fault outside its remit and escalates has
failed by a resolution metric while behaving exactly as intended. Collapsing
these into a single success rate discards the information that matters most
for deployment.

## 2.4 Confidence: the load-bearing assumption

Any system that decides between acting and escalating requires a quantity to
threshold against. In practice that quantity is the agent's confidence, and
confidence-gated escalation has become the dominant deployment pattern: when
an agent's confidence falls below a threshold, it routes the case to a human
rather than proceeding [Zyl26]. AIR, an incident response framework for agent
systems, likewise identifies confidence-aware protocols as the practical
mitigation for unreliable agent judgement [AIR26].

The difficulty is that the quantity being thresholded is not known to be
trustworthy. Verbalized confidence — asking a model to state a probability —
exhibits systematic overconfidence [Xiong24], a limitation consistent with
the broader finding that modern neural networks are poorly calibrated
[Guo17] and that models' self-assessed knowledge diverges from their actual
accuracy [Kadavath22]. Practitioner analyses report claimed confidence of
90% corresponding to empirical accuracy nearer 75% [Dig26]. Calibration and
discrimination are moreover independent properties: a score may rank correct
answers above incorrect ones while being numerically wrong, or be numerically
plausible while failing to separate them [Gal26].

This is a load-bearing assumption with little support beneath it. Kirchhof et al.
[Kirchhof25] argue that the traditional aleatoric–epistemic decomposition is unsuitable
for interactive agents, and that the field should reason from the practical task — abstention
among them — treating uncertainty estimators as tools rather than as labels. They further
note that numerical uncertainty with a threshold remains appropriate where an agent's
output is consumed by an automated system rather than a human, which is the configuration
studied here. What neither that paper nor the wider literature supplies is empirical evidence
about which estimator best serves that thresholding task in an operational setting. The mechanism
on which safe autonomy depends has not been evaluated in the operational setting where it
is used.

Alternatives to self-report exist but are unevaluated in this domain.
Self-consistency — sampling repeatedly and measuring agreement [Wang23] —
requires no privileged access to model internals and is therefore portable
across providers. Grounding confidence in externally verifiable evidence
rather than model self-report is a further alternative, and one that fits
operational contexts where ground truth is observable from system state.

## 2.5 Safety mechanisms: deployed but unmeasured

Industry practice has converged on a pattern that the academic literature has
not evaluated. Agent actions are classified into tiers by reversibility and
blast radius, with an oversight mode assigned to each tier [Dig26];
practitioner guidance recommends never gating on a single confidence score,
but combining it with rule-based validators and historical accuracy [Dev26].

The few academic treatments are suggestive. Work on subverting LLM-driven IT
operations through telemetry manipulation demonstrates that agents can be
induced to mishandle incidents by poisoning their inputs [Oops25], which
matters directly for any system whose confidence derives from observed
system state. Research on oversight capacity finds that realized safety is
maximised at an escalation rate below full escalation — escalating everything
is strictly worse than a calibrated policy — implying that the escalation
threshold is a genuine optimisation problem rather than a matter of caution
[Cap26]. And measurement infrastructure remains weak: widely deployed tools
such as K8sGPT [K8sGPT] and HolmesGPT [Holmes] report accuracy
observationally, without controlled comparison against an agent-disabled
baseline [Meas26]. Notably, both tools stop at explanation and suggestion
rather than execution, which is itself evidence of where practitioner
confidence currently ends.

## 2.6 Structured comparison

The following table compares the reviewed systems across the incident
lifecycle and along two evaluation dimensions. Cells marked *partial*
indicate the capability is present but not systematically evaluated.

| Work | Detect | Localise | RCA | Mitigate | Safety evaluated | Controlled baseline | Public artifact |
|---|---|---|---|---|---|---|---|
| K8sGPT | yes | yes | yes | no | no | no | yes |
| HolmesGPT | yes | yes | yes | suggests only | no | no | yes |
| RCAgent [Wang24] | — | yes | yes | no | no | partial | no |
| SynergyRCA [Xiang25] | yes | yes | yes | no | no | partial | no |
| MetaKube [Meta26] | yes | yes | yes | partial | no | yes | partial |
| AIOpsLab [Chen25] | yes | yes | yes | partial | no | yes | yes |
| ITBench [Jha25] | yes | yes | yes | partial | no | yes | yes |
| STRATUS [Stratus25] | yes | yes | yes | yes | partial (TNR) | partial | partial |
| **This project** | — | yes | yes | yes | **yes** | yes | yes |

Read column-wise, the pattern is unambiguous. Detection, localisation and
root cause analysis are near-universally addressed. Mitigation is addressed
by a recent minority. The *safety evaluated* column — whether the work
measures the cost of incorrect or disproportionate action, rather than only
the rate of successful action — is empty.

This is the demonstrated form of a claim frequently made in passing: the
field has established that agents can understand faults, and has begun to
establish that they can fix them, but has not established when they should be
permitted to try.

## 2.7 Synthesis and positioning

Three findings emerge from this review.

Diagnosis is a solved-enough problem that further work on it yields
diminishing returns, and remediation capability is being actively benchmarked
by well-resourced groups. This project therefore does not attempt to advance
either.

Confidence-gated escalation is the dominant mechanism for governing
autonomous action in deployed systems, yet the confidence signal it depends on
is known to be miscalibrated in general and has not been evaluated in
operational incident response. No evidence exists as to which estimator best
supports that thresholding decision in an operational setting.

Success in remediation is currently measured as resolution, which conflates
proportionate repair with disproportionate repair, and conflates appropriate
escalation with failure.

Accordingly, this project treats the confidence estimator as an experimental
variable rather than a fixed component, comparing self-reported confidence
against sampling-based agreement and against evidence grounded in observed
cluster state, and measuring the calibration of each. It formalises the
escalation decision as a policy over declared action risk tiers and blast
radius bounds, so that "tightening the policy" denotes a measurable change
rather than a disposition. And it decomposes outcome along two independent
axes — whether the incident was resolved, and whether the action taken was
proportionate — so that resolution by destructive means is recorded
distinctly from clean resolution and from benign escalation.

The contribution is not a more capable agent. It is a controlled measurement
of where the boundary between autonomous action and human escalation should
be drawn, and of whether the signal used to draw it can bear the weight.
