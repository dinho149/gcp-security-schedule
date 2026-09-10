# Grading prompt

Grade the most recent ungraded quiz, explain what was missed, and update mastery.

## Reading answers

For each question message, call `slack_get_reactions`. Count **only** reactions
from `config.local.yaml` → `slack.user_id` — the channel is public, and the
connector itself posts as that same account, so nothing here may add reactions.

- 1️⃣–4️⃣ → the answer. Two reactions on a `(choose two)` question is a complete answer.
- 💡 → the AWS hint was used. Record it; the topic gets weighted for review.
- 🥱 → too basic. Route to `feedback-sdlc`, which appends to `assume_known`.
- No reaction → **skipped**, not wrong. Re-queue it; do not count it against the score.

## Per-question reply

Post into each question's thread:

```
<✅|❌> Q<n> — <correct option>
<why the keyed answer is right, in one or two lines>
<why the chosen distractor is wrong — name the specific difference>
🔁 <AWS anchor from profile anchors, if one applies>
📖 <Page> → "<heading>"
```

For a wrong answer, the important half is **why their choice fails**, not why the
right one works. They can usually reconstruct the latter.

## Summary message

```
📊 Quiz #<n> — <score>/10
<per-section breakdown using the colour squares>
❌ <each miss, one line: what was picked, what was right, the distinction>
🔻 Weak: <topic> — <n>/<m> over last <k> quizzes
   → tomorrow's digest covers <what>
📈 <dashboard url>
```

## Mastery update

For each answered question update `state.local/mastery.json`: attempts, correct,
`hint_used`, `last_seen`, ease, `next_due`. Skipped questions update nothing
except a re-queue flag.

Weight review toward:
1. Wrong answers on `aws_traps` topics — the highest-value misses.
2. Correct-but-hinted answers. A 💡 means it was not actually known.
3. Anything not seen in a while.

## Then

1. Write results to the `📊 Quiz Results` Notion database (durable record).
2. Update `state.local/` (fast cache).
3. Republish the readiness dashboard to its existing URL.
4. Link the dashboard from the summary.

## Tone

Analytical, not encouraging. Expect 4–6/10 early — exam-level scenarios on
fundamentals-level material are genuinely hard, and the tracker is calibrated for
that. Do not congratulate; report, then say what tomorrow targets.
