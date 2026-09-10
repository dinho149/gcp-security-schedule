#!/usr/bin/env python3
"""Simulate N days of digests with NO new material added.

This is the direct answer to "would I get repeated data?". It drives selection
forward day by day, feeding each day's picks back into an in-memory ledger, and
reports whether anything repeats and when the material runs out.

    .venv/bin/python scripts/simulate_days.py [days]
"""
from __future__ import annotations

import datetime
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from select_topics import select  # noqa: E402


def main(argv: list[str]) -> int:
    days = int(argv[0]) if argv else 12
    start = datetime.date(2026, 9, 12)
    ledger = {"sections": {}, "questions": {}}

    seen: Counter[tuple[str, str]] = Counter()
    repeats: list[tuple[str, tuple]] = []
    exhausted_on = None

    print(f"simulating {days} days with no new material\n")
    for i in range(days):
        date = (start + datetime.timedelta(days=i)).isoformat()
        r = select(today=date, ledger=ledger)

        if not r["topics"]:
            exhausted_on = date
            print(f"{date}  phase E — EXHAUSTED  ({r['remaining_angles']} angles left)")
            print(f"            reason: {r.get('reason')}")
            break

        labels = []
        for t in r["topics"]:
            pair = (t["key"], t["angle"])
            if seen[pair]:
                repeats.append((date, pair))
            seen[pair] += 1
            labels.append(f"§{t['blueprint']}/{t['angle'][:4]}")

            entry = ledger["sections"].setdefault(t["key"], {
                "angles_used": [], "taught": [], "blueprint": [t["blueprint"]]})
            entry["angles_used"].append(t["angle"])
            entry["taught"].append({"date": date, "angle": t["angle"]})
            entry["last_taught"] = date

        phases = "".join(sorted({t["phase"] for t in r["topics"]}))
        print(f"{date}  phase {phases}  {' '.join(labels):<44} "
              f"remaining={r['remaining_angles']}")

    print()
    print(f"distinct (section, angle) pairs taught : {len(seen)}")
    print(f"repeated pairs                         : {len(repeats)}"
          f"{'  <-- BUG' if repeats else '  ✓ none'}")
    for date, pair in repeats[:5]:
        print(f"    {date}  {pair}")

    first_two = [p for p, c in seen.items()][:8]
    saif = sum(1 for k, _ in first_two if "SAIF" in k or "Secure AI" in k)
    print(f"SAIF sections in the first two days     : {saif}/8"
          f"{'  ✓ not dominating' if saif <= 2 else '  <-- dominating'}")
    print(f"exhausted on                            : {exhausted_on or 'not within window'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
