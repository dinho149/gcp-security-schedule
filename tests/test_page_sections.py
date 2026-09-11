"""Heading depth is not consistent across the cached pages.

The three module pages put index headings at `#` with `##` children; the AI
review page puts them at `##` with `###` children. A parser fixed at one depth
returns nothing for the other, and the failure is silent -- the locator simply
stops being offered rather than being visibly wrong.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from page_sections import (  # noqa: E402
    bodies, parse, section_text, subheadings, words)

H1_PAGE = """# 01 — Virtual private cloud networking

## What is a VPC?
Text.

## Example: subnets spanning zones
Text.

### A detail below the sub-heading
Not a navigation target.

# 02 — Compute Engine

## What is Compute Engine?
Text.
"""

H2_PAGE = """> Course summary notes.

## How AI models work

### Creation
Text.

### Use
Text.

## Three forms of AI security
Text with no children.
"""


class TestParse(unittest.TestCase):
    def test_hash_one_page(self):
        got = parse(H1_PAGE)
        self.assertEqual(got["01 — Virtual private cloud networking"],
                         ["What is a VPC?", "Example: subnets spanning zones"])
        self.assertEqual(got["02 — Compute Engine"], ["What is Compute Engine?"])

    def test_hash_two_page(self):
        got = parse(H2_PAGE)
        self.assertEqual(got["How AI models work"], ["Creation", "Use"])

    def test_only_the_immediate_child_depth_is_returned(self):
        """A `###` under a `##` is detail within that sub-heading, not a
        separate place to send the reader."""
        self.assertNotIn("A detail below the sub-heading",
                         parse(H1_PAGE)["01 — Virtual private cloud networking"])

    def test_section_with_no_children_is_empty_not_missing(self):
        got = parse(H2_PAGE)
        self.assertIn("Three forms of AI security", got)
        self.assertEqual(got["Three forms of AI security"], [])

    def test_headings_inside_a_code_fence_are_not_headings(self):
        md = "# Real\n\n```\n# Not a heading\n```\n\n## Child\n"
        self.assertEqual(parse(md)["Real"], ["Child"])

    def test_unknown_heading_is_absent(self):
        self.assertNotIn("Module quiz", parse(H1_PAGE))


class TestSubheadings(unittest.TestCase):
    def test_missing_page_is_empty_not_an_error(self):
        """A cloud run hydrates only the pages it cites, so an absent cache is
        normal. validate.py needs to tell 'absent' from 'wrong'."""
        self.assertEqual(subheadings(Path("knowledge/pages/nope.md"), "x"), [])

    def test_unknown_heading_is_empty(self):
        page = ROOT / "knowledge/pages/module-3-virtual-machines-and-networks-in-the-cloud.md"
        if not page.exists():
            self.skipTest("cached page is gitignored and absent")
        self.assertEqual(subheadings(page, "Not a real heading"), [])

    def test_real_page_resolves(self):
        page = ROOT / "knowledge/pages/module-3-virtual-machines-and-networks-in-the-cloud.md"
        if not page.exists():
            self.skipTest("cached page is gitignored and absent")
        subs = subheadings(page, "01 — Virtual private cloud networking")
        self.assertIn("Example: subnets spanning zones", subs)


if __name__ == "__main__":
    unittest.main()


class TestBodies(unittest.TestCase):
    """The body is what the anchor and the thin-material gate read."""

    def test_a_section_owns_its_subheadings_prose(self):
        body = bodies(H1_PAGE)["01 — Virtual private cloud networking"]
        self.assertIn("Not a navigation target.", body)

    def test_but_not_the_subheading_lines_themselves(self):
        """House style §7: a heading is a navigation aid, not an exam fact. So a
        quiz can never anchor a question to one."""
        body = bodies(H1_PAGE)["01 — Virtual private cloud networking"]
        self.assertNotIn("What is a VPC?", body)
        self.assertNotIn("#", body)

    def test_the_next_same_depth_heading_ends_it(self):
        body = bodies(H1_PAGE)["01 — Virtual private cloud networking"]
        self.assertNotIn("What is Compute Engine?", body)

    def test_level_relative_on_the_hash_two_page(self):
        """The AI-review page puts sections at ## with ### children. A parser
        fixed at one depth returns nothing here, silently."""
        body = bodies(H2_PAGE)["How AI models work"]
        self.assertIn("Text.", body)
        self.assertNotIn("Three forms of AI security", body)

    def test_fenced_content_stays_in_the_body(self):
        md = "# Real\n\nBefore.\n\n```\n# Not a heading\n```\n"
        self.assertIn("# Not a heading", bodies(md)["Real"])


class TestSectionText(unittest.TestCase):
    """None means "cannot answer"; "" means "answered: nothing there". A caller
    that conflates them turns every check that reads the text into a no-op."""

    def test_missing_page_is_none(self):
        self.assertIsNone(section_text(Path("knowledge/pages/nope.md"), "x"))

    def test_unknown_heading_is_none(self):
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "p.md"
            page.write_text(H1_PAGE)
            self.assertIsNone(section_text(page, "Not a real heading"))

    def test_empty_section_is_empty_string_not_none(self):
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "p.md"
            page.write_text("# Empty\n\n# Next\nText.\n")
            self.assertEqual(section_text(page, "Empty"), "")

    def test_words_counts_the_body(self):
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "p.md"
            page.write_text("# H\n\none two three four\n")
            self.assertEqual(words(page, "H"), 4)
            self.assertIsNone(words(page, "Nope"))
