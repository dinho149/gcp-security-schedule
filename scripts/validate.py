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
sys.path.insert(0, str(ROOT / "scripts"))

from build_ledger import fingerprint, miss_for_section  # noqa: E402  shared
from page_sections import subheadings  # noqa: E402  one parse of a cached page
from slack_links import PERMALINK_RE  # noqa: E402  one definition of the format

# A question answered wrong may be re-asked verbatim exactly once, and not before
# this many days. Repeating it sooner tests recall of an answer, not understanding.
RETEST_MIN_DAYS = 3

# From reference/question-spec.md §2, measured from the official corpus.
OPTIONS_EXACT = 4
OPT_WORDS_MIN, OPT_WORDS_MAX = 1, 26
OPT_SPREAD_MAX = 8
OPT_RATIO_MAX = 2.6
SENTENCES_MAX = 5

# docs/house-style.md §5. Four per message: the section square and the timer are
# two, and the ❌/✅ contrast pair spends the rest.
EMOJI_BUDGET = 4

# Ranges deliberately exclude arrows (U+2190-21FF): "Module 2 -> ..." appears in
# every citation and is punctuation, not decoration.
_EMOJI_CHAR = "[\U0001f300-\U0001faff\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF]"
EMOJI_RE = re.compile(
    r"[0-9#*]\ufe0f?\u20e3"                                  # keycaps: 1 2 3 4
    rf"|{_EMOJI_CHAR}\ufe0f?(?:\u200d{_EMOJI_CHAR}\ufe0f?)*"
)

# docs/house-style.md §5: three or more parallel named items belong on their own
# lines. The rule is enforced conservatively, because a gate that cries wolf
# stops being read -- the same reasoning that makes line length a warning.
#
# Two forms fail, and both were shipped on 2026-09-11:
#   "The six elements - a, b, c, d, e, f - are ..."   (a count, then the items)
#   "... infra, deployment, identity, storage, internet, operational are ..."
# Note neither has a terminal "and". Requiring one would have missed both.
ENUM_HARD_ITEMS = 5    # five short items inline is a list, whatever the wording
ENUM_COUNTED_ITEMS = 3  # three is enough when the sentence names the count
ENUM_ITEM_WORDS = 5    # each item must read as a noun phrase, not a clause
ENUM_LEAD_IN_WORDS = 4  # extra room for a lead-in glued to the first item

# Clause boundaries. An inline enumeration is usually fenced off by dashes,
# a colon or a semicolon, and the fence is not part of an item.
CLAUSE_RE = re.compile(r"\s+[\u2014\u2013-]\s+|[:;]\s*|(?<=[.!?])\s+")
# "the six core elements", "three forms of", "4 levels"
COUNT_RE = re.compile(
    r"\b(three|four|five|six|seven|eight|nine|ten|[3-9]|10)\b", re.I)
# "Scope: org, folder, project, resource" -- an enumeration with no conjunction.
# Warned rather than failed, because the colon form is sometimes a legend.
ENUM_COLON_RE = re.compile(r":\s*((?:[^,;.]{1,40},\s*){3,}[^,;.!?]{1,40})\s*$")

# Digests posted before this date were never cached, so there is nothing to check
# them against and never will be. From this date on, a missing cache is an error:
# check_style globbed */digest.md for the system's whole life and never found
# one, which is how a run-on enumeration and a bare "Q8" both shipped unchecked.
CACHE_REQUIRED_FROM = "2026-09-12"

# Not decoration, so not charged to the budget: the answer emoji ARE the
# interface, and the ballot box is a list bullet that happens to live in a symbol
# block. The section square is NOT exempt -- it is one of the four, which is what
# makes the budget concrete enough to write to.
EMOJI_EXEMPT = {
    "1\ufe0f\u20e3", "2\ufe0f\u20e3", "3\ufe0f\u20e3", "4\ufe0f\u20e3",
    "1\u20e3", "2\u20e3", "3\u20e3", "4\u20e3",
    "\u2610",
}

LINE_CHARS_MAX = 90
MESSAGE_LINES_MAX = 12

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


def _days_between(a: str, b: str) -> int | None:
    try:
        import datetime
        return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days
    except (ValueError, TypeError):
        return None


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

    check_readiness_schedule(r, sch)
    return {"blueprint": bp, "schedule": sch}


