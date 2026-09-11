#!/usr/bin/env python3
"""Build Slack permalinks for messages this system has already posted.

A digest that remediates a miss used to say "Q8" and stop there, which asks the
reader to scroll back a day to find out what Q8 was. Every quiz question is its
own top-level Slack message and its `message_ts` has always been recorded, so
the link was constructible the whole time -- nothing built one.

This lives in a script rather than in the prompt because the ts -> permalink
transform (drop the dot, prefix `p`) is exactly the kind of rule a model gets
subtly wrong in a way nobody notices until a link 404s.

    .venv/bin/python scripts/slack_links.py --date 2026-09-10 --n 5
    .venv/bin/python scripts/slack_links.py --fingerprint 283b2389f2d418a3
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config/config.local.yaml"
LEDGER = ROOT / "state.local/ledger.json"

# Slack ts is seconds.microseconds. Anything else is not a message handle, and a
# permalink built from it would resolve to nothing.
TS_RE = re.compile(r"^\d{10}\.\d{6}$")
# The <name> in https://<name>.slack.com.
WS_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")
CHAN_RE = re.compile(r"^[CGD][A-Z0-9]{6,}$")

# What a built permalink looks like, so validate.py can check one without
# reimplementing the format.
PERMALINK_RE = re.compile(
    r"^https://[a-z0-9][a-z0-9-]*\.slack\.com/archives/[CGD][A-Z0-9]{6,}/p\d{16}"
    r"(\?\S*)?$")


def workspace(cfg: dict | None = None) -> str:
    """The workspace subdomain, from config.local.yaml.

    Raises rather than guessing. A wrong subdomain yields a URL that looks right
    and lands nowhere, which is worse than no link at all -- and the value is
    personal, so it cannot have a committed default.
    """
    if cfg is None:
        if not CONFIG.exists():
            raise SystemExit(f"missing {CONFIG.relative_to(ROOT)} -- "
                             "copy config/config.example.yaml and fill it in")
        cfg = yaml.safe_load(CONFIG.read_text()) or {}
    ws = ((cfg.get("slack") or {}).get("workspace") or "").strip()
    if not ws:
        raise SystemExit("slack.workspace is not set in config/config.local.yaml "
                         "-- it is the <name> in https://<name>.slack.com")
    if not WS_RE.match(ws):
        raise SystemExit(f"slack.workspace {ws!r} is not a workspace subdomain")
    return ws


def permalink(ws: str, channel_id: str, ts: str,
              thread_ts: str | None = None) -> str | None:
    """None -- never a half-formed URL -- if any part fails its regex."""
    if not (ws and channel_id and ts):
        return None
    if not (WS_RE.match(ws) and CHAN_RE.match(channel_id) and TS_RE.match(ts)):
        return None
    url = f"https://{ws}.slack.com/archives/{channel_id}/p{ts.replace('.', '')}"
    if thread_ts and TS_RE.match(thread_ts):
        url += f"?thread_ts={thread_ts}&cid={channel_id}"
    return url


def question_ref(entry: dict, ws: str) -> dict | None:
    """A ledger question entry -> everything a digest needs to cite it.

    Returns None when the entry records no miss: there is nothing to remediate,
    so there is nothing to link. A miss with no `message_ts` -- history written
    before the field existed -- still returns a ref, with `url: None`. The digest
    degrades to an unlinked "Q5 on 10 Sep" rather than dropping the reference.
    """
    miss = (entry or {}).get("last_miss")
    if not miss:
        return None
    return {
        "n": miss.get("n"),
        "date": miss.get("date"),
        "url": permalink(ws, miss.get("channel_id") or "", miss.get("message_ts") or ""),
        "stem": entry.get("stem"),
        "scenario": entry.get("scenario"),
        "options": entry.get("options"),
        "answered": miss.get("answered"),
        "keyed": miss.get("keyed"),
    }


def _ledger() -> dict:
    if not LEDGER.exists():
        raise SystemExit(f"missing {LEDGER.relative_to(ROOT)} -- "
                         "run scripts/build_ledger.py first")
    return json.loads(LEDGER.read_text())


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fingerprint", help="ledger question id")
    ap.add_argument("--date", help="with --n, the quiz date")
    ap.add_argument("--n", type=int, help="with --date, the question number")
    args = ap.parse_args(argv)

    ws = workspace()
    led = _ledger()
    questions = led.get("questions") or {}

    if args.fingerprint:
        entry = questions.get(args.fingerprint)
        if entry is None:
            print(f"no question {args.fingerprint!r} in the ledger", file=sys.stderr)
            return 1
    elif args.date and args.n:
        entry = next((e for e in questions.values()
                      if any(o.get("date") == args.date and o.get("n") == args.n
                             for o in e.get("occurrences") or [])), None)
        if entry is None:
            print(f"no question Q{args.n} on {args.date} in the ledger", file=sys.stderr)
            return 1
    else:
        ap.error("give --fingerprint, or --date and --n")

    ref = question_ref(entry, ws)
    if ref is None:
        # Not an error: the question exists and was answered correctly.
        print(json.dumps({"ref": None, "reason": "no recorded miss"}, indent=2))
        return 0
    print(json.dumps(ref, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
