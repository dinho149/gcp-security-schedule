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

**Never add reactions to a quiz message.** The Slack connector acts as the
learner's own account, not as a bot — a reaction it adds is attributed to
`U0C1UME5GQG`, indistinguishable from a real answer. Pre-seeding 1️⃣–4️⃣ would
post four answers under the learner's name and destroy the result.

Verified empirically, not assumed: see `docs/decisions.md`.

So question messages go out clean. The learner picks the number emoji themselves;
after the first quiz these sit in Slack's frequently-used row and are one tap.

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