def check_readiness_schedule(r: Report, sch: dict) -> None:
    """Pure so it is testable without a config on disk."""
    rd = sch.get("readiness") or {}
    if not rd:
        r.error("schedule", "no readiness block — exam-readiness has nothing to fire on")
        return

    if not re.fullmatch(r"\d{2}:\d{2}", str(rd.get("at") or "")):
        r.error("schedule", f"readiness.at={rd.get('at')!r} is not HH:MM")

    rdays, days = set(rd.get("days") or []), set(sch.get("days") or [])
    if not rdays:
        r.error("schedule", "readiness.days is empty — the report would never fire")
    elif not rdays <= days:
        # The check that earns its keep: a report that never fires looks exactly
        # like a report with nothing to say.
        r.error("schedule", f"readiness.days {sorted(rdays - days)} fall outside the "
                            "run days, so no tick ever reaches them")

    target = rd.get("target")
    if not isinstance(target, (int, float)) or not 0 < target <= 1:
        r.error("schedule", f"readiness.target={target!r} must be a fraction in 0..1")
    elif not str(rd.get("target_basis") or "").strip():
        # Google publishes no pass mark for this exam. An unattributed target
        # becomes "the pass mark" the first time someone reads it quickly.
        r.error("schedule", "readiness.target has no target_basis — the target is ours, "
                            "not Google's, and the file must say so")

    daily = rd.get("daily_from")
    if not isinstance(daily, (int, float)) or not 0 <= daily <= 100:
        r.error("schedule", f"readiness.daily_from={daily!r} outside 0..100")
    elif isinstance(target, (int, float)) and daily <= target * 100:
        r.warn("schedule", "daily_from is at or below target — the report would switch "
                           "to daily the moment it says you are ready")


