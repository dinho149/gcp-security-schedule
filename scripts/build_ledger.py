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


def retracted_ts(digest: dict) -> set:
    """Slack timestamps of topic messages withdrawn after posting.

    A withdrawal is recorded two ways and both must be honoured: a `retracted`
    flag on the topic itself, and a top-level `retractions[]` audit entry. Only
    the first was ever checked, so a topic withdrawn the second way still
    counted as taught -- the ledger would believe ground was covered that had in
    fact been pulled.

    Match on `ts`, never on the topic NUMBER, even though `retractions[]` records
    both. A withdrawn topic is usually replaced, and the replacement reuses the
    same number -- 2026-09-11 retracted topic 4 at ts 1789073167 and reposted a
    different topic 4 at ts 1789073437. Keying on the number drops the
    replacement and undercounts what was taught, which is the same class of error
    as counting the retraction, pointing the other way.
    """
    return {r.get("ts") for r in (digest.get("retractions") or []) if r.get("ts")}


def quiz_sets(day_dir: Path) -> list[tuple[Path, Path]]:
    """Every quiz posted on a day, paired with its results.

    `quiz.json` is the scheduled set; `quiz-<HHMM>.json` are on-demand ones.
    schedule.yaml sets `on_demand.counts_toward_mastery: true`, but only the
    bare name was ever globbed, so a second quiz in a day could not be recorded
    and ad-hoc practice moved nothing.

    Scheduled first, then on-demand by ascending suffix, so replay order is
    total and a rebuild is reproducible.
    """
    sets = []
    if (scheduled := day_dir / "quiz.json").exists():
        sets.append((scheduled, day_dir / "results.json"))
    for quiz in sorted(day_dir.glob("quiz-*.json")):
        sets.append((quiz, day_dir / f"results-{quiz.stem.split('-', 1)[1]}.json"))
    return sets


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
    untagged: list[str] = []

    for day_dir in sorted(HISTORY.glob("*")) if HISTORY.exists() else []:
        if not day_dir.is_dir():
            continue
        date = day_dir.name

        # ── taught sections ────────────────────────────────────────────────
        digest_file = day_dir / "digest.json"
        if digest_file.exists():
            digest = json.loads(digest_file.read_text())
            retracted = retracted_ts(digest)
            for topic in (digest.get("slack") or {}).get("topics", []):
                # A retracted topic was withdrawn, so it must not count as taught
                # — otherwise the ledger believes that ground is covered and the
                # section never gets taught properly.
                if topic.get("retracted") or topic.get("ts") in retracted:
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
                # It was taught; from which angle may be unknown. Defaulting to
                # "delta" claimed the AWS-delta pass -- the highest-value first
                # pass for this reader -- on sections that had never had one, and
                # selection would then skip straight to a weaker angle. Record
                # the pass, leave the angle unclaimed, and say so loudly.
                angle = topic.get("angle")
                if angle:
                    if angle not in entry["angles_used"]:
                        entry["angles_used"].append(angle)
                else:
                    entry["needs_angle"] = True
                    untagged.append(f"{date} topic {topic.get('n', '?')} — "
                                    f"{src.get('heading')}")
                entry["taught"].append({"date": date, "angle": angle})
                entry["last_taught"] = date

        # ── asked questions, and their outcomes ────────────────────────────
        for quiz_file, results_file in quiz_sets(day_dir):
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

            if not results_file.exists():
                continue
            results = json.loads(results_file.read_text())
            by_n = {q.get("n"): fingerprint(q) for q in quiz.get("questions", [])}
            for graded in results.get("questions", []):
                fp = by_n.get(graded.get("n"))
                if fp and fp in questions:
                    questions[fp]["outcomes"].append(graded.get("outcome", "unknown"))

    return {
        # relative_to fails when HISTORY is redirected (tests inject a tmpdir),
        # and a cosmetic header must never be the thing that breaks a rebuild.
        "_generated_from": str(HISTORY.relative_to(ROOT)
                               if HISTORY.is_relative_to(ROOT) else HISTORY),
        "_note": "Derived from posted history. Do not hand-edit; rerun build_ledger.py.",
        "sections": sections,
        "questions": questions,
        "untagged_topics": untagged,
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
    if untagged := ledger["untagged_topics"]:
        print(f"\nWARNING: {len(untagged)} topic(s) carry no angle. They count as "
              f"taught but claim no angle, so the section stays eligible:")
        for line in untagged:
            print(f"  {line}")
    print(f"-> {LEDGER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
