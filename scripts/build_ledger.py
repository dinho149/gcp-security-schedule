#!/usr/bin/env python3
"""Rebuild state.local/ledger.json from posted history.

The ledger answers "what have we already said?" — which sections were taught,
from which angle, and which questions were asked with what outcome.

It is DERIVED, never hand-edited. It is rebuilt by scanning
state.local/history/*/{digest,quiz,results}.json, so it cannot drift from what
was actually posted, and deleting it loses nothing.

    .venv/bin/python scripts/build_ledger.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "state.local/history"
LEDGER = ROOT / "state.local/ledger.json"


def section_key(source: dict) -> str:
    """Stable identity for a taught section."""
    return f"{source.get('page', '?')}::{source.get('heading', '?')}"


def fingerprint(question: dict) -> str:
    """Identity of a question, insensitive to formatting and option order.

    Option order is sorted deliberately: shuffling the same four options is the
    same question, and must not read as a new one.
    """
    stem = re.sub(r"\s+", " ", (question.get("stem") or "")).strip().lower()
    scenario = re.sub(r"\s+", " ", (question.get("scenario") or "")).strip().lower()
    opts = sorted(re.sub(r"\s+", " ", o).strip().lower()
                  for o in question.get("options", []))
    payload = "|".join([scenario, stem, *opts])
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build() -> dict:
    sections: dict[str, dict] = {}
    questions: dict[str, dict] = {}

    for day_dir in sorted(HISTORY.glob("*")) if HISTORY.exists() else []:
        if not day_dir.is_dir():
            continue
        date = day_dir.name

        # ── taught sections ────────────────────────────────────────────────
        digest_file = day_dir / "digest.json"
        if digest_file.exists():
            digest = json.loads(digest_file.read_text())
            for topic in (digest.get("slack") or {}).get("topics", []):
                # A retracted topic was withdrawn, so it must not count as taught
                # — otherwise the ledger believes that ground is covered and the
                # section never gets taught properly.
                if topic.get("retracted"):
                    continue
                src = topic.get("source") or {}
                if not src.get("heading"):
                    continue
                key = section_key(src)
                entry = sections.setdefault(key, {
                    "page": src.get("page"), "heading": src.get("heading"),
                    "notion_url": src.get("notion_url"),
                    "blueprint": [], "angles_used": [], "taught": [],
                })
                if bp := topic.get("blueprint"):
                    if bp not in entry["blueprint"]:
                        entry["blueprint"].append(bp)
                angle = topic.get("angle", "delta")
                if angle not in entry["angles_used"]:
                    entry["angles_used"].append(angle)
                entry["taught"].append({"date": date, "angle": angle})
                entry["last_taught"] = date

        # ── asked questions ────────────────────────────────────────────────
        quiz_file = day_dir / "quiz.json"
        if quiz_file.exists():
            quiz = json.loads(quiz_file.read_text())
            for q in quiz.get("questions", []):
                fp = fingerprint(q)
                entry = questions.setdefault(fp, {
                    "blueprint": q.get("blueprint"),
                    "section": section_key(q.get("source") or {}),
                    "asked": [], "outcomes": [], "retested": False,
                })
                if date not in entry["asked"]:
                    entry["asked"].append(date)
                if q.get("is_retest"):
                    entry["retested"] = True

        # ── outcomes ───────────────────────────────────────────────────────
        results_file = day_dir / "results.json"
        if results_file.exists():
            results = json.loads(results_file.read_text())
            quiz = json.loads(quiz_file.read_text()) if quiz_file.exists() else {"questions": []}
            by_n = {q.get("n"): fingerprint(q) for q in quiz.get("questions", [])}
            for graded in results.get("questions", []):
                fp = by_n.get(graded.get("n"))
                if fp and fp in questions:
                    questions[fp]["outcomes"].append(graded.get("outcome", "unknown"))

    return {
        "_generated_from": str(HISTORY.relative_to(ROOT)),
        "_note": "Derived from posted history. Do not hand-edit; rerun build_ledger.py.",
        "sections": sections,
        "questions": questions,
    }


def main() -> int:
    ledger = build()
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")

    secs, qs = ledger["sections"], ledger["questions"]
    passes = sum(len(s["taught"]) for s in secs.values())
    wrong = sum(1 for q in qs.values() if "wrong" in q["outcomes"])
    print(f"sections taught  : {len(secs)}  ({passes} pass(es) total)")
    print(f"questions asked  : {len(qs)}  ({wrong} answered wrong)")
    if secs:
        print("angles used:")
        for key, s in sorted(secs.items()):
            print(f"  {', '.join(s['angles_used']):<24} {key}")
    print(f"-> {LEDGER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
