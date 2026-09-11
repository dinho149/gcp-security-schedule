#!/usr/bin/env python3
"""Rebuild state.local/readiness.json — am I ready, and when will I be?

Answers it twice, because there is only one honest way to say it:

    on covered material   of what the training has taught, how much is solid
    true exam readiness   of the WHOLE exam, how much is solid  (capped by coverage)

    true = on_covered x reachable

Never report the first without the second. Alone it is a claim about 61% of the
exam dressed up as a claim about the exam -- CLAUDE.md rule 2, pointed at the
learner instead of at GCP.

Per blueprint subsection s:

    W_s  exam weight            section weight / subsection count
    M_s  has material           1 if an INGESTED section carries the tag
    T_s  taught fraction        taught sections / sections with material
    p0   prior                  0.25 + 0.25 * T_s
    P_s  proven                 (credit + k*p0) / (attempts + k),  k = 4
    R_s  readiness              M_s * P_s

0.25 is the 4-option guess rate -- measured across the official samples and
enforced by validate.OPTIONS_EXACT -- so an unproven topic starts where blind
guessing lands. p0 caps at 0.50, so TEACHING ALONE CAN NEVER REACH THE TARGET:
a fully-taught, never-quizzed exam is structurally capped at half.

Teaching is a prior, not a gate. The 2026-09-10 quiz asked a 3.3 question and 3.3
has never been in a digest; gating on taught would score a correct answer there
as zero. Proof beats teaching; teaching only fills the gap where proof is absent.

    .venv/bin/python scripts/build_readiness.py [--date YYYY-MM-DD] [--json]
"""
from __future__ import annotations

import argparse
import datetime
import json
import statistics
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_mastery  # noqa: E402

HISTORY = ROOT / "state.local/history"
READINESS = ROOT / "state.local/readiness.json"

GUESS_FLOOR = 0.25    # four options, always — reference/question-spec.md
TAUGHT_PRIOR = 0.50   # the ceiling teaching alone can reach
SHRINK_K = 4          # smallest k where one lucky hit reads below "proven"


def load(rel: str, default=None):
    p = ROOT / rel
    if not p.exists():
        return default
    return (yaml.safe_load if p.suffix in (".yaml", ".yml") else json.loads)(p.read_text())


# ── The blueprint side ─────────────────────────────────────────────────────
def subsection_weights(blueprint: dict) -> dict[str, float]:
    """Exam weight per subsection — the same even split build_coverage.py uses.

    Google publishes weights per SECTION only; the split across subsections is
    this repo's assumption, and the report says so.
    """
    out = {}
    for sec in blueprint.get("sections", []):
        share = sec["weight"] / len(sec["subsections"])
        for sub in sec["subsections"]:
            out[sub["id"]] = share
    return out


def material_sections(index: dict, on: str | None = None) -> list[dict]:
    """Ingested, blueprint-tagged sections — optionally as of a past date.

    `ingested_on` is null for pages read before the field existed. Null means
    "before the measurement window": it counts toward the level of coverage at
    every date, but contributes no rate.
    """
    out = []
    for course in index.get("courses", []):
        for page in course.get("material", {}).get("pages", []):
            if not page.get("ingested"):
                continue
            when = page.get("ingested_on")
            if on and when and when > on:
                continue
            for s in page.get("sections", []):
                if not s.get("exam_tags"):
                    continue
                out.append({"key": f"{page['title']}::{s['heading']}",
                            "blueprint": s["exam_tags"], "ingested_on": when})
    return out


def taught_keys(ledger: dict, on: str | None = None) -> set[str]:
    keys = set()
    for key, entry in (ledger.get("sections") or {}).items():
        dates = [t.get("date") for t in entry.get("taught", [])]
        if not on or any(d and d <= on for d in dates):
            keys.add(key)
    return keys


# ── The score ──────────────────────────────────────────────────────────────
def score_subsection(weight: float, has_material: bool, taught: int, with_material: int,
                     attempts: int, credit: float) -> dict:
    t = (taught / with_material) if with_material else 0.0
    p0 = GUESS_FLOOR + (TAUGHT_PRIOR - GUESS_FLOOR) * t
    proven = (credit + SHRINK_K * p0) / (attempts + SHRINK_K)   # k>0, never /0
    readiness = proven if has_material else 0.0

    if not has_material:
        evidence = "no material ingested"
    elif attempts == 0 and taught == 0:
        evidence = "material only"
    elif attempts == 0:
        evidence = "prior only"          # taught, never quizzed
    elif taught == 0:
        evidence = "graded, untaught"
    else:
        evidence = "graded"

    return {"weight": round(weight, 2), "has_material": has_material,
            "taught": taught, "sections_with_material": with_material,
            "taught_fraction": round(t, 3), "prior": round(p0, 3),
            "attempts": attempts, "credit": round(credit, 2),
            "proven": round(proven, 4), "readiness": round(readiness, 4),
            "points": round(weight * readiness, 3),
            "reachable_points": round(weight, 3) if has_material else 0.0,
            "evidence": evidence}


