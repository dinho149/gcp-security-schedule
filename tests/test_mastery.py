#!/usr/bin/env python3
"""Tests for the mastery replay: credit, and the spaced-repetition ladder.

Hermetic — history is written into a temp directory, so nothing reads the
gitignored state.local/ and these run in CI. An earlier test file in this repo
read real data and silently never ran; that mistake is not repeated here.

    .venv/bin/python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_mastery  # noqa: E402

PAGE = "Module 3: Virtual Machines and Networks in the Cloud"
HEAD = "01 — Virtual private cloud networking"
KEY = f"{PAGE}::{HEAD}"
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri"]


class MasteryCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.history = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def quiz_day(self, date, outcomes, heading=HEAD, blueprint="2.2", suffix=""):
        """outcomes: list of (outcome, hint_used)."""
        day = self.history / date
        day.mkdir(parents=True, exist_ok=True)
        qs, gs = [], []
        for i, (outcome, hinted) in enumerate(outcomes, 1):
            qs.append({"n": i, "blueprint": blueprint, "stem": f"Q{i} on {date}?",
                       "options": ["a", "b", "c", "d"],
                       "source": {"page": PAGE, "heading": heading,
                                  "notion_url": "https://app.notion.com/p/x"}})
            gs.append({"n": i, "outcome": outcome, "hint_used": hinted})
        (day / f"quiz{suffix}.json").write_text(json.dumps({"questions": qs}))
        (day / f"results{suffix}.json").write_text(json.dumps({"questions": gs}))

    def build(self, **kw):
        return build_mastery.build(history=self.history, study_days=WEEKDAYS, **kw)

    def sec(self, key=KEY, **kw):
        return self.build(**kw)["sections"][key]


class TestCredit(MasteryCase):
    def test_clean_correct_is_full_credit(self):
        self.quiz_day("2026-09-14", [("correct", False)])
        s = self.sec()
        self.assertEqual((s["attempts"], s["credit"], s["correct"]), (1, 1.0, 1))

    def test_hinted_correct_is_half_credit(self):
        """grade-quiz's own rule: correct-but-hinted is not known."""
        self.quiz_day("2026-09-14", [("correct", True)])
        s = self.sec()
        self.assertEqual((s["attempts"], s["credit"], s["hint_used"]), (1, 0.5, 1))

    def test_wrong_is_zero_credit_but_still_an_attempt(self):
        self.quiz_day("2026-09-14", [("wrong", False)])
        s = self.sec()
        self.assertEqual((s["attempts"], s["credit"], s["wrong"]), (1, 0.0, 1))

    def test_skipped_changes_absolutely_nothing(self):
        """A skip is an absence of evidence. It must not move a score OR a
        schedule — the second half is the one easy to get wrong."""
        self.quiz_day("2026-09-14", [("skipped", False)])
        s = self.sec()
        self.assertEqual(s["attempts"], 0)
        self.assertEqual(s["credit"], 0.0)
        self.assertIsNone(s["last_seen"])
        self.assertIsNone(s["next_due"])
        self.assertEqual(s["skipped"], 1)
        self.assertEqual(s["reps"], 0)

    def test_skipped_question_is_requeued(self):
        self.quiz_day("2026-09-14", [("skipped", False)])
        self.assertEqual(len(self.build()["requeue"]), 1)

    def test_a_fully_skipped_quiz_is_not_a_graded_day(self):
        self.quiz_day("2026-09-14", [("skipped", False), ("skipped", False)])
        self.assertEqual(self.build()["graded_days"], [])

    def test_section_and_subsection_are_projections_not_sums(self):
        self.quiz_day("2026-09-14", [("correct", False), ("wrong", False)])
        m = self.build()
        self.assertEqual(m["sections"][KEY]["attempts"], 2)
        self.assertEqual(m["subsections"]["2.2"]["attempts"], 2)
        self.assertEqual(m["subsections"]["2.2"]["credit"], 1.0)


class TestDayCredit(MasteryCase):
    def test_all_correct_is_one(self):
        self.assertEqual(build_mastery.day_credit([1.0, 1.0]), 1.0)

    def test_below_half_is_zero(self):
        self.assertEqual(build_mastery.day_credit([0.0, 0.0, 1.0]), 0.0)

    def test_exactly_half_rounds_up_to_partial(self):
        self.assertEqual(build_mastery.day_credit([0.0, 1.0]), 0.5)

    def test_a_single_hinted_answer_is_partial(self):
        self.assertEqual(build_mastery.day_credit([0.5]), 0.5)

    def test_one_rating_per_section_per_day_not_per_question(self):
        """Three questions on one section in one quiz must advance the ladder
        once, not cube the interval."""
        self.quiz_day("2026-09-14", [("correct", False)] * 3)
        self.assertEqual(self.sec()["reps"], 1)


