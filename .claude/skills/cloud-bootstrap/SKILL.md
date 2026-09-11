---
name: cloud-bootstrap
description: Rehydrate the gitignored working files from Notion at the start of a cloud run, and write changed state back at the end. Used by cloud-run; never needed on the laptop, which already has the files.
---

# cloud-bootstrap

A cloud run starts from a fresh clone of a **public** repo, so every file the
pipeline actually reads is absent: `config/config.local.yaml`,
`profile.local.yaml`, `knowledge/`, `state.local/`, `reference/exemplars/`.

This skill puts them back from Notion, and writes the changed ones back at the
end. Two entry points, `hydrate` and `dehydrate`, and `cloud-run` calls both.

On the laptop it is never needed — the files are already there.

## The rule that matters

**Never invent state, and never proceed on partial state.** An empty
`state.local/history/` does not mean "nothing has been taught", it means the read
failed — and a digest generated from it would repeat a week of material and
silently reset the ledger. If any required payload is missing or will not parse:
stop, post the failure to Slack, and run nothing. A run that does not happen is
recoverable. A run against blank state corrupts the record.

Same reasoning as rule 2 in `CLAUDE.md`: absence of evidence is not evidence of
absence.

## Layout in Notion

Under the same root as `📊 Quiz Results` and `📖 Daily Digests`:

```
🔧 Pipeline State        one page, a fenced code block per payload
├── config               config/config.local.yaml            (yaml)
├── watermark            state.local/last_run.json           (json)
├── sources              knowledge/sources.local.json        (json)
├── control              {"paused", "force_full", "synced_on",
│                          "exemplars_file_upload_id", "render_probe"}
└── readiness            one line per run: date, on_covered, cadence, too_early

👤 Learner Profile       profile.local.yaml                  (yaml)
📚 Exam Samples          reference/exemplars/official-samples.md
```

Each payload is one fenced code block under a heading of that exact name. Write
with `notion-update-page` (it takes markdown and handles block chunking), read
with `notion-fetch` (it returns enhanced markdown, so the fence comes back whole).

**If a payload ever exceeds what a code block round-trips cleanly**, switch that
one to `notion-create-attachment` (inline `content`, 200 KiB ceiling, JSON and
YAML both supported) and record its `file_upload_id` in the `control` block for
`notion-download-attachment` to read back. Nothing here is near that ceiling
today — the largest is `index.json` at 16K — so code blocks stay the default.

## Bootstrap — finding the page without config

Reading Notion needs `root_page_id`, which lives in the config being read. Break
the cycle by **searching for `🔧 Pipeline State` by title**. No environment
variable, no credential, nothing to rotate.

Notion search is fuzzy and ranks by relevance, so it returns near-misses too.
**Match on the title being exactly `🔧 Pipeline State`, not on being the first
result.** Verified: the exact-title page ranks first, but four unrelated pages
come back with it.

If that yields anything other than exactly one page, stop. Zero means the state
store is missing and a run would build on nothing; two means a duplicate and a
split-brain store. Both are worse than no run.

## hydrate

1. Find `🔧 Pipeline State`. Read `control` first.

   **If `paused` is true, do not stop dead.** Scan Slack for `!resume` and
   `!ping` only, act on those, and skip everything else. Nothing else is read,
   nothing is posted, no state is written.

   This exception is not a nicety. `!resume` is an on-demand command, on-demand
   commands are handled by `daily-run`, and `daily-run` runs *inside* the thing
   the pause stops — so a pause that stopped everything could never be lifted
   from Slack, only by opening a session. A pause with no remote release is a
   trap, and the whole point of these commands is that the phone is enough.
2. Write `config/config.local.yaml` and `profile.local.yaml`.
3. Write `knowledge/sources.local.json`. **Never regenerate this from a fresh
   walk** — it carries the `ingested_on` stamps, which `sync-notion` says are
   written once and never rewritten. They are what lets the readiness estimate
   measure pace; a re-walk would silently reset every one of them to today and
   make the coverage rate unknowable.
4. Rebuild `knowledge/index.json` and `knowledge/coverage.md` **from `sources`**,
   with no Notion access at all:

   ```bash
   .venv/bin/python scripts/build_index.py      # <- sources.local.json
   .venv/bin/python scripts/build_coverage.py   # <- index.json + exam-blueprint.yaml
   ```

   Verified, not assumed: `build_index.py` reads nothing but
   `knowledge/sources.local.json`, and rebuilding produces a byte-identical
   `index.json`. `coverage.md` then derives from that plus the committed
   blueprint, differing only in its generation date. Neither is stored in Notion,
   because storing a derived file invites the two copies to disagree.

   Then decide whether to walk at all: **if `control.synced_on` is today, skip
   `sync-notion`.** Otherwise run it and stamp the date in `dehydrate`.

   That check is what keeps the cost sane. `sync-notion` is specified to run on
   the first session of each day, but every cloud run is a fresh sandbox and
   therefore looks like the first — without the stamp, five routines a day means
   five full walks of the tree for an answer that cannot have changed.
