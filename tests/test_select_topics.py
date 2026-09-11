"""The digest mix is a quota, and these are the bounds it promises.

Written after 2026-09-11 shipped three remediation passes and one new section:
remediation ran first and unbounded, so a quiz with four misses would have left
no new ground at all. Hermetic -- ledger, index and mastery are all injected, so
nothing here reads state.local/ or the real knowledge index.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from select_topics import select  # noqa: E402

TODAY = "2026-09-20"


def index(n=8, ingested_on=None):
    """A synthetic page of `n` blueprint-tagged sections, heaviest first."""
    tags = ["1.4", "2.2", "1.1", "2.1", "1.2", "2.3", "1.5", "3.3"]
    return {"courses": [{
        "title": "C", "material": {"pages": [{
            "title": "P", "url": "https://app.notion.com/p/x", "ingested": True,
            "cache": "pages/p.md",
            "sections": [{"heading": f"{i:02d} — S{i}", "exam_tags": [tags[i % len(tags)]],
                          "services": [],
                          **({"ingested_on": ingested_on} if ingested_on else {})}
                         for i in range(n)],
        }]},
    }]}


def key(i):
    return f"P::{i:02d} — S{i}"


def taught(*idx, date="2026-09-01", angle="delta"):
    return {k: {"page": "P", "heading": k.split("::")[1], "angles_used": [angle],
                "taught": [{"date": date, "angle": angle}], "last_taught": date,
                "blueprint": []}
            for k in (key(i) for i in idx)}


def missed(*idx):
    """A recorded wrong answer against each section, as build_ledger writes it."""
    return {f"fp{i}": {
        "section": key(i), "blueprint": "1.1", "asked": ["2026-09-10"],
        "outcomes": ["wrong"], "retested": False, "stem": f"Q about S{i}",
        "occurrences": [{"date": "2026-09-10", "set": "quiz.json", "n": i,
                         "channel_id": "CTESTCHAN01", "message_ts": "1789071974.214939",
                         "outcome": "wrong", "hint_used": False,
                         "answered": ["C"], "keyed": ["A"]}],
        "last_miss": {"date": "2026-09-10", "set": "quiz.json", "n": i,
                      "channel_id": "CTESTCHAN01", "message_ts": "1789071974.214939",
                      "outcome": "wrong", "hint_used": False,
                      "answered": ["C"], "keyed": ["A"]},
    } for i in idx}


def run(ledger=None, idx=None, mastery=None, today=TODAY):
    return select(today=today, index=idx or index(),
                  ledger=ledger or {"sections": {}, "questions": {}},
                  mastery=mastery if mastery is not None else {})


class TestRemediationCap(unittest.TestCase):
    def test_at_most_two_remediation_topics(self):
        r = run({"sections": {}, "questions": missed(0, 1, 2, 3, 4)})
        self.assertEqual(r["mix"]["remediation"], 2)

    def test_the_overflow_is_deferred_and_named(self):
        r = run({"sections": {}, "questions": missed(0, 1, 2, 3, 4)})
        held = {d["key"] for d in r["deferred"]}
        picked = {t["key"] for t in r["topics"] if t["band"] == "remediation"}
        self.assertEqual(len(held), 3)
        self.assertFalse(held & picked)
        self.assertTrue(all(d["band"] == "remediation" for d in r["deferred"]))

    def test_new_ground_survives_a_quiz_full_of_misses(self):
        """The complaint this module exists for."""
        r = run({"sections": {}, "questions": missed(0, 1, 2, 3, 4)})
        self.assertGreaterEqual(r["mix"]["new"], 1)

    def test_a_remediation_pick_carries_its_question(self):
        r = run({"sections": {}, "questions": missed(0, 1)})
        rem = [t for t in r["topics"] if t["band"] == "remediation"]
        self.assertTrue(rem)
        for t in rem:
            self.assertIsNotNone(t["miss"])
            self.assertIn("message_ts", t["miss"])
            self.assertEqual(t["miss"]["answered"], ["C"])

    def test_non_remediation_picks_carry_no_miss(self):
        r = run({"sections": {}, "questions": missed(0)})
        for t in r["topics"]:
            if t["band"] != "remediation":
                self.assertIsNone(t["miss"])


class TestNewFloor(unittest.TestCase):
    def test_untaught_section_is_always_reached(self):
        r = run({"sections": taught(0, 1, 2), "questions": missed(0, 1, 2)})
        self.assertGreaterEqual(r["mix"]["new"], 1)

    def test_unmet_floor_is_reported_not_padded(self):
        idx = index(n=3)
        r = run({"sections": taught(0, 1, 2), "questions": {}}, idx=idx)
        self.assertIn("new", r["unfilled_floors"])
        self.assertEqual(r["mix"]["new"], 0)

    def test_no_section_is_picked_twice(self):
        r = run({"sections": taught(0, 1), "questions": missed(0, 1, 2)})
        keys = [t["key"] for t in r["topics"]]
        self.assertEqual(len(keys), len(set(keys)))


class TestFreshSlot(unittest.TestCase):
    def test_freshly_ingested_material_jumps_the_weight_queue(self):
        idx = index(n=6)
        # Only the lowest-weight section is fresh.
        for s in idx["courses"][0]["material"]["pages"][0]["sections"]:
            s["ingested_on"] = None
        idx["courses"][0]["material"]["pages"][0]["sections"][5]["ingested_on"] = TODAY
        r = run(idx=idx)
        self.assertTrue(r["fresh_slot"]["filled"])
        self.assertEqual(r["fresh_slot"]["key"], key(5))

    def test_fresh_is_capped_at_one_slot(self):
        r = run(idx=index(n=8, ingested_on=TODAY))
        self.assertEqual(r["mix"]["fresh"], 1)
        self.assertGreaterEqual(r["mix"]["new"], 1)

    def test_material_older_than_the_window_is_not_fresh(self):
        r = run(idx=index(n=8, ingested_on="2026-09-01"))
        self.assertFalse(r["fresh_slot"]["filled"])
        self.assertEqual(r["mix"]["fresh"], 0)

    def test_null_ingested_on_is_never_fresh(self):
        """The cold-start guard. `null` means 'before the measurement window';
        treating it as today would mark every section fresh at once and fire the
        slot daily on arbitrary material."""
        r = run(idx=index(n=8, ingested_on=None))
        self.assertFalse(r["fresh_slot"]["filled"])


class TestReviewBand(unittest.TestCase):
    def test_a_section_not_yet_due_is_not_reviewed(self):
        """The point of consulting mastery: it was taught long ago, but the
        learner has demonstrably retained it."""
        idx = index(n=3)
        led = {"sections": taught(0, 1, 2, date="2026-08-01"), "questions": {}}
        mastery = {"sections": {key(i): {"next_due": "2026-12-01"} for i in range(3)}}
        r = run(led, idx=idx, mastery=mastery)
        self.assertEqual(r["mix"]["review"], 0)

    def test_an_overdue_section_is_reviewed(self):
        idx = index(n=3)
        led = {"sections": taught(0, 1, 2, date="2026-08-01"), "questions": {}}
        mastery = {"sections": {key(i): {"next_due": "2026-09-01"} for i in range(3)}}
        r = run(led, idx=idx, mastery=mastery)
        self.assertGreaterEqual(r["mix"]["review"], 1)

    def test_the_most_overdue_is_reviewed_first(self):
        idx = index(n=3)
        led = {"sections": taught(0, 1, 2, date="2026-08-01"), "questions": {}}
        mastery = {"sections": {
            key(0): {"next_due": "2026-09-19"},
            key(1): {"next_due": "2026-08-01"},   # most overdue
            key(2): {"next_due": "2026-09-18"}}}
        r = run(led, idx=idx, mastery=mastery)
        review = [t for t in r["topics"] if t["band"] == "review"]
        self.assertEqual(review[0]["key"], key(1))

    def test_without_mastery_it_falls_back_to_staleness(self):
        """A fresh sandbox has no mastery.json until build_mastery.py runs.
        Missing must not read as 'nothing is due'."""
        idx = index(n=3)
        led = {"sections": taught(0, 1, 2, date="2026-08-01"), "questions": {}}
        r = run(led, idx=idx, mastery={})
        self.assertGreaterEqual(r["mix"]["review"], 1)

    def test_a_recently_taught_section_is_not_stale(self):
        idx = index(n=3)
        led = {"sections": taught(0, 1, 2, date=TODAY), "questions": {}}
        r = run(led, idx=idx, mastery={})
        self.assertEqual(r["mix"]["review"], 0)


class TestEnvelope(unittest.TestCase):
    def test_bands_are_mutually_exclusive(self):
        r = run({"sections": taught(0, 1), "questions": missed(0, 2, 3)})
        self.assertEqual(sum(r["mix"].values()), len(r["topics"]))

    def test_phases_lists_every_phase_present(self):
        r = run({"sections": {}, "questions": missed(0, 1)})
        self.assertEqual(r["phase"], "".join(r["phases"]))
        self.assertIn("B", r["phases"])
        self.assertIn("A", r["phases"])

    def test_empty_index_is_still_phase_e(self):
        r = select(today=TODAY, index={"courses": []},
                   ledger={"sections": {}, "questions": {}}, mastery={})
        self.assertEqual(r["phase"], "E")
        self.assertEqual(r["topics"], [])

    def test_never_returns_more_than_the_quota(self):
        r = run({"sections": {}, "questions": missed(0, 1, 2, 3, 4, 5)})
        self.assertLessEqual(len(r["topics"]), 4)


if __name__ == "__main__":
    unittest.main()
