#!/usr/bin/env python3
"""Tests for the repetition model: ledger, selection, and repeat rejection.

These exist because of a direct question -- "what happens if I add no new
material, would I get repeated data?" -- which the system previously had no way
to answer. The multi-day simulation test is the one that actually answers it.

    .venv/bin/python -m unittest discover -s tests -v
"""
from __future__ import annotations

import datetime
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_ledger  # noqa: E402
import select_topics  # noqa: E402
import validate  # noqa: E402


def q(stem="What should you do?", options=None,
      scenario="A team needs access to one bucket. No other workload should have it."):
    return {"n": 1, "stem": stem, "scenario": scenario,
            "options": options or ["Alpha option", "Beta option",
                                   "Gamma option", "Delta option"]}


class TestFingerprint(unittest.TestCase):
    def test_identical_questions_match(self):
        self.assertEqual(build_ledger.fingerprint(q()), build_ledger.fingerprint(q()))

    def test_whitespace_and_case_are_ignored(self):
        a = q(stem="What should you do?")
        b = q(stem="  WHAT   SHOULD you DO? ")
        self.assertEqual(build_ledger.fingerprint(a), build_ledger.fingerprint(b))

    def test_shuffled_options_are_the_same_question(self):
        """Reordering four options is not a new question."""
        a = q(options=["Alpha option", "Beta option", "Gamma option", "Delta option"])
        b = q(options=["Delta option", "Gamma option", "Beta option", "Alpha option"])
        self.assertEqual(build_ledger.fingerprint(a), build_ledger.fingerprint(b))

    def test_different_option_is_a_different_question(self):
        a = q()
        b = q(options=["Alpha option", "Beta option", "Gamma option", "Epsilon option"])
        self.assertNotEqual(build_ledger.fingerprint(a), build_ledger.fingerprint(b))

    def test_different_scenario_is_a_different_question(self):
        self.assertNotEqual(build_ledger.fingerprint(q()),
                            build_ledger.fingerprint(q(scenario="A different setup.")))


class TestQuizRepeatRules(unittest.TestCase):
    """Verbatim retest once, then fresh."""

    SRC = {"page": "Module 2", "heading": "03 — IAM roles", "notion_url": "https://x"}

    def check(self, question, ledger, quiz_date="2026-09-20"):
        r = validate.Report()
        question = {**question, "blueprint": "1.4", "answer": ["A"],
                    "source": self.SRC, "depth": "mid", "services": []}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"questions": [question]}, f)
            path = Path(f.name)
        try:
            validate.check_quiz(r, path, {"headings": {"03 — IAM roles"},
                                          "schedule": {}, "services": set(),
                                          "ledger": ledger, "quiz_date": quiz_date})
        finally:
            path.unlink()
        return r

    def ledger_with(self, question, asked, outcomes, retested=False):
        return {"questions": {build_ledger.fingerprint(question): {
            "asked": asked, "outcomes": outcomes, "retested": retested}}}

    def test_unseen_question_passes(self):
        self.assertEqual(self.check(q(), {"questions": {}}).errors, [])

    def test_duplicate_is_rejected(self):
        r = self.check(q(), self.ledger_with(q(), ["2026-09-10"], ["correct"]))
        self.assertTrue(any("duplicate question" in e for e in r.errors), r.errors)

    def test_sanctioned_retest_of_a_miss_is_allowed(self):
        led = self.ledger_with(q(), ["2026-09-10"], ["wrong"])
        r = self.check({**q(), "is_retest": True}, led)
        self.assertEqual(r.errors, [], r.errors)

    def test_retest_rejected_if_never_wrong(self):
        led = self.ledger_with(q(), ["2026-09-10"], ["correct"])
        r = self.check({**q(), "is_retest": True}, led)
        self.assertTrue(any("never answered wrong" in e for e in r.errors), r.errors)

    def test_second_retest_is_rejected(self):
        """One verbatim retest only; after that the concept comes back fresh."""
        led = self.ledger_with(q(), ["2026-09-10"], ["wrong"], retested=True)
        r = self.check({**q(), "is_retest": True}, led)
        self.assertTrue(any("already retested once" in e for e in r.errors), r.errors)

    def test_retest_too_soon_is_rejected(self):
        led = self.ledger_with(q(), ["2026-09-19"], ["wrong"])
        r = self.check({**q(), "is_retest": True}, led, quiz_date="2026-09-20")
        self.assertTrue(any("minimum is" in e for e in r.errors), r.errors)

    def test_validating_a_posted_quiz_does_not_flag_itself(self):
        """The ledger is built from history, so a posted quiz contains its own
        fingerprints. Re-validating it must not report duplicates."""
        led = self.ledger_with(q(), ["2026-09-20"], [])
        self.assertEqual(self.check(q(), led, quiz_date="2026-09-20").errors, [])


