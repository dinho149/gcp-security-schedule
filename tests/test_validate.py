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
sys.path.insert(0, str(ROOT / "tests"))

import validate  # noqa: E402
from material_fixture import (  # noqa: E402  a cached page the checks can read
    ANCHOR, HEADING, PAGE_CACHE, PAGE_TITLE, SOURCE, THIN_HEADING)

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
    "source": copy.deepcopy(SOURCE),
    "depth": "mid",
}

# Injected rather than read from knowledge/aws-gcp-map.json, which is gitignored
# and absent in CI. Without this the hallucination test would pass vacuously there.
CTX = {
    "headings": {HEADING},
    "page_headings": {PAGE_TITLE: {HEADING, THIN_HEADING}},
    # Absolute, so the anchor check reads the fixture instead of the gitignored
    # knowledge/ tree -- which is absent in CI, where it would pass vacuously.
    "page_cache": dict(PAGE_CACHE),
    "schedule": {},
    "services": {"compute engine", "cloud storage", "cloud identity"},
    # A blank cell is Google leaving the AWS column empty on purpose, which is the
    # answer rather than missing data -- VPC Service Controls is the real case.
    "aws_map": {
        "compute engine": "amazon ec2",
        "cloud storage": "aws simple storage service (s3)",
        "cloud identity": "aws iam identity center",
        "vpc service controls": "",
    },
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


class TestDigestCoverage(unittest.TestCase):
    """A digest may only teach what the ingested material covers.

    The first digest shipped a topic that taught past the course, because the
    sync-notion skill described gaps as "prime digest material". These lock the
    rule down so wording alone is not the only thing holding it.
    """

    CTX = {
        "headings": {"03 — IAM roles", "08 — Connecting Networks to Google VPC"},
        "covered_subsections": {"1.4", "2.3"},
    }

    def run_digest(self, topics, **extra):
        r = validate.Report()
        with tempfile.NamedTemporaryFile("w", suffix="digest.json", delete=False) as f:
            json.dump({"slack": {"topics": topics}, **extra}, f)
            path = Path(f.name)
        try:
            validate.check_digest(r, path, self.CTX)
        finally:
            path.unlink()
        return r

    def good_topic(self, **over):
        t = {"n": 1, "blueprint": "1.4", "component": "chain", "angle": "delta",
             "source": {"heading": "03 — IAM roles", "notion_url": "https://x"}}
        t.update(over)
        return t

    def test_covered_topic_passes(self):
        self.assertEqual(self.run_digest([self.good_topic()]).errors, [])

    def test_rejects_topic_without_angle(self):
        """The ledger defaulted a missing angle to 'delta', claiming the
        highest-value first pass on sections that never had one."""
        t = self.good_topic()
        del t["angle"]
        r = self.run_digest([t])
        self.assertTrue(any("no angle recorded" in e for e in r.errors), r.errors)

    def test_rejects_uncovered_subsection(self):
        r = self.run_digest([self.good_topic(blueprint="4.1")])
        self.assertTrue(any("has not reached it yet" in e for e in r.errors), r.errors)

    def test_rejects_topic_marked_beyond_material(self):
        r = self.run_digest([self.good_topic(beyond_material=True)])
        self.assertTrue(any("never digest content" in e for e in r.errors), r.errors)

    def test_rejects_gap_flag(self):
        r = self.run_digest([self.good_topic(gap=True)])
        self.assertTrue(any("never digest content" in e for e in r.errors), r.errors)

    def test_rejects_heading_not_in_index(self):
        r = self.run_digest([self.good_topic(
            source={"heading": "99 — Invented", "notion_url": "https://x"})])
        self.assertTrue(any("not present in knowledge/index.json" in e for e in r.errors), r.errors)

    def test_rejects_unsourced_topic(self):
        r = self.run_digest([self.good_topic(source={})])
        self.assertTrue(any("sourced from ingested material" in e for e in r.errors), r.errors)

    def test_warns_on_repeated_visual_component(self):
        r = self.run_digest([
            self.good_topic(n=1, component="chain"),
            self.good_topic(n=2, component="chain"),
        ])
        self.assertEqual(r.errors, [])
        self.assertTrue(any("repeats visual component" in w for w in r.warnings), r.warnings)


class TestVisualState(TestDigestCoverage):
    """A digest must say whether it had a renderer, and then act like it.

    The cloud sandbox has no browser binary, so a text-only digest went from
    theoretical to routine. "One visual per topic minimum" was asserted in three
    documents and enforced in none.
    """

    def run_visuals(self, topics, visuals):
        return self.run_digest(topics, visuals=visuals)

    def topic(self, **over):
        return self.good_topic(**over)

    def test_rendered_with_every_topic_visual_passes(self):
        r = self.run_visuals([self.topic(n=1, visual="topic-1-x")],
                     {"state": "rendered"})
        self.assertEqual(r.errors, [])

    def test_rejects_rendered_with_a_topic_missing_its_visual(self):
        r = self.run_visuals([self.topic(n=1, visual="topic-1-x"),
                      self.topic(n=2, component="compare")],
                     {"state": "rendered"})
        self.assertTrue(any("carry no visual" in e for e in r.errors), r.errors)

    def test_unavailable_needs_a_reason(self):
        r = self.run_visuals([self.topic()], {"state": "unavailable"})
        self.assertTrue(any("with no reason" in e for e in r.errors), r.errors)

    def test_unavailable_with_a_reason_passes(self):
        r = self.run_visuals([self.topic()],
                     {"state": "unavailable", "reason": "no chrome binary in sandbox"})
        self.assertEqual(r.errors, [])

    def test_rejects_unavailable_that_still_claims_a_visual(self):
        r = self.run_visuals([self.topic(visual="topic-1-x")],
                     {"state": "unavailable", "reason": "no browser"})
        self.assertTrue(any("one of the two is wrong" in e for e in r.errors), r.errors)

    def test_rejects_an_unknown_state(self):
        r = self.run_visuals([self.topic()], {"state": "maybe"})
        self.assertTrue(any("is not 'rendered' or 'unavailable'" in e
                            for e in r.errors), r.errors)

    def test_warns_when_the_field_is_absent(self):
        """Records written before the field existed stay valid."""
        r = self.run_digest([self.topic()])
        self.assertEqual(r.errors, [])
        self.assertTrue(any("no visuals.state recorded" in w
                            for w in r.warnings), r.warnings)


class TestAwsEquivalents(unittest.TestCase):
    """The bracketed "(~ S3)" claims must come from Google's own table.

    They replaced a free-prose aws_anchor field that asserted whatever it liked
    and was checked against nothing.
    """

    def assert_fails(self, claims, needle):
        r = run(mutate(aws_equivalents=claims))
        self.assertTrue(any(needle in e for e in r.errors),
                        f"expected {needle!r} in {r.errors}")

    def test_absent_field_is_not_a_claim(self):
        # Records written before the field existed assert nothing, so they pass.
        self.assertEqual(run(GOOD).errors, [])

    def test_empty_list_passes(self):
        r = run(mutate(aws_equivalents=[]))
        self.assertEqual(r.errors, [])

    def test_pair_in_the_map_passes(self):
        r = run(mutate(aws_equivalents=[{"gcp": "Cloud Storage", "aws": "S3"}]))
        self.assertEqual(r.errors, [], f"valid equivalence rejected: {r.errors}")

    def test_hallucinated_counterpart_fails(self):
        self.assert_fails([{"gcp": "Cloud Storage", "aws": "DynamoDB"}], "the map says")

    def test_service_absent_from_map_fails(self):
        # Shared VPC, IAM, GKE and Dedicated Interconnect are all absent in real
        # life; the digest used to write "no clean AWS counterpart" about them,
        # which asserts a fact nothing backs.
        self.assert_fails([{"gcp": "Shared VPC", "aws": "RAM"}], "absent")

    def test_blank_cell_claim_fails(self):
        self.assert_fails([{"gcp": "VPC Service Controls", "aws": "SCPs"}],
                          "no AWS equivalent")

    def test_entry_without_a_service_fails(self):
        self.assert_fails([{"aws": "S3"}], "no gcp service named")


class TestPostedStyle(unittest.TestCase):
    """docs/house-style.md §5, over the cached text of what actually went out."""

    def check(self, text) -> validate.Report:
        r = validate.Report()
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(text)
            path = Path(f.name)
        try:
            validate.check_style(r, path, CTX)
        finally:
            path.unlink()
        return r

    AT_BUDGET = (
        "\U0001f7e6 1 · Where a custom role can be defined · \u23f1 60s\n"
        "\n"
        "Policies inherit down the hierarchy. Where a role is *created* does not.\n"
        "\n"
        "\u274c *AWS habit* \u2014 attach a customer-managed policy anywhere\n"
        "\u2705 *GCP reality* \u2014 defined and granted are separate questions\n"
    )

    def test_message_at_budget_passes(self):
        self.assertEqual(self.check(self.AT_BUDGET).errors, [])

    def test_one_emoji_over_budget_fails(self):
        r = self.check(self.AT_BUDGET + "\n\U0001f3af One more marker.\n")
        self.assertTrue(any("budget is 4" in e for e in r.errors), r.errors)

    def test_answer_emoji_and_squares_are_exempt(self):
        # Four option emoji plus the square and timer would blow a naive count,
        # but they are the interface and the colour language, not decoration.
        r = self.check(
            "\U0001f7e9 _Q5_ · \u00a72.2 Boundary segmentation · \u23f1 60s\n"
            "\n"
            "_What should you do?_\n"
            "\n"
            "1\ufe0f\u20e3  Use Shared VPC to share the subnets\n"
            "2\ufe0f\u20e3  Set up VPC peering between every pair\n"
            "3\ufe0f\u20e3  Configure Cloud VPN tunnels between projects\n"
            "4\ufe0f\u20e3  Enable Private Google Access on the subnets\n"
        )
        self.assertEqual(r.errors, [], r.errors)

    def test_arrows_are_not_emoji(self):
        # Every citation contains "->"; counting it would fail every message.
        r = self.check("\U0001f7e6 One \u2192 two \u2192 three \u2192 four \u2192 five\n")
        self.assertEqual(r.errors, [], r.errors)

    def test_doubled_blank_line_fails(self):
        r = self.check("\U0001f7e6 Title\n\n\nBody after two blanks.\n")
        self.assertTrue(any("doubled" in e for e in r.errors), r.errors)

    def test_messages_are_counted_separately(self):
        # Three emoji each, six across the file: per-message, not per-file.
        one = "\U0001f7e6 a \u23f1 b \u274c c\n"
        r = self.check(one + "\n---8<---\n\n" + one)
        self.assertEqual(r.errors, [], r.errors)

    def test_horizontal_rule_inside_a_message_is_not_a_split(self):
        """`---` is in-message typography (house style §5), not a separator.

        Splitting on it would cut one message in two and compute the emoji
        budget over each half, passing a message that breaks the very rule the
        budget exists to enforce.
        """
        one = "\U0001f7e6 a \u23f1 b \u274c c\n"
        r = self.check(one + "\n---\n\n" + one)
        self.assertTrue(any("emoji" in e for e in r.errors), r.errors)

    def test_long_message_warns_but_does_not_fail(self):
        r = self.check("\U0001f7e6 Title\n" + "\n".join(f"line {i}" for i in range(20)))
        self.assertEqual(r.errors, [])
        self.assertTrue(any("belongs in the thread" in w for w in r.warnings), r.warnings)


class TestGradedFlag(unittest.TestCase):
    """A graded quiz whose flag stayed false gets graded twice.

    Latent while nothing read the check-mark on the quiz parent; live the moment
    something does. The 2026-09-10 quiz shipped in exactly that state.
    """

    def warns(self, graded, with_results=True) -> bool:
        d = Path(tempfile.mkdtemp())
        if with_results:
            (d / "results.json").write_text("{}")
        (d / "quiz.json").write_text(json.dumps({"questions": [GOOD], "graded": graded}))
        r = validate.Report()
        validate.check_quiz(r, d / "quiz.json", CTX)
        return any("re-grade" in w for w in r.warnings)

    def test_results_without_the_flag_warns(self):
        self.assertTrue(self.warns(graded=False))

    def test_flag_set_is_silent(self):
        self.assertFalse(self.warns(graded=True))

    def test_ungraded_quiz_with_no_results_is_silent(self):
        self.assertFalse(self.warns(graded=False, with_results=False))


class TestEnumerationStyle(unittest.TestCase):
    """SAIF's six core elements shipped as one comma-separated sentence.

    The check has to be conservative: house style asks for a list at three
    items, but a gate that fails on the arguable case gets argued with and then
    ignored. Five short items run into a sentence has no defence; four behind a
    stated count sometimes reads as a chain, so it warns.
    """

    SHIPPED = ("The six elements — security foundations, detection and response, "
               "automated defenses, platform controls, feedback loops, business "
               "context — are not a sequence.")

    def check(self, text) -> validate.Report:
        r = validate.Report()
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(text)
            path = Path(f.name)
        try:
            validate.check_style(r, path, CTX)
        finally:
            path.unlink()
        return r

    def test_the_sentence_that_shipped_fails(self):
        r = self.check("\U0001f7e6 Title\n\n" + self.SHIPPED + "\n")
        self.assertTrue(any("items into a sentence" in e for e in r.errors), r.errors)

    def test_a_lead_in_glued_to_the_first_item_is_still_caught(self):
        """No dash to separate the lead-in, so the first item carries
        'The six elements are' with it."""
        line = ("The six elements are security foundations, detection and response, "
                "automated defenses, platform controls, feedback loops, business context.")
        r = self.check("\U0001f7e6 Title\n\n" + line + "\n")
        self.assertTrue(any("items into a sentence" in e for e in r.errors), r.errors)

    def test_the_same_items_as_a_list_pass(self):
        items = "\n".join(f"• {i}" for i in
                          ["security foundations", "detection and response",
                           "automated defenses", "platform controls",
                           "feedback loops", "business context"])
        r = self.check("\U0001f7e6 Title\n\n" + items + "\n")
        self.assertEqual(r.errors, [], r.errors)

    def test_three_items_are_prose_not_a_violation(self):
        r = self.check("\U0001f7e6 Title\n\nPolicies inherit through resources, "
                       "projects and folders.\n")
        self.assertEqual(r.errors, [], r.errors)

    def test_a_multi_clause_sentence_is_not_an_enumeration(self):
        r = self.check("\U0001f7e6 Title\n\nIt is billed separately, can have its "
                       "own owners, and holds resources that each belong to one "
                       "project.\n")
        self.assertEqual(r.errors, [], r.errors)

    def test_four_items_behind_a_count_warns_rather_than_fails(self):
        r = self.check("\U0001f7e6 Title\n\nFour levels, bottom up: resources, "
                       "projects, folders, the organization node.\n")
        self.assertEqual(r.errors, [], r.errors)
        self.assertTrue(any("items into a sentence" in w for w in r.warnings), r.warnings)

    def test_a_table_row_is_not_an_enumeration(self):
        r = self.check("\U0001f7e6 Title\n\n| a | b | c | d | e | f |\n")
        self.assertEqual(r.errors, [], r.errors)

    def test_a_citation_line_is_not_an_enumeration(self):
        r = self.check("\U0001f7e6 Title\n\n<https://app.notion.com/p/x|M3 → "
                       "\"01 — a, b, c, d, e, f\">\n")
        self.assertEqual(r.errors, [], r.errors)


class TestLocator(TestDigestCoverage):
    """A citation may point at a place on the page — and if it does, the place
    has to exist. An invented sub-heading is worse than no locator at all."""

    CTX = dict(TestDigestCoverage.CTX, page_cache={"P": "pages/fake.md"})

    def test_no_locator_is_fine(self):
        self.assertEqual(self.run_digest([self.good_topic()]).errors, [])

    def test_locator_without_a_subheading_fails(self):
        t = self.good_topic()
        t["source"]["locator"] = {"look_for": "the table"}
        r = self.run_digest([t])
        self.assertTrue(any("no subheading" in e for e in r.errors), r.errors)

    def test_unresolvable_page_warns_rather_than_fails(self):
        """A cloud run hydrates only the pages it cites, so an absent cache is
        normal and must not fail the digest."""
        t = self.good_topic()
        t["source"]["page"] = "Unknown Page"
        t["source"]["locator"] = {"subheading": "Anything", "look_for": "the table"}
        r = self.run_digest([t])
        self.assertEqual(r.errors, [], r.errors)
        self.assertTrue(any("cannot check the locator" in w for w in r.warnings), r.warnings)


class TestRemediationReference(TestDigestCoverage):
    """A remediation topic must name, recap and link the question it corrects."""

    MISS = {"date": "2026-09-10", "set": "quiz.json", "n": 5,
            "channel_id": "CTESTCHAN01", "message_ts": "1789071974.214939",
            "outcome": "wrong", "answered": ["C"], "keyed": ["A"]}
    URL = ("https://a-workspace.slack.com/archives/CTESTCHAN01/"
           "p1789071974214939")

    def ledger(self, message_ts="1789071974.214939"):
        miss = dict(self.MISS, message_ts=message_ts)
        return {"questions": {"fp": {
            "section": "None::03 — IAM roles", "stem": "Q", "outcomes": ["wrong"],
            "occurrences": [miss], "last_miss": miss}}}

    def run_one(self, ref, ledger=None):
        self.CTX = dict(TestDigestCoverage.CTX,
                        ledger=ledger if ledger is not None else self.ledger())
        t = self.good_topic(angle="remediation")
        if ref is not None:
            t["question_ref"] = ref
        return self.run_digest([t])

    def good_ref(self, **over):
        ref = {"n": 5, "date": "2026-09-10", "url": self.URL,
               "recap": "asked about VPC scope; you picked Global"}
        ref.update(over)
        return ref

    def test_a_complete_reference_passes(self):
        self.assertEqual(self.run_one(self.good_ref()).errors, [])

    def test_missing_reference_fails(self):
        r = self.run_one(None)
        self.assertTrue(any("must name the question" in e for e in r.errors), r.errors)

    def test_bare_number_without_a_recap_fails(self):
        r = self.run_one(self.good_ref(recap="   "))
        self.assertTrue(any("no recap" in e for e in r.errors), r.errors)

    def test_citing_a_question_that_is_not_the_miss_fails(self):
        r = self.run_one(self.good_ref(n=99))
        self.assertTrue(any("not how" in e for e in r.errors), r.errors)

    def test_linkable_but_unlinked_fails(self):
        r = self.run_one(self.good_ref(url=None))
        self.assertTrue(any("no permalink" in e for e in r.errors), r.errors)

    def test_malformed_permalink_fails(self):
        r = self.run_one(self.good_ref(url="https://slack.com/q5"))
        self.assertTrue(any("not a Slack permalink" in e for e in r.errors), r.errors)

    def test_history_without_a_message_ts_warns_rather_than_fails(self):
        """Records written before message_ts existed must stay valid: cite the
        question unlinked rather than failing the digest."""
        r = self.run_one(self.good_ref(url=None), ledger=self.ledger(message_ts=None))
        self.assertEqual(r.errors, [], r.errors)
        self.assertTrue(any("cannot be linked" in w for w in r.warnings), r.warnings)

    def test_a_non_remediation_topic_needs_no_reference(self):
        self.CTX = dict(TestDigestCoverage.CTX, ledger=self.ledger())
        self.assertEqual(self.run_digest([self.good_topic()]).errors, [])


class TestDigestCacheRequired(unittest.TestCase):
    """check_style globbed */digest.md for the system's whole life and never
    found one, so every digest went out unchecked. A missing cache is now an
    error — dated, because the two existing history entries have none and never
    will, and a gate that fails on its own state gets switched off."""

    def run_main(self, day):
        with tempfile.TemporaryDirectory() as d:
            day_dir = Path(d) / day
            day_dir.mkdir()
            (day_dir / "digest.json").write_text(json.dumps(
                {"slack": {"topics": [{"n": 1, "blueprint": "1.4", "angle": "delta",
                                       "source": {"heading": "03 — IAM roles",
                                                  "notion_url": "https://x"}}]}}))
            r = validate.Report()
            ctx = dict(TestDigestCoverage.CTX)
            path = day_dir / "digest.json"
            validate.check_digest(r, path, ctx)
            if not (path.parent / "digest.md").exists():
                msg = "no sibling digest.md"
                report = (r.error if path.parent.name >= validate.CACHE_REQUIRED_FROM
                          else r.warn)
                report(path.name, msg)
            return r

    def test_after_the_cutover_a_missing_cache_is_an_error(self):
        r = self.run_main("2026-09-20")
        self.assertTrue(any("digest.md" in e for e in r.errors), r.errors)

    def test_before_the_cutover_it_only_warns(self):
        r = self.run_main("2026-09-11")
        self.assertEqual(r.errors, [], r.errors)
        self.assertTrue(any("digest.md" in w for w in r.warnings), r.warnings)

def with_source(**changes):
    """GOOD with its source fields overridden."""
    q = copy.deepcopy(GOOD)
    q["source"] = {**q["source"], **changes}
    return q


def run_ctx(question, ctx, quiz=None):
    """check_quiz over one question with an explicit ctx and quiz envelope."""
    r = validate.Report()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({**(quiz or {}), "questions": [question]}, f)
        path = Path(f.name)
    try:
        validate.check_quiz(r, path, ctx)
    finally:
        path.unlink()
    return r


class TestAnchor(unittest.TestCase):
    """The anchor is the only check that reads the material rather than metadata
    about it. Everything else a question carries -- a heading that resolves, a
    non-empty URL, services in the AWS map -- is satisfied perfectly by a
    question composed from general GCP knowledge. docs/decisions.md, "The prose
    was never sourced"."""

    def test_verbatim_anchor_passes(self):
        self.assertFalse(run(copy.deepcopy(GOOD)).errors)

    def test_a_paraphrase_fails(self):
        """The load-bearing test. _norm folds markup; if it ever folds a WORD,
        the gate stops distinguishing sourced prose from invented prose and this
        is what notices."""
        for bad in ("The quick brown fox leaps over the lazy dog — twice, on a Tuesday",
                    "The quick brown foxes jump over the lazy dog — twice, on a Tuesday",
                    "Twice on a Tuesday, the quick brown fox jumps over the lazy dog"):
            with self.subTest(bad=bad):
                r = run(with_source(anchor=bad))
                self.assertTrue(any("not verbatim" in m for m in r.errors), r.errors)

    def test_markup_variance_still_matches(self):
        """How a line is quoted differs from how the cache stores it. None of
        these change a word, so none of them may fail."""
        for ok in (
            "The quick brown fox jumps over the lazy dog - twice, on a Tuesday",
            "The quick brown fox jumps over the lazy dog—twice, on a Tuesday",
            "**The quick brown fox** jumps over the lazy dog — twice, on a Tuesday",
            "The quick brown fox jumps over the\nlazy dog — twice, on a Tuesday",
            "the QUICK brown fox jumps over the lazy dog — twice, on a Tuesday",
        ):
            with self.subTest(ok=ok[:40]):
                self.assertFalse(run(with_source(anchor=ok)).errors)

    def test_typographic_quotes_match_straight_ones(self):
        """The cache has curly quotes; a quote of it may not. Neither changes a
        word, so neither may fail."""
        self.assertFalse(run(with_source(
            anchor='a third one after that mentions "a phrase in typographic '
                   'quotes" which the normaliser has to see through')).errors)

    def test_an_anchor_from_a_different_section_fails(self):
        """Real text on the right page, but not under the heading cited. Same
        class of error as citing the wrong page, one level down."""
        r = run(with_source(anchor="Fourteen words of placeholder, which is not "
                                   "enough to build any question on."))
        self.assertTrue(any("not verbatim" in m for m in r.errors), r.errors)

    def test_a_missing_anchor_fails(self):
        r = run(with_source(anchor=""))
        self.assertTrue(any("no source.anchor" in m for m in r.errors), r.errors)

    def test_too_short_to_be_a_claim_fails(self):
        r = run(with_source(anchor="The quick brown fox"))
        self.assertTrue(any("term, not a claim" in m for m in r.errors), r.errors)

    def test_no_cached_page_is_an_error_not_a_warning(self):
        """Deliberately stricter than the digest's locator check. daily-quiz must
        cache every page it asks about, so an absent cache at validate time means
        the question was written without reading the material -- and a gate that
        degrades to a warning in the cloud is a gate that never runs there."""
        r = run_ctx(copy.deepcopy(GOOD), {**CTX, "page_cache": {}})
        self.assertTrue(any("no cached text" in m for m in r.errors), r.errors)

    def test_history_written_before_the_checks_existed_only_warns(self):
        """Otherwise validate.py goes red on the system's own history and stays
        red, which is how a gate gets switched off. Same cutover as
        CACHE_REQUIRED_FROM."""
        r = validate.Report()
        with tempfile.TemporaryDirectory() as d:
            day = Path(d) / "2026-09-10"
            day.mkdir()
            (day / "quiz.json").write_text(json.dumps(
                {"questions": [with_source(anchor="")]}))
            validate.check_quiz(r, day / "quiz.json", CTX)
        self.assertFalse([m for m in r.errors if "anchor" in m], r.errors)
        self.assertTrue(any("anchor" in m for m in r.warnings), r.warnings)

    def test_a_directory_that_is_not_a_date_is_checked_in_full(self):
        """"The folder name did not sort like a date" must never be a way for a
        live quiz to skip the gate."""
        r = validate.Report()
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "quiz.json").write_text(json.dumps(
                {"questions": [with_source(anchor="")]}))
            validate.check_quiz(r, Path(d) / "quiz.json", CTX)
        self.assertTrue(any("anchor" in m for m in r.errors), r.errors)