def compute(blueprint: dict, index: dict, ledger: dict, mastery: dict,
            on: str | None = None) -> dict:
    weights = subsection_weights(blueprint)
    mats = material_sections(index, on)
    taught = taught_keys(ledger, on)
    subs_m = mastery.get("subsections", {})

    with_material: dict[str, int] = {}
    taught_count: dict[str, int] = {}
    for s in mats:
        for tag in s["blueprint"]:
            with_material[tag] = with_material.get(tag, 0) + 1
            if s["key"] in taught:
                taught_count[tag] = taught_count.get(tag, 0) + 1

    subsections = {}
    for sub_id, weight in weights.items():
        m = subs_m.get(sub_id, {})
        subsections[sub_id] = score_subsection(
            weight, with_material.get(sub_id, 0) > 0, taught_count.get(sub_id, 0),
            with_material.get(sub_id, 0), m.get("attempts", 0), m.get("credit", 0.0))

    sections = []
    for sec in blueprint.get("sections", []):
        ids = [s["id"] for s in sec["subsections"]]
        pts = sum(subsections[i]["points"] for i in ids)
        reach = sum(subsections[i]["reachable_points"] for i in ids)
        sections.append({
            "id": sec["id"], "square": sec["square"], "title": sec["title"],
            "weight": sec["weight"],
            "subsections_with_material": sum(1 for i in ids if subsections[i]["has_material"]),
            "subsections_total": len(ids),
            "reachable_points": round(reach, 2),
            "points": round(pts, 2),
            # null, not 0: "not measured" and "measured at zero" are different
            # facts, and a 0% here would read as a failed test.
            "on_covered": round(pts / reach, 4) if reach else None,
            "attempts": sum(subsections[i]["attempts"] for i in ids),
            "subsections": ids,
        })

    total_pts = sum(s["points"] for s in sections)
    reachable = sum(s["reachable_points"] for s in sections)
    return {
        "as_of": on,
        "true": round(total_pts / 100, 4),
        "reachable": round(reachable / 100, 4),
        "on_covered": round(total_pts / reachable, 4) if reachable else None,
        "points": round(total_pts, 2),
        "sections": sections,
        "subsections": subsections,
    }


# ── The trend, by replay ───────────────────────────────────────────────────
def series(blueprint: dict, index: dict, ledger: dict, history: Path,
           study_days: list[str]) -> list[dict]:
    """Readiness as of each graded day.

    Recomputed by replay rather than appended to a stored log, so it stays
    derived — and self-corrects if a past results.json is ever fixed.
    """
    dates = build_mastery.build(history=history, study_days=study_days)["graded_days"]
    out = []
    for d in dates:
        m = build_mastery.build(history=history, study_days=study_days, through=d)
        snap = compute(blueprint, index, ledger, m, on=d)
        out.append({"date": d, "true": snap["true"], "reachable": snap["reachable"],
                    "on_covered": snap["on_covered"]})
    return out


def theil_sen(points: list[tuple[float, float]]) -> tuple[float | None, float | None]:
    """Median of pairwise slopes, plus the 25th percentile of them.

    Robust where least squares is not: one big ingestion day is a genuine
    outlier that OLS would let dominate the forecast. The 25th percentile is
    what stops "high confidence" being handed to a series that rose once and
    then flatlined.
    """
    slopes = [(y2 - y1) / (x2 - x1)
              for i, (x1, y1) in enumerate(points)
              for (x2, y2) in points[i + 1:] if x2 != x1]
    if not slopes:
        return None, None
    slopes.sort()
    q1 = slopes[max(0, int(len(slopes) * 0.25) - (1 if len(slopes) > 3 else 0))]
    return statistics.median(slopes), q1


def days_between(a: str, b: str) -> int:
    return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days


def coverage_rate(index: dict, snap: dict, today: str) -> dict:
    """Exam weight unlocked per day, from ingestion date stamps."""
    stamps = sorted({p.get("ingested_on")
                     for c in index.get("courses", [])
                     for p in c.get("material", {}).get("pages", [])
                     if p.get("ingested") and p.get("ingested_on")})
    pending = [{"title": p["title"], "expected": p.get("expected_exam_tags", [])}
               for c in index.get("courses", [])
               for p in c.get("material", {}).get("pages", []) if not p.get("ingested")]
    if len(stamps) < 2:
        return {"rate": None, "stamps": len(stamps), "pending": pending,
                "why": "needs 2 dated ingestions to measure a pace"}
    span = days_between(stamps[0], today)
    if span < 7:
        return {"rate": None, "stamps": len(stamps), "pending": pending,
                "why": f"only {span}d of ingestion history; needs 7"}
    return {"rate": (snap["reachable"] - 0.0) / span if span else None,
            "stamps": len(stamps), "pending": pending, "span_days": span, "why": None}


