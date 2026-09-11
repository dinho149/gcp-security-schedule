#!/usr/bin/env python3
"""Find the sub-headings under a section of a cached Notion page.

A citation used to point at a page and stop: `Module 3 -> "01 -- Virtual private
cloud networking"` is a 200-line page, and the reader had to hunt. The page text
already says where to look; it just never reached the citation.

The parse is LEVEL-RELATIVE, never hard-coded to `##`. Heading depth is not
consistent across the cached pages: the three module pages put index headings at
`#` with `##` children, while `introduction-to-security-in-the-world-of-ai-review`
puts them at `##` with `###` children. A parser fixed at one depth silently
returns nothing for that page, which is the failure mode where a locator quietly
stops being offered rather than being visibly wrong.

    .venv/bin/python scripts/page_sections.py --page knowledge/pages/<slug>.md
    .venv/bin/python scripts/page_sections.py --page <p> --heading "05 -- Security"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"(?m)^\s*```")


def _headings(md: str) -> list[tuple[int, str]]:
    """(depth, text) for every heading outside a fenced code block."""
    out, in_fence, = [], False
    for line in md.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip()))
    return out


def parse(md: str) -> dict[str, list[str]]:
    """Cached page markdown -> {section heading: [sub-headings]}.

    A section owns every heading deeper than itself, up to the next heading at
    the same depth or shallower. Only the immediate child depth is returned:
    deeper levels are detail within a sub-heading, not a place to navigate to.
    """
    heads = _headings(md)
    out: dict[str, list[str]] = {}
    for i, (depth, text) in enumerate(heads):
        subs: list[str] = []
        child_depth = None
        for sub_depth, sub_text in heads[i + 1:]:
            if sub_depth <= depth:
                break
            if child_depth is None:
                child_depth = sub_depth
            if sub_depth == child_depth:
                subs.append(sub_text)
        # Later duplicates of a heading do not silently clobber the first.
        out.setdefault(text, subs)
    return out


def subheadings(page_cache: Path, heading: str) -> list[str]:
    """[] when the page is missing or the heading is not on it.

    A cloud run fetches only the pages it cites, so an absent cache is normal
    and must not raise -- validate.py distinguishes "absent" from "wrong".
    """
    p = page_cache if page_cache.is_absolute() else ROOT / page_cache
    if not p.exists():
        return []
    return parse(p.read_text()).get(heading, [])


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--page", required=True, help="path to a cached page markdown file")
    ap.add_argument("--heading", help="one section; omit to list every section")
    args = ap.parse_args(argv)

    p = Path(args.page)
    p = p if p.is_absolute() else ROOT / p
    if not p.exists():
        print(f"no cached page at {args.page}", file=sys.stderr)
        return 2

    parsed = parse(p.read_text())
    if args.heading:
        if args.heading not in parsed:
            print(f"heading {args.heading!r} is not on this page. It has: "
                  f"{sorted(parsed)}", file=sys.stderr)
            return 1
        print(json.dumps({args.heading: parsed[args.heading]}, indent=2))
    else:
        print(json.dumps(parsed, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
