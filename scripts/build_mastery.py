#!/usr/bin/env python3
"""Rebuild state.local/mastery.json — how well each topic is actually known.

Every prompt in this repo claimed to read this file. Nothing ever wrote it, and
its dimension ("per topic") was never defined, so spaced repetition and
`quiz.mix.review_due` had nothing to select from.

It is DERIVED, never hand-edited: a full replay of
state.local/history/*/{quiz,results}.json in date order, so it cannot drift from
what was actually answered and deleting it loses nothing.

Two projections of one event stream, never a sum:

    sections     "<page>::<heading>"   the unit that gets taught and scheduled
    subsections  "1.4"                 the unit exam weight attaches to

A question carries both, so neither is inferred. Scheduling is on sections
because `review_due` needs a unit a NEW question can be grounded in -- "§3.3 is
due" spans nine sections, one heading does not -- and because a question
fingerprint may be asked at most twice (validate.py), so its ladder could never
reach a third rung.

    .venv/bin/python scripts/build_mastery.py
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_ledger import quiz_sets, section_key  # noqa: E402  one definition, not two

HISTORY = ROOT / "state.local/history"
MASTERY = ROOT / "state.local/mastery.json"

# ── Scoring ────────────────────────────────────────────────────────────────
# A hinted-correct answer is half credit: grade-quiz's own rule is that
# "correct-but-hinted is not known". A skipped question is dropped entirely --
# it is an absence of evidence, not evidence of absence, and must not move a
# score OR a schedule.
CREDIT = {("correct", False): 1.0, ("correct", True): 0.5, ("wrong", False): 0.0,
          ("wrong", True): 0.0}

# ── Spaced repetition: SM-2 lite ───────────────────────────────────────────
# ease starts below SM-2's 2.5 because grading is calibrated for 4-6/10 on
# exam-level scenarios over fundamentals material; 2.5 over-spaces from day one.
EASE_START, EASE_MIN, EASE_MAX = 2.3, 1.3, 2.8
# Asymmetric on purpose: a hit can be a 1-in-4 guess, a miss cannot be.
EASE_DELTA = {1.0: +0.10, 0.5: -0.05, 0.0: -0.25}
MAX_INTERVAL = 21   # beyond three weeks is unverifiable inside a study window


def day_credit(credits: list[float]) -> float:
    """One rating per section per day, from that day's answers on it.

    Bucketed to three values rather than used as a raw mean, so the state
    machine stays exhaustively testable.
    """
    mean = sum(credits) / len(credits)
    if mean >= 1.0 - 1e-9:
        return 1.0
    return 0.0 if mean < 0.5 - 1e-9 else 0.5


def advance(state: dict, rating: float, date: str, study_days: list[str]) -> None:
    """Apply one day's rating to a section's schedule, in place."""
    state["ease"] = min(EASE_MAX, max(EASE_MIN, state["ease"] + EASE_DELTA[rating]))

    if rating == 0.0:
        state["reps"] = 0
        state["lapses"] += 1
        interval = 1
    elif rating == 0.5:
        # A hint is not knowledge, so it does not promote — but it is not a
        # lapse either. Pull the next look sooner without resetting.
        interval = max(1, int(state["interval_days"] * 0.5 + 0.5))
    else:
        state["reps"] += 1
        interval = {1: 1, 2: 3}.get(state["reps"],
                                    int(state["interval_days"] * state["ease"] + 0.5))

    state["interval_days"] = min(MAX_INTERVAL, max(1, interval))
    state["last_seen"] = date
    state["next_due"] = next_study_day(date, state["interval_days"], study_days)


def next_study_day(date: str, interval: int, study_days: list[str]) -> str:
    """Due date, advanced to the next day the learner actually studies.

    Without the snap, an interval landing on a Saturday is permanently stale and
    `review_due` never fires for it.
    """
    d = datetime.date.fromisoformat(date) + datetime.timedelta(days=interval)
    if study_days:
        for _ in range(7):
            if d.strftime("%a").lower() in study_days:
                break
            d += datetime.timedelta(days=1)
    return d.isoformat()


def new_section(q: dict) -> dict:
    src = q.get("source") or {}
    return {"page": src.get("page"), "heading": src.get("heading"),
            "notion_url": src.get("notion_url"), "blueprint": [],
            "attempts": 0, "correct": 0, "hint_used": 0, "wrong": 0, "skipped": 0,
            "credit": 0.0, "reps": 0, "ease": EASE_START, "interval_days": 0,
            "lapses": 0, "last_seen": None, "next_due": None, "exposures": []}


def new_subsection() -> dict:
    return {"attempts": 0, "correct": 0, "hint_used": 0, "wrong": 0, "skipped": 0,
            "credit": 0.0, "last_seen": None}


def build(history: Path | None = None, study_days: list[str] | None = None,
          through: str | None = None) -> dict:
    """Replay history into mastery. Injectable so tests need no disk state."""
    history = history or HISTORY
    if study_days is None:
        sch = yaml.safe_load((ROOT / "config/schedule.yaml").read_text()) or {}
        study_days = sch.get("days") or []

    sections: dict[str, dict] = {}
    subsections: dict[str, dict] = {}
    requeue: list[dict] = []
    graded_days: list[str] = []

    for day_dir in sorted(history.glob("*")) if history.exists() else []:
        if not day_dir.is_dir():
            continue
        date = day_dir.name
        if through and date > through:
            break

        for quiz_file, results_file in quiz_sets(day_dir):
            if not results_file.exists():
                continue
            quiz = json.loads(quiz_file.read_text())
            results = json.loads(results_file.read_text())
            by_n = {q.get("n"): q for q in quiz.get("questions", [])}

            # (section key -> that day's credits) so scheduling advances once.
            per_section: dict[str, list[float]] = {}
            scored = 0

            for graded in sorted(results.get("questions", []),
                                 key=lambda g: g.get("n", 0)):
                q = by_n.get(graded.get("n"))
                if not q:
                    continue
                key = section_key(q.get("source") or {})
                sec = sections.setdefault(key, new_section(q))
                sub = subsections.setdefault(q.get("blueprint"), new_subsection()) \
                    if q.get("blueprint") else None
                if (bp := q.get("blueprint")) and bp not in sec["blueprint"]:
                    sec["blueprint"].append(bp)

                outcome = graded.get("outcome", "unknown")
                if outcome == "skipped":
                    # Touches nothing: not attempts, not last_seen, not next_due.
                    sec["skipped"] += 1
                    if sub:
                        sub["skipped"] += 1
                    requeue.append({"date": date, "n": graded.get("n"), "section": key})
                    continue

                hinted = bool(graded.get("hint_used"))
                credit = CREDIT.get((outcome, hinted))
                if credit is None:
                    continue

                scored += 1
                for bucket in (sec, sub) if sub else (sec,):
                    bucket["attempts"] += 1
                    bucket["credit"] += credit
                    bucket["last_seen"] = date
                    if outcome == "wrong":
                        bucket["wrong"] += 1
                    else:
                        bucket["correct"] += 1
                    if hinted:
                        bucket["hint_used"] += 1

                per_section.setdefault(key, []).append(credit)

            if scored:
                graded_days.append(date)
            for key, credits in per_section.items():
                rating = day_credit(credits)
                advance(sections[key], rating, date, study_days)
                sections[key]["exposures"].append({
                    "date": date, "n_questions": len(credits), "day_credit": rating,
                    "ease_after": round(sections[key]["ease"], 3),
                    "interval_after": sections[key]["interval_days"],
                    "next_due": sections[key]["next_due"]})

    for sec in sections.values():
        sec["ease"] = round(sec["ease"], 3)
        sec["credit"] = round(sec["credit"], 3)
    for sub in subsections.values():
        sub["credit"] = round(sub["credit"], 3)

    return {
        "_generated_from": str(history.relative_to(ROOT)
                               if history.is_relative_to(ROOT) else history),
        "_note": "Derived from posted history. Do not hand-edit; rerun build_mastery.py.",
        "_replayed_through": through or (graded_days[-1] if graded_days else None),
        "params": {"ease_start": EASE_START, "ease_min": EASE_MIN,
                   "ease_max": EASE_MAX, "interval_max_days": MAX_INTERVAL,
                   "study_days": study_days},
        "graded_days": sorted(set(graded_days)),
        "sections": sections,
        "subsections": subsections,
        "requeue": requeue,
    }


def due_sections(mastery: dict, on: str) -> list[str]:
    """Sections whose next_due has arrived — what `quiz.mix.review_due` selects."""
    return sorted(k for k, s in mastery.get("sections", {}).items()
                  if s.get("next_due") and s["next_due"] <= on)


def main() -> int:
    mastery = build()
    MASTERY.parent.mkdir(parents=True, exist_ok=True)
    MASTERY.write_text(json.dumps(mastery, indent=2, sort_keys=True,
                                  ensure_ascii=False) + "\n")

    secs, subs = mastery["sections"], mastery["subsections"]
    attempts = sum(s["attempts"] for s in secs.values())
    credit = sum(s["credit"] for s in secs.values())
    skipped = sum(s["skipped"] for s in secs.values())
    today = datetime.date.today().isoformat()

    print(f"graded quizzes   : {len(mastery['graded_days'])}")
    print(f"answered         : {attempts}  ({skipped} skipped, not scored)")
    if attempts:
        print(f"credit           : {credit:.1f}/{attempts}  "
              f"({credit / attempts:.0%} hint-weighted)")
    print(f"sections scored  : {len(secs)}   subsections: {len(subs)}")
    print(f"due for review   : {len(due_sections(mastery, today))}")
    if not attempts:
        print("\nNothing graded yet — every readiness number will be prior, not "
              "measurement. Grade a quiz to give it evidence.")
    print(f"-> {MASTERY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
