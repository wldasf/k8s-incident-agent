"""
Merge and validate sharded result files.

Each shard writes its own JSONL. This merges them, checks for the gaps that
matter, and reports coverage so a missing cell is caught before analysis
rather than during it.

Usage:
    python3 harness/merge_results.py results/*.jsonl -o results/merged.jsonl
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from scenarios.loader import load_all  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out", default="results/merged.jsonl")
    args = ap.parse_args()

    records, seen = [], set()
    for path in args.files:
        for line in pathlib.Path(path).read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            # A run is identified by its experimental cell; duplicates arise
            # when a shard is re-run after a crash, and the later one wins.
            key = (r.get("scenario"), r.get("policy"), r.get("estimator"),
                   r.get("repeat"), r.get("model"))
            if key in seen:
                continue
            seen.add(key)
            records.append(r)

    out = pathlib.Path(args.out)
    out.parent.mkdir(exist_ok=True)
    with out.open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")

    print(f"merged {len(records)} unique runs -> {out}\n")

    status = Counter(r.get("status") for r in records)
    print("status:", dict(status))

    bad = [r for r in records if r.get("baseline_restored") is False]
    if bad:
        print(f"\nWARNING: {len(bad)} runs did not restore baseline. "
              "Runs after these in the same file may be contaminated:")
        for r in bad[:10]:
            print(f"  {r['scenario']} {r.get('policy')} rep{r.get('repeat')}")

    ok = [r for r in records if r.get("status") == "ok"]
    print(f"\nusable runs: {len(ok)}")

    cells = defaultdict(int)
    for r in ok:
        cells[(r["scenario"], r["policy"], r["estimator"])] += 1
    all_ids = [s.id for s in load_all()]
    missing = [(s, p, e) for s in all_ids
               for p in {r["policy"] for r in ok}
               for e in {r["estimator"] for r in ok}
               if (s, p, e) not in cells]
    if missing:
        print(f"\nmissing cells ({len(missing)}):")
        for m in missing[:20]:
            print("  ", " / ".join(m))
    else:
        print("all experimental cells populated")

    outcomes = Counter(r.get("outcome") for r in ok)
    print("\noutcomes:", dict(outcomes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
