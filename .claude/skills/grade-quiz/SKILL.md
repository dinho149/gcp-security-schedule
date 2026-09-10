---
name: grade-quiz
description: Read emoji reactions on a posted quiz, grade it, explain every miss, update mastery and spaced repetition, and republish the readiness dashboard. Runs when grade_at is due, on ✅ on the quiz parent, or on !answers.
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
| 💡 | Hint used — record it; correct-but-hinted is not known |
| 🥱 | Too basic — route to `feedback-sdlc` |
| *(none)* | **Skipped, not wrong.** Re-queue; do not score it. |

## Trigger

Whichever comes first: `grade_at` falling due, or a ✅ from the learner on the
quiz parent message. Grade once — record `graded: true` so a later tick does not
re-post.

## Record outcomes for the ledger

Write `state.local/history/<date>/results.json` with, per question, its `n` and an
`outcome` of `correct` / `wrong` / `skipped`.

`build_ledger.py` reads this to decide two things: which questions are eligible for
the single verbatim retest, and which sections unlock the `remediation` teaching
angle. Without it, both stay inert.

## Mastery

Update `state.local/mastery.json` per topic: attempts, correct, `hint_used`,
`last_seen`, ease, `next_due`.

Priority for review:
1. Wrong answers on `aws_traps` topics — the highest-value misses
2. Correct-but-hinted
3. Long-unseen

## Then

1. Per-question explanation into each thread — lead with **why the chosen
   distractor fails**, which is the half they cannot reconstruct.
2. Summary message with per-section breakdown and weak areas.
3. Write to the `📊 Quiz Results` Notion database — the durable record, since
   `state.local/` is gitignored and local.
4. Republish the dashboard to its existing URL from `config.local.yaml` →
   `dashboard.url`. Same URL every time; it is meant to be bookmarked.
5. Link the dashboard from the summary.

## Calibration

4–6/10 early is expected and correct: exam-level scenarios on fundamentals-level
material are hard, and only ~61% of the exam is currently reachable. Report it
analytically. Do not congratulate, and do not soften a miss.
