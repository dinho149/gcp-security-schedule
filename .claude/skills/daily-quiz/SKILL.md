---
name: daily-quiz
description: Generate a 10-question exam-style quiz grounded in ingested Notion material, validate it, and post it to Slack with emoji answering. Runs when quiz_at is due, or on !quiz.
---

# daily-quiz

Follow `prompts/quiz.md` for content and `reference/question-spec.md` for
structure. **Read the spec in full before generating** — it is measured from 20
real sample questions and overrides intuition about how these questions look.

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

Parent message, then one threaded reply per question.

Pre-seed 1️⃣–4️⃣ on every question message with `slack_add_reaction` so answering
is a tap rather than an emoji hunt. Grading filters to `slack.user_id`, so the
seeds do not corrupt the result.

Post the AWS hint as a **collapsed thread reply under each question**
(`prompts/hint.md`). Slack hides thread replies by default, which makes it a
spoiler the reader opens deliberately — with none of the latency a
reaction-triggered hint would have.

## Multi-select

`(choose two)` questions keep **four** options — this is measured from the
corpus, not a simplification. Say so in the stem; the reader reacts twice.

## Record

`state.local/history/<date>/quiz.json`, including for each question: blueprint
tag, `source` (page, exact heading, Notion URL), keyed answer, explanation, AWS
anchor, `services[]`, `depth`, and the Slack `message_ts` grading will read.

Set `"trigger": "scheduled"` or `"on_demand"`.

## On demand

`!quiz` creates an **additional** practice set. It never replaces the scheduled
quiz or marks it done. `!quiz <§>` scopes to a subsection, which must be ✅ in
`coverage.md`; if it is not, say so and name what is available instead.