def check_index(r: Report, bp: dict) -> dict:
    p = ROOT / "knowledge/index.json"
    if not p.exists():
        r.warn("index", "knowledge/index.json missing (run build_index.py) — skipping")
        return {}

    idx = json.loads(p.read_text())
    valid = {sub["id"] for s in bp.get("sections", []) for sub in s["subsections"]}

    headings: set[str] = set()
    covered: set[str] = set()
    page_cache: dict[str, str] = {}
    for course in idx.get("courses", []):
        for page in course["material"]["pages"]:
            if page["ingested"] and not page["sections"]:
                r.warn("index", f"{page['title']!r} marked ingested but has no sections")
            if page["ingested"] and not (ROOT / "knowledge" / (page.get("cache") or "")).is_file():
                # The digest and quiz write FROM this text. Without it they compose
                # from a heading plus general GCP knowledge, which is what made the
                # output read synthetic -- and leaves a citation resolving to a
                # section whose prose was never consulted. A warning, not an error:
                # the existing map predates the field and the write path falls back
                # to fetching the page.
                r.warn("index", f"{page['title']!r} is ingested but has no cached text "
                                "(sync-notion writes knowledge/pages/<slug>.md)")
            if not page["ingested"] and page["sections"]:
                r.error("index", f"{page['title']!r} has sections but ingested=false")
            if page.get("cache"):
                page_cache[page["title"]] = page["cache"]
            for s in page["sections"]:
                headings.add(s["heading"])
                for tag in s["exam_tags"]:
                    if tag not in valid:
                        r.error("index", f"{page['title']!r} → {s['heading']!r} "
                                         f"has unknown exam tag {tag!r}")
                    elif page["ingested"]:
                        covered.add(tag)
    return {"index": idx, "headings": headings, "covered_subsections": covered,
            "page_cache": page_cache}


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

        # ── repetition ────────────────────────────────────────────────────
        fp = fingerprint(q)
        prior = (ctx.get("ledger", {}).get("questions") or {}).get(fp)
        if prior:
            # The ledger is built FROM posted history, so re-validating a quiz
            # that has already been posted would otherwise flag every question as
            # a duplicate of itself. Only earlier outings count.
            asked = [d for d in prior.get("asked", []) if d != ctx.get("quiz_date")]
        if prior and asked:
            wrong = "wrong" in prior.get("outcomes", [])
            if q.get("is_retest"):
                if not wrong:
                    r.error(qid, "flagged as a retest but was never answered wrong")
                elif prior.get("retested"):
                    r.error(qid, "already retested once — the concept must now come "
                                 "back as a newly-written question")
                elif asked and ctx.get("quiz_date"):
                    gap = _days_between(asked[-1], ctx["quiz_date"])
                    if gap is not None and gap < RETEST_MIN_DAYS:
                        r.error(qid, f"retest only {gap}d after the miss; "
                                     f"minimum is {RETEST_MIN_DAYS}d")
            else:
                r.error(qid, f"duplicate question — already asked on {asked[-1] if asked else '?'}"
                             + (". Mark is_retest to use the one sanctioned verbatim retest"
                                if wrong else ". Write a new question on this section"))

        src = q.get("source", {})
        if not src.get("notion_url"):
            r.error(qid, "no source.notion_url — ungrounded")
        if headings and src.get("heading") and src["heading"] not in headings:
            r.error(qid, f"cites heading {src['heading']!r} not present in knowledge/index.json")

        if known_services:
            for name in q.get("services", []):
                if name.lower() not in known_services:
                    r.error(qid, f"names service {name!r} not in aws-gcp-map.json — possible hallucination")

        check_aws_equivalents(r, qid, q.get("aws_equivalents"), ctx.get("aws_map", {}))

    # A graded quiz whose flag stayed false gets graded again on the next run,
    # re-posting every explanation. Latent while nothing read the check-mark;
    # live the moment it does. Found on 2026-09-10, whose results.json existed
    # and had already fed the readiness report while graded read false.
    if not quiz.get("graded") and (path.parent / "results.json").exists():
        r.warn(where, "results.json exists but graded is false — a later run "
                      "will re-grade and re-post. Set graded: true when writing results")

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
        if not src.get("notion_url"):
            r.error(tid, "no source.notion_url — the citation cannot be linked, "
                         "and the page text cannot be fetched to write from")

        # Locator: a citation may point at a PLACE on the page, and if it does,
        # that place must exist. Pointing at a page and stopping left the reader
        # hunting through 200 lines; pointing at an invented sub-heading would be
        # worse, so the pointer is checked against the page it claims.
        loc = src.get("locator") or {}
        if loc:
            sub = (loc.get("subheading") or "").strip()
            cache = (ctx.get("page_cache") or {}).get(src.get("page"))
            if not sub:
                r.error(tid, "source.locator has no subheading — drop the locator "
                             "or name the sub-heading to jump to")
            elif not cache:
                r.warn(tid, "cannot check the locator: no cached text for "
                            f"{src.get('page')!r}")
            else:
                subs = subheadings(Path("knowledge") / cache, heading or "")
                if not subs:
                    r.warn(tid, f"cannot check the locator: {heading!r} has no "
                                "sub-headings in the cached page, or the page is "
                                "not hydrated in this environment")
                elif sub not in subs:
                    r.error(tid, f"locator points at {sub!r}, which is not under "
                                 f"{heading!r}. That section has: {subs}")
            if not (loc.get("look_for") or "").strip():
                r.warn(tid, "locator names a sub-heading but not what to look at "
                            "there — name the table, callout or phrase")

        check_aws_equivalents(r, tid, topic.get("aws_equivalents"), ctx.get("aws_map", {}))

        # Coverage: the subsection must actually be teachable.
        sub = topic.get("blueprint")
        if not sub:
            r.error(tid, "no blueprint subsection recorded")
        elif covered and sub not in covered:
            r.error(tid, f"subsection {sub} is not covered by ingested material — "
                         "the training has not reached it yet, so it must not be taught")

        # Repetition: the same section may be taught again, but never from an
        # angle it has already had. That is what makes a second pass worth reading.
        angle = topic.get("angle")
        if not angle:
            r.error(tid, "no angle recorded — the ledger cannot tell which pass this "
                         "was. It used to default to 'delta', silently burning the "
                         "AWS-delta pass on a section that may never have had one.")
        led_sec = (ctx.get("ledger", {}).get("sections") or {}).get(
            f"{src.get('page')}::{heading}")
        if angle and led_sec and angle in led_sec.get("angles_used", []):
            prior = [t2["date"] for t2 in led_sec.get("taught", [])
                     if t2.get("angle") == angle]
            if prior and prior[-1] != (ctx.get("digest_date") or ""):
                r.error(tid, f"already taught from the {angle!r} angle on {prior[-1]} — "
                             "pick an unused angle or a different section")

        # A remediation topic must say WHICH question, and say enough about it
        # that the reader does not have to scroll back a day. "Q8" alone was the
        # shipped behaviour and it assumes a memory of last night's quiz.
        if angle == "remediation":
            ref = topic.get("question_ref") or {}
            key = f"{src.get('page')}::{heading}"
            _fp, q = miss_for_section(ctx.get("ledger") or {}, key)
            if not ref.get("n"):
                r.error(tid, "a remediation topic must name the question it is "
                             "remediating — question_ref.n")
            elif not (ref.get("recap") or "").strip():
                r.error(tid, f"question_ref cites Q{ref['n']} with no recap — the "
                             "number alone means nothing without scrolling back")
            if ref.get("n") and q is None:
                r.error(tid, f"cites Q{ref.get('n')} but the ledger records no miss "
                             f"on {heading!r} — remediate the question actually "
                             "answered wrong, or pick another angle")
            elif ref.get("n") and q is not None:
                occ = q.get("occurrences") or []
                if not any(o.get("n") == ref.get("n")
                           and (not ref.get("date") or o.get("date") == ref["date"])
                           for o in occ):
                    r.error(tid, f"cites Q{ref['n']} on {ref.get('date')}, which is "
                                 f"not how {heading!r} was missed — the ledger has "
                                 f"Q{(q.get('last_miss') or {}).get('n')} on "
                                 f"{(q.get('last_miss') or {}).get('date')}")
                has_ts = bool((q.get("last_miss") or {}).get("message_ts"))
                if has_ts and not ref.get("url"):
                    r.error(tid, "the ledger has this question's message_ts but the "
                                 "topic carries no permalink — build it with "
                                 "scripts/slack_links.py")
                elif not has_ts:
                    r.warn(tid, "no message_ts recorded for this question, so it "
                                "cannot be linked — cite it as 'Q<n> on <date>'")
            if (url := ref.get("url")) and not PERMALINK_RE.match(url):
                r.error(tid, f"question_ref.url {url!r} is not a Slack permalink")

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


