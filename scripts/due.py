#!/usr/bin/env python3
"""Is the readiness report due on this tick?

Every other step's due-ness is prose in daily-run/SKILL.md, and that is fine —
they are a time and a day. Readiness has a state-dependent cadence with a
hysteresis band, which reads fine as a sentence and is easy to get wrong in
practice, so it lives here where it can be tested.

    .venv/bin/python scripts/due.py readiness [--date YYYY-MM-DD] [--now HH:MM]
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "state.local/history"


def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def readiness_due(date: str, now: str, schedule: dict, posted_today: bool,
                  last_score: float | None, was_daily: bool) -> tuple[bool, str]:
    """Pure: no disk, no clock. Returns (should_run, why).

    `last_score` is the covered-material score from the LAST computed report, so
    deciding whether to run is cheap and never depends on the run it is deciding
    about.
    """
    cfg = (schedule.get("readiness") or {})
    if not cfg:
        return False, "no readiness block in schedule.yaml"

    # Never twice in a day. Same guard the digest uses: the file existing.
    if posted_today:
        return False, "already posted today"

    weekday = datetime.date.fromisoformat(date).strftime("%a").lower()
    if weekday not in (schedule.get("days") or []):
        return False, f"{weekday} is not a run day"

    # Daily once the score is high enough, with a band so a score sitting on the
    # line does not flip the cadence every day.
    threshold = cfg.get("daily_from", 101)
    band = cfg.get("daily_hysteresis", 0)
    score = None if last_score is None else last_score * 100
    if score is not None and (score >= threshold or (was_daily and score >= threshold - band)):
        cadence = "daily"
    else:
        cadence = "weekly"

    if cadence == "weekly" and weekday not in (cfg.get("days") or []):
        return False, f"weekly cadence; {weekday} is not a readiness day"

    at = minutes(cfg.get("at", "21:15"))
    grace = schedule.get("grace_minutes", 60)
    then = minutes(now)
    if then < at:
        return False, f"not due until {cfg.get('at')} ({cadence})"
    if then >= at + grace:
        # A missed window still fires: a late report beats no report, exactly as
        # a late digest does.
        return True, f"window missed by {then - at - grace}min — running late ({cadence})"
    return True, f"due ({cadence})"


def last_report() -> tuple[bool, float | None, bool]:
    """(posted today, last covered score, was the last run daily)."""
    today = datetime.date.today().isoformat()
    posted = (HISTORY / today / "readiness.json").exists()
    files = sorted(HISTORY.glob("*/readiness.json")) if HISTORY.exists() else []
    if not files:
        return posted, None, False
    rec = json.loads(files[-1].read_text())
    return posted, (rec.get("source") or {}).get("on_covered"), \
        rec.get("cadence") == "daily"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("step", choices=["readiness"])
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--now", default=datetime.datetime.now().strftime("%H:%M"))
    args = ap.parse_args(argv)

    schedule = yaml.safe_load((ROOT / "config/schedule.yaml").read_text()) or {}
    posted, score, was_daily = last_report()
    ok, why = readiness_due(args.date, args.now, schedule, posted, score, was_daily)
    print(f"{'DUE' if ok else 'skip'}: {why}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