def estimate(cfg: dict, snap: dict, trend: list[dict], mastery: dict,
             cover: dict, today: str) -> dict:
    """A single number and a confidence, or an honest refusal."""
    target = cfg.get("target", 0.75)
    attempts = sum(s["attempts"] for s in mastery.get("sections", {}).values())
    quizzes = len(mastery.get("graded_days", []))
    span = days_between(trend[0]["date"], trend[-1]["date"]) if len(trend) > 1 else 0

    pts = [(float(days_between(trend[0]["date"], p["date"])), p["true"]) for p in trend]
    slope, q1 = theil_sen(pts) if len(pts) > 1 else (None, None)

    checks = [
        ("graded quizzes", quizzes >= cfg.get("min_graded_quizzes", 2),
         f"{quizzes}/{cfg.get('min_graded_quizzes', 2)}"),
        ("answered questions", attempts >= cfg.get("min_attempts", 15),
         f"{attempts}/{cfg.get('min_attempts', 15)}"),
        ("readiness snapshots", len(trend) >= cfg.get("min_snapshots", 5),
         f"{len(trend)}/{cfg.get('min_snapshots', 5)}"),
        ("trend span", span >= 7, f"{span}d/7d"),
        ("improving", bool(slope and slope > 0),
         "flat or falling" if slope is not None and slope <= 0 else "yes" if slope else "—"),
        ("ingestion pace", cover["rate"] is not None or snap["reachable"] >= target,
         cover.get("why") or "measured"),
    ]
    blockers = [(name, detail) for name, ok, detail in checks if not ok]

    out = {"target": target, "target_basis": cfg.get("target_basis", ""),
           "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks],
           "too_early": bool(blockers), "days": None, "confidence": None,
           "blocked_by": blockers[0][0] if blockers else None,
           "slope_per_day": round(slope, 5) if slope else None,
           "coverage_rate_per_day": round(cover["rate"], 5) if cover.get("rate") else None}

    if blockers:
        out["reason"] = (f"needs {blockers[0][0]} — {blockers[0][1]}"
                         if slope is None or slope > 0 else
                         "readiness is flat or falling; nothing to extrapolate")
        return out

    if snap["true"] >= target:
        out["days"] = 0
        out["confidence"] = "high"
        out["reason"] = "target met on current evidence"
        return out

    d_mastery = -(-(target - snap["true"]) // slope)
    d_cover = 0
    if target > snap["reachable"] and cover["rate"]:
        d_cover = -(-(target - snap["reachable"]) // cover["rate"])
    days = int(max(d_mastery, d_cover))

    if days > 365:
        out["reason"] = "beyond a year at the current rate"
        out["too_early"] = True
        out["blocked_by"] = "pace"
        return out

    agree = abs(d_mastery - d_cover) / days if days else 0
    if quizzes >= 6 and len(trend) >= 12 and attempts >= 60 and (q1 or 0) > 0 and agree <= 0.3:
        conf = "high"
    elif quizzes >= 3 and len(trend) >= 8 and attempts >= 30 and agree <= 0.6:
        conf = "medium"
    else:
        conf = "low"

    out.update({"days": days, "confidence": conf,
                "days_mastery": int(d_mastery), "days_coverage": int(d_cover),
                "ready_on": (datetime.date.fromisoformat(today)
                             + datetime.timedelta(days=days)).isoformat()})
    return out


def caveats(snap: dict, mastery: dict) -> list[dict]:
    """Only the ones currently true — a wall of standing disclaimers gets skimmed."""
    out = []
    attempts = sum(s["attempts"] for s in mastery.get("sections", {}).values())
    skipped = sum(s["skipped"] for s in mastery.get("sections", {}).values())
    gap = round((1 - snap["reachable"]) * 100, 1)

    if snap["reachable"] < 1:
        out.append({"id": "renormalised", "severity": "high", "text":
                    f"Quiz weights are renormalised over the reachable "
                    f"{snap['reachable']:.1%}, so raw quiz score answers 'how well do "
                    f"I do on what I've studied', never 'how would I do on the exam'. "
                    f"The two headline numbers exist to make that visible."})
    out.append({"id": "even-split", "severity": "medium", "text":
                "Google publishes exam weights per SECTION only. Splitting them "
                "evenly across subsections is this repo's assumption, shared with "
                "coverage.md and the topic selector."})
    if attempts == 0:
        out.append({"id": "no-evidence", "severity": "high", "text":
                    "Nothing has been graded, so every number here is prior, not "
                    "measurement. Most of it is the bare 4-option guess floor."})
    if skipped >= 3:
        out.append({"id": "skips", "severity": "medium", "text":
                    f"{skipped} question(s) skipped and excluded from scoring. Skipping "
                    "the hard ones biases readiness upward, and that is not correctable."})
    out.append({"id": "closed-loop", "severity": "medium", "text":
                "Questions are generated from the same material they test. A high "
                "score means 'consistent with my own material', not 'consistent with "
                "the exam'."})
    if gap > 0:
        out.append({"id": "ceiling", "severity": "high", "text":
                    f"{gap}% of the exam has no ingested material behind it. True "
                    "readiness cannot exceed the ceiling however well quizzes go."})
    return out


def build(today: str | None = None) -> dict:
    today = today or datetime.date.today().isoformat()
    blueprint = load("config/exam-blueprint.yaml", {})
    index = load("knowledge/index.json", {})
    ledger = load("state.local/ledger.json", {"sections": {}, "questions": {}})
    schedule = load("config/schedule.yaml", {}) or {}
    cfg = schedule.get("readiness", {}) or {}
    study_days = schedule.get("days") or []

    mastery = build_mastery.build(history=HISTORY, study_days=study_days)
    snap = compute(blueprint, index, ledger, mastery)
    trend = series(blueprint, index, ledger, HISTORY, study_days)
    cover = coverage_rate(index, snap, today)
    est = estimate(cfg, snap, trend, mastery, cover, today)

    # Coverage, four ways — teaching, depth, the course itself, and testing.
    teachable = material_sections(index)
    taught = taught_keys(ledger)
    quizzed = {q.get("section") for q in (ledger.get("questions") or {}).values()}
    pages = [p for c in index.get("courses", []) for p in c.get("material", {}).get("pages", [])]
    coverage = {
        "course_pages_ingested": sum(1 for p in pages if p.get("ingested")),
        "course_pages_total": len(pages),
        "sections_taught": len([s for s in teachable if s["key"] in taught]),
        "sections_teachable": len(teachable),
        "sections_quizzed": len([s for s in teachable if s["key"] in quizzed and s["key"] in taught]),
        "angles_remaining": None,
        "blind_spots": sorted(s["key"] for s in teachable
                              if s["key"] in taught and s["key"] not in quizzed),
    }
    try:
        import select_topics
        angles = (load("config/angles.yaml", {}) or {}).get("angles", [])
        coverage["angles_remaining"] = select_topics.remaining_angles(
            select_topics.teachable_sections(index), angles, ledger)
    except Exception:
        pass

    # Where study pays most: heavy weight, least proven.
    leverage = sorted(
        ({"subsection": k, "gain": round(v["weight"] * (est["target"] - v["readiness"]), 2),
          "weight": v["weight"], "readiness": v["readiness"], "evidence": v["evidence"]}
         for k, v in snap["subsections"].items()),
        key=lambda r: -r["gain"])[:5]

    return {
        "_generated_from": "state.local/history + knowledge/index.json",
        "_note": "Derived. Do not hand-edit; rerun build_readiness.py.",
        "as_of": today,
        "evidence": {"graded_quizzes": len(mastery["graded_days"]),
                     "answered": sum(s["attempts"] for s in mastery["sections"].values()),
                     "skipped": sum(s["skipped"] for s in mastery["sections"].values())},
        "headline": {"true": snap["true"], "on_covered": snap["on_covered"],
                     "reachable": snap["reachable"]},
        "sections": snap["sections"],
        "subsections": snap["subsections"],
        "coverage": coverage,
        "due_for_review": build_mastery.due_sections(mastery, today),
        "leverage": leverage,
        "estimate": est,
        "trend": trend,
        "caveats": caveats(snap, mastery),
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    r = build(args.date)
    READINESS.parent.mkdir(parents=True, exist_ok=True)
    READINESS.write_text(json.dumps(r, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0

    h, e = r["headline"], r["evidence"]
    oc = f"{h['on_covered']:.1%}" if h["on_covered"] is not None else "—"
    print(f"true exam readiness : {h['true']:.1%}")
    print(f"on covered material : {oc}   (ceiling {h['reachable']:.1%})")
    print(f"evidence            : {e['graded_quizzes']} graded quiz(zes), "
          f"{e['answered']} answered")
    for s in r["sections"]:
        got = f"{s['on_covered']:.0%}" if s["on_covered"] is not None else "—"
        print(f"  {s['square']} {s['id']} {s['title'][:34]:<34} {got:>4}  "
              f"{s['points']:>5.1f}/{s['weight']}%")
    est = r["estimate"]
    if est["too_early"]:
        print(f"\ndays estimate       : still too early to decide — {est['reason']}")
    else:
        print(f"\ndays estimate       : ~{est['days']} days · {est['confidence']} confidence")
    print(f"-> {READINESS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
