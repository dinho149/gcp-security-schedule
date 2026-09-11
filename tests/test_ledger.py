#!/usr/bin/env python3
"""Tests for what the ledger believes was taught and asked.

Every case here is a regression. Each one is a bug that shipped, went unnoticed
because the ledger looked plausible, and would have fed a wrong number straight
into the readiness report -- which is what made them visible at all.

Hermetic: HISTORY is redirected to a temp directory, so nothing reads the
gitignored state.local/ and these run in CI like any other test.

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

import build_ledger  # noqa: E402

PAGE = "Module 3: Virtual Machines and Networks in the Cloud"
HEAD = "01 — Virtual private cloud networking"
KEY = f"{PAGE}::{HEAD}"


def topic(n=1, ts=None, heading=HEAD, **extra):
    t = {"n": n, "ts": ts or f"178907300{n}.000000", "blueprint": "2.2",
         "source": {"page": PAGE, "heading": heading,
                    "notion_url": "https://app.notion.com/p/x"}}
    t.update(extra)
    return t


def question(n=1, stem="What should you do?"):
    return {"n": n, "stem": stem, "blueprint": "2.2",
            "scenario": "A team needs access to one subnet.",
            "options": ["Alpha option", "Beta option", "Gamma option", "Delta option"],
            "source": {"page": PAGE, "heading": HEAD}}


class LedgerCase(unittest.TestCase):
    """Writes real history files into a temp dir and rebuilds from them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.history = Path(self.tmp.name)
        self._saved = build_ledger.HISTORY
        build_ledger.HISTORY = self.history
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda: setattr(build_ledger, "HISTORY", self._saved))

    def write(self, date, name, payload):
        day = self.history / date
        day.mkdir(parents=True, exist_ok=True)
        (day / name).write_text(json.dumps(payload))

    def digest(self, date="2026-09-11", topics=(), retractions=()):
        self.write(date, "digest.json",
                   {"date": date, "slack": {"topics": list(topics)},
                    "retractions": list(retractions)})
        return build_ledger.build()


class TestRetraction(LedgerCase):
    """A retracted topic counted as taught, inflating coverage.

    The 2026-09-11 digest recorded its retraction top-level as
    `retractions: [{topic: 4, ts: ...}]`, while build_ledger only ever checked
    `topic.get("retracted")`.
    """

    def test_topic_level_flag_excludes_it(self):
        led = self.digest(topics=[topic(1, retracted=True)])
        self.assertNotIn(KEY, led["sections"])

    def test_top_level_retraction_excludes_it(self):
        t = topic(1, ts="1789073167.701699")
        led = self.digest(topics=[t], retractions=[{"topic": 1, "ts": t["ts"]}])
        self.assertNotIn(KEY, led["sections"])

    def test_a_replacement_reusing_the_number_still_counts(self):
        """The case that makes `ts` the key and the topic number a trap.

        A withdrawn topic is normally replaced, and the replacement reuses the
        same number. Keying on the number drops the replacement and undercounts
        what was taught -- the same error as counting the retraction, pointing
        the other way. This is exactly what 2026-09-11 did.
        """
        replacement = topic(4, ts="1789073437.260319")
        led = self.digest(topics=[replacement],
                          retractions=[{"topic": 4, "ts": "1789073167.701699"}])
        self.assertIn(KEY, led["sections"])
        self.assertEqual(len(led["sections"][KEY]["taught"]), 1)

    def test_retraction_does_not_inflate_the_taught_count(self):
        led = self.digest(
            topics=[topic(1, ts="a"), topic(2, ts="b", heading="04 — Important VPC compatibilities")],
            retractions=[{"topic": 1, "ts": "a"}])
        self.assertEqual(sum(len(s["taught"]) for s in led["sections"].values()), 1)

    def test_withdrawn_ground_returns_to_the_pool(self):
        """The point of the fix: a section whose only topic was pulled must be
        teachable again, not silently marked covered."""
        led = self.digest(topics=[topic(1, ts="a")], retractions=[{"topic": 1, "ts": "a"}])
        self.assertEqual(led["sections"], {})


