#!/usr/bin/env python3
"""Decide what a digest should teach today — or that there is nothing left.

Selection used to be a judgement call inside the prompt, which meant the system
had no way to know it was repeating itself. This makes it a deterministic,
testable function.

Selection is a QUOTA over bands, not a priority order over phases. It used to be
the latter, and remediation ran first and unbounded: 2026-09-11 shipped three
remediation passes and one new section, and a quiz with four misses would have
left no new ground at all.

    fresh        untaught sections whose material landed in the last few days
    remediation  sections with a recorded miss                    (capped)
    new          untaught sections, ranked by exam weight PER SECTION
    review       taught sections that are DUE, by spaced repetition
    synthesis    taught sections combined with a taught neighbour

A section lands in the first band it qualifies for. Bands fill to their floors
first, then to their ceilings; `fresh` and `remediation` have hard ceilings, so
a fourth miss defers to tomorrow rather than eating the digest. Everything left
over is reported -- `deferred`, `unfilled_floors` -- rather than silently
dropped, because "there is no new ground left" is something the digest should
say out loud rather than paper over.

`new` ranks by weight/section deliberately. SAIF (3.3) holds 9 of 20 teachable
sections but only 7.7% of reachable weight; ranking on raw novelty would spend
the first two days there while Authorization (1.4) waited.

`review` is the band that finally reads state.local/mastery.json. The spaced
repetition the system already computes drove the quiz and never the digest, so
"what do I need reminding on?" had no answer here at all. A section whose
`next_due` is in the future is not eligible however long ago it was taught --
the learner has demonstrably retained it.

    .venv/bin/python scripts/select_topics.py [--date YYYY-MM-DD] [--json]
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_ledger import miss_for_section  # noqa: E402  one lookup, shared


def load(rel: str, default=None):
    p = ROOT / rel
    if not p.exists():
        return default
    return (yaml.safe_load if p.suffix in (".yaml", ".yml") else json.loads)(p.read_text())


def section_key(page: str, heading: str) -> str:
    return f"{page}::{heading}"


def teachable_sections(index: dict) -> list[dict]:
    """Every ingested, blueprint-tagged section — the pool a digest may draw on."""
    out = []
    for course in index.get("courses", []):
        for page in course["material"]["pages"]:
            if not page["ingested"]:
                continue
            for s in page["sections"]:
                if not s["exam_tags"]:
                    continue
                out.append({
                    "key": section_key(page["title"], s["heading"]),
                    "page": page["title"], "heading": s["heading"],
                    "notion_url": page["url"], "cache": page.get("cache"),
                    "blueprint": s["exam_tags"],
                    "services": s.get("services", []), "note": s.get("note"),
                    # A section added to an already-ingested page carries its own
                    # stamp; otherwise the page's stands in. Null means "before
                    # the measurement window" (see sync-notion), which reads as
                    # "not fresh" -- the safe direction, since a cold start that
                    # guessed today would mark every section fresh at once.
                    "ingested_on": s.get("ingested_on") or page.get("ingested_on"),
                })
    return out


def weight_per_section(blueprint: dict, sections: list[dict]) -> dict[str, float]:
    """Exam weight a single section carries, by subsection.

    A subsection's weight is its share of its section's weight, divided by how
    many teachable sections cover it. This is what stops a subsection with many
    thin sections outranking a heavier one with few.
    """
    counts: dict[str, int] = {}
    for s in sections:
        for tag in s["blueprint"]:
            counts[tag] = counts.get(tag, 0) + 1

    out: dict[str, float] = {}
    for sec in blueprint.get("sections", []):
        share = sec["weight"] / len(sec["subsections"])
        for sub in sec["subsections"]:
            n = counts.get(sub["id"], 0)
            out[sub["id"]] = share / n if n else 0.0
    return out


def applicable_angles(section: dict, angles: list[dict], ledger: dict,
                      all_sections: list[dict]) -> list[str]:
    """Which angles could ever apply to this section."""
    entry = (ledger.get("sections") or {}).get(section["key"], {})
    taught_keys = set((ledger.get("sections") or {}).keys())

    has_miss = any(
        "wrong" in q.get("outcomes", []) and q.get("section") == section["key"]
        for q in (ledger.get("questions") or {}).values()
    )
    siblings_taught = sum(
        1 for other in all_sections
        if other["key"] != section["key"]
        and set(other["blueprint"]) & set(section["blueprint"])
        and other["key"] in taught_keys
    )
    # An AWS reference exists if we know a mapping, or know there is none.
    has_aws_ref = True

    ok = []
    for a in angles:
        rule = a["applicable"]
        if rule == "always":
            ok.append(a["id"])
        elif rule == "has_aws_reference" and has_aws_ref:
            ok.append(a["id"])
        elif rule == "sibling_taught" and siblings_taught:
            ok.append(a["id"])
        elif rule == "has_recorded_miss" and has_miss:
            ok.append(a["id"])
    del entry
    return ok


def remaining_angles(sections: list[dict], angles: list[dict], ledger: dict) -> int:
    """The honest answer to 'is there more to say?'"""
    total = 0
    for s in sections:
        used = set(((ledger.get("sections") or {}).get(s["key"]) or {}).get("angles_used", []))
        total += len(set(applicable_angles(s, angles, ledger, sections)) - used)
    return total


def uncovered_subsections(blueprint: dict, sections: list[dict]) -> list[tuple]:
    """What to add next, heaviest exam weight first."""
    covered = {t for s in sections for t in s["blueprint"]}
    out = []
    for sec in blueprint.get("sections", []):
        share = sec["weight"] / len(sec["subsections"])
        for sub in sec["subsections"]:
            if sub["id"] not in covered:
                out.append((sub["id"], sub["title"], round(share, 1), sec["square"]))
    return sorted(out, key=lambda r: -r[2])


# Bands map onto the old phase letters so `phase` stays a string that existing
# readers understand. A digest now normally spans several.
BAND_PHASE = {"fresh": "A", "new": "A", "remediation": "B",
              "review": "C", "synthesis": "D"}

MIX_DEFAULTS = {
    "fresh":       {"min": 0, "max": 1, "hard": True},
    "remediation": {"min": 0, "max": 2, "hard": True},
    "new":         {"min": 1, "max": 4},
    "review":      {"min": 0, "max": 4},
    "synthesis":   {"min": 0, "max": 1},
}


def mix_config(cfg: dict) -> dict:
    """Read the `mix:` block, falling back to the pre-quota behaviour's shape.

    An angles.yaml with no `mix:` still works: it gets these defaults and
    `topics_per_digest`, so the change cannot break a config that has not been
    migrated -- including the copy a cloud run rehydrates from Notion.
    """
    mix = dict(cfg.get("mix") or {})
    mix.setdefault("topics", cfg.get("topics_per_digest", 4))
    mix.setdefault("order", ["fresh", "remediation", "new", "review", "synthesis"])
    mix.setdefault("absorb", ["new", "review", "synthesis"])
    mix.setdefault("fresh_window_days", 3)
    configured = mix.get("bands") or {}
    bands = {}
    for name in mix["order"]:
        b = dict(MIX_DEFAULTS.get(name, {}))
        b.update(configured.get(name) or {})
        b.setdefault("min", 0)
        b.setdefault("max", mix["topics"])
        b.setdefault("hard", False)
        bands[name] = b
    mix["bands"] = bands
    return mix


def _days(today: str, when: str | None) -> int | None:
    """Whole days from `when` to `today`, or None if there is no usable date."""
    if not when:
        return None
    try:
        return (datetime.date.fromisoformat(today)
                - datetime.date.fromisoformat(when)).days
    except (TypeError, ValueError):
        return None


def select(today: str | None = None, ledger: dict | None = None,
           index: dict | None = None, mastery: dict | None = None) -> dict:
    """Ledger, index and mastery are injectable so the multi-day simulation and
    the tests can drive selection without writing files."""
    blueprint = load("config/exam-blueprint.yaml", {})
    cfg = load("config/angles.yaml", {})
    angles = cfg.get("angles", [])
    if index is None:
        index = load("knowledge/index.json", {})
    if ledger is None:
        ledger = load("state.local/ledger.json", {"sections": {}, "questions": {}})
    # A fresh sandbox has no mastery file until build_mastery.py runs. Missing is
    # not "nothing is due" -- it means the spaced-repetition signal is
    # unavailable, so `review` falls back to staleness and the envelope says so.
    mastery_missing = mastery is None and not (ROOT / "state.local/mastery.json").exists()
    if mastery is None:
        mastery = load("state.local/mastery.json", {"sections": {}})

    today = today or datetime.date.today().isoformat()
    mix = mix_config(cfg)
    want = mix["topics"]
    restale = cfg.get("restale_days", 5)

    sections = teachable_sections(index)
    if not sections:
        return {"date": today, "phase": "E", "phases": [], "topics": [],
                "reason": "no ingested material", "remaining_angles": 0,
                "teachable_sections": 0, "mix": {}, "unfilled_floors": [],
                "fresh_slot": {"filled": False}, "deferred": [], "add_next": []}

    wps = weight_per_section(blueprint, sections)
    led_secs = ledger.get("sections") or {}
    mas_secs = mastery.get("sections") or {}
    by_angle = {a["id"]: a for a in angles}

    def sec_weight(s):
        return max((wps.get(t, 0.0) for t in s["blueprint"]), default=0.0)

    def days_since(key):
        d = _days(today, (led_secs.get(key) or {}).get("last_taught"))
        return 10_000 if d is None else d

    def first_angle(app, exclude):
        return next((a["id"] for a in sorted(angles, key=lambda x: x["priority"])
                     if a["id"] in app and a["id"] not in exclude), None)

    def due(key):
        """(eligible, overdue_days, tier, why). Tier 1 -- a real spaced-repetition
        due date -- outranks tier 0, which is bare staleness for a section that
        has never been quizzed and so has no mastery record to be due against."""
        nd = (mas_secs.get(key) or {}).get("next_due")
        over = _days(today, nd)
        if over is not None:
            return over >= 0, max(over, 0), 1, "due for review"
        d = days_since(key)
        return d >= restale, d, 0, f"not seen in {d}d"

    def candidacies(s):
        """Every band this section could serve, with the angle and rank for each.

        Bands OVERLAP deliberately. `fresh` is a priority overlay on `new`, not a
        separate population: when a big sync makes everything fresh, a strict
        partition empties `new`, its floor cannot be met, and the digest collapses
        to the single section the fresh cap allows. A section is still only ever
        picked once -- exclusivity belongs to the picks, not to the candidacy.
        """
        key = s["key"]
        app = applicable_angles(s, angles, ledger, sections)
        used = set((led_secs.get(key) or {}).get("angles_used", []))
        taught = key in led_secs
        w = sec_weight(s)
        out = []

        if not taught:
            age = _days(today, s.get("ingested_on"))
            if age is not None and 0 <= age <= mix["fresh_window_days"]:
                angle = first_angle(app, used | {"remediation", "synthesis"}) or "trap"
                out.append(("fresh", angle,
                            f"ingested {s['ingested_on']} · not taught yet",
                            (s.get("ingested_on") or "", w)))

        if "remediation" in app and "remediation" not in used:
            out.append(("remediation", "remediation",
                        "answered wrong in a previous quiz", (w,)))

        if not taught:
            angle = first_angle(app, used | {"remediation"}) or "trap"
            # Sections with a pending miss sort LAST within `new`, so the two
            # bands cooperate instead of competing for the same section. Without
            # this the `new` floor grabs the heaviest untaught section, which is
            # often one carrying a miss, and the remediation band loses the very
            # topic whose question the reader most needs linked back.
            has_miss = "remediation" in app and "remediation" not in used
            out.append(("new", angle,
                        f"not taught yet · {w:.1f}% of exam per section",
                        (0 if has_miss else 1, w)))

        if taught:
            eligible, over, tier, why = due(key)
            if eligible:
                angle = first_angle(app, used | {"synthesis"})
                if angle:
                    out.append(("review", angle,
                                f"taught {days_since(key)}d ago · {why} · new angle",
                                (tier, over, w)))

            if "synthesis" in app and "synthesis" not in used:
                out.append(("synthesis", "synthesis",
                            "combine with a taught neighbour", (w,)))
        return out

    # ── candidates, ranked within each band ────────────────────────────────
    cands: dict[str, list] = {b: [] for b in mix["order"]}
    for s in sections:
        for band, angle, why, rank in candidacies(s):
            if band in cands:
                cands[band].append({"s": s, "angle": angle, "why": why, "rank": rank})
    for band in cands:
        cands[band].sort(key=lambda c: c["rank"], reverse=True)

    picks: list[dict] = []
    used_keys: set[str] = set()
    taken = {b: 0 for b in mix["order"]}

    def add(c, band):
        s = c["s"]
        pick = {
            "key": s["key"], "page": s["page"], "heading": s["heading"],
            "notion_url": s["notion_url"], "cache": s.get("cache"),
            "blueprint": s["blueprint"][0] if s["blueprint"] else None,
            "angle": c["angle"],
            "angle_label": by_angle.get(c["angle"], {}).get("label", c["angle"]),
            "band": band, "phase": BAND_PHASE.get(band, "A"), "why": c["why"],
            "weight_per_section": round(sec_weight(s), 2),
            "ingested_on": s.get("ingested_on"),
            "miss": None,
        }
        if band == "remediation":
            fp, q = miss_for_section(ledger, s["key"])
            if q:
                # The handle only. Building the URL needs config.local.yaml, and
                # the selector has no business reading it -- scripts/slack_links.py
                # turns this into a permalink.
                pick["miss"] = dict(q["last_miss"], fingerprint=fp,
                                    stem=q.get("stem"), scenario=q.get("scenario"),
                                    options=q.get("options"))
        picks.append(pick)
        used_keys.add(s["key"])
        taken[band] += 1

    def fill(band, limit):
        for c in cands[band]:
            if len(picks) >= want or taken[band] >= limit:
                return
            if c["s"]["key"] in used_keys:
                continue
            add(c, band)

    for band in mix["order"]:                       # floors, in order
        fill(band, mix["bands"][band]["min"])
    for band in mix["order"]:                       # then ceilings
        fill(band, mix["bands"][band]["max"])

    # Slack goes to the soft bands. A hard ceiling is never relaxed: that is what
    # makes "at most two misses" true on a day with five of them.
    progress = True
    while len(picks) < want and progress:
        progress = False
        for band in mix["absorb"]:
            if len(picks) >= want or mix["bands"].get(band, {}).get("hard"):
                continue
            before = len(picks)
            fill(band, taken[band] + 1)
            progress = progress or len(picks) > before

    unfilled = [b for b in mix["order"]
                if taken[b] < mix["bands"][b]["min"]]
    # Held over only if NO band took the section: one that overflowed the fresh
    # cap but was picked up as `new` was taught today, not deferred.
    deferred = [
        {"key": c["s"]["key"], "heading": c["s"]["heading"], "band": band,
         "why": f"over the {mix['bands'][band]['max']}-per-digest cap on "
                f"{band}; queued for the next digest"}
        for band in mix["order"] if mix["bands"][band].get("hard")
        for c in cands[band] if c["s"]["key"] not in used_keys
    ]
    fresh_pick = next((p for p in picks if p["band"] == "fresh"), None)

    phases = sorted({p["phase"] for p in picks})
    result = {
        "date": today,
        "phase": "".join(phases) if phases else "E",
        "phases": phases,
        "topics": picks,
        "mix": {b: taken[b] for b in mix["order"]},
        "unfilled_floors": unfilled,
        "fresh_slot": ({"filled": True, "key": fresh_pick["key"],
                        "ingested_on": fresh_pick["ingested_on"]}
                       if fresh_pick else
                       {"filled": False,
                        "reason": "no section ingested in the last "
                                  f"{mix['fresh_window_days']} days"}),
        "deferred": deferred,
        "remaining_angles": remaining_angles(sections, angles, ledger),
        "teachable_sections": len(sections),
        "add_next": uncovered_subsections(blueprint, sections),
    }
    if mastery_missing:
        result["mastery_unavailable"] = (
            "state.local/mastery.json is absent, so `review` ranked on staleness "
            "alone. Run scripts/build_mastery.py.")
    if not picks:
        result["reason"] = ("every teachable section has been covered from every "
                            "applicable angle")
    return result


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    r = select(args.date)
    if args.json:
        print(json.dumps(r, indent=2))
        return 0

    print(f"date {r['date']} · phase {r['phase']} · "
          f"{r['remaining_angles']} angle(s) of new material remaining")
    if mix := {b: n for b, n in (r.get("mix") or {}).items() if n}:
        print("mix  " + " · ".join(f"{b} {n}" for b, n in mix.items()))
    if r.get("mastery_unavailable"):
        print(f"note {r['mastery_unavailable']}")
    for band in r.get("unfilled_floors") or []:
        print(f"note no {band!r} section was available — say so in the digest "
              "rather than padding")
    for d in r.get("deferred") or []:
        print(f"held {d['heading']} — {d['why']}")
    if not r["topics"]:
        print(f"\nEXHAUSTED — {r.get('reason')}")
        print("\nAdd next, heaviest exam weight first:")
        for sid, title, w, sq in r["add_next"][:5]:
            print(f"  {sq} {sid} {title}  ({w}% of the exam)")
        return 0
    for i, t in enumerate(r["topics"], 1):
        print(f"  {i}. [{t['band']}] §{t['blueprint']} {t['heading']}")
        print(f"       angle={t['angle']:<12} {t['why']}")
        if m := t.get("miss"):
            print(f"       miss  Q{m.get('n')} on {m.get('date')} — "
                  f"answered {m.get('answered')}, keyed {m.get('keyed')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
