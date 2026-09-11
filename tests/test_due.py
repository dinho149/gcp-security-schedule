#!/usr/bin/env python3
"""Tests for the readiness cadence: weekly, daily past a threshold, hysteresis.

The hysteresis band is the reason this logic is a function rather than a
sentence in a skill file. A score oscillating around the line would otherwise
flip the cadence every day, which reads as instability in the score rather than
in the rule.

    .venv/bin/python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import due  # noqa: E402
import yaml  # noqa: E402

SCHEDULE = {
    "days": ["mon", "tue", "wed", "thu", "fri"],
    "grace_minutes": 60,
    "readiness": {"at": "21:15", "days": ["fri"], "daily_from": 85,
                  "daily_hysteresis": 5},
}
FRI, THU = "2026-09-11", "2026-09-10"


def ask(date=FRI, now="21:20", posted=False, score=None, was_daily=False,
        schedule=None):
    return due.readiness_due(date, now, schedule or SCHEDULE, posted, score, was_daily)


class TestWeekly(unittest.TestCase):
    def test_due_on_the_readiness_day_inside_the_window(self):
        ok, why = ask()
        self.assertTrue(ok)
        self.assertIn("weekly", why)

    def test_not_due_before_the_time(self):
        self.assertFalse(ask(now="20:00")[0])

    def test_not_due_on_a_non_readiness_weekday(self):
        ok, why = ask(date=THU)
        self.assertFalse(ok)
        self.assertIn("not a readiness day", why)

    def test_not_due_on_a_non_run_day(self):
        ok, why = ask(date="2026-09-12")   # Saturday
        self.assertFalse(ok)
        self.assertIn("not a run day", why)


class TestIdempotency(unittest.TestCase):
    def test_already_posted_today_beats_everything(self):
        ok, why = ask(posted=True, score=0.99)
        self.assertFalse(ok)
        self.assertIn("already posted", why)


class TestMissedWindow(unittest.TestCase):
    def test_a_missed_window_still_fires_late(self):
        """A late report beats no report, exactly as a late digest does."""
        ok, why = ask(now="23:59")
        self.assertTrue(ok)
        self.assertIn("late", why)


class TestDailySwitch(unittest.TestCase):
    def test_below_the_threshold_stays_weekly(self):
        self.assertFalse(ask(date=THU, score=0.80)[0])

    def test_at_the_threshold_switches_to_daily(self):
        ok, why = ask(date=THU, score=0.85)
        self.assertTrue(ok)
        self.assertIn("daily", why)

    def test_daily_runs_on_any_run_day_not_just_the_readiness_day(self):
        for day in ("2026-09-07", "2026-09-08", "2026-09-09", THU):
            self.assertTrue(ask(date=day, score=0.90)[0], day)

    def test_daily_still_respects_the_time(self):
        self.assertFalse(ask(date=THU, score=0.90, now="09:00")[0])


class TestHysteresis(unittest.TestCase):
    """The test that justifies this file existing."""

    def test_inside_the_band_stays_daily(self):
        ok, why = ask(date=THU, score=0.82, was_daily=True)   # 85 - 3
        self.assertTrue(ok)
        self.assertIn("daily", why)

    def test_below_the_band_reverts_to_weekly(self):
        ok, why = ask(date=THU, score=0.79, was_daily=True)   # 85 - 6
        self.assertFalse(ok)
        self.assertIn("not a readiness day", why)

    def test_the_band_does_not_let_a_weekly_report_creep_into_daily(self):
        """Hysteresis holds a cadence, it must never start one."""
        self.assertFalse(ask(date=THU, score=0.82, was_daily=False)[0])


class TestConfig(unittest.TestCase):
    def test_a_missing_readiness_block_never_fires(self):
        ok, why = ask(schedule={"days": ["fri"], "grace_minutes": 60})
        self.assertFalse(ok)
        self.assertIn("no readiness block", why)

    def test_the_real_schedule_is_wired_up(self):
        sch = yaml.safe_load((ROOT / "config/schedule.yaml").read_text())
        self.assertIn("readiness", sch)
        self.assertTrue(ask(schedule=sch)[0])


if __name__ == "__main__":
    unittest.main()
