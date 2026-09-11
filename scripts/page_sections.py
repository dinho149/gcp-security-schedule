#!/usr/bin/env python3
"""Find the sub-headings, and the body text, under a section of a cached page.

A citation used to point at a page and stop: `Module 3 -> "01 -- Virtual private
cloud networking"` is a 200-line page, and the reader had to hunt. The page text
already says where to look; it just never reached the citation.

The bodies are here for a second reason. A quiz question must be anchored to a
verbatim line of the section it cites, and a section too thin to support a
question must not be asked about at all -- `knowledge/pages/introduction-to-
security-in-the-world-of-ai-review.md` has a tagged section of SIXTEEN words, and
a 4-sentence scenario built on it can only be invention. Both need the body, not
just the heading, and both need it scoped to ONE section rather than the page.

The parse is LEVEL-RELATIVE, never hard-coded to `##`. Heading depth is not
consistent across the cached pages: the three module pages put index headings at
`#` with `##` children, while `introduction-to-security-in-the-world-of-ai-review`
puts them at `##` with `###` children. A parser fixed at one depth silently
returns nothing for that page, which is the failure mode where a locator quietly
stops being offered rather than being visibly wrong.

    .venv/bin/python scripts/page_sections.py --page knowledge/pages/<slug>.md
    .venv/bin/python scripts/page_sections.py --page <p> --heading "05 -- Security"
    .venv/bin/python scripts/page_sections.py --page <p> --words
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")


def _walk(md: str) -> list[tuple[int, str, int, int]]:
    """(depth, text, body_start, body_end) for every heading outside a fence.

    `body_start`/`body_end` are half-open line indices into `md.split("\\n")`.
    A heading owns everything down to the next heading at its own depth or
    shallower -- its own prose AND its sub-headings' prose. That is the same
    ownership rule `parse()` uses to decide which sub-headings belong to it, so
    the two can never disagree about where a section ends.
    """
    lines = md.split("\n")
    heads: list[tuple[int, int, str]] = []  # (line index, depth, text)
    in_fence = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m:
            heads.append((i, len(m.group(1)), m.group(2).strip()))

    out: list[tuple[int, str, int, int]] = []
    for j, (i, depth, text) in enumerate(heads):
        end = len(lines)
        for i2, depth2, _ in heads[j + 1:]:
            if depth2 <= depth:
                end = i2
                break
        out.append((depth, text, i + 1, end))
    return out


def parse(md: str) -> dict[str, list[str]]:
    """Cached page markdown -> {section heading: [sub-headings]}.

    Only the immediate child depth is returned: deeper levels are detail within a
    sub-heading, not a place to navigate to.
    """
    heads = _walk(md)
    out: dict[str, list[str]] = {}
    for i, (depth, text, _, _) in enumerate(heads):
        subs: list[str] = []
        child_depth = None
        for sub_depth, sub_text, _, _ in heads[i + 1:]:
            if sub_depth <= depth:
                break
            if child_depth is None:
                child_depth = sub_depth
            if sub_depth == child_depth:
                subs.append(sub_text)
        # Later duplicates of a heading do not silently clobber the first.
        out.setdefault(text, subs)
    return out


def bodies(md: str) -> dict[str, str]:
    """Cached page markdown -> {section heading: body text}.

    The body keeps every sub-heading's PROSE and drops the sub-heading LINES. A
    reader sent to a section reads all of it, so the prose belongs; the heading
    text does not, because house style §7 already holds that a heading is a
    navigation aid and not an exam fact. Dropping it makes that mechanical: a
    quiz cannot anchor a question to a heading, only to something the page says.
    """
    lines = md.split("\n")
    walked = _walk(md)
    # A heading's body starts on the line after it, so start - 1 IS that heading.
    heading_lines = {start - 1 for _, _, start, _ in walked}
    out: dict[str, str] = {}
    for _, text, start, end in walked:
        out.setdefault(text, "\n".join(
            ln for i, ln in enumerate(lines[start:end], start)
            if i not in heading_lines).strip())
    return out


def _read(page_cache: Path) -> str | None:
    p = page_cache if page_cache.is_absolute() else ROOT / page_cache
    return p.read_text() if p.exists() else None


def subheadings(page_cache: Path, heading: str) -> list[str]:
    """[] when the page is missing or the heading is not on it.

    A cloud run fetches only the pages it cites, so an absent cache is normal
    and must not raise -- validate.py distinguishes "absent" from "wrong".
    """
    md = _read(page_cache)
    return [] if md is None else parse(md).get(heading, [])


def section_text(page_cache: Path, heading: str) -> str | None:
    """The body of one section, or None.

    None means "cannot answer" -- no cached page, or no such heading on it. An
    empty string means "answered: that section has no body". Callers MUST tell
    those apart: treating a missing cache as an empty section would silently pass
    every check that reads the text, which is how a gate becomes a no-op.
    """
    md = _read(page_cache)
    return None if md is None else bodies(md).get(heading)


def words(page_cache: Path, heading: str) -> int | None:
    """Word count of a section's body, or None when it cannot be answered."""
    body = section_text(page_cache, heading)
    return None if body is None else len(body.split())


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--page", required=True, help="path to a cached page markdown file")
    ap.add_argument("--heading", help="one section; omit to list every section")
    ap.add_argument("--words", action="store_true",
                    help="report body word counts instead of sub-headings — how "
                         "much material a section actually has to be asked about")
    args = ap.parse_args(argv)

    p = Path(args.page)
    p = p if p.is_absolute() else ROOT / p
    if not p.exists():
        print(f"no cached page at {args.page}", file=sys.stderr)
        return 2

    md = p.read_text()
    parsed = {h: len(b.split()) for h, b in bodies(md).items()} if args.words \
        else parse(md)
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
