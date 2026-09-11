#!/usr/bin/env python3
"""Simulate N days of digests with NO new material added.

This is the direct answer to "would I get repeated data?". It drives selection
forward day by day, feeding each day's picks back into an in-memory ledger, and
reports whether anything repeats and when the material runs out.

It also asserts the mix invariant every day. The ledger here used to hold no
questions at all, so the remediation band was permanently empty and the very
behaviour the quota exists to bound was never simulated -- a run could look
perfect while a real day with four misses shipped four remediation passes.

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
    violations: list[str] = []

    seen: Counter[tuple[str, str]] = Counter()
    repeats: list[tuple[str, tuple]] = []
    exhausted_on = None

    print(f"simulating {days} days with no new material\n")
    for i in range(days):
        date = (start + datetime.timedelta(days=i)).isoformat()
        # mastery={} keeps the simulation hermetic: without it `review` ranks
        # against whatever the real state.local/mastery.json happens to say.
        r = select(today=date, ledger=ledger, mastery={})

        mix = r.get("mix") or {}
        if mix.get("remediation", 0) > 2:
            violations.append(f"{date}: {mix['remediation']} remediation topics")
        if r["topics"] and not mix.get("new") and "new" not in r["unfilled_floors"]:
            violations.append(f"{date}: no new ground and no floor reported")

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

        # Every taught section gets a miss recorded against it, so from the next
        # day on the remediation band is over-subscribed and the cap is exercised.
        for t2 in r["topics"]:
            ledger["questions"][f"{date}-{t2['key']}"] = {
                "section": t2["key"], "blueprint": t2["blueprint"],
                "asked": [date], "outcomes": ["wrong"], "retested": False,
                "stem": "simulated", "occurrences": [], "last_miss": None,
            }

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
    print(f"mix invariant violations                : {len(violations)}"
          f"{'  <-- BUG' if violations else '  ✓ none'}")
    for v in violations[:5]:
        print(f"    {v}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
