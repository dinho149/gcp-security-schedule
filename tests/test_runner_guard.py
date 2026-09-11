#!/usr/bin/env python3
"""Tests for the stale-laptop guard.

Slack timestamps are decimal strings of equal width, so string and numeric
ordering happen to agree on well-formed input -- the float parse is not doing
clever work there, and this file does not pretend otherwise. What it does buy is
the two cases that are not well-formed: a watermark that will not parse, and a
watermark that is absent. Both must block rather than raise, because this guard
runs before a run that would otherwise post to Slack.

The direction of the two clean cases is the part worth pinning down. Behind
blocks; ahead does not, because ahead means local work that has not been
mirrored yet, and refusing to run would strand it.

    .venv/bin/python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import runner_guard  # noqa: E402


class TestCompare(unittest.TestCase):
    def test_in_step_is_safe(self):
        ok, why = runner_guard.compare("1789111712.617369", "1789111712.617369")
        self.assertTrue(ok)
        self.assertIn("in step", why)

    def test_behind_is_blocked(self):
        ok, why = runner_guard.compare("1789111712.617369", "1789222222.000000")
        self.assertFalse(ok)
        self.assertIn("behind", why)

    def test_ahead_is_allowed_but_flagged(self):
        """Ahead means unmirrored local work -- run, but say it needs dehydrating."""
        ok, why = runner_guard.compare("1789222222.000000", "1789111712.617369")
        self.assertTrue(ok)
        self.assertIn("dehydrate", why)

    def test_compares_numerically_across_integer_widths(self):
        """Text ordering flips when the integer part gains a digit; numeric does not.

        Slack's second-count crosses ten digits into eleven eventually, and on
        that boundary the two orderings genuinely disagree: as text the shorter
        one sorts LAST, as a number it is smaller. Behind must still read behind.
        """
        local, remote = "9999999999.5", "10000000000.5"
        self.assertGreater(local, remote)            # lexically: local looks ahead
        ok, why = runner_guard.compare(local, remote)
        self.assertFalse(ok)                         # numerically it is behind
        self.assertIn("behind", why)

    def test_missing_notion_watermark_blocks(self):
        ok, why = runner_guard.compare("1789111712.617369", None)
        self.assertFalse(ok)
        self.assertIn("cannot tell", why)

    def test_missing_local_watermark_blocks(self):
        """A fresh clone has no history; the cloud has both. Do not run from here."""
        ok, why = runner_guard.compare(None, "1789111712.617369")
        self.assertFalse(ok)
        self.assertIn("never run", why)

    def test_unparseable_blocks_rather_than_crashes(self):
        ok, why = runner_guard.compare("not-a-ts", "1789111712.617369")
        self.assertFalse(ok)
        self.assertIn("unparseable", why)


if __name__ == "__main__":
    unittest.main()