class TestThinMaterial(unittest.TestCase):
    """A section of sixteen words is a legal citation, and a four-sentence
    scenario built on one can only be invention."""

    RATIO = {"schedule": {"quiz": {"min_source_ratio": 1.5}}}

    def test_a_question_may_not_outgrow_its_source(self):
        q = with_source(heading=THIN_HEADING)
        r = run_ctx(q, {**CTX, **self.RATIO,
                        "headings": {HEADING, THIN_HEADING},
                        "page_headings": {PAGE_TITLE: {HEADING, THIN_HEADING}}})
        self.assertTrue(any("words of material" in m for m in r.errors), r.errors)

    def test_a_section_with_enough_material_passes(self):
        self.assertFalse(run_ctx(copy.deepcopy(GOOD), {**CTX, **self.RATIO}).errors)

    def test_no_configured_ratio_means_no_ratio_check(self):
        q = with_source(heading=THIN_HEADING, anchor=ANCHOR)
        r = run_ctx(q, {**CTX, "headings": {HEADING, THIN_HEADING},
                        "page_headings": {PAGE_TITLE: {HEADING, THIN_HEADING}}})
        self.assertFalse([m for m in r.errors if "words of material" in m])


class TestQuizCoverage(unittest.TestCase):
    """CLAUDE.md rule 3 covers quizzing as well as teaching. check_quiz never
    read q["blueprint"] at all, so a question on an UNCOVERED subsection
    validated clean."""

    def test_uncovered_subsection_fails(self):
        r = run_ctx(mutate(blueprint="4.1"),
                    {**CTX, "covered_subsections": {"1.4"}})
        self.assertTrue(any("not covered" in m for m in r.errors), r.errors)

    def test_missing_blueprint_fails(self):
        q = copy.deepcopy(GOOD)
        del q["blueprint"]
        r = run_ctx(q, {**CTX, "covered_subsections": {"1.4"}})
        self.assertTrue(any("no blueprint" in m for m in r.errors), r.errors)

    def test_covered_subsection_passes(self):
        self.assertFalse(run_ctx(copy.deepcopy(GOOD),
                                 {**CTX, "covered_subsections": {"1.4"}}).errors)


