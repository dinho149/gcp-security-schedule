#!/usr/bin/env python3
"""Tests for the readiness score, its ceiling, and its refusal to guess.

Hermetic: every fixture is built in code. The one test that touches real repo
data reconciles against build_coverage.py and skips when knowledge/ is absent,
because knowledge/ is gitignored and missing in CI.

    .venv/bin/python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_readiness as br  # noqa: E402
import validate  # noqa: E402

BLUEPRINT = {"sections": [
    {"id": "1", "title": "Access", "weight": 60, "square": "🟦",
     "subsections": [{"id": "1.1", "title": "A"}, {"id": "1.2", "title": "B"}]},
    {"id": "2", "title": "Data", "weight": 40, "square": "🟨",
     "subsections": [{"id": "2.1", "title": "C"}]},
]}


def index(pages):
    """pages: list of (title, ingested, [(heading, [tags])], ingested_on)."""
    return {"courses": [{"material": {"pages": [
        {"title": t, "url": "u", "ingested": ing, "ingested_on": on,
         "sections": [{"heading": h, "exam_tags": tags} for h, tags in secs]}
        for t, ing, secs, on in pages]}}]}


def ledger(taught):
    return {"sections": {k: {"taught": [{"date": d, "angle": "delta"}]}
                         for k, d in taught}, "questions": {}}


def mastery(subs=None, sections=None, graded_days=()):
    return {"subsections": subs or {}, "sections": sections or {},
            "graded_days": list(graded_days)}


IDX = index([("P", True, [("h1", ["1.1"]), ("h2", ["2.1"])], "2026-09-01"),
             ("Q", False, [], None)])


class TestWeights(unittest.TestCase):
    def test_subsection_weight_is_an_even_split(self):
        w = br.subsection_weights(BLUEPRINT)
        self.assertEqual(w["1.1"], 30.0)
        self.assertEqual(w["2.1"], 40.0)

    def test_weights_sum_to_the_blueprint_total(self):
        self.assertAlmostEqual(sum(br.subsection_weights(BLUEPRINT).values()), 100.0)


class TestScoring(unittest.TestCase):
    def test_unproven_untaught_starts_at_the_guess_floor(self):
        """Four options, so blind guessing is 25%. Nothing may start below it,
        and nothing untaught and unproven may start above."""
        s = br.score_subsection(30, True, 0, 1, 0, 0.0)
        self.assertAlmostEqual(s["readiness"], 0.25)

    def test_teaching_alone_caps_at_half(self):
        """The structural answer to 'am I fooling myself by reading digests?'"""
        s = br.score_subsection(30, True, 2, 2, 0, 0.0)
        self.assertAlmostEqual(s["readiness"], 0.50)
        self.assertEqual(s["evidence"], "prior only")

    def test_one_lucky_correct_answer_is_not_mastery(self):
        s = br.score_subsection(30, True, 0, 1, 1, 1.0)
        self.assertLess(s["readiness"], 0.5)
        self.assertAlmostEqual(s["readiness"], 0.4)

    def test_evidence_overrides_the_prior_with_enough_of_it(self):
        s = br.score_subsection(30, True, 2, 2, 20, 20.0)
        self.assertGreater(s["readiness"], 0.9)

    def test_sustained_wrong_answers_fall_below_the_floor(self):
        s = br.score_subsection(30, True, 1, 1, 12, 0.0)
        self.assertLess(s["readiness"], 0.15)

    def test_no_material_scores_zero_whatever_the_evidence(self):
        """The cap. Un-ingested weight cannot be earned."""
        s = br.score_subsection(30, False, 0, 0, 10, 10.0)
        self.assertEqual(s["readiness"], 0.0)
        self.assertEqual(s["evidence"], "no material ingested")

    def test_zero_attempts_never_divides_by_zero(self):
        self.assertIsNotNone(br.score_subsection(30, True, 0, 0, 0, 0.0)["readiness"])

    def test_quizzed_but_never_taught_still_scores(self):
        """A real case: the first quiz asked a 3.3 question and 3.3 had never
        been in a digest. Gating on taught would score it zero."""
        s = br.score_subsection(30, True, 0, 1, 4, 4.0)
        self.assertGreater(s["readiness"], 0.25)
        self.assertEqual(s["evidence"], "graded, untaught")


class TestRollup(unittest.TestCase):
    def snap(self, **kw):
        return br.compute(BLUEPRINT, IDX, ledger([]), mastery(), **kw)

    def test_identity_true_equals_covered_times_reachable(self):
        s = self.snap()
        self.assertAlmostEqual(s["true"], s["on_covered"] * s["reachable"], places=9)

    def test_reachable_counts_only_ingested_subsections(self):
        # 1.1 and 2.1 have material; 1.2 does not. 30 + 40 = 70.
        self.assertAlmostEqual(self.snap()["reachable"], 0.70)

    def test_a_section_with_no_material_reports_null_not_zero(self):
        """'Not measured' and 'measured at zero' are different facts, and a 0%
        would read as a failed test."""
        idx = index([("P", True, [("h2", ["2.1"])], "2026-09-01")])
        s = br.compute(BLUEPRINT, idx, ledger([]), mastery())
        sec1 = next(x for x in s["sections"] if x["id"] == "1")
        self.assertIsNone(sec1["on_covered"])
        self.assertEqual(sec1["points"], 0.0)

    def test_whole_exam_unreachable_yields_null_not_a_crash(self):
        s = br.compute(BLUEPRINT, index([("P", False, [], None)]), ledger([]), mastery())
        self.assertIsNone(s["on_covered"])
        self.assertEqual(s["true"], 0.0)

    def test_teaching_raises_the_score_without_any_quiz(self):
        untaught = self.snap()["true"]
        taught = br.compute(BLUEPRINT, IDX, ledger([("P::h1", "2026-09-10")]),
                            mastery())["true"]
        self.assertGreater(taught, untaught)

    def test_taught_is_filtered_by_date_for_the_trend(self):
        led = ledger([("P::h1", "2026-09-10")])
        before = br.compute(BLUEPRINT, IDX, led, mastery(), on="2026-09-09")
        after = br.compute(BLUEPRINT, IDX, led, mastery(), on="2026-09-11")
        self.assertLess(before["true"], after["true"])

    def test_material_is_filtered_by_ingestion_date(self):
        early = br.compute(BLUEPRINT, IDX, ledger([]), mastery(), on="2026-08-31")
        self.assertEqual(early["reachable"], 0.0)


class TestEstimate(unittest.TestCase):
    CFG = {"target": 0.75, "min_graded_quizzes": 2, "min_attempts": 15,
           "min_snapshots": 5}

    def trend(self, n=8, start=0.20, step=0.01):
        return [{"date": f"2026-09-{d:02d}", "true": round(start + step * i, 4),
                 "reachable": 0.9, "on_covered": 0.5}
                for i, d in enumerate(range(1, 1 + n * 2, 2))]

    def cover(self, rate=0.004):
        return {"rate": rate, "stamps": 3, "pending": [], "why": None}

    def est(self, snap_true=0.30, trend=None, m=None, cover=None):
        snap = {"true": snap_true, "reachable": 0.9, "on_covered": snap_true / 0.9}
        return br.estimate(self.CFG, snap, trend if trend is not None else self.trend(),
                           m or mastery({}, {"k": {"attempts": 40, "skipped": 0}},
                                        [f"d{i}" for i in range(6)]),
                           cover or self.cover(), "2026-09-20")

    def test_gives_a_number_when_the_data_supports_it(self):
        e = self.est()
        self.assertFalse(e["too_early"])
        self.assertIsInstance(e["days"], int)
        self.assertIn(e["confidence"], {"low", "medium", "high"})

    def test_too_early_without_enough_graded_quizzes(self):
        e = self.est(m=mastery({}, {"k": {"attempts": 40}}, ["d1"]))
        self.assertTrue(e["too_early"])
        self.assertEqual(e["blocked_by"], "graded quizzes")
        self.assertIsNone(e["days"])

    def test_too_early_without_enough_answered_questions(self):
        e = self.est(m=mastery({}, {"k": {"attempts": 3}}, ["d1", "d2", "d3"]))
        self.assertEqual(e["blocked_by"], "answered questions")

    def test_too_early_without_enough_snapshots(self):
        e = self.est(trend=self.trend(n=3))
        self.assertEqual(e["blocked_by"], "readiness snapshots")

    def test_a_flat_trend_is_reported_as_not_improving(self):
        e = self.est(trend=self.trend(step=0.0))
        self.assertTrue(e["too_early"])
        self.assertEqual(e["blocked_by"], "improving")
        self.assertIn("flat or falling", e["reason"])

    def test_a_falling_trend_never_yields_a_number(self):
        e = self.est(trend=self.trend(start=0.4, step=-0.01))
        self.assertTrue(e["too_early"])
        self.assertIsNone(e["days"])

    def test_unmeasurable_ingestion_pace_blocks_the_estimate(self):
        """Only when coverage still has to grow to reach the target."""
        snap = {"true": 0.30, "reachable": 0.50, "on_covered": 0.60}
        e = br.estimate(self.CFG, snap, self.trend(),
                        mastery({}, {"k": {"attempts": 40}}, [f"d{i}" for i in range(6)]),
                        {"rate": None, "stamps": 1, "pending": [],
                         "why": "needs 2 dated ingestions to measure a pace"},
                        "2026-09-20")
        self.assertEqual(e["blocked_by"], "ingestion pace")
        self.assertTrue(e["too_early"])

    def test_ingestion_pace_is_irrelevant_once_coverage_clears_the_target(self):
        """Nothing left to unlock, so an unmeasurable pace must not block."""
        snap = {"true": 0.30, "reachable": 0.90, "on_covered": 0.33}
        e = br.estimate(self.CFG, snap, self.trend(),
                        mastery({}, {"k": {"attempts": 40}}, [f"d{i}" for i in range(6)]),
                        {"rate": None, "stamps": 1, "pending": [], "why": "x"},
                        "2026-09-20")
        self.assertFalse(e["too_early"])

    def test_target_already_met_reports_zero_not_a_negative(self):
        e = self.est(snap_true=0.80)
        self.assertEqual(e["days"], 0)
        self.assertIn("target met", e["reason"])

    def test_coverage_is_a_floor_the_estimate_cannot_undercut(self):
        """Proving readiness on material you have not unlocked is impossible."""
        e = self.est(cover=self.cover(rate=0.0005))
        self.assertGreaterEqual(e["days"], e["days_coverage"])

    def test_an_impossible_pace_refuses_rather_than_printing_a_huge_number(self):
        e = self.est(trend=self.trend(step=0.00001), cover=self.cover(rate=0.00001))
        self.assertTrue(e["too_early"])
        self.assertIn("beyond a year", e["reason"])

    def test_every_check_is_reported_not_just_the_blocker(self):
        e = self.est(m=mastery({}, {"k": {"attempts": 40}}, ["d1"]))
        self.assertEqual(len(e["checks"]), 6)
        self.assertTrue(any(c["ok"] for c in e["checks"]))

    def test_target_basis_is_carried_through(self):
        cfg = dict(self.CFG, target_basis="Self-set; Google publishes no pass mark.")
        e = br.estimate(cfg, {"true": 0.3, "reachable": 0.9, "on_covered": 0.33},
                        self.trend(), mastery({}, {}, []), self.cover(), "2026-09-20")
        self.assertIn("no pass mark", e["target_basis"])


class TestTheilSen(unittest.TestCase):
    def test_slope_of_a_clean_line(self):
        slope, _ = br.theil_sen([(0.0, 0.0), (1.0, 2.0), (2.0, 4.0)])
        self.assertAlmostEqual(slope, 2.0)

    def test_one_outlier_does_not_dominate(self):
        """Least squares would be dragged badly by the spike; the median of
        pairwise slopes is not."""
        pts = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 40.0)]
        slope, _ = br.theil_sen(pts)
        self.assertLess(slope, 5.0)

    def test_a_single_point_has_no_slope(self):
        self.assertEqual(br.theil_sen([(0.0, 1.0)]), (None, None))


class TestAgainstRealMaterial(unittest.TestCase):
    """Reconciles with build_coverage.py. Skipped when knowledge/ is absent."""

    def setUp(self):
        if not (ROOT / "knowledge/index.json").exists():
            self.skipTest("knowledge/ is gitignored and absent")

    def test_reachable_matches_build_coverage(self):
        import json
        bp = br.load("config/exam-blueprint.yaml")
        idx = json.loads((ROOT / "knowledge/index.json").read_text())
        snap = br.compute(bp, idx, {"sections": {}, "questions": {}}, mastery())

        sources = {tag for c in idx["courses"] for p in c["material"]["pages"]
                   if p["ingested"] for s in p["sections"] for tag in s["exam_tags"]}
        expect = sum(sec["weight"] / len(sec["subsections"])
                     for sec in bp["sections"]
                     for sub in sec["subsections"] if sub["id"] in sources)
        self.assertAlmostEqual(snap["reachable"] * 100, expect, places=2)

    def test_true_never_exceeds_the_ceiling(self):
        import json
        snap = br.compute(br.load("config/exam-blueprint.yaml"),
                          json.loads((ROOT / "knowledge/index.json").read_text()),
                          br.load("state.local/ledger.json",
                                  {"sections": {}, "questions": {}}), mastery())
        self.assertLessEqual(snap["true"], snap["reachable"] + 1e-9)



class TestReadinessGate(unittest.TestCase):
    """validate.check_readiness — the message must say what the script computed.

    The failure with teeth is a report that disagrees with its own file: it
    looks exactly like a correct one to a reader.
    """

    CTX = {"blueprint": {"sections": [{"id": "1"}, {"id": "2"}]},
           "schedule": {"readiness": {"target": 0.75}}}

    def record(self, **over):
        rec = {"date": "2026-10-09", "trigger": "scheduled", "cadence": "weekly",
               "source": {"true": 0.48, "on_covered": 0.78, "reachable": 0.61,
                          "too_early": False, "target": 0.75},
               "posted": {"headline_true": 48, "headline_covered": 78,
                          "days_estimate": 24, "confidence": "medium",
                          "too_early": False, "sections": {"1": 82, "2": 71}}}
        for key, val in over.items():
            rec[key] = val
        return rec

    def run_gate(self, rec):
        import json as _json
        import tempfile
        r = validate.Report()
        with tempfile.NamedTemporaryFile("w", suffix="readiness.json",
                                         delete=False) as f:
            _json.dump(rec, f)
            path = Path(f.name)
        try:
            validate.check_readiness(r, path, self.CTX)
        finally:
            path.unlink()
        return r

    def test_a_faithful_report_passes(self):
        self.assertEqual(self.run_gate(self.record()).errors, [])

    def test_a_snapshot_warns_rather_than_failing(self):
        """state.local/readiness.json also ends in readiness.json."""
        r = self.run_gate({"as_of": "2026-10-09", "headline": {}})
        self.assertEqual(r.errors, [])
        self.assertTrue(any("snapshot" in w for w in r.warnings))

    def test_rejects_a_missing_true_headline(self):
        rec = self.record()
        rec["posted"].pop("headline_true")
        r = self.run_gate(rec)
        self.assertTrue(any("headline_true missing" in e for e in r.errors), r.errors)

    def test_rejects_a_headline_that_drifted_from_the_file(self):
        rec = self.record()
        rec["posted"]["headline_true"] = 78      # quoted the covered score
        r = self.run_gate(rec)
        self.assertTrue(any("disagree" in e for e in r.errors), r.errors)

    def test_rejects_readiness_above_the_ceiling(self):
        rec = self.record()
        rec["source"]["true"] = 0.90             # ceiling is 0.61
        r = self.run_gate(rec)
        self.assertTrue(any("exceeds the coverage ceiling" in e for e in r.errors),
                        r.errors)

    def test_rejects_an_estimate_posted_alongside_too_early(self):
        rec = self.record()
        rec["source"]["too_early"] = True
        rec["posted"]["too_early"] = True
        r = self.run_gate(rec)
        self.assertTrue(any("still too early" in e for e in r.errors), r.errors)

    def test_accepts_a_proper_too_early_report(self):
        rec = self.record()
        rec["source"]["too_early"] = True
        rec["posted"].update({"too_early": True, "days_estimate": None,
                              "confidence": None})
        self.assertEqual(self.run_gate(rec).errors, [])

    def test_rejects_a_dropped_section(self):
        rec = self.record()
        del rec["posted"]["sections"]["2"]
        r = self.run_gate(rec)
        self.assertTrue(any("dropped section" in e for e in r.errors), r.errors)

    def test_rejects_an_invented_confidence_word(self):
        rec = self.record()
        rec["posted"]["confidence"] = "pretty sure"
        r = self.run_gate(rec)
        self.assertTrue(any("low/medium/high" in e for e in r.errors), r.errors)

    def test_rejects_a_stale_target(self):
        rec = self.record()
        rec["source"]["target"] = 0.70
        r = self.run_gate(rec)
        self.assertTrue(any("config says" in e for e in r.errors), r.errors)


class TestScheduleConfig(unittest.TestCase):
    BASE = {"days": ["mon", "fri"],
            "readiness": {"at": "21:15", "days": ["fri"], "daily_from": 85,
                          "target": 0.75, "target_basis": "Self-set; none published."}}

    def check(self, **over):
        sch = {**self.BASE, "readiness": {**self.BASE["readiness"], **over}}
        r = validate.Report()
        validate.check_readiness_schedule(r, sch)
        return r

    def test_a_sane_block_passes(self):
        self.assertEqual(self.check().errors, [])

    def test_rejects_readiness_days_outside_the_run_days(self):
        """A report that never fires looks exactly like one with nothing to say."""
        r = self.check(days=["sun"])
        self.assertTrue(any("no tick ever reaches them" in e for e in r.errors), r.errors)

    def test_rejects_a_malformed_time(self):
        self.assertTrue(any("not HH:MM" in e for e in self.check(at="9pm").errors))

    def test_rejects_a_target_without_a_basis(self):
        """Google publishes no pass mark; an unattributed target becomes 'the
        pass mark' the first time someone reads it quickly."""
        r = self.check(target_basis="")
        self.assertTrue(any("not Google's" in e for e in r.errors), r.errors)

    def test_rejects_a_target_outside_zero_to_one(self):
        self.assertTrue(any("fraction in 0..1" in e for e in self.check(target=75).errors))

    def test_warns_when_daily_would_start_at_the_target(self):
        self.assertTrue(any("switch to daily" in w for w in self.check(daily_from=70).warnings))

    def test_a_missing_block_is_an_error(self):
        r = validate.Report()
        validate.check_readiness_schedule(r, {"days": ["fri"]})
        self.assertTrue(any("nothing to fire on" in e for e in r.errors))

    def test_the_real_schedule_passes(self):
        import yaml as _yaml
        sch = _yaml.safe_load((ROOT / "config/schedule.yaml").read_text())
        r = validate.Report()
        validate.check_readiness_schedule(r, sch)
        self.assertEqual(r.errors, [])


if __name__ == "__main__":
    unittest.main()
