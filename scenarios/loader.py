"""
Scenario loading and validation.

Every scenario is validated against the schema *and* cross-checked against the
action catalogue before any experiment runs. A malformed scenario discovered
mid-experiment would invalidate a run, so validation is a precondition of the
harness rather than an optional check.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.actions import CATALOGUE, RiskTier, spec_for  # noqa: E402
from scenarios.schema import FaultClass, Scenario  # noqa: E402

DEFINITIONS_DIR = Path(__file__).parent / "definitions"


def load_all(directory: Path = DEFINITIONS_DIR) -> list[Scenario]:
    """Load and schema-validate every scenario definition."""
    scenarios: list[Scenario] = []
    for path in sorted(directory.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text())
        try:
            scenarios.append(Scenario.model_validate(raw))
        except Exception as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
    return scenarios


def cross_check(scenarios: list[Scenario]) -> list[str]:
    """Checks that cannot be expressed in the schema alone."""
    problems: list[str] = []
    seen_ids: set[str] = set()

    for s in scenarios:
        if s.id in seen_ids:
            problems.append(f"{s.id}: duplicate scenario id")
        seen_ids.add(s.id)

        # The reference fix must be an action the agent can actually propose.
        if spec_for(s.reference_fix.action) is None:
            problems.append(
                f"{s.id}: reference fix '{s.reference_fix.action}' is not in the action catalogue"
            )

        # A reference fix should never itself be destructive: the minimal
        # correct remediation is the yardstick for proportionality, so a
        # destructive yardstick would make harmful successes unscoreable.
        spec = spec_for(s.reference_fix.action)
        if spec and spec.tier == RiskTier.R3_DESTRUCTIVE:
            problems.append(
                f"{s.id}: reference fix is destructive (R3); the minimal fix should be R1 or R2"
            )

        # Read-only actions cannot be a remediation.
        if spec and spec.tier == RiskTier.R0_READ_ONLY:
            problems.append(f"{s.id}: reference fix is a read-only action")

        # The id prefix must agree with the declared fault class.
        prefix = s.id.split("-")[0]
        expected = {
            "RES": FaultClass.RESOURCE_EXHAUSTION,
            "CFG": FaultClass.CONFIGURATION_DRIFT,
            "DEP": FaultClass.DEPENDENCY_FAILURE,
            "APP": FaultClass.APPLICATION_SATURATION,
        }[prefix]
        if s.fault_class != expected:
            problems.append(f"{s.id}: prefix implies {expected.value}, declared {s.fault_class.value}")

        # Injections must be reversible, or the harness cannot reset between runs.
        if s.teardown is None:
            problems.append(f"{s.id}: no teardown defined; runs would not be independent")

        # Distractors are what let the analysis report *how* the agent erred.
        if not s.known_distractors:
            problems.append(f"{s.id}: no known distractors recorded")

    return problems


def summarise(scenarios: list[Scenario]) -> None:
    by_class: dict[str, int] = {}
    for s in scenarios:
        by_class[s.fault_class.value] = by_class.get(s.fault_class.value, 0) + 1

    print(f"{'ID':8} {'fault class':24} {'root cause':30} {'fix':24} {'tier':6}")
    print("-" * 96)
    for s in scenarios:
        spec = spec_for(s.reference_fix.action)
        tier = spec.tier.name.split("_")[0] if spec else "?"
        print(f"{s.id:8} {s.fault_class.value:24} {s.root_cause_class.value:30} "
              f"{s.reference_fix.action:24} {tier:6}")

    print(f"\nTotal: {len(scenarios)} scenarios")
    for cls, n in sorted(by_class.items()):
        print(f"  {cls:26} {n}")
    print(f"Distinct root-cause classes: {len({s.root_cause_class for s in scenarios})}")
    print(f"Actions referenced: {sorted({s.reference_fix.action for s in scenarios})}")
    print(f"Catalogue size: {len(CATALOGUE)} actions")


if __name__ == "__main__":
    scenarios = load_all()
    problems = cross_check(scenarios)
    summarise(scenarios)
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("\nAll scenarios valid.")