class TestPageHeadingAgreement(unittest.TestCase):
    """Both halves of a citation resolving separately is not the same as the
    pair being real. A reader following a mismatched pair lands on a page the
    answer is not on."""

    def test_right_heading_under_the_wrong_page_fails(self):
        r = run_ctx(copy.deepcopy(GOOD),
                    {**CTX, "page_headings": {PAGE_TITLE: {"04 — Service accounts"}}})
        self.assertTrue(any("not on that page" in m for m in r.errors), r.errors)

    def test_a_page_absent_from_the_index_fails(self):
        r = run_ctx(copy.deepcopy(GOOD),
                    {**CTX, "page_headings": {"Module 3": {HEADING}}})
        self.assertTrue(any("not in knowledge/index.json" in m for m in r.errors),
                        r.errors)

    def test_flat_set_only_still_passes(self):
        """Callers injecting just `headings` keep working — that is every
        existing digest test."""
        ctx = {k: v for k, v in CTX.items() if k != "page_headings"}
        self.assertFalse(run_ctx(copy.deepcopy(GOOD), ctx).errors)


class TestShortQuiz(unittest.TestCase):
    """Posting short is the INTENDED outcome of rejecting what cannot be
    anchored. Posting short silently is not: the learner asked not to be served
    questions the course does not support, and a seven-question quiz that says
    nothing is indistinguishable from a broken generator."""

    SCHED = {"schedule": {"quiz": {"questions": 10,
                                   "depth": {"bare": 1, "mid": 6, "deep": 3}}}}

    def quiz(self, n, **envelope):
        r = validate.Report()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({**envelope,
                       "questions": [copy.deepcopy(GOOD) for _ in range(n)]}, f)
            path = Path(f.name)
        try:
            validate.check_quiz(r, path, {**CTX, **self.SCHED})
        finally:
            path.unlink()
        return r

    def test_short_and_silent_fails(self):
        r = self.quiz(1)
        self.assertTrue(any("short_reason" in m for m in r.errors), r.errors)

    def test_short_and_said_so_passes(self):
        r = self.quiz(1, short_reason="Two sections hold too little material.")
        self.assertFalse([m for m in r.errors if "short_reason" in m], r.errors)

    def test_over_posting_fails(self):
        r = self.quiz(11, short_reason="n/a")
        self.assertTrue(any("configured 10" in m for m in r.errors), r.errors)

    def test_a_short_set_does_not_warn_about_an_unreachable_mix(self):
        """The configured integers cannot be met on a set that is deliberately
        not full. Warning every time trains the reader to ignore it."""
        r = self.quiz(1, short_reason="thin material")
        self.assertFalse([m for m in r.warnings if "depth mix" in m], r.warnings)

    def test_but_a_band_running_over_its_share_still_warns(self):
        """Thin material producing heavy scenarios is the failure this whole gate
        exists for, so it stays caught even on a short set."""
        deep = mutate(depth="deep", scenario="One thing. Two things. Three. Four.")
        r = validate.Report()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"short_reason": "thin",
                       "questions": [copy.deepcopy(deep), copy.deepcopy(deep)]}, f)
            path = Path(f.name)
        try:
            validate.check_quiz(r, path, {**CTX, **self.SCHED})
        finally:
            path.unlink()
        self.assertTrue(any("configured mix allows" in m for m in r.warnings),
                        r.warnings)
