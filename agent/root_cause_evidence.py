"""
Evidence predicates keyed by root-cause class.

These support the E3 (evidence-grounded) confidence estimator. Given the root
cause the agent *claims*, E3 checks whether the observable signals associated
with that claim actually hold against live cluster state.

Critically, these predicates are keyed by claimed root cause, NOT taken from
the running scenario's definition. Using the scenario's own predicates would
leak ground truth into the confidence signal: an agent's confidence would rise
merely because it happened to be correct, which is circular. Here, an agent
that claims `oom_kill` is scored on whether OOM evidence is present -- whether
or not OOM is the true cause. A confident wrong answer therefore scores low,
which is the entire point.

Each predicate is (description, source, expression, threshold, comparison,
weight). Expressions take {ns} and {wl} placeholders.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidencePredicate:
    description: str
    source: str          # "k8s_field" | "promql" | "http_probe"
    expr: str
    threshold: float | None
    comparison: str      # "gt" | "lt" | "contains"
    weight: float


P = EvidencePredicate

EVIDENCE: dict[str, list[EvidencePredicate]] = {

    "oom_kill": [
        P("Container last terminated with OOMKilled", "k8s_field",
          "last_termination_contains:OOMKilled", None, "contains", 1.0),
        P("Container restarts climbing", "promql",
          'increase(kube_pod_container_status_restarts_total{{namespace="{ns}"}}[5m])',
          1, "gt", 0.8),
        P("Memory working set near configured limit", "promql",
          'max(container_memory_working_set_bytes{{namespace="{ns}",pod=~"{wl}.*"}}) '
          '/ max(kube_pod_container_resource_limits{{namespace="{ns}",pod=~"{wl}.*",resource="memory"}})',
          0.85, "gt", 0.7),
    ],

    "resource_limit_misconfig": [
        P("Container last terminated with OOMKilled", "k8s_field",
          "last_termination_contains:OOMKilled", None, "contains", 0.9),
        P("Memory working set near configured limit", "promql",
          'max(container_memory_working_set_bytes{{namespace="{ns}",pod=~"{wl}.*"}}) '
          '/ max(kube_pod_container_resource_limits{{namespace="{ns}",pod=~"{wl}.*",resource="memory"}})',
          0.85, "gt", 1.0),
        P("Container restarts climbing", "promql",
          'increase(kube_pod_container_status_restarts_total{{namespace="{ns}"}}[5m])',
          1, "gt", 0.6),
    ],

    "cpu_throttling": [
        P("High proportion of CFS throttled periods", "promql",
          'rate(container_cpu_cfs_throttled_periods_total{{namespace="{ns}",pod=~"{wl}.*"}}[5m]) '
          '/ rate(container_cpu_cfs_periods_total{{namespace="{ns}",pod=~"{wl}.*"}}[5m])',
          0.20, "gt", 1.0),
        P("No container restarts (distinguishes throttling from OOM)", "promql",
          'increase(kube_pod_container_status_restarts_total{{namespace="{ns}",pod=~"{wl}.*"}}[10m])',
          1, "lt", 0.6),
    ],

    "memory_pressure": [
        P("A node reports MemoryPressure", "promql",
          'max(kube_node_status_condition{{condition="MemoryPressure",status="true"}})',
          0, "gt", 1.0),
        P("Pod evictions occurring", "promql",
          'increase(kube_pod_status_reason{{reason="Evicted"}}[10m])', 0, "gt", 0.9),
        P("Node memory nearly consumed", "promql",
          '1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)', 0.85, "gt", 0.6),
    ],

    "disk_pressure": [
        P("A node reports DiskPressure", "promql",
          'max(kube_node_status_condition{{condition="DiskPressure",status="true"}})',
          0, "gt", 1.0),
        P("Pod evictions occurring", "promql",
          'increase(kube_pod_status_reason{{reason="Evicted"}}[10m])', 0, "gt", 0.7),
    ],

    "bad_image_tag": [
        P("Pods waiting on image pull", "k8s_field",
          "waiting_reason_contains:ImagePull", None, "contains", 1.0),
        P("Deployment has unavailable replicas", "promql",
          'kube_deployment_status_replicas_unavailable{{namespace="{ns}",deployment="{wl}"}}',
          0, "gt", 0.8),
        P("Image pull failures in events", "log_match",
          "Failed to pull image|ErrImagePull|ImagePullBackOff", None, "contains", 0.9),
    ],

    "misconfigured_env": [
        P("Deployment has unavailable or not-ready replicas", "promql",
          'kube_deployment_status_replicas_unavailable{{namespace="{ns}",deployment="{wl}"}}',
          0, "gt", 0.7),
        P("Configuration or resolution errors in logs", "log_match",
          "no such host|name resolution|connection refused|probe failed|invalid", None, "contains", 1.0),
        P("Container is not restarting (process itself healthy)", "promql",
          'increase(kube_pod_container_status_restarts_total{{namespace="{ns}",pod=~"{wl}.*"}}[10m])',
          2, "lt", 0.5),
    ],

    "downstream_timeout": [
        P("Frontend p99 latency elevated", "http_probe", "p99_latency_ms", 1500, "gt", 1.0),
        P("Timeout or deadline errors in logs", "log_match",
          "DeadlineExceeded|context deadline exceeded|timeout|Unavailable", None, "contains", 0.9),
        P("Target workload not restarting", "promql",
          'increase(kube_pod_container_status_restarts_total{{namespace="{ns}",pod=~"{wl}.*"}}[10m])',
          1, "lt", 0.5),
    ],

    "network_partition": [
        P("Connection failures in logs", "log_match",
          "connection refused|i/o timeout|Unavailable|transport is closing|no route", None, "contains", 1.0),
        P("Elevated frontend error rate", "http_probe", "error_rate", 0.02, "gt", 0.8),
        P("Both endpoints report replicas available", "promql",
          'min(kube_deployment_status_replicas_available{{namespace="{ns}"}})', 0, "gt", 0.6),
    ],

    "dns_failure": [
        P("Name resolution errors in logs", "log_match",
          "no such host|SERVFAIL|name resolution|lookup ", None, "contains", 1.0),
        P("Dependency itself reports available replicas", "promql",
          'min(kube_deployment_status_replicas_available{{namespace="{ns}"}})', 0, "gt", 0.7),
    ],

    "connection_pool_exhaustion": [
        P("Frontend p99 latency elevated", "http_probe", "p99_latency_ms", 1200, "gt", 1.0),
        P("CPU utilisation low despite latency", "promql",
          'max(rate(container_cpu_usage_seconds_total{{namespace="{ns}",pod=~"{wl}.*"}}[5m]))',
          0.30, "lt", 0.9),
        P("Pool or connection errors in logs", "log_match",
          "pool|connection timeout|could not acquire|no available connection", None, "contains", 0.7),
    ],

    "thread_starvation": [
        P("Frontend p95 latency elevated across endpoints", "http_probe", "p95_latency_ms", 1500, "gt", 1.0),
        P("CPU utilisation low despite latency", "promql",
          'max(rate(container_cpu_usage_seconds_total{{namespace="{ns}",pod=~"{wl}.*"}}[5m]))',
          0.40, "lt", 0.9),
        P("Throughput collapsed", "http_probe", "requests_per_s", 3.0, "lt", 0.6),
    ],

    "cascading_latency": [
        P("Frontend p99 latency elevated", "http_probe", "p99_latency_ms", 1200, "gt", 1.0),
        P("No resource pressure anywhere in namespace", "promql",
          'max(rate(container_cpu_cfs_throttled_periods_total{{namespace="{ns}"}}[5m]))',
          0.05, "lt", 0.7),
        P("Multiple workloads report degraded readiness or errors", "promql",
          'count(kube_pod_status_ready{{namespace="{ns}",condition="false"}} > 0)', 0, "gt", 0.5),
    ],
}


def predicates_for(root_cause: str) -> list[EvidencePredicate]:
    return EVIDENCE.get(root_cause, [])