def check_aws_equivalents(r: Report, where: str, claims, amap: dict) -> None:
    """Every asserted GCP->AWS equivalence must appear in Google's own table.

    This replaces a free-prose `aws_anchor` field, which could assert anything and
    be checked against nothing. It is not the tautological kind of gate this repo
    has shipped before: the claim is model-generated and the table is not, so a
    hallucinated counterpart fails here rather than in Slack.

    Absent field == no claim, which keeps records written before it existed valid.
    """
    if not claims or not amap:
        return
    for c in claims:
        gcp, aws = (c.get("gcp") or "").strip(), (c.get("aws") or "").strip()
        if not gcp:
            r.error(where, "aws_equivalents entry with no gcp service named")
            continue
        entry = amap.get(gcp.lower())
        if entry is None:
            r.error(where, f"claims an AWS counterpart for {gcp!r}, which is absent "
                           "from aws-gcp-map.json -- say nothing about AWS instead")
            continue
        if not entry:
            r.error(where, f"claims {aws!r} for {gcp!r}, whose AWS cell is blank. "
                           "That blank IS the answer: say it has no AWS equivalent")
            continue
        if aws and aws.lower() not in entry:
            r.error(where, f"claims {gcp!r} ~ {aws!r}; the map says {entry!r}")


# A line that is exactly this separates one posted message from the next in a
# cached post file. NOT `---`: house style §5 lists a horizontal rule as
# in-message typography, so splitting on it would cut one message into two and
# compute the emoji budget too leniently over each half -- the check would pass
# a message that breaks the rule it exists to enforce.
MESSAGE_SEP = "---8<---"


def _messages(text: str) -> list[str]:
    """Cached post text, one message per separator-delimited block."""
    blocks = [b.strip("\n") for b in
              re.split(rf"(?m)^{re.escape(MESSAGE_SEP)}\s*$", text) if b.strip()]
    return blocks


def _enumeration(line: str) -> tuple[list[str], bool] | None:
    """(items, hard) for an inline enumeration that should have been a list.

    Splits the line into clauses first, so text on either side of a dash is not
    mistaken for an item, then looks for a run of short comma-separated noun
    phrases inside one clause.

    `hard` separates the indefensible from the arguable. Five or more short items
    run into a sentence is never right. Three or four behind a stated count --
    "Four levels, bottom up: resources, projects, folders, the organization
    node" -- is usually worth breaking out but sometimes reads as a chain, so it
    warns rather than failing. A gate that fails on the arguable case gets
    argued with, then ignored.
    """
    counted = bool(COUNT_RE.search(line))
    for clause in CLAUSE_RE.split(line):
        if not clause or "," not in clause:
            continue
        items = [i.strip(" \t*_`") for i in clause.split(",")]
        if any(not i for i in items):
            continue
        # The FIRST item may carry a lead-in that no punctuation separated off
        # -- "The six elements are security foundations, ..." -- so it gets more
        # room than the rest. Every other item must read as a bare noun phrase,
        # which is what keeps an ordinary multi-clause sentence from tripping.
        if len(items[0].split()) > ENUM_ITEM_WORDS + ENUM_LEAD_IN_WORDS:
            continue
        if any(len(i.split()) > ENUM_ITEM_WORDS for i in items[1:]):
            continue
        if len(items) >= ENUM_HARD_ITEMS:
            return items, True
        if counted and len(items) >= ENUM_COUNTED_ITEMS:
            return items, False
    return None