class TestLadder(MasteryCase):
    def test_clean_run_gives_1_3_then_ease_scaled(self):
        for d in ("2026-09-14", "2026-09-15", "2026-09-16"):
            self.quiz_day(d, [("correct", False)])
        s = self.sec()
        self.assertEqual(s["reps"], 3)
        # ease climbs 2.3 -> 2.4 -> 2.5 -> 2.6; third interval = round(3 * 2.6)
        self.assertEqual([e["interval_after"] for e in s["exposures"]], [1, 3, 8])

    def test_wrong_resets_the_interval_and_counts_a_lapse(self):
        self.quiz_day("2026-09-14", [("correct", False)])
        self.quiz_day("2026-09-15", [("correct", False)])
        self.quiz_day("2026-09-16", [("wrong", False)])
        s = self.sec()
        self.assertEqual((s["reps"], s["interval_days"], s["lapses"]), (0, 1, 1))

    def test_hinted_correct_does_not_promote(self):
        self.quiz_day("2026-09-14", [("correct", False)])
        self.quiz_day("2026-09-15", [("correct", True)])
        s = self.sec()
        self.assertEqual(s["reps"], 1)          # unchanged by the hinted day
        self.assertEqual(s["lapses"], 0)        # but not a lapse either

    def test_ease_is_clamped_at_both_ends(self):
        for i in range(12):
            self.quiz_day(f"2026-09-{14 + i:02d}", [("wrong", False)])
        self.assertEqual(self.sec()["ease"], build_mastery.EASE_MIN)

    def test_interval_never_exceeds_the_cap(self):
        for i in range(20):
            self.quiz_day(f"2026-10-{1 + i:02d}", [("correct", False)])
        self.assertLessEqual(self.sec()["interval_days"], build_mastery.MAX_INTERVAL)


class TestDueDates(MasteryCase):
    def test_next_due_never_lands_on_a_weekend(self):
        """Without the snap an interval landing on Saturday is permanently
        stale and review_due never fires for it."""
        for i in range(14):
            self.quiz_day(f"2026-09-{14 + i:02d}", [("correct", False)])
        for e in self.sec()["exposures"]:
            import datetime
            day = datetime.date.fromisoformat(e["next_due"]).strftime("%a").lower()
            self.assertIn(day, WEEKDAYS, f"{e['next_due']} is a {day}")

    def test_due_sections_reports_what_has_come_due(self):
        self.quiz_day("2026-09-14", [("correct", False)])   # Mon -> due Tue
        m = self.build()
        self.assertEqual(build_mastery.due_sections(m, "2026-09-15"), [KEY])
        self.assertEqual(build_mastery.due_sections(m, "2026-09-14"), [])

    def test_a_never_quizzed_section_is_undue_not_due(self):
        """Undue and unproven are different states; a null next_due must not
        read as 'come due'."""
        self.quiz_day("2026-09-14", [("skipped", False)])
        self.assertEqual(build_mastery.due_sections(self.build(), "2030-01-01"), [])


class TestReplay(MasteryCase):
    def test_rebuild_is_byte_identical(self):
        self.quiz_day("2026-09-14", [("correct", False), ("wrong", False)])
        self.quiz_day("2026-09-15", [("correct", True)])
        dump = lambda m: json.dumps(m, indent=2, sort_keys=True, ensure_ascii=False)
        self.assertEqual(dump(self.build()), dump(self.build()))

    def test_through_truncates_the_replay(self):
        self.quiz_day("2026-09-14", [("correct", False)])
        self.quiz_day("2026-09-15", [("correct", False)])
        self.assertEqual(self.sec(through="2026-09-14")["attempts"], 1)
        self.assertEqual(self.sec()["attempts"], 2)

    def test_no_history_yields_empty_not_a_crash(self):
        m = self.build()
        self.assertEqual((m["sections"], m["subsections"], m["graded_days"]), ({}, {}, []))

    def test_an_ungraded_quiz_contributes_nothing(self):
        day = self.history / "2026-09-14"
        day.mkdir(parents=True)
        (day / "quiz.json").write_text(json.dumps({"questions": [{"n": 1}]}))
        self.assertEqual(self.build()["sections"], {})

    def test_on_demand_sets_are_replayed(self):
        """schedule.yaml says on-demand practice counts toward mastery."""
        self.quiz_day("2026-09-14", [("correct", False)])
        self.quiz_day("2026-09-14", [("wrong", False)], suffix="-1400")
        self.assertEqual(self.sec()["attempts"], 2)


if __name__ == "__main__":
    unittest.main()