5. Rebuild `state.local/history/` from the two databases: query every row, take
   the verbatim JSON out of each row's `state` toggle, and write it back to
   `state.local/history/<date>/{digest,quiz,results}.json`.
6. Write `state.local/last_run.json` from `watermark`, and reconstruct
   `state.local/history/<date>/readiness.json` for each entry in `readiness`,
   **in the shape `due.py` reads** — `{"date", "cadence", "source": {"on_covered"}}`.

   The nesting under `source` is not decorative. `due.py` reads exactly
   `(rec.get("source") or {}).get("on_covered")`; a flat `score` key reads as
   `None`, the hysteresis band then compares against nothing, and the cadence
   flips every day on a score sitting near the line — while looking correct.

   Readiness deliberately gets no Notion database — `docs/privacy.md` argues a
   mirror would put a second competence profile in the workspace and buy nothing
   a rerun does not. That still holds: the *report* is recomputed, because
   `build_readiness.series()` replays mastery per graded day. What cannot be
   recomputed is the **cadence decision** — `due.py` reads the last report's
   score and whether it was daily, to apply the hysteresis band — and the marker
   that says one already posted today. Those two facts are all that is stored,
   which is why this is a line per run and not a snapshot archive.
7. Rebuild the history-derived files, in this order — the chain is not optional
   and the order is not arbitrary:

   ```bash
   .venv/bin/python scripts/build_ledger.py
   .venv/bin/python scripts/build_mastery.py
   .venv/bin/python scripts/build_readiness.py
   ```

8. `reference/exemplars/official-samples.md`, only if a quiz is going to be
   generated. It is the one file kept out of the repo for copyright rather than
   privacy, and the one payload stored as an **attachment** rather than a code
   block: read it with `notion-download-attachment` using
   `control.exemplars_file_upload_id`.

   The id is recorded in `control` because fetching `📚 Exam Samples` yields a
   signed file URL, not an upload id, and the download tool takes the id. Both
   carriers are verified: a 14K code block round-trips byte-identically, and the
   13K attachment reads back complete.
9. **Nothing.** Renderer resolution moved out of hydrate and into the renderer
   itself — `dashboard/ensure_chrome.py`, which `render.py` calls. Do not write
   `render.chrome_path`; the stored macOS path is treated as a hint and fallen
   through when it does not exist.

   This is deliberate laziness. Only the digest renders a PNG, so only the digest
   should pay for a browser. Resolving in hydrate made the quiz, grading and
   readiness routines wait on a capability none of them use.

   What hydrate *does* owe the renderer is the cached probe. Read
   `control.render_probe`:

   ```json
   {"checked_on": "2026-09-11", "result": "installed", "via": "npx-puppeteer"}
   ```

   - `result: "unavailable"` and `checked_on` within 7 days → pass `--no-install`
     to `render.py`. The sandbox has already proved it cannot host a browser;
     re-paying a three-minute download every morning buys nothing.
   - a recorded `via` → pass it as `--prefer`, so the resolver goes straight to
     the installer that worked rather than walking a route it knows fails.
   - `checked_on` older than 7 days, or absent → probe fresh and rewrite it.

   **The TTL is the load-bearing part.** The sandbox image changes under us, and a
   cached negative with no expiry is how visuals stay off forever after one bad
   morning.

   **A missing browser never fails the run.** `render.py` exits 2 with the reason;
   `daily-digest` posts text-only, records it in `digest.json`, and says so. A
   digest without diagrams is worth more than no digest.

`knowledge/pages/<slug>.md` is **not** hydrated in bulk. A run cites a handful of
sections, so digest and quiz fetch the pages they actually need from Notion and
cache them locally for the rest of that run.

## dehydrate

Write back only what changed, and only what is primary:

| Write back | Where |
|---|---|
| `state.local/history/<today>/*.json` | the `state` toggle on today's database rows |
| `state.local/last_run.json` | `watermark` |
| a `readiness` line, if one posted | `readiness` |
| `knowledge/sources.local.json` | `sources`, if `sync-notion` ran |
| today's date as `synced_on` | `control`, if `sync-notion` ran |
| `render_probe`, if the renderer was resolved this run | `control` |
| `profile.local.yaml` | `👤 Learner Profile`, if `!known` or 🥱 changed it |

**Never write back** `ledger.json`, `mastery.json`, `readiness.json`,
`index.json`, `coverage.md`, or anything under `dashboard/`. Every one of them is
derived — from `sources` or from history — and `hydrate` rebuilds them in
seconds. Storing a derived file only creates a second copy to disagree with.

**Write the watermark last.** It is the marker that says this run's intake was
handled; writing it before the work is durable means a crash in between loses a
`!quiz` with no trace that it was ever asked for.

## Ordering

`hydrate` fully, then run, then `dehydrate` fully. Do not interleave — a run that
writes state back as it goes and then fails halfway leaves Notion holding a day
that half happened, which is the one thing the idempotency guard in `daily-run`
cannot detect, because a half-written history row looks exactly like a finished one.
