#!/usr/bin/env python3
"""Adversarial tests for the question validator.

The feedback loop can auto-merge PRs that touch prompts. These tests are what
stops a well-meaning prompt change from quietly disabling the grounding gate.

    .venv/bin/python -m unittest discover -s tests -v
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import validate  # noqa: E402

GOOD = {
    "n": 1,
    "blueprint": "1.4",
    "scenario": "Your team needs an on-call group to restart instances. "
                "They must not be able to reconfigure them.",
    "stem": "What should you do?",
    "options": [
        "Create a custom role at the organization level and grant it.",
        "Create a custom role at the folder level and grant it there.",
        "Grant the basic Editor role on the project to the group.",
        "Grant the Compute Instance Admin role on the project.",
    ],
    "answer": ["A"],
    "services": ["Compute Engine"],
    "source": {
        "page": "Module 2",
        "heading": "03 — IAM roles",
        "notion_url": "https://app.notion.com/p/x",
    },
    "depth": "mid",
}

# Injected rather than read from knowledge/aws-gcp-map.json, which is gitignored
# and absent in CI. Without this the hallucination test would pass vacuously there.
CTX = {
    "headings": {"03 — IAM roles"},
    "schedule": {},
    "services": {"compute engine", "cloud storage", "cloud identity"},
}


def run(question) -> validate.Report:
    r = validate.Report()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"questions": [question]}, f)
        path = Path(f.name)
    try:
        validate.check_quiz(r, path, CTX)
    finally:
        path.unlink()
    return r


def mutate(**changes):
    q = copy.deepcopy(GOOD)
    q.update(changes)
    return q


class TestAcceptsValid(unittest.TestCase):
    def test_good_question_passes(self):
        r = run(GOOD)
        self.assertEqual(r.errors, [], f"valid question rejected: {r.errors}")


class TestStructure(unittest.TestCase):
    def assert_fails(self, question, needle):
        r = run(question)
        self.assertTrue(
            any(needle in e for e in r.errors),
            f"expected an error containing {needle!r}, got {r.errors}",
        )

    def test_rejects_five_options(self):
        self.assert_fails(
            mutate(options=GOOD["options"] + ["Grant the Owner role on the folder."]),
            "spec requires exactly 4",
        )

    def test_rejects_three_options(self):
        self.assert_fails(mutate(options=GOOD["options"][:3]), "spec requires exactly 4")

    def test_rejects_unequal_option_lengths(self):
        opts = list(GOOD["options"])
        opts[0] = ("Create a custom role at the organization level and grant it to the "
                   "on-call group across every project that sits beneath the folder in "
                   "question, taking care to avoid basic roles entirely.")
        self.assert_fails(mutate(options=opts), "spread")

    def test_rejects_all_of_the_above(self):
        opts = list(GOOD["options"])
        opts[3] = "All of the above are appropriate here."
        self.assert_fails(mutate(options=opts), "all/none of the above")

    def test_rejects_unattested_stem(self):
        self.assert_fails(mutate(stem="Pick the best option below."), "attested form")

    def test_rejects_fictional_company(self):
        self.assert_fails(
            mutate(scenario="Riverbend Logistics runs a fleet service. It needs restarts."),
            "fictional company",
        )

    def test_rejects_overlong_scenario(self):
        self.assert_fails(
            mutate(scenario=" ".join(f"Sentence number {i} here." for i in range(7)),
                   depth="deep"),
            "sentences, max",
        )


class TestMultiSelect(unittest.TestCase):
    def test_choose_two_needs_two_answers(self):
        q = mutate(stem="Which two controls apply? (choose two)", answer=["A"])
        r = run(q)
        self.assertTrue(any("choose two" in e for e in r.errors), r.errors)

    def test_single_select_rejects_two_answers(self):
        r = run(mutate(answer=["A", "B"]))
        self.assertTrue(any("single-select" in e for e in r.errors), r.errors)

    def test_choose_two_with_two_answers_passes(self):
        q = mutate(stem="Which two controls apply? (choose two)", answer=["A", "B"])
        self.assertEqual(run(q).errors, [])


class TestGrounding(unittest.TestCase):
    """The anti-hallucination gate. These are the important ones."""

    def test_rejects_missing_source_url(self):
        q = mutate(source={"page": "Module 2", "heading": "03 — IAM roles"})
        r = run(q)
        self.assertTrue(any("ungrounded" in e for e in r.errors), r.errors)

    def test_rejects_heading_not_in_index(self):
        q = mutate(source={**GOOD["source"], "heading": "07 — A heading that does not exist"})
        r = run(q)
        self.assertTrue(any("not present in knowledge/index.json" in e for e in r.errors), r.errors)

    def test_rejects_invented_service_name(self):
        r = run(mutate(services=["Cloud Hyperscale Defender"]))
        self.assertTrue(any("possible hallucination" in e for e in r.errors), r.errors)

    def test_rejects_depth_label_mismatch(self):
        r = run(mutate(depth="deep"))
        self.assertTrue(any("labelled depth" in e for e in r.errors), r.errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