class TestMissingAngle(LedgerCase):
    """`topic.get("angle", "delta")` marked every untagged topic as taught from
    the delta angle. All four topics of the first real digest were untagged, so
    the ledger claimed a delta pass on four sections that had never had one --
    and selection would have skipped straight to a weaker angle."""

    def test_untagged_topic_does_not_claim_the_delta_angle(self):
        led = self.digest(topics=[topic(1)])
        self.assertEqual(led["sections"][KEY]["angles_used"], [])

    def test_untagged_topic_still_counts_as_a_pass(self):
        # It WAS taught. What is unknown is from which angle.
        led = self.digest(topics=[topic(1)])
        self.assertEqual(len(led["sections"][KEY]["taught"]), 1)
        self.assertEqual(led["sections"][KEY]["last_taught"], "2026-09-11")

    def test_untagged_topic_is_flagged_for_backfill(self):
        led = self.digest(topics=[topic(1)])
        self.assertTrue(led["sections"][KEY]["needs_angle"])
        self.assertEqual(len(led["untagged_topics"]), 1)

    def test_explicit_angle_is_recorded(self):
        led = self.digest(topics=[topic(1, angle="trap")])
        self.assertEqual(led["sections"][KEY]["angles_used"], ["trap"])
        self.assertNotIn("needs_angle", led["sections"][KEY])
        self.assertEqual(led["untagged_topics"], [])


class TestOnDemandQuizzes(LedgerCase):
    """schedule.yaml sets `on_demand.counts_toward_mastery: true`, but only the
    bare `quiz.json` was globbed -- so a second quiz in a day could not be
    recorded, and ad-hoc practice moved nothing."""

    def test_scheduled_quiz_is_recorded(self):
        self.write("2026-09-10", "quiz.json", {"questions": [question(1)]})
        self.assertEqual(len(build_ledger.build()["questions"]), 1)

    def test_on_demand_quiz_is_recorded_alongside_it(self):
        self.write("2026-09-10", "quiz.json", {"questions": [question(1)]})
        self.write("2026-09-10", "quiz-1400.json",
                   {"questions": [question(1, stem="Which action is required?")]})
        self.assertEqual(len(build_ledger.build()["questions"]), 2)

    def test_on_demand_outcomes_are_paired_by_suffix(self):
        self.write("2026-09-10", "quiz-1400.json", {"questions": [question(1)]})
        self.write("2026-09-10", "results-1400.json",
                   {"questions": [{"n": 1, "outcome": "wrong"}]})
        qs = build_ledger.build()["questions"]
        self.assertEqual([e["outcomes"] for e in qs.values()], [["wrong"]])

    def test_results_are_not_crossed_between_sets(self):
        """results.json must never be applied to quiz-1400.json's questions."""
        self.write("2026-09-10", "quiz.json", {"questions": [question(1)]})
        self.write("2026-09-10", "results.json",
                   {"questions": [{"n": 1, "outcome": "correct"}]})
        self.write("2026-09-10", "quiz-1400.json",
                   {"questions": [question(1, stem="Which action is required?")]})
        outcomes = sorted(e["outcomes"] for e in build_ledger.build()["questions"].values())
        self.assertEqual(outcomes, [[], ["correct"]])

    def test_replay_order_is_scheduled_then_ascending_suffix(self):
        day = self.history / "2026-09-10"
        day.mkdir(parents=True)
        for name in ("quiz.json", "quiz-0900.json", "quiz-1400.json"):
            (day / name).write_text(json.dumps({"questions": []}))
        got = [p.name for p, _ in build_ledger.quiz_sets(day)]
        self.assertEqual(got, ["quiz.json", "quiz-0900.json", "quiz-1400.json"])


if __name__ == "__main__":
    unittest.main()
