"""
Scenario schema.

A scenario is the unit of evaluation. Each one couples a reproducible fault
injection to the ground truth needed to score an agent's response: what
actually went wrong, what the minimal correct remediation is, how to tell
whether the incident is resolved, and which observable predicates corroborate
the true root cause.

The predicates serve double duty. They are the ground truth for scoring
diagnostic accuracy, and they are the evidence base for the E3 confidence
estimator, which scores a candidate diagnosis by the weighted fraction of its
predicates that hold against live cluster state.

Fault classes are grounded in published empirical studies of microservice
failure rather than assembled ad hoc. Each scenario records the literature
that establishes its fault as a recognised class, so the benchmark's coverage
is defensible against the published record rather than asserted.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FaultClass(str, Enum):
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CONFIGURATION_DRIFT = "configuration_drift"
    DEPENDENCY_FAILURE = "dependency_failure"
    APPLICATION_SATURATION = "application_saturation"


class RootCauseClass(str, Enum):
    """Canonical root-cause labels. The agent's free-text diagnosis is mapped
    onto this closed set before scoring, so that accuracy is measured against
    a fixed vocabulary rather than by fuzzy string comparison."""

    OOM_KILL = "oom_kill"
    CPU_THROTTLING = "cpu_throttling"
    DISK_PRESSURE = "disk_pressure"
    MEMORY_PRESSURE = "memory_pressure"
    BAD_IMAGE_TAG = "bad_image_tag"
    MISCONFIGURED_ENV = "misconfigured_env"
    RESOURCE_LIMIT_MISCONFIG = "resource_limit_misconfig"
    DOWNSTREAM_TIMEOUT = "downstream_timeout"
    NETWORK_PARTITION = "network_partition"
    DNS_FAILURE = "dns_failure"
    CONNECTION_POOL_EXHAUSTION = "connection_pool_exhaustion"
    THREAD_STARVATION = "thread_starvation"
    CASCADING_LATENCY = "cascading_latency"


class Target(BaseModel):
    namespace: str
    workload: str
    container: str | None = None


class Injection(BaseModel):
    """How the fault is introduced.

    `chaos_mesh` applies a CRD manifest; `kubectl_patch` applies a strategic
    merge patch. Both are fully reversible via `teardown`.
    """

    method: Literal["chaos_mesh", "kubectl_patch", "kubectl_apply"]
    manifest: dict | None = None
    patch: dict | None = None
    # Seconds to wait after injection before the incident is considered live.
    settle_seconds: int = Field(default=60, ge=0, le=600)


class Predicate(BaseModel):
    """An observable check that corroborates the true root cause.

    `source` determines how it is evaluated:
      k8s_field  - JSONPath-style field on a Kubernetes object
      promql     - PromQL expression compared against `threshold`
      log_match  - regular expression matched against recent container logs
    """

    id: str
    description: str
    source: Literal["k8s_field", "promql", "log_match"]
    expr: str
    threshold: float | None = None
    comparison: Literal["gt", "lt", "eq", "contains"] = "gt"
    weight: float = Field(default=1.0, gt=0, le=1.0)


class ReferenceFix(BaseModel):
    """The minimal known-correct remediation.

    This is the yardstick for both proportionality and minimality in the
    outcome taxonomy: an agent that resolves the incident using a higher risk
    tier or a much wider blast radius than this is scored as a harmful
    success rather than a clean resolution.
    """

    action: str
    params: dict = Field(default_factory=dict)
    blast_radius: int = Field(ge=0)
    rationale: str


class ResolutionCheck(BaseModel):
    """How the harness decides the incident is over.

    The check must hold continuously for `sustain_seconds` to guard against
    transient recovery being scored as a fix.
    """

    source: Literal["promql", "http", "k8s_field"]
    expr: str
    threshold: float | None = None
    comparison: Literal["gt", "lt", "eq"] = "lt"
    sustain_seconds: int = Field(default=90, ge=30)
    timeout_seconds: int = Field(default=900, ge=60)


class Scenario(BaseModel):
    id: str = Field(pattern=r"^(RES|CFG|DEP|APP)-\d{2}$")
    name: str
    fault_class: FaultClass
    description: str
    # Citations establishing this fault as a recognised class in the
    # empirical literature. Required: a scenario without a documented basis
    # is an assertion, not a justified benchmark entry.
    literature_basis: str = Field(min_length=40)

    target: Target
    injection: Injection
    teardown: Injection | None = None

    root_cause_class: RootCauseClass
    ground_truth_explanation: str

    predicates: list[Predicate] = Field(min_length=2)
    reference_fix: ReferenceFix
    resolution_check: ResolutionCheck

    # Distractors: plausible but incorrect diagnoses this scenario is designed
    # to elicit. Recording these lets the analysis report *how* the agent was
    # wrong, not merely that it was.
    known_distractors: list[str] = Field(default_factory=list)

    @field_validator("predicates")
    @classmethod
    def weights_are_sane(cls, v: list[Predicate]) -> list[Predicate]:
        if sum(p.weight for p in v) <= 0:
            raise ValueError("predicate weights must sum to a positive value")
        return v
