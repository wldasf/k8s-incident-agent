"""
Consistency audit across the dissertation and the data it reports.

Checks three things that manual reading tends to miss:

  1. Draft artefacts -- placeholder markers, draft annotations, dates left in
     narrative text -- which indicate a chapter predates the data it cites.
  2. Numbers asserted in the prose against the numbers actually present in the
     results files.
  3. Citation keys used in the chapters against the keys defined in the
     citation tracker, in both directions.

Run from the project root:
    python3 audit.py
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

WRITING = Path("writing")
RESULTS = Path("results")

PROBLEMS: list[str] = []
NOTES: list[str] = []


def problem(s: str) -> None:
    PROBLEMS.append(s)


def note(s: str) -> None:
    NOTES.append(s)


# ---------------------------------------------------------------- 1. drafts

def check_draft_artefacts() -> None:
    print("\n=== 1. Draft artefacts ===")
    patterns = {
        "placeholder ⟨…⟩": re.compile(r"⟨"),
        "TODO/TBD/XXX": re.compile(r"\b(TODO|TBD|XXX|FIXME)\b"),
        "draft annotation": re.compile(r"^\*(Draft|Scaffolding|Outline)", re.M),
        "narrative date": re.compile(
            r"\b\d{1,2}\s+(January|February|March|April|May|June|July|August|"
            r"September|October|November|December)\s+20\d\d\b"),
    }
    clean = True
    for path in sorted(WRITING.glob("*.md")):
        text = path.read_text()
        for label, pat in patterns.items():
            hits = pat.findall(text)
            if hits:
                clean = False
                problem(f"{path.name}: {len(hits)} × {label}")
                print(f"  {path.name:28} {len(hits):>3} × {label}")
    if clean:
        print("  none found")


# ---------------------------------------------------------------- 2. figures

def load_runs() -> list[dict]:
    rows: list[dict] = []
    for p in RESULTS.glob("*.jsonl"):
        for line in p.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return [r for r in rows if r.get("status") == "ok"]


def check_figures() -> None:
    print("\n=== 2. Asserted figures against the data ===")
    runs = load_runs()
    if not runs:
        problem("no result files found under results/")
        print("  no data")
        return

    scored = [r for r in runs if not r.get("diagnosis_only")]
    n = len(runs)

    facts: dict[str, object] = {}
    facts["total runs"] = n
    facts["scored runs"] = len(scored)
    facts["diagnosis-only runs"] = n - len(scored)
    facts["strict correct"] = sum(1 for r in runs if r.get("root_cause_correct"))
    facts["lenient correct"] = sum(1 for r in runs if r.get("root_cause_accepted"))
    facts["executed actions"] = sum(1 for r in runs if r.get("gate_decision") == "EXECUTE")
    facts["resolved"] = sum(1 for r in scored if r.get("resolved"))
    facts["R3 proposals"] = sum(1 for r in runs
                                if str(r.get("action_tier", "")).startswith("R3"))
    facts["harmful successes"] = sum(1 for r in scored
                                     if r.get("outcome") == "harmful_success")
    facts["compound failures"] = sum(1 for r in scored
                                     if r.get("outcome") == "compound_failure")
    facts["protocol failures"] = sum(1 for r in runs if not r.get("completed", True))
    facts["policies"] = sorted({r.get("policy") for r in runs})
    facts["scenarios"] = len({r.get("scenario") for r in runs})

    e1 = [r["e1"] for r in runs if r.get("e1") is not None]
    e3 = [r["e3"] for r in runs if r.get("e3") is not None]
    if e1:
        facts["E1 mean"] = round(sum(e1) / len(e1), 3)
    if e3:
        facts["E3 mean"] = round(sum(e3) / len(e3), 3)

    by_class = defaultdict(lambda: [0, 0])
    for r in runs:
        c = r.get("fault_class", "?")
        by_class[c][0] += 1
        by_class[c][1] += bool(r.get("root_cause_correct"))

    for k, v in facts.items():
        print(f"  {k:24} {v}")
    print("\n  accuracy by fault class:")
    for c, (tot, cor) in sorted(by_class.items()):
        print(f"    {c:24} {cor}/{tot}")

    # Cross-check the counts most often asserted in prose.
    text = " ".join(p.read_text() for p in WRITING.glob("*.md"))

    checks = [
        (r"\b(\d+)\s+(?:completed\s+)?runs\b", "runs", n),
        (r"across\s+(\d+)\s+executed actions", "executed actions", facts["executed actions"]),
        (r"\b(\d+)\s+scenarios\b", "scenarios", facts["scenarios"]),
    ]
    print("\n  numbers asserted in prose:")
    for pat, label, actual in checks:
        found = sorted({int(m) for m in re.findall(pat, text)})
        flag = "" if actual in found or not found else "   <-- CHECK"
        print(f"    {label:20} prose says {found}, data says {actual}{flag}")
        if found and actual not in found:
            problem(f"prose cites {label} as {found}, data says {actual}")


# -------------------------------------------------------------- 3. citations

def check_citations() -> None:
    print("\n=== 3. Citation keys ===")
    tracker = WRITING / "citations_to_verify.md"
    if not tracker.exists():
        problem("citations_to_verify.md not found")
        return

    defined = set(re.findall(r"^\|\s*`([A-Za-z0-9]+)`", tracker.read_text(), re.M))

    used: Counter = Counter()
    for path in WRITING.glob("*.md"):
        if path.name == "citations_to_verify.md":
            continue
        for group in re.findall(r"\[([A-Za-z0-9, ]+?)\]", path.read_text()):
            for key in group.split(","):
                key = key.strip()
                if re.fullmatch(r"[A-Z][A-Za-z]+\d{2}", key) or key in ("K8sGPT", "Holmes"):
                    used[key] += 1

    undefined = sorted(set(used) - defined)
    unused = sorted(defined - set(used))

    print(f"  defined in tracker: {len(defined)}")
    print(f"  used in chapters:   {len(used)}")
    if undefined:
        for k in undefined:
            problem(f"citation [{k}] used but not defined in tracker")
            print(f"    UNDEFINED  [{k}]  ({used[k]}×)")
    if unused:
        for k in unused:
            note(f"citation `{k}` defined but never cited")
            print(f"    unused     `{k}`")
    if not undefined and not unused:
        print("  all keys match")


# ------------------------------------------------------------------- report

def main() -> int:
    print("Dissertation consistency audit")
    check_draft_artefacts()
    check_figures()
    check_citations()

    print("\n" + "=" * 60)
    if PROBLEMS:
        print(f"{len(PROBLEMS)} problem(s) requiring attention:\n")
        for p in PROBLEMS:
            print(f"  - {p}")
    else:
        print("No problems found.")
    if NOTES:
        print(f"\n{len(NOTES)} note(s):\n")
        for x in NOTES:
            print(f"  - {x}")
    return 1 if PROBLEMS else 0


if __name__ == "__main__":
    raise SystemExit(main())
