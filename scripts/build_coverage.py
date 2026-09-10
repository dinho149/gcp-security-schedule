#!/usr/bin/env python3
"""Generate knowledge/coverage.md — blueprint subsection -> is it teachable yet?

Drives quiz sampling: weights are renormalised over covered subsections only, so
an untouched exam section contributes nothing until its material lands in Notion.

    .venv/bin/python scripts/build_coverage.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    bp = yaml.safe_load((ROOT / "config/exam-blueprint.yaml").read_text())
    idx = json.loads((ROOT / "knowledge/index.json").read_text())

    sources: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for course in idx["courses"]:
        for page in course["material"]["pages"]:
            if not page["ingested"]:
                continue
            for s in page["sections"]:
                for tag in s["exam_tags"]:
                    sources[tag].append((page["title"], s["heading"], page["url"]))

    lines = [
        "# Coverage — exam blueprint vs. ingested material",
        "",
        f"Generated {idx['_generated']} from `knowledge/index.json` and `config/exam-blueprint.yaml`.",
        "**Do not edit by hand** — run `scripts/build_coverage.py`.",
        "",
        "A quiz may only ask about a subsection marked ✅. Sections fill in",
        "automatically as you add training to Notion; no code change needed.",
        "",
    ]

    total_available = 0.0
    per_section_rows = []
    for sec in bp["sections"]:
        share = sec["weight"] / len(sec["subsections"])
        n_cov = sum(1 for sub in sec["subsections"] if sources.get(sub["id"]))
        avail = share * n_cov
        total_available += avail
        per_section_rows.append(
            (sec["square"], sec["id"], sec["title"], sec["weight"], n_cov,
             len(sec["subsections"]), avail)
        )

    lines += ["## Summary", "",
              "| | Section | Exam weight | Subsections covered | Reachable weight |",
              "|---|---|---|---|---|"]
    for sq, sid, title, w, n, tot, avail in per_section_rows:
        lines.append(f"| {sq} | **{sid}** {title} | {w}% | {n}/{tot} | {avail:.1f}% |")
    lines += ["", f"**Total exam weight currently reachable: {total_available:.1f}%** "
                  f"of 100%.", ""]

    if total_available < 100:
        lines += [
            f"> The remaining {100 - total_available:.1f}% is not yet teachable from your "
            "material. Quiz weights are renormalised over the reachable portion, so today's "
            "quizzes over-represent what you have studied — by design.",
            "",
        ]

    lines += ["## Detail", ""]
    for sec in bp["sections"]:
        lines += [f"### {sec['square']} Section {sec['id']} — {sec['title']} ({sec['weight']}%)", ""]
        for sub in sec["subsections"]:
            srcs = sources.get(sub["id"], [])
            mark = "✅" if srcs else "⬜"
            lines.append(f"- {mark} **{sub['id']} {sub['title']}**")
            for page, heading, url in sorted(set(srcs)):
                lines.append(f"  - [{page} → \"{heading}\"]({url})")
            if not srcs:
                lines.append("  - *no ingested material*")
        lines.append("")

    pending = [
        (c["title"], p["title"], p["url"])
        for c in idx["courses"] for p in c["material"]["pages"] if not p["ingested"]
    ]
    if pending:
        lines += ["## Known but not yet ingested", "",
                  "These pages exist in Notion but have not been read, so nothing may cite them.", ""]
        for course, title, url in pending:
            lines.append(f"- [{title}]({url}) — *{course}*")
        lines.append("")

    out = ROOT / "knowledge/coverage.md"
    out.write_text("\n".join(lines))
    print(f"reachable exam weight: {total_available:.1f}%")
    print(f"covered subsections  : {sum(1 for s in sources if s)}/"
          f"{sum(len(s['subsections']) for s in bp['sections'])}")
    print(f"pending pages        : {len(pending)}")
    print(f"-> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
