# Abstract

Deployed systems that let language-model agents act on live infrastructure
almost universally gate that action on the agent's confidence: act above a
threshold, escalate below it. The confidence signal on which this depends is
known to be poorly calibrated in general and has not been evaluated in
operational incident response, and no empirical evidence exists as to which
estimator best serves that thresholding task.

This dissertation measures where that boundary should fall. It contributes a
validated benchmark of eleven reproducible Kubernetes fault scenarios spanning
resource exhaustion, configuration drift, dependency failure and application
saturation; a formally specified safety gate that decides between executing,
escalating and denying a proposed remediation on the basis of declared action
risk, computed blast radius and confidence; and three confidence estimators,
including one grounded in observable cluster state rather than model
self-report. Outcomes are classified along two independent axes — whether the
incident resolved, and whether the action taken was proportionate — so that
resolution by destructive means is recorded distinctly from clean resolution
and from appropriate escalation.

Ninety-nine runs were collected across three policy conditions on a live
multi-node cluster. Diagnostic accuracy was found to have a boundary rather
than a gradient: 98% where the cause is stated in declarative cluster state,
24% where it must be inferred across services. Calibration and discrimination
came apart, with the evidence-grounded estimator better calibrated but the
model's own stated confidence ranking correct diagnoses substantially better
(AUROC 0.876 against 0.736) — and ranking is the property a threshold
requires. No threshold achieved both substantial automation and a low error
rate; the most favourable operating point automated 48% of eligible incidents
at a 35% error rate. A destructive action was proposed once in ninety-nine
runs, and under the one policy that forbade it, indicating that categorical
tier restriction functions as insurance against a rare event rather than as a
constant restraint.

Two contamination modes were found during collection and are reported as
findings: the fault-injection framework leaked ground truth into
agent-visible telemetry, and five of twelve resolution checks could not detect
their own fault. Both produced results that were wrong but entirely plausible,
and neither was visible in summary statistics.
