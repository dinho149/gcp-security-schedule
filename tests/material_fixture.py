#!/usr/bin/env python3
"""A cached course page on disk, for tests that read the material.

The anchor and ratio checks open `knowledge/pages/<slug>.md` and read it. That
tree is gitignored and absent in CI, so a test that relied on it would pass
vacuously there -- the same trap `CTX` in test_validate.py already documents for
the AWS map. This writes a real page to a temp directory instead, and the checks
resolve it because an ABSOLUTE cache path passes through `_cache_path` unchanged.

**The prose here is invented, and must stay invented.** `knowledge/` is
gitignored because the course material is not ours to republish, and a fixture is
a tracked file. `leakcheck.py` catches Notion ids, not quoted course text, so
nothing catches this for you. What the fixture has to reproduce is the SHAPE the
checks care about -- heading depth, an em dash, a typographic quote, bold, a
table row, a list -- not anything the course actually says.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

PAGE_TITLE = "Module 2"
HEADING = "03 — IAM roles"
THIN_HEADING = "09 — A section with almost nothing in it"

PAGE_TEXT = """<!-- Cached by sync-notion. Source of record is Notion. -->

# 03 — IAM roles

Placeholder prose standing in for a course section. It exists so the anchor check
has real text to search, and it says nothing about any actual product.

## The first sub-heading
Three invented things live here, listed so the enumeration rules have something
to look at: the first thing, the second thing, and the third thing.

| Column | Column | Column |
|---|---|---|
| **Alpha** | Placeholder | Invented |
| **Beta** | Placeholder | Invented |

## The second sub-heading
The quick brown fox jumps over the lazy dog — twice, on a Tuesday, for no
particular reason anyone has written down. A second sentence follows it so that
the section has more than one line of prose to anchor against, and a third one
after that mentions “a phrase in typographic quotes” which the normaliser has to
see through. The paragraph ends with a list:

- one placeholder item
- a second placeholder item
- a third placeholder item

# 09 — A section with almost nothing in it
Fourteen words of placeholder, which is not enough to build any question on.
"""

# 13 words, verbatim from "The second sub-heading". Deliberately spans an em dash
# and a comma, because both are things `_norm` must see through.
ANCHOR = "The quick brown fox jumps over the lazy dog — twice, on a Tuesday"

_DIR = Path(tempfile.mkdtemp(prefix="gcp-material-fixture-"))
PAGE = _DIR / "module-2.md"
PAGE.write_text(PAGE_TEXT)

SOURCE = {
    "page": PAGE_TITLE,
    "heading": HEADING,
    "notion_url": "https://app.notion.com/p/x",
    "locator": {"subheading": "The second sub-heading",
                "look_for": "the paragraph before the list"},
    "anchor": ANCHOR,
}

# Absolute, so `Path("knowledge") / cache` resolves straight back to the fixture.
PAGE_CACHE = {PAGE_TITLE: str(PAGE)}
