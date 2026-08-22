"""
Scenario sharding.

Scenarios cannot be parallelised within a single cluster: node-stress and
network-partition faults affect the whole cluster, and the baseline health
check is namespace-wide, so a concurrent run would see another run's damage
as its own. Independent clusters remove that coupling entirely.

Shards are assigned so that each cluster receives a mix of fault classes
rather than a contiguous block. If one shard is lost, the remaining data
still spans all four classes rather than losing a class outright.
"""

from __future__ import annotations

SHARDS: dict[str, list[str]] = {
    "shard1": ["RES-01", "CFG-01", "DEP-01"],
    "shard2": ["RES-02", "CFG-02", "DEP-02"],
    "shard3": ["RES-03", "CFG-03", "DEP-03"],
    "shard4": ["APP-01", "APP-02", "APP-03"],
}


def scenarios_for(shard: str) -> list[str]:
    if shard not in SHARDS:
        raise ValueError(f"unknown shard '{shard}'; valid: {', '.join(SHARDS)}")
    return SHARDS[shard]


def shard_of(scenario_id: str) -> str | None:
    for name, ids in SHARDS.items():
        if scenario_id in ids:
            return name
    return None
