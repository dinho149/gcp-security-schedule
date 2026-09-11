"""Heading depth is not consistent across the cached pages.

The three module pages put index headings at `#` with `##` children; the AI
review page puts them at `##` with `###` children. A parser fixed at one depth
returns nothing for the other, and the failure is silent -- the locator simply
stops being offered rather than being visibly wrong.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from page_sections import parse, subheadings  # noqa: E402

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