def check_style(r: Report, path: Path, ctx: dict) -> None:
    """House style over what was actually posted (docs/house-style.md §5).

    Only the countable half. Voice is carried by prompts/ and cannot be entailed
    from text -- the same division docs/decisions.md settled for teaching beyond
    the material. Emoji budget and blank-line runs are exact, so they are errors;
    length is a judgement, so it warns.
    """
    where = path.name
    text = path.read_text()

    for i, msg in enumerate(_messages(text), 1):
        mid = f"{where} message {i}"
        lines = msg.split("\n")

        found = [e for e in EMOJI_RE.findall(msg) if e not in EMOJI_EXEMPT]
        if len(found) > EMOJI_BUDGET:
            r.error(mid, f"{len(found)} emoji, budget is {EMOJI_BUDGET}: "
                         f"{' '.join(found)}")

        for n, (a, b) in enumerate(zip(lines, lines[1:]), 1):
            if not a.strip() and not b.strip():
                r.error(mid, f"blank line {n} is doubled -- exactly one between blocks")
                break

        in_fence = False
        for n, line in enumerate(lines, 1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence or line.lstrip().startswith("|") or "http" in line:
                continue
            if len(line) > LINE_CHARS_MAX:
                r.warn(mid, f"line {n} is {len(line)} chars; wrap under {LINE_CHARS_MAX}")
            # Headings, block quotes and Slack link syntax are not prose.
            # Bullets deliberately stay in scope: a bullet holding six
            # comma-separated things is the same failure as a sentence holding
            # them, which is how SAIF's six elements shipped as one line.
            if line.lstrip().startswith(("#", ">")) or "<" in line:
                continue
            if found := _enumeration(line):
                items, hard = found
                msg = (f"line {n} runs {len(items)} items into a sentence: "
                       f"{items} — house style §5 puts three or more parallel "
                       "items on their own lines")
                (r.error if hard else r.warn)(mid, msg)
            elif mc := ENUM_COLON_RE.search(line):
                listed = [i.strip() for i in mc.group(1).split(",") if i.strip()]
                if len(listed) >= ENUM_COUNTED_ITEMS + 1:
                    r.warn(mid, f"line {n} lists {len(listed)} items after a colon: "
                                f"{listed} — consider one per line")

        body = [ln for ln in lines if ln.strip()]
        if len(body) > MESSAGE_LINES_MAX:
            r.warn(mid, f"{len(body)} non-blank lines; over ~{MESSAGE_LINES_MAX} "
                        "the overflow belongs in the thread")


def check_readiness(r: Report, path: Path, ctx: dict) -> None:
    """The posted report must say what the script computed.

    The numbers themselves are script-generated and deliberately NOT re-derived
    here -- that would be one script re-asserting another, the tautological gate
    this repo has already shipped once. What is checked is the transcription,
    because a report that drops a headline or rounds the wrong number looks
    exactly like a correct one to a reader.
    """
    where = path.name
    try:
        rec = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        r.error(where, f"invalid JSON: {e}")
        return

    posted, src = rec.get("posted"), rec.get("source") or {}
    if posted is None:
        # state.local/readiness.json (the snapshot) also ends in readiness.json.
        r.warn(where, "no posted block — snapshot, not a posted report; skipping")
        return

    for key in ("headline_true", "headline_covered"):
        if posted.get(key) is None:
            r.error(where, f"{key} missing — never post one headline without the "
                           "other; alone it is a claim about the reachable slice "
                           "dressed up as a claim about the exam")

    for posted_key, src_key in (("headline_true", "true"),
                                ("headline_covered", "on_covered")):
        got, want = posted.get(posted_key), src.get(src_key)
        if got is None or want is None:
            continue
        if round(want * 100) != got:
            r.error(where, f"{posted_key}={got} but the script computed "
                           f"{want * 100:.1f}% — the message and the file disagree")

    true, ceiling = src.get("true"), src.get("reachable")
    if true is not None and ceiling is not None and true > ceiling + 5e-4:
        r.error(where, f"true readiness {true:.1%} exceeds the coverage ceiling "
                       f"{ceiling:.1%} — readiness is capped by coverage, and "
                       "breaking that lies in the flattering direction")

    if posted.get("too_early") != src.get("too_early"):
        r.error(where, "posted too_early disagrees with the computed estimate")
    if posted.get("too_early") and posted.get("days_estimate") is not None:
        r.error(where, "a days estimate was posted alongside 'still too early to "
                       "decide' — one of the two is wrong")
    if not posted.get("too_early") and posted.get("confidence") not in \
            {"low", "medium", "high"}:
        r.error(where, f"confidence {posted.get('confidence')!r} is not one of "
                       "low/medium/high")

    want_ids = {s["id"] for s in (ctx.get("blueprint", {}).get("sections") or [])}
    got_ids = set((posted.get("sections") or {}).keys())
    if want_ids and got_ids != want_ids:
        r.error(where, f"per-section breakdown covers {sorted(got_ids)}, expected "
                       f"{sorted(want_ids)} — a dropped section is invisible to a reader")

    cfg_target = ((ctx.get("schedule") or {}).get("readiness") or {}).get("target")
    if cfg_target is not None and src.get("target") not in (None, cfg_target):
        r.error(where, f"report computed against target {src.get('target')} but the "
                       f"config says {cfg_target}")


def main(argv: list[str]) -> int:
    r = Report()
    ctx = check_config(r)
    ctx.update(check_index(r, ctx.get("blueprint", {})))

    led = ROOT / "state.local/ledger.json"
    ctx["ledger"] = json.loads(led.read_text()) if led.exists() else {}

    amap = ROOT / "knowledge/aws-gcp-map.json"
    if amap.exists():
        svcs = json.loads(amap.read_text())["services"]
        ctx["services"] = {s["gcp"].lower() for s in svcs}
        # Lowercased AWS cell per service. An empty string is meaningful: Google
        # left that cell blank on purpose, so it means "no counterpart", never
        # "unknown". check_aws_equivalents relies on the distinction.
        ctx["aws_map"] = {s["gcp"].lower(): (s.get("aws") or "").lower() for s in svcs}
    else:
        ctx["services"] = set()
        ctx["aws_map"] = {}

    quizzes = [Path(a) for a in argv if a.endswith("quiz.json")]
    digests = [Path(a) for a in argv if a.endswith("digest.json")]
    reports = [Path(a) for a in argv if a.endswith("readiness.json")]
    posts = [Path(a) for a in argv if a.endswith((".md",))]
    if not argv:
        quizzes = sorted((ROOT / "state.local/history").glob("*/quiz.json"))
        digests = sorted((ROOT / "state.local/history").glob("*/digest.json"))
        # history/ only, so the state.local/readiness.json snapshot is never
        # picked up by the no-arg glob.
        reports = sorted((ROOT / "state.local/history").glob("*/readiness.json"))
        posts = sorted((ROOT / "state.local/history").glob("*/digest.md")) + \
            sorted((ROOT / "state.local/history").glob("*/quiz.md"))
    for q in quizzes:
        ctx["quiz_date"] = q.parent.name
        check_quiz(r, q, ctx)
    for d in digests:
        ctx["digest_date"] = d.parent.name
        check_digest(r, d, ctx)
        # Without the cached text there is nothing for check_style to read, and
        # for the system's whole life there never was one: the */digest.md glob
        # matched nothing, so every posted digest went out unchecked.
        if not (d.parent / "digest.md").exists():
            msg = ("no sibling digest.md — the posted text was never cached, so "
                   "house style was not checked against what actually went out")
            report = r.error if d.parent.name >= CACHE_REQUIRED_FROM else r.warn
            report(d.name, msg)
    for po in posts:
        check_style(r, po, ctx)
    for rd in reports:
        ctx["readiness_date"] = rd.parent.name
        check_readiness(r, rd, ctx)

    print(f"validate: config + index checked, {len(quizzes)} quiz + "
          f"{len(digests)} digest + {len(reports)} readiness + "
          f"{len(posts)} posted-text file(s)")
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
