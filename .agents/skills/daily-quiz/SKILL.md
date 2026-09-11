---
name: daily-quiz
description: Generate a 10-question exam-style quiz grounded in ingested Notion material, validate it, and post it to Slack with emoji answering. Runs when quiz_at is due, or on !quiz.
---

# daily-quiz

Follow `prompts/quiz.md` for content and `reference/question-spec.md` for
structure. **Read the spec in full before generating** — it is measured from 20
real sample questions and overrides intuition about how these questions look.

## Read the material first

Open the cached text (`knowledge/pages/<slug>.md`) for every page you are asking
about. A question assembled from a heading plus general GCP knowledge is
ungrounded even when its citation resolves — that is the gap `docs/house-style.md`
§2 closes. If a page has no cache, fetch it from its `notion_url` and write one.

## Repetition rules

Run `scripts/build_ledger.py` first. A question whose fingerprint has been asked
before is **rejected** — except that a question answered *wrong* may return
verbatim **once**, at least 3 days later, flagged `"is_retest": true`.

`quiz.mix.new` means a new fingerprint, not a new section, so **the quiz never
exhausts** even when the digest reports it has nothing new to teach.

## Generate then prove

```bash
.venv/bin/python scripts/validate.py state.local/history/<date>/quiz.json
```

**Post only when it exits zero.** A failing question is regenerated, not posted,
and not softened. The gate checks option count and parallelism, stem form,
absence of fictional companies, scenario depth against its label, and — the part
that matters — that every citation and every service name resolves to real
ingested material.

## Posting

Parent message, then **one top-level message per question, with no thread**.
The AWS-analogy reply that used to hang under each question is retired; see
`docs/decisions.md`.

**Never add reactions to a quiz message.** The Slack connector acts as the
learner's own account, not as a bot — a reaction it adds is attributed to
them, indistinguishable from a real answer. Pre-seeding 1️⃣–4️⃣ would
post four answers under the learner's name and destroy the result.

Verified empirically, not assumed: see `docs/decisions.md`.

So question messages go out clean. The learner picks the number emoji themselves;
after the first quiz these sit in Slack's frequently-used row and are one tap.

**Say when the grade will land, and do not overstate it.** A ✅ is read by the
next scheduled run — the hourly drain, or the 20:45 grade routine. That is within
the hour, not instant. Say which, and point at the instant route: open a cloud
session from the phone, or the repo on the laptop, and say "grade it".

## Multi-select

`(choose two)` questions keep **four** options — this is measured from the
corpus, not a simplification. Say so in the stem; the reader reacts twice.

## Record

`state.local/history/<date>/quiz.json`, including for each question: blueprint
tag, `source` (page, exact heading, Notion URL), keyed answer, explanation,
`services[]`, `depth`, and the Slack `message_ts` grading will read.

`aws_equivalents` replaces the old free-prose `aws_anchor`: a list of
`{"gcp": ..., "aws": ...}` for every bracketed equivalence the message asserts,
empty when it asserts none. `validate.py` checks each pair against
`aws-gcp-map.json`, which free prose made impossible.

**`slack.parent_ts` is required.** It is the only handle on the parent message
once the run ends, and `grade-quiz` needs it to find a ✅. It was always written
and never documented, which is how the ✅ trigger came to have no stated way to
find the message it polls.

Also cache the posted message text to `state.local/history/<date>/quiz.md`, so
`validate.check_style` has something to read and there is a record of what
actually went out.

**Then create the `📊 Quiz Results` row now**, with `status: ungraded` and a
collapsed `state` toggle holding `quiz.json` verbatim in a fenced code block.

The row used to be created at grading time. It cannot be, any more: `grade-quiz`
needs `slack.parent_ts` and every question's `message_ts` to read the reactions,
those live nowhere but `quiz.json`, and a cloud run posting the quiz is a
different sandbox from the one grading it. A row that appears only after grading
is a row that arrives too late to make grading possible.

So the lifecycle is now: **`daily-quiz` creates the row, `grade-quiz` completes
it.** `status: ungraded` is also what makes "the most recent ungraded quiz"
answerable from Notion, which is how `!answers` finds its target in the cloud.
See `cloud-bootstrap`.

Set `"trigger": "scheduled"` or `"on_demand"`.

## On demand

`!quiz` creates an **additional** practice set. It never replaces the scheduled
quiz or marks it done. `!quiz <§>` scopes to a subsection, which must be ✅ in
`coverage.md`; if it is not, say so and name what is available instead.
