#!/usr/bin/env python3
"""Is this machine safe to run the pipeline from?

The cloud is the runner. The laptop is for editing logic, which travels through
git. Both can still reach the same Slack channel and the same Notion databases,
so nothing physically stops a local session posting a second digest over one a
routine already posted an hour ago.

What stops it is the watermark. Every run writes `state.local/last_run.json` and
mirrors it to Notion; a laptop whose local copy is behind the mirrored one has
stale state, and stale state is the one input the idempotency guard in daily-run
cannot see past. It checks whether today's output exists in `state.local/history/`
-- and on a laptop that missed three cloud runs, it does not.

The comparison lives here so it can be tested. The Notion value is fetched by the
agent and passed in, because scripts/ has no Notion credential and this file is
not the place to grow one.

    .venv/bin/python scripts/runner_guard.py --notion-ts 1789111712.617369
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAST_RUN = ROOT / "state.local/last_run.json"


def compare(local_ts: str | None, notion_ts: str | None) -> tuple[bool, str]:
    """Pure: no disk, no network. Returns (safe_to_run, why).

    Slack timestamps are decimal strings ("1789111712.617369"), parsed to float
    rather than compared as text. On today's fixed-width values the two orderings
    agree, so this is about the malformed cases, not a clever ordering trick:
    a missing or unparseable watermark must BLOCK, because this runs immediately
    before something that would post to Slack, and "I could not tell" is not a
    reason to go ahead.
    """
    if notion_ts is None:
        return False, ("no watermark in Notion -- cannot tell whether this "
                       "machine is current. Hydrate first, or pass --force.")
    if local_ts is None:
        return False, ("no local watermark, so this clone has never run and "
                       "has no history. The cloud has both; let it run.")
    try:
        local, remote = float(local_ts), float(notion_ts)
    except ValueError:
        return False, f"unparseable watermark: local={local_ts!r} notion={notion_ts!r}"

    if local < remote:
        return False, (f"local state is behind the cloud ({local_ts} < {notion_ts}). "
                       "A run from here would post against a stale history and "
                       "could repeat a digest the cloud already sent.")
    if local > remote:
        return True, (f"local state is ahead of the cloud ({local_ts} > {notion_ts}). "
                      "This machine has unmirrored work -- dehydrate it.")
    return True, "in step with the cloud"


def local_watermark() -> str | None:
    if not LAST_RUN.exists():
        return None
    try:
        return (json.loads(LAST_RUN.read_text()) or {}).get("ts")
    except (json.JSONDecodeError, OSError):
        return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--notion-ts", default=None,
                    help="watermark from the Notion Pipeline State page")
    ap.add_argument("--force", action="store_true",
                    help="report the comparison but always exit zero")
    args = ap.parse_args(argv)

    ok, why = compare(local_watermark(), args.notion_ts)
    print(f"{'OK' if ok else 'STALE'}: {why}")
    if not ok and not args.force:
        print("\nThe cloud owns this pipeline. To run from here anyway, hydrate "
              "first (cloud-bootstrap) or pass --force and accept the risk.")
    return 0 if (ok or args.force) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
