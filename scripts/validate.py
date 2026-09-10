#!/usr/bin/env python3
"""Validate configuration and generated content.

Three layers:
  config    schema + internal consistency of the YAML the pipeline reads
  index     knowledge/index.json well-formed, tags resolve to the blueprint
  content   generated quizzes obey reference/question-spec.md and are grounded

Content checks are the anti-hallucination gate. A quiz that fails must be
regenerated, not posted.

    .venv/bin/python scripts/validate.py [quiz.json ...]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# From reference/question-spec.md §2, measured from the official corpus.
OPTIONS_EXACT = 4
OPT_WORDS_MIN, OPT_WORDS_MAX = 1, 26
OPT_SPREAD_MAX = 8
OPT_RATIO_MAX = 2.6
SENTENCES_MAX = 5

STEM_FORMS = [
    r"what should you do\??$",
    r"what action should (you|the customer) take.*\??$",
    r"what should your team do.*\??$",
    r"how should you .*\??$",
    r"how can the customer .*\??$",
    r"which (solution|action|approach) .*\??$",
    r"which google cloud solution .*\??$",
    r"which two .*\?\s*\(choose two\)$",
    r"which .*\??$",
    r"what .*\??$",
]

BANNED_OPTION = re.compile(r"\b(all|none) of the above\b", re.I)
# Fictional-company tell: a capitalised multi-word name with a corporate suffix.
FICTIONAL_CO = re.compile(
    r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)?\s+"
    r"(Inc|Ltd|LLC|Corp|Corporation|Logistics|Outfitters|Retail|Holdings|Industries|Systems|Bank)\b"
)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")


def load_yaml(rel: str):
    p = ROOT / rel
    return yaml.safe_load(p.read_text()) if p.exists() else None


def check_config(r: Report) -> dict:
    bp = load_yaml("config/exam-blueprint.yaml")
    if not bp:
        r.error("blueprint", "config/exam-blueprint.yaml missing")
        return {}

    total = sum(s["weight"] for s in bp["sections"])
    if total != 100:
        r.error("blueprint", f"weights sum to {total}, expected 100")

    ids = [sub["id"] for s in bp["sections"] for sub in s["subsections"]]
    if len(ids) != len(set(ids)):
        r.error("blueprint", "duplicate subsection ids")
    for s in bp["sections"]:
        if not s.get("square"):
            r.error("blueprint", f"section {s['id']} has no colour square")

    sch = load_yaml("config/schedule.yaml")
    if not sch:
        r.error("schedule", "config/schedule.yaml missing")
        return {"blueprint": bp}

    q = sch.get("quiz", {})
    n = q.get("questions", 0)
    for key in ("mix", "depth"):
        got = sum((q.get(key) or {}).values())
        if got != n:
            r.error("schedule", f"quiz.{key} sums to {got}, expected questions={n}")

    times = {}
    for key in ("digest_at", "quiz_at", "grade_at"):
        val = sch.get(key)
        if not re.fullmatch(r"\d{2}:\d{2}", str(val or "")):
            r.error("schedule", f"{key}={val!r} is not HH:MM")
        else:
            times[key] = val
    if len(times) == 3 and not (times["digest_at"] < times["quiz_at"] < times["grade_at"]):
        r.warn("schedule",
               f"order is digest {times['digest_at']} -> quiz {times['quiz_at']} -> "
               f"grade {times['grade_at']}; the pipeline enforces order regardless, "
               "but this reads oddly")

    tick = sch.get("tick_minutes", 0)
    if not 1 <= tick <= 120:
        r.error("schedule", f"tick_minutes={tick} outside 1..120")
    if tick > sch.get("grace_minutes", 0):
        r.warn("schedule", "tick_minutes exceeds grace_minutes; a step could be skipped")

    return {"blueprint": bp, "schedule": sch}


def check_index(r: Report, bp: dict) -> dict:
    p = ROOT / "knowledge/index.json"
    if not p.exists():
        r.warn("index", "knowledge/index.json missing (run build_index.py) — skipping")
        return {}

    idx = json.loads(p.read_text())
    valid = {sub["id"] for s in bp.get("sections", []) for sub in s["subsections"]}

    headings: set[str] = set()
    covered: set[str] = set()
    for course in idx.get("courses", []):
        for page in course["material"]["pages"]:
            if page["ingested"] and not page["sections"]:
                r.warn("index", f"{page['title']!r} marked ingested but has no sections")
            if not page["ingested"] and page["sections"]:
                r.error("index", f"{page['title']!r} has sections but ingested=false")
            for s in page["sections"]:
                headings.add(s["heading"])
                for tag in s["exam_tags"]:
                    if tag not in valid:
                        r.error("index", f"{page['title']!r} → {s['heading']!r} "
                                         f"has unknown exam tag {tag!r}")
                    elif page["ingested"]:
                        covered.add(tag)
    return {"index": idx, "headings": headings, "covered_subsections": covered}


def check_quiz(r: Report, path: Path, ctx: dict) -> None:
    where = path.name
    try:
        quiz = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        r.error(where, f"invalid JSON: {e}")
        return

    questions = quiz.get("questions", [])
    if not questions:
        r.error(where, "no questions")
        return

    # Injected via ctx so the check is testable without the gitignored map on disk.
    known_services = ctx.get("services", set())
    headings = ctx.get("headings", set())

    depth_seen = {"bare": 0, "mid": 0, "deep": 0}

    for i, q in enumerate(questions, 1):
        qid = f"{where} Q{i}"
        opts = q.get("options", [])

        if len(opts) != OPTIONS_EXACT:
            r.error(qid, f"{len(opts)} options, spec requires exactly {OPTIONS_EXACT}")
            continue

        words = [len(o.split()) for o in opts]
        if min(words) < OPT_WORDS_MIN or max(words) > OPT_WORDS_MAX:
            r.error(qid, f"option lengths {words} outside {OPT_WORDS_MIN}..{OPT_WORDS_MAX} words")
        if max(words) - min(words) > OPT_SPREAD_MAX:
            r.error(qid, f"option word spread {max(words) - min(words)} > {OPT_SPREAD_MAX} "
                         "— unequal length is a giveaway")
        if max(words) / max(min(words), 1) > OPT_RATIO_MAX:
            r.error(qid, f"option length ratio {max(words) / max(min(words), 1):.1f} > {OPT_RATIO_MAX}")

        for o in opts:
            if BANNED_OPTION.search(o):
                r.error(qid, "uses 'all/none of the above'")

        stem = (q.get("stem") or "").strip()
        if not any(re.search(f, stem, re.I) for f in STEM_FORMS):
            r.error(qid, f"stem does not match an attested form: {stem!r}")

        answers = q.get("answer", [])
        answers = answers if isinstance(answers, list) else [answers]
        multi = "(choose two)" in stem.lower()
        if multi and len(answers) != 2:
            r.error(qid, f"stem says (choose two) but {len(answers)} answer(s) keyed")
        if not multi and len(answers) != 1:
            r.error(qid, f"{len(answers)} answers keyed but stem is single-select")

        scenario = q.get("scenario", "") or ""
        if FICTIONAL_CO.search(scenario):
            r.error(qid, "scenario uses a fictional company name — the corpus never does")
        n_sent = len([s for s in re.split(r"(?<=[.?])\s+", scenario) if s.strip()])
        if n_sent > SENTENCES_MAX:
            r.error(qid, f"scenario is {n_sent} sentences, max {SENTENCES_MAX}")
        band = "bare" if n_sent <= 1 else "mid" if n_sent <= 3 else "deep"
        depth_seen[band] += 1
        if q.get("depth") and q["depth"] != band:
            r.error(qid, f"labelled depth={q['depth']!r} but scenario is {n_sent} "
                         f"sentence(s), which is {band!r}")

        src = q.get("source", {})
        if not src.get("notion_url"):
            r.error(qid, "no source.notion_url — ungrounded")
        if headings and src.get("heading") and src["heading"] not in headings:
            r.error(qid, f"cites heading {src['heading']!r} not present in knowledge/index.json")

        if known_services:
            for name in q.get("services", []):
                if name.lower() not in known_services:
                    r.error(qid, f"names service {name!r} not in aws-gcp-map.json — possible hallucination")

    want = (ctx.get("schedule") or {}).get("quiz", {}).get("depth")
    if want and depth_seen != want:
        r.warn(where, f"scenario depth mix {depth_seen} != configured {want}")


def check_digest(r: Report, path: Path, ctx: dict) -> None:
    """A digest may only teach what the ingested material covers.

    The learner is working through their course in order and asked explicitly not
    to be run ahead of. An earlier version of the digest prompt encouraged
    "flagging gaps" -- teaching things the course had not reached yet -- which is
    exactly that. This makes the rule mechanical rather than a matter of wording.
    """
    where = path.name
    try:
        digest = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        r.error(where, f"invalid JSON: {e}")
        return

    topics = (digest.get("slack") or {}).get("topics", [])
    if not topics:
        r.warn(where, "no topics recorded")
        return

    covered = ctx.get("covered_subsections", set())
    headings = ctx.get("headings", set())

    seen_components = []
    for topic in topics:
        tid = f"{where} topic {topic.get('n', '?')}"

        # Sourcing: must cite an ingested heading.
        src = topic.get("source") or {}
        heading = src.get("heading")
        if not heading:
            r.error(tid, "no source heading — a topic must be sourced from ingested material")
        elif headings and heading not in headings:
            r.error(tid, f"cites heading {heading!r} not present in knowledge/index.json")

        # Coverage: the subsection must actually be teachable.
        sub = topic.get("blueprint")
        if not sub:
            r.error(tid, "no blueprint subsection recorded")
        elif covered and sub not in covered:
            r.error(tid, f"subsection {sub} is not covered by ingested material — "
                         "the training has not reached it yet, so it must not be taught")

        # Explicit guard against the failure this check exists for.
        if topic.get("beyond_material") or topic.get("gap"):
            r.error(tid, "marked as beyond the course material — gaps are planning "
                         "signal for coverage reporting, never digest content")

        if c := topic.get("component"):
            seen_components.append(c)

    dupes = {c for c in seen_components if seen_components.count(c) > 1}
    if dupes:
        r.warn(where, f"repeats visual component(s) {sorted(dupes)} — house style asks "
                      "for a different shape per topic")


def main(argv: list[str]) -> int:
    r = Report()
    ctx = check_config(r)
    ctx.update(check_index(r, ctx.get("blueprint", {})))

    amap = ROOT / "knowledge/aws-gcp-map.json"
    if amap.exists():
        ctx["services"] = {s["gcp"].lower() for s in json.loads(amap.read_text())["services"]}
    else:
        ctx["services"] = set()

    quizzes = [Path(a) for a in argv if a.endswith("quiz.json")]
    digests = [Path(a) for a in argv if a.endswith("digest.json")]
    if not argv:
        quizzes = sorted((ROOT / "state.local/history").glob("*/quiz.json"))
        digests = sorted((ROOT / "state.local/history").glob("*/digest.json"))
    for q in quizzes:
        check_quiz(r, q, ctx)
    for d in digests:
        check_digest(r, d, ctx)

    print(f"validate: config + index checked, {len(quizzes)} quiz + "
          f"{len(digests)} digest file(s)")
    for w in r.warnings:
        print(f"  WARN  {w}")
    for e in r.errors:
        print(f"  FAIL  {e}", file=sys.stderr)
    if r.errors:
        print(f"\n{len(r.errors)} error(s)", file=sys.stderr)
        return 1
    print(f"validate: ok ({len(r.warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
