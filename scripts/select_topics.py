#!/usr/bin/env python3
"""Decide what a digest should teach today — or that there is nothing left.

Selection used to be a judgement call inside the prompt, which meant the system
had no way to know it was repeating itself. This makes it a deterministic,
testable function.

Phases, in order:

    A  breadth      untaught sections, ranked by exam weight PER SECTION
    B  remediation  sections with a recorded miss
    C  second pass  taught sections with an unused applicable angle
    D  synthesis    pairs of taught sections in one subsection
    E  exhausted    nothing left — say so, and name what to add

Phase A ranks by weight/section deliberately. SAIF (3.3) holds 9 of 20 teachable
sections but only 7.7% of reachable weight; ranking on raw novelty would spend
the first two days there while Authorization (1.4) waited.

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
                    "notion_url": page["url"], "blueprint": s["exam_tags"],
                    "services": s.get("services", []), "note": s.get("note"),
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


def select(today: str | None = None, ledger: dict | None = None,
           index: dict | None = None) -> dict:
    """Ledger and index are injectable so the multi-day simulation and the tests
    can drive selection without writing files."""
    blueprint = load("config/exam-blueprint.yaml", {})
    cfg = load("config/angles.yaml", {})
    angles = cfg.get("angles", [])
    if index is None:
        index = load("knowledge/index.json", {})
    if ledger is None:
        ledger = load("state.local/ledger.json", {"sections": {}, "questions": {}})

    today = today or datetime.date.today().isoformat()
    want = cfg.get("topics_per_digest", 4)
    restale = cfg.get("restale_days", 5)

    sections = teachable_sections(index)
    if not sections:
        return {"phase": "E", "topics": [], "reason": "no ingested material",
                "remaining_angles": 0, "add_next": []}

    wps = weight_per_section(blueprint, sections)
    led_secs = ledger.get("sections") or {}
    by_angle = {a["id"]: a for a in angles}

    def sec_weight(s):
        return max((wps.get(t, 0.0) for t in s["blueprint"]), default=0.0)

    def days_since(key):
        last = (led_secs.get(key) or {}).get("last_taught")
        if not last:
            return 10_000
        d = datetime.date.fromisoformat(today) - datetime.date.fromisoformat(last)
        return d.days

    picks: list[dict] = []
    used_keys: set[str] = set()

    def add(section, angle, phase, why):
        picks.append({
            "key": section["key"], "page": section["page"],
            "heading": section["heading"], "notion_url": section["notion_url"],
            "blueprint": section["blueprint"][0] if section["blueprint"] else None,
            "angle": angle, "angle_label": by_angle.get(angle, {}).get("label", angle),
            "phase": phase, "why": why,
            "weight_per_section": round(sec_weight(section), 2),
        })
        used_keys.add(section["key"])

    # ── Phase B first: a recorded miss outranks new ground ──────────────────
    for s in sorted(sections, key=lambda x: -sec_weight(x)):
        if len(picks) >= want:
            break
        if s["key"] in used_keys:
            continue
        used = set((led_secs.get(s["key"]) or {}).get("angles_used", []))
        app = applicable_angles(s, angles, ledger, sections)
        if "remediation" in app and "remediation" not in used:
            add(s, "remediation", "B", "answered wrong in a previous quiz")

    # ── Phase A: untaught, weight-aware ────────────────────────────────────
    untaught = [s for s in sections if s["key"] not in led_secs and s["key"] not in used_keys]
    for s in sorted(untaught, key=lambda x: -sec_weight(x)):
        if len(picks) >= want:
            break
        app = applicable_angles(s, angles, ledger, sections)
        first = next((a["id"] for a in sorted(angles, key=lambda x: x["priority"])
                      if a["id"] in app and a["id"] != "remediation"), "trap")
        add(s, first, "A", f"not taught yet · {sec_weight(s):.1f}% of exam per section")

    # ── Phase C: second pass on an unused angle ────────────────────────────
    if len(picks) < want:
        cands = []
        for s in sections:
            if s["key"] in used_keys or s["key"] not in led_secs:
                continue
            if days_since(s["key"]) < restale:
                continue
            used = set((led_secs[s["key"]] or {}).get("angles_used", []))
            for a in sorted(angles, key=lambda x: x["priority"]):
                if a["id"] in applicable_angles(s, angles, ledger, sections) \
                        and a["id"] not in used and a["id"] != "synthesis":
                    cands.append((sec_weight(s) * days_since(s["key"]), s, a["id"]))
                    break
        for _, s, angle in sorted(cands, key=lambda r: -r[0]):
            if len(picks) >= want:
                break
            add(s, angle, "C", f"taught {days_since(s['key'])}d ago · new angle")

    # ── Phase D: synthesis across siblings ─────────────────────────────────
    if len(picks) < want:
        for s in sorted(sections, key=lambda x: -sec_weight(x)):
            if len(picks) >= want or s["key"] in used_keys or s["key"] not in led_secs:
                continue
            used = set((led_secs[s["key"]] or {}).get("angles_used", []))
            if "synthesis" in applicable_angles(s, angles, ledger, sections) \
                    and "synthesis" not in used:
                add(s, "synthesis", "D", "combine with a taught neighbour")

    remaining = remaining_angles(sections, angles, ledger)
    phase = picks[0]["phase"] if picks else "E"
    result = {
        "date": today,
        "phase": phase,
        "topics": picks,
        "remaining_angles": remaining,
        "teachable_sections": len(sections),
        "add_next": uncovered_subsections(blueprint, sections),
    }
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
    if not r["topics"]:
        print(f"\nEXHAUSTED — {r.get('reason')}")
        print("\nAdd next, heaviest exam weight first:")
        for sid, title, w, sq in r["add_next"][:5]:
            print(f"  {sq} {sid} {title}  ({w}% of the exam)")
        return 0
    for i, t in enumerate(r["topics"], 1):
        print(f"  {i}. [{t['phase']}] §{t['blueprint']} {t['heading']}")
        print(f"       angle={t['angle']:<12} {t['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
