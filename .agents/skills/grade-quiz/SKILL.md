---
name: grade-quiz
description: Read emoji reactions on a posted quiz, grade it, explain every miss, and rebuild mastery and spaced repetition from the result. Runs when grade_at is due, on ✅ on the quiz parent, or on !answers.
---

# grade-quiz

Follow `prompts/grading.md` for wording. This file covers mechanics.

## Reading answers

For each question's `message_ts`, call `slack_get_reactions`.

**Count only reactions from `config.local.yaml` → `slack.user_id`.**

Two reasons, and the second is the one that bites:

1. The channel is public, so anyone in the workspace could react.
2. The connector acts as the learner's own account. Anything the agent reacts
   with is attributed to them — which is why `daily-quiz` never seeds option
   emoji, and why nothing here may add reactions either.

| Reaction | Meaning |
|---|---|
| 1️⃣–4️⃣ | The answer. Two on a `(choose two)` is complete. |
| 🥱 | Too basic — route to `feedback-sdlc` |
| *(none)* | **Skipped, not wrong.** Re-queue; do not score it. |

💡 is retired along with the AWS-analogy thread it reported on. Write
`hint_used: false`; `build_mastery.py` still reads the field for the one
historical record that carries a true.

## Trigger

Whichever comes first: `grade_at` having passed today, or a ✅ from the learner on
the quiz parent message. Grade once — record `graded: true` so a later run does
not re-post.

**To find the ✅**, read `quiz.json` → `slack.parent_ts` and call
`slack_get_reactions` on it. That field is always written; until now nothing said
to read it, so the ✅ trigger had no stated way to reach the message it polls.

A ✅ is acted on by the next scheduled run: the hourly drain, or the 20:45 grade
routine, whichever comes first. Within the hour, not instant — and the quiz
parent says which, rather than implying a live grade.

In the cloud, `parent_ts` comes out of the `state` toggle on the `📊 Quiz Results`
row, because the sandbox that posted the quiz is gone and `state.local/` with it.
`cloud-bootstrap` rehydrates it before this skill runs; if it is missing, stop and
say so rather than grading a quiz you cannot match to its messages.

## Record outcomes for the ledger

Write `state.local/history/<date>/results.json` with, per question, its `n`, an
`outcome` of `correct` / `wrong` / `skipped`, and `hint_used`:

```json
{"questions": [{"n": 1, "outcome": "correct", "hint_used": true}]}
```

**`hint_used` is a separate boolean, never a fourth `outcome` value.**
`select_topics.py` keys the remediation angle on the literal string `"wrong"`, so
an outcome of `"wrong_hinted"` would pass silently and switch that angle off.
Keep `outcome` to the three values.

`build_ledger.py` reads this to decide which questions are eligible for the single
verbatim retest and which sections unlock the `remediation` teaching angle;
`build_mastery.py` reads it for everything else. Without it, all of them stay
inert — and every readiness number stays a prior rather than a measurement.

An on-demand set posted the same day goes in `quiz-<HHMM>.json` /
`results-<HHMM>.json`, which is how `on_demand.counts_toward_mastery` actually
takes effect.

## Mastery

Do not hand-write it. Once `results.json` exists:

```bash
.venv/bin/python scripts/build_mastery.py
```

It replays every graded quiz in date order into `state.local/mastery.json`:
attempts, correct, `hint_used`, `last_seen`, `ease`, `next_due`. Derived, never
authored — the same contract as the ledger, and the reason the numbers cannot
drift from what was actually answered.

A hinted-correct answer scores half. A skipped question scores nothing and moves
nothing — not the score, not the due date; it lands in `requeue`.

Priority for review, on top of what `next_due` says:
1. Wrong answers on `aws_traps` topics — the highest-value misses
2. Correct-but-hinted
3. Long-unseen

## Then

1. Per-question explanation into each thread — lead with **why the chosen
   distractor fails**, which is the half they cannot reconstruct.
2. Summary message with per-section breakdown and weak areas.
3. **Complete** the `📊 Quiz Results` row that `daily-quiz` created: flip
   `status` to `graded`, write the rich result blocks, and add `results.json`
   verbatim to the row's `state` toggle alongside the `quiz.json` already there.
   Do not create a second row — one row per quiz, created at post time.

   This is the durable record, since `state.local/` is gitignored, local, and in
   the cloud discarded when the run ends.
4. Hand off to `exam-readiness`, which owns the dashboard and the readiness
   report. Grading says how today went; readiness says where that leaves you, and
   it has its own cadence.

## Calibration

4–6/10 early is expected and correct: exam-level scenarios on fundamentals-level
material are hard, and only ~61% of the exam is currently reachable. Report it
analytically. Do not congratulate, and do not soften a miss.
