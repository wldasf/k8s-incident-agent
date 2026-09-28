# Scenarios

Eleven reproducible fault scenarios across four classes. Each definition pairs
a reversible fault injection with the ground truth needed to score an agent's
response: the true root cause, accepted alternative labels, the minimal correct
remediation, and a resolution check.

| ID | Fault | Target | Reference fix |
|---|---|---|---|
| CFG-01 | Invalid image reference | checkoutservice | roll back deployment |
| CFG-02 | Wrong dependency address | frontend | roll back deployment |
| CFG-03 | Broken readiness probe (stalled rollout) | shippingservice | roll back deployment |
| RES-01 | Memory limit below working set | cartservice | patch resource limits |
| RES-02 | CPU limit below demand | productcatalogservice | patch resource limits |
| DEP-01 | Slow downstream dependency | currencyservice | delete pod |
| DEP-02 | Partition to frontend | cartservice | delete pod |
| DEP-03 | Partition to backing store | cartservice | delete pod |
| APP-01 | Connection pool exhaustion | cartservice | scale workload |
| APP-02 | Thread starvation (diagnosis only) | recommendationservice | scale workload |
| APP-03 | Cascading latency | productcatalogservice | delete pod |

APP-02 is scored for diagnosis only. Its fault is real and correctly injected,
but the frontend renders without the slowed dependency, so there is no
client-visible failure for a resolution check to observe.

`excluded/` holds a twelfth scenario, node memory pressure, removed after
validation. Its stressor caused a liveness-probe timeout rather than node
pressure, duplicating CFG-03's failure mode.

Every scenario was validated before data collection: its resolution check must
pass on a healthy cluster and fail under the injected fault. Run the validation
with `python3 -m harness.validate_scenarios` on the control plane.
