"""A permalink is either correct or absent -- never nearly right.

A subtly wrong URL looks fine in review and lands on nothing, which is worse
than the bare "Q8" it replaced.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from slack_links import PERMALINK_RE, permalink, question_ref, workspace  # noqa: E402

WS, CHAN, TS = "a-workspace", "CTESTCHAN01", "1789071974.214939"


class TestPermalink(unittest.TestCase):
    def test_drops_the_dot_and_prefixes_p(self):
        self.assertEqual(
            permalink(WS, CHAN, TS),
            "https://a-workspace.slack.com/archives/CTESTCHAN01/p1789071974214939")

    def test_matches_the_shared_format(self):
        self.assertRegex(permalink(WS, CHAN, TS), PERMALINK_RE)

    def test_thread_form_carries_thread_ts_and_cid(self):
        url = permalink(WS, CHAN, TS, thread_ts="1789071965.891069")
        self.assertIn("thread_ts=1789071965.891069", url)
        self.assertIn(f"cid={CHAN}", url)
        self.assertRegex(url, PERMALINK_RE)

    def test_malformed_ts_yields_none_not_a_broken_url(self):
        for bad in ("", "1789071974", "1789071974.21", "not-a-ts", "1789071974,214939"):
            self.assertIsNone(permalink(WS, CHAN, bad), bad)

    def test_malformed_channel_yields_none(self):
        for bad in ("", "X0C0WD773EH", "c0c0wd773eh"):
            self.assertIsNone(permalink(WS, bad, TS), bad)

    def test_malformed_workspace_yields_none(self):
        for bad in ("", "Upper", "has space", "-leading"):
            self.assertIsNone(permalink(bad, CHAN, TS), bad)


class TestWorkspace(unittest.TestCase):
    def test_blank_raises_rather_than_guessing(self):
        with self.assertRaises(SystemExit):
            workspace({"slack": {"workspace": ""}})

    def test_non_subdomain_raises(self):
        with self.assertRaises(SystemExit):
            workspace({"slack": {"workspace": "https://x.slack.com"}})

    def test_reads_the_value(self):
        self.assertEqual(workspace({"slack": {"workspace": WS}}), WS)


class TestQuestionRef(unittest.TestCase):
    def entry(self, **miss):
        base = {"date": "2026-09-10", "n": 4, "channel_id": CHAN,
                "message_ts": TS, "answered": ["C"], "keyed": ["A"]}
        base.update(miss)
        return {"stem": "What scope does a VPC subnet have?",
                "scenario": None, "options": ["Regional", "Zonal"],
                "last_miss": base}

    def test_no_miss_is_no_reference(self):
        self.assertIsNone(question_ref({"last_miss": None}, WS))

    def test_carries_what_the_reader_actually_picked(self):
        ref = question_ref(self.entry(), WS)
        self.assertEqual(ref["n"], 4)
        self.assertEqual(ref["answered"], ["C"])
        self.assertEqual(ref["keyed"], ["A"])
        self.assertRegex(ref["url"], PERMALINK_RE)

    def test_history_without_a_message_ts_still_gives_a_reference(self):
        """Pre-message_ts history must degrade to an unlinked citation, not
        vanish: the recap is the load-bearing half, the link is the convenience."""
        ref = question_ref(self.entry(message_ts=None), WS)
        self.assertIsNotNone(ref)
        self.assertIsNone(ref["url"])
        self.assertEqual(ref["n"], 4)


if __name__ == "__main__":
    unittest.main()
