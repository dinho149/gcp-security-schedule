#!/usr/bin/env python3
"""Assemble knowledge/index.json from the Notion ingestion map.

This script is pure logic. The ingestion map — page ids, course and module
titles, section headings — lives in `knowledge/sources.local.json`, which is
gitignored, because this repository is public and that data describes a private
Notion workspace. See docs/privacy.md.

The agent (see .claude/skills/sync-notion) walks Notion and writes that map.
Anything not actually read is marked ingested=false: the grounding gate refuses
to cite a section with no ingested content, so a stub can never back a quiz
answer.

    .venv/bin/python scripts/build_index.py
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "knowledge/sources.local.json"
OUT = ROOT / "knowledge/index.json"


def main() -> int:
    if not SOURCES.exists():
        print(f"missing {SOURCES.relative_to(ROOT)}", file=sys.stderr)
        print("Run the sync-notion skill to build it, or copy "
              "config/sources.example.json and fill it in.", file=sys.stderr)
        return 2

    src = json.loads(SOURCES.read_text())
    courses = src.get("courses", [])
    if not courses:
        print("ingestion map contains no courses", file=sys.stderr)
        return 1

    doc = {
        "_generated": datetime.date.today().isoformat(),
        "_root": src.get("root", {}),
        "_note": "Sections with ingested=false are known to exist but have not been "
                 "read. The grounding gate refuses to cite them.",
        "courses": courses,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2) + "\n")

    pages = [p for c in courses for p in c["material"]["pages"]]
    done = [p for p in pages if p["ingested"]]
    secs = [s for p in done for s in p["sections"]]
    tagged = [s for s in secs if s["exam_tags"]]
    print(f"courses          : {len(courses)}")
    print(f"material pages   : {len(done)}/{len(pages)} ingested")
    print(f"sections         : {len(secs)} ({len(tagged)} mapped to blueprint)")
    print(f"blueprint tags   : {sorted({t for s in tagged for t in s['exam_tags']})}")
    print(f"not-yet-covered  : {sum('NOT-YET-COVERED' in (s.get('note') or '') for s in secs)}")
    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
