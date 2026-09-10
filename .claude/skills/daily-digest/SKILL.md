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
   .venv/bin/python scripts/select_topics.py --json
   ```

   It returns each section, the **angle** to use, and the phase. It knows what has
   already been taught and from which angle; you do not.

3. Write each topic at the angle given. Record the `angle` on every topic in
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

## Post — a sequence, not one message

1. **Parent**: hook, thesis, ⏱ total, numbered agenda of the topics.
2. **One top-level message per topic**, each ending in its Notion citation.
3. **Into each topic's thread**: its visual(s), then the deep dive.
   Upload with `slack_get_file_upload_url` → POST bytes → `slack_complete_file_upload`
   with `thread_ts` set to that topic's message.
4. **Closing message**: the pre-quiz checklist, which ends the run.

Record every `message_ts` in `state.local/history/<date>/digest.json` so a later
`!digest` on the same day can reference what was already covered.

Threads are flat in Slack (`docs/decisions.md`), which is exactly why topics are
top-level messages: a visual can only be collapsed under a top-level parent.

## Then

1. Write to the `📖 Daily Digests` Notion database as **rich blocks** — coloured
   callouts per section, toggles for depth, dividers, tables. Not plain text.
2. Cache to `state.local/history/<date>/digest.md`.
3. Record which subsections it covered, so the quiz draws from the same ones.

## Ordering guarantee

The digest must land before the quiz. `daily-run` enforces this, but check
anyway: if today's quiz somehow exists and the digest does not, post the digest
and note the inversion rather than skipping it.

## On demand

`!digest` when one already went out today generates a **new** digest on the next
weakest topics — never a repeat. `!digest <topic>` scopes to one subsection,
which must still be ✅ in `coverage.md`.
