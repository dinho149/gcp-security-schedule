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
2. Read `knowledge/coverage.md` for what is teachable.
3. Read `state.local/mastery.json` for what is weak or due.
4. Pick topics, weighting `aws_traps` up.

## Diagram

Render one PNG per digest and upload it into the digest thread —
`slack_get_file_upload_url` then `slack_complete_file_upload`. This is the only
route to real imagery in Slack and it is worth doing every day.

Draw whatever is structural that day: resource hierarchy, IAM evaluation order,
VPC topology, log routing. If nothing is structural, the topic choice is probably
too thin.

## Post

1. Main message to `config.local.yaml` → `slack.channel_id`.
2. Deep dives as thread replies — progressive disclosure, never inline.
3. Diagram uploaded into the thread.

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
