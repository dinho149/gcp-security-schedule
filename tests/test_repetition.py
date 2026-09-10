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


def fixture_index() -> dict:
    """A synthetic ingestion map with the real material's awkward shape.

    Built in-test rather than read from knowledge/index.json, which is gitignored
    and therefore absent in CI — an earlier version read the real file and simply
    errored on the runner, so the most important test here never actually ran.

    The shape that matters: one subsection with MANY thin sections (3.3, mirroring
    SAIF's 9) against several with few heavy ones. That is what makes ranking by
    novelty wrong and ranking by weight-per-section right.
    """
    def sec(heading, tags):
        return {"heading": heading, "exam_tags": tags, "services": []}

    pages = [{
        "title": "Module A", "url": "https://n/a", "ingested": True,
        "sections": [sec("01 — Hierarchy", ["1.5"]), sec("02 — IAM", ["1.4"]),
                     sec("03 — Roles", ["1.4"]), sec("04 — Service accounts", ["1.2"]),
                     sec("05 — Security", ["5.1"])],
    }, {
        "title": "Module B", "url": "https://n/b", "ingested": True,
        "sections": [sec("01 — VPC", ["2.2"]), sec("04 — Compat", ["2.2"]),
                     sec("05 — LB", ["2.1"]), sec("08 — Connect", ["2.3"])],
    }, {
        # The SAIF-shaped page: many sections, one low-weight subsection.
        "title": "AI Notes", "url": "https://n/c", "ingested": True,
        "sections": [sec(f"AI section {i}", ["3.3"]) for i in range(1, 10)],
    }, {
        "title": "Unread", "url": "https://n/d", "ingested": False, "sections": [],
    }]
    return {"courses": [{"material": {"pages": pages}}]}


def drive(index, days=40):
    """Run selection forward, feeding picks back in. Returns (pairs, exhausted_on, last)."""
    ledger = {"sections": {}, "questions": {}}
    start = datetime.date(2026, 9, 12)
    seen, dupes, last = [], [], None
    for i in range(days):
        date = (start + datetime.timedelta(days=i)).isoformat()
        r = select_topics.select(today=date, ledger=ledger, index=index)
        last = r
        if not r["topics"]:
            return seen, date, r, dupes
        for t in r["topics"]:
            pair = (t["key"], t["angle"])
            if pair in seen:
                dupes.append((date, pair))
            seen.append(pair)
            e = ledger["sections"].setdefault(
                t["key"], {"angles_used": [], "taught": [], "blueprint": [t["blueprint"]]})
            e["angles_used"].append(t["angle"])
            e["taught"].append({"date": date, "angle": t["angle"]})
            e["last_taught"] = date
    return seen, None, last, dupes


class TestSelection(unittest.TestCase):
    """Hermetic: no dependency on private material, so these run in CI."""

    def setUp(self):
        self.index = fixture_index()

    def test_weight_per_section_beats_novelty(self):
        """The many-thin-sections subsection must not lead day one."""
        r = select_topics.select(today="2026-09-12",
                                 ledger={"sections": {}, "questions": {}},
                                 index=self.index)
        top_two = [t["blueprint"] for t in r["topics"][:2]]
        self.assertNotIn("3.3", top_two,
                         "a low-weight subsection with many sections must not lead")
        self.assertGreaterEqual(r["topics"][0]["weight_per_section"], 5.0)

    def test_reports_remaining_angles(self):
        r = select_topics.select(today="2026-09-12",
                                 ledger={"sections": {}, "questions": {}},
                                 index=self.index)
        self.assertGreater(r["remaining_angles"], 0)

    def test_no_repeats_with_no_new_material(self):
        """The question that prompted this work: add nothing, do I get repeats?"""
        seen, exhausted, _, dupes = drive(self.index)
        self.assertEqual(dupes, [], f"repeated (section, angle) pairs: {dupes[:3]}")
        self.assertEqual(len(seen), len(set(seen)))
        self.assertIsNotNone(exhausted, "must reach exhaustion, not loop forever")
        self.assertGreater(len(seen), 40, "should yield weeks of distinct material first")

    def test_exhaustion_names_what_to_add(self):
        _, exhausted, last, _ = drive(self.index)
        self.assertIsNotNone(exhausted)
        self.assertEqual(last["phase"], "E")
        self.assertIn("reason", last)
        ids = [row[0] for row in last["add_next"]]
        self.assertTrue(ids, "must name uncovered subsections")
        # Heaviest uncovered first; §4.x is untouched by the fixture.
        self.assertTrue(ids[0].startswith("4"),
                        f"heaviest uncovered should lead, got {ids[:3]}")


@unittest.skipUnless((ROOT / "knowledge/index.json").exists(),
                     "real index is gitignored; hermetic tests cover the logic")
class TestSelectionAgainstRealMaterial(unittest.TestCase):
    """Same guarantees against the actual ingested material, when present."""

    def test_no_repeats_and_reaches_exhaustion(self):
        index = json.loads((ROOT / "knowledge/index.json").read_text())
        seen, exhausted, last, dupes = drive(index)
        self.assertEqual(dupes, [])
        self.assertIsNotNone(exhausted)


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
