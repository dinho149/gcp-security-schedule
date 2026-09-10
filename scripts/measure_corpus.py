#!/usr/bin/env python3
"""Measure the official sample-question corpus and print the numbers that
reference/question-spec.md asserts.

The spec is empirical on purpose: several widely-repeated claims about GCP exam
question structure (five options for multi-select, 10-30 word options, no
near-variant distractors) are wrong. Re-run this whenever the corpus changes
instead of arguing from memory.

    .venv/bin/python scripts/measure_corpus.py
"""
from __future__ import annotations

import re
import statistics
import sys
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "reference/exemplars/official-samples.md"
OPTION_RE = re.compile(r"^([A-E])\.\s+(.*)$")


def parse(text: str) -> list[dict]:
    questions = []
    for block in re.split(r"\n## Q\d+", text)[1:]:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        options, prose = [], []
        for ln in lines:
            m = OPTION_RE.match(ln)
            if m:
                options.append(m.group(2))
            elif not ln.startswith(("#", ">", "|", "-")):
                prose.append(ln)
        body = " ".join(prose[1:]) if len(prose) > 1 else ""
        sentences = [s for s in re.split(r"(?<=[.?])\s+", body) if s]
        questions.append(
            {
                "options": options,
                "words": [len(o.split()) for o in options],
                "sentences": len(sentences),
                "stem": sentences[-1] if sentences else "",
                "multi": "(choose two)" in body.lower(),
            }
        )
    return questions


def main() -> int:
    if not CORPUS.exists():
        print(f"corpus not found: {CORPUS}", file=sys.stderr)
        print("(reference/exemplars/ is gitignored — expected on a fresh clone)", file=sys.stderr)
        return 2

    qs = parse(CORPUS.read_text())
    if not qs:
        print("no questions parsed", file=sys.stderr)
        return 1

    counts = [len(q["options"]) for q in qs]
    words = [w for q in qs for w in q["words"]]
    spreads = [max(q["words"]) - min(q["words"]) for q in qs]
    ratios = [max(q["words"]) / max(min(q["words"]), 1) for q in qs]
    sentences = [q["sentences"] for q in qs]

    def pct(vals, p):
        return sorted(vals)[min(int(p * len(vals)), len(vals) - 1)]

    print(f"questions parsed: {len(qs)}")
    print(f"multi-select:     {sum(q['multi'] for q in qs)}")
    print()
    print(f"option count:     {sorted(set(counts))}  (all-four={set(counts) == {4}})")
    print(f"option words:     min={min(words)} median={statistics.median(words)} "
          f"max={max(words)} mean={statistics.mean(words):.1f}")
    print(f"within-q spread:  median={statistics.median(spreads)} p90={pct(spreads, .9)} max={max(spreads)}")
    print(f"within-q ratio:   median={statistics.median(ratios):.2f} max={max(ratios):.2f}")
    print(f"scenario+stem:    min={min(sentences)} median={statistics.median(sentences)} max={max(sentences)}")
    print()

    depth = {"bare (0-1)": 0, "mid (2-3)": 0, "deep (4-5)": 0}
    for n in sentences:
        depth["bare (0-1)" if n <= 1 else "mid (2-3)" if n <= 3 else "deep (4-5)"] += 1
    print("scenario depth mix:")
    for k, v in depth.items():
        print(f"  {k:<12} {v:>2}  {'█' * v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