class TestSelection(unittest.TestCase):
    def setUp(self):
        self.index = json.loads((ROOT / "knowledge/index.json").read_text())

    def test_weights_by_section_not_by_novelty(self):
        """SAIF has 9 of 20 sections but the least weight each. It must not lead."""
        r = select_topics.select(today="2026-09-12",
                                 ledger={"sections": {}, "questions": {}},
                                 index=self.index)
        first = r["topics"][0]
        self.assertGreaterEqual(first["weight_per_section"], 5.0)
        self.assertNotIn("3.3", [t["blueprint"] for t in r["topics"][:2]],
                         "SAIF should not occupy the top of day one")

    def test_reports_remaining_angles(self):
        r = select_topics.select(today="2026-09-12",
                                 ledger={"sections": {}, "questions": {}},
                                 index=self.index)
        self.assertGreater(r["remaining_angles"], 0)

    def test_no_repeats_across_a_full_run(self):
        """The question that prompted all this: no new material, do I get repeats?"""
        ledger = {"sections": {}, "questions": {}}
        start = datetime.date(2026, 9, 12)
        seen, exhausted = set(), None

        for i in range(40):
            date = (start + datetime.timedelta(days=i)).isoformat()
            r = select_topics.select(today=date, ledger=ledger, index=self.index)
            if not r["topics"]:
                exhausted = date
                break
            for t in r["topics"]:
                pair = (t["key"], t["angle"])
                self.assertNotIn(pair, seen, f"repeated {pair} on {date}")
                seen.add(pair)
                e = ledger["sections"].setdefault(
                    t["key"], {"angles_used": [], "taught": [], "blueprint": [t["blueprint"]]})
                e["angles_used"].append(t["angle"])
                e["taught"].append({"date": date, "angle": t["angle"]})
                e["last_taught"] = date

        self.assertIsNotNone(exhausted, "should reach exhaustion rather than loop forever")
        self.assertGreater(len(seen), 50, "should yield weeks of distinct material first")

    def test_exhaustion_names_what_to_add(self):
        ledger = {"sections": {}, "questions": {}}
        start = datetime.date(2026, 9, 12)
        for i in range(40):
            date = (start + datetime.timedelta(days=i)).isoformat()
            r = select_topics.select(today=date, ledger=ledger, index=self.index)
            if not r["topics"]:
                self.assertEqual(r["phase"], "E")
                self.assertIn("reason", r)
                ids = [row[0] for row in r["add_next"]]
                self.assertIn("4.1", ids, "should name the heaviest uncovered area")
                self.assertEqual(r["add_next"][0][0][0], "4",
                                 "heaviest uncovered subsection should lead")
                return
            for t in r["topics"]:
                e = ledger["sections"].setdefault(
                    t["key"], {"angles_used": [], "taught": [], "blueprint": [t["blueprint"]]})
                e["angles_used"].append(t["angle"])
                e["taught"].append({"date": date, "angle": t["angle"]})
                e["last_taught"] = date
        self.fail("never exhausted")


class TestDigestAngleRepeat(unittest.TestCase):
    def test_same_angle_twice_is_rejected(self):
        r = validate.Report()
        ledger = {"sections": {"Module 2::03 — IAM roles": {
            "angles_used": ["delta"],
            "taught": [{"date": "2026-09-11", "angle": "delta"}]}}}
        topics = [{"n": 1, "blueprint": "1.4", "angle": "delta", "component": "chain",
                   "source": {"page": "Module 2", "heading": "03 — IAM roles",
                              "notion_url": "https://x"}}]
        with tempfile.NamedTemporaryFile("w", suffix="digest.json", delete=False) as f:
            json.dump({"slack": {"topics": topics}}, f)
            path = Path(f.name)
        try:
            validate.check_digest(r, path, {
                "headings": {"03 — IAM roles"}, "covered_subsections": {"1.4"},
                "ledger": ledger, "digest_date": "2026-09-20"})
        finally:
            path.unlink()
        self.assertTrue(any("already taught from the 'delta' angle" in e for e in r.errors),
                        r.errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
