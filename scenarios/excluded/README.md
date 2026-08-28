# Excluded scenarios

Retained for the record. Each was excluded for a measured reason, documented
in the file's own comments and in the decisions log.

**RES-03 — node memory pressure.** Excluded after validation. StressChaos with
`mode: one` runs the stressor inside a single pod's cgroup, so the node never
reports MemoryPressure. The observed failure was different from the intended
one: CPU contention from the stressor made the target slow enough to fail its
own liveness probe (exit 137, "Liveness probe failed: timeout within 5s"),
producing a crash loop rather than node-level pressure. That failure mode
duplicates CFG-03, and the crash-looping pod blocked the baseline check of
subsequent runs — four aborted runs in one batch traced to it.

The original DNS-based DEP-03 was replaced rather than excluded; see
`definitions/DEP-03.yaml` for the rationale.
