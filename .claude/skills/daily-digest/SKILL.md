---
name: daily-digest
description: Generate and post the daily digest to Slack, mirror it to Notion, and cache it locally. Prepares the reader for the day's quiz. Runs when digest_at is due, or on !digest.
---

# daily-digest

Follow `prompts/digest.md` for content and `docs/house-style.md` for form. This
file covers the mechanics.

## Before writing

1. Read `profile.local.yaml`. **Altitude first** — the reader holds AWS Security
   Specialty, AWS SA Pro and CKA and leads a platform security team. Explaining
   something on `assume_known` is the worst failure this system can make.
2. **Run the selector — do not choose topics yourself:**

   ```bash
   .venv/bin/python scripts/build_ledger.py
   .venv/bin/python scripts/build_mastery.py
   .venv/bin/python scripts/select_topics.py --json
   ```

   It returns each section, the **angle** to use, and the band. It knows what has
   already been taught and from which angle; you do not.

   `build_mastery.py` is a prerequisite: the `review` band ranks on `next_due`,
   and without it selection falls back to bare staleness.

   Four fields of the envelope are **content, not diagnostics** — they say
   something the digest has to say out loud:

   | Field | Say |
   |---|---|
   | `mix` | the shape of today: misses, new ground, review |
   | `deferred` | "two more misses are queued for tomorrow" — one line, closing message |
   | `unfilled_floors` | `["new"]` means there is no new ground left. Do not pad around it |
   | `fresh_slot` | mark the agenda entry `_(just ingested)_` |

3. **Open the cached page text for every section the selector returned**
   (`knowledge/pages/<slug>.md`, path in `index.json` as `cache`). Write the
   topic from that text, in its terms — `docs/house-style.md` §2. If a page has
   no cache yet, fetch it from its `notion_url` and write one.

   The selector hands you a heading, a URL and a service list. None of that is
   the material. A topic written from it alone is the model's own prose wearing a
   citation, which is the single largest reason the digest reads synthetic.

   While the page is open, pick the **locator** for its citation — the
   sub-heading the reader should jump to, and the table, callout or phrase to
   read there (`docs/house-style.md` §7):

   ```bash
   .venv/bin/python scripts/page_sections.py --page knowledge/<cache> --heading "<heading>"
   ```

   Record it as `source.locator` on the topic. `validate.py` rejects a
   sub-heading the page does not actually have. Five of the thirty ingested
   sections are flat — omit the locator for those rather than inventing one.

4. Write each topic at the angle given. Record the `angle` on every topic in
   `digest.json` — the ledger and the repeat check both depend on it.

### If the selector returns no topics (phase E)

The material is exhausted. **Do not pad.** Post the short honest message described
in `prompts/digest.md`: what has been covered, where they stand, and precisely
what to add next from `add_next`. Then let the quiz run as normal — spaced
repetition does not exhaust.

## Visuals

Write every visual for the day into one spec file, then render them in a single
command:

```bash
.venv/bin/python dashboard/render.py state.local/history/<date>/visuals.json
# -> state.local/history/<date>/visuals/<id>.png
```

`dashboard/visuals.py` holds six components (`compare`, `chain`, `contrast`,
`sequence`, `decision`, `code`) and their demo specs, which double as fixtures.
`.venv/bin/python dashboard/visuals.py --demo-specs` prints a working example of
each.

**One visual per topic minimum, two when the topic earns it. Never repeat a
component within one digest.**

The renderer **fails loudly if a visual would be clipped** — it detects content
reaching the canvas edge via the sentinel border. Fix the spec (shorter text, or a
wider `width`); do not post a truncated diagram.

Rendering takes ~2s per visual and needs no browser session, so it runs unattended.

**If no browser binary exists at all** — possible in a cloud sandbox, where
`cloud-bootstrap` probes for one — post the digest text-only and say the visuals
are unavailable. Do not skip the digest, and do not describe a diagram that was
never rendered. A clipped visual is a bug worth failing on; an absent renderer is
an environment fact, and the words carry the day's teaching on their own.

## Post — a sequence, not one message

1. **Parent**: hook, thesis, ⏱ total, numbered agenda of the topics.
2. **One top-level message per topic**, each ending in its Notion citation.
3. **Into each topic's thread**: its visual(s), then the deep dive.
   Upload with `slack_get_file_upload_url` → POST bytes → `slack_complete_file_upload`
   with `thread_ts` set to that topic's message.
4. **Closing message**: the pre-quiz checklist, plus any `deferred` misses.
5. **Cache what went out, and validate it before going further**:

   ```bash
   # every posted message verbatim, in posted order, separated by a line
   # containing only ---8<---   (NOT ---, which is in-message typography)
   #   -> state.local/history/<date>/digest.md
   .venv/bin/python scripts/validate.py \
       state.local/history/<date>/digest.json state.local/history/<date>/digest.md
   ```

   **Do not mirror to Notion until this passes.** This step was specified for the
   system's whole life and never actually done, so `check_style` globbed
   `*/digest.md`, matched nothing, and every digest ever posted went out
   unchecked — which is how a run-on list of SAIF's six elements and a bare "Q8"
   both shipped on 11 Sep. A retracted message must **not** appear in the cache:
   it is a record of what a reader sees, not of what was attempted.

Record every `message_ts` in `state.local/history/<date>/digest.json` so a later
`!digest` on the same day can reference what was already covered.

**Record each topic's `angle`**, exactly as the selector returned it. It is not
optional: the ledger used to default a missing angle to `delta`, which claimed the
AWS-delta pass — the highest-value first pass for this reader — on sections that
had never had one, and selection then skipped straight to a weaker angle.
`validate.py` now rejects a topic without one.

Threads are flat in Slack (`docs/decisions.md`), which is exactly why topics are
top-level messages: a visual can only be collapsed under a top-level parent.

## Then

1. Write to the `📖 Daily Digests` Notion database as **rich blocks** — coloured
   callouts per section, toggles for depth, dividers, tables. Not plain text.
2. On that same row, add a collapsed **`state`** toggle holding `digest.json`
   verbatim in a fenced code block — `message_ts` values included.

   The rich blocks above are for a human to read; this is for the next run to
   parse. A cloud run starts from a fresh clone with no `state.local/`, so a
   `ts` that exists only on the laptop may as well not exist: `build_ledger.py`
   matches retractions on `ts`, and `!digest` later the same day needs to know
   what already went out. See `cloud-bootstrap`.
3. (The posted text was already cached and validated — Post step 5.)
4. Record which subsections it covered, so the quiz draws from the same ones.

## Retraction

If a posted topic has to be withdrawn — it ran ahead of the material, it was
wrong — record it **both** ways, because they answer different questions:

```json
"retractions": [{"topic": 4, "ts": "<the withdrawn message ts>",
                 "retracted_ts": "...", "reason": "..."}]
```

and, if the message stays in `topics[]`, `"retracted": true` on the topic itself.

`build_ledger.py` matches on **`ts`**, never on the topic number. A withdrawn
topic is usually replaced and the replacement reuses the same number, so keying on
the number drops the replacement and undercounts what was taught — the same error
as counting the retraction, pointing the other way. That is exactly what the
2026-09-11 digest did.

## Ordering guarantee

The digest must land before the quiz. `daily-run` enforces this, but check
anyway: if today's quiz somehow exists and the digest does not, post the digest
and note the inversion rather than skipping it.

## On demand

`!digest` when one already went out today generates a **new** digest on the next
weakest topics — never a repeat. `!digest <topic>` scopes to one subsection,
which must still be ✅ in `coverage.md`.
