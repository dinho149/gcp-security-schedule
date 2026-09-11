# Grading prompt

Grade the most recent ungraded quiz, explain what was missed, and update mastery.

## Reading answers

For each question message, call `slack_get_reactions`. Count **only** reactions
from `config.local.yaml` → `slack.user_id` — the channel is public, and the
connector itself posts as that same account, so nothing here may add reactions.

- 1️⃣–4️⃣ → the answer. Two reactions on a `(choose two)` question is a complete answer.
- 🥱 → too basic. Route to `feedback-sdlc`, which appends to `assume_known`.
- No reaction → **skipped**, not wrong. Re-queue it; do not count it against the score.

💡 is retired. It used to mean "I opened the AWS analogy in the thread", and
there is no longer a thread to open. Historical results still carry `hint_used`
and `build_mastery.py` still honours it; nothing produces it any more.

## Per-question reply

Post into each question's thread:

```
<✅|❌> Q<n> — <correct option>

<why the keyed answer is right, in one or two lines>
<why the chosen distractor is wrong — name the specific difference>

> <source.anchor, verbatim>
<notion_url|<Page> → "<heading>">
On the page: _<sub-heading>_ — <what to read there>
```

**The anchor is the half the question held back.** It is the line of the course
the keyed answer rests on, quoted exactly as the page has it, and it is what lets
the reader confirm the answer came from their material rather than from us. Post
it as a **block quote**: `check_style` skips `>` lines, so the instructor's own
sentence is not measured against house-style rules we are not free to apply to it.

Quote it verbatim. Tidying it up is the failure this whole mechanism exists to
prevent, one step later.

Where an AWS counterpart genuinely clarifies the miss, it goes **inline and in
brackets** in those lines — `Cloud Storage (≈ S3)` — and only where
`aws-gcp-map.json` carries one. `docs/house-style.md` §3. No standalone analogy
line: the 🔁 marker is retired.

For a wrong answer, the important half is **why their choice fails**, not why the
right one works. They can usually reconstruct the latter.

## Summary message

```
Quiz #<n> — <score>/10

<per-section breakdown using the colour squares>

❌ <each miss, one line: what was picked, what was right, the distinction>

Weak: <topic> — <n>/<m> over last <k> quizzes
→ tomorrow's digest covers <what>
```

Today's score, not a readiness claim. It is measured over the reachable slice of
the exam, so it reads systematically higher than readiness does; `exam-readiness`
is where that gets said properly.

## Mastery update

Record the outcomes, then rebuild — do not hand-write the mastery file:

```bash
.venv/bin/python scripts/build_mastery.py
```

`results.json` carries per question its `n` and an `outcome` of
`correct`/`wrong`/`skipped`. A skipped question updates nothing at all — not the
score, not the due date — and is re-queued.

Write `hint_used: false`. The field stays in the schema because
`state.local/history/2026-09-10/results.json` records a true on Q5 and
`build_mastery.py` still halves credit for it; dropping the field would silently
change what that record means.

Weight review toward:
1. Wrong answers on `aws_traps` topics — the highest-value misses.
2. Anything not seen in a while.

## Then

1. Write results to the `📊 Quiz Results` Notion database (durable record).
2. Update `state.local/` (fast cache).
3. Leave readiness to `exam-readiness`. It owns the dashboard and the two
   headline numbers, and it runs on its own cadence — today's score is not the
   same claim as "how ready am I", and merging them was how the second one went
   unbuilt for so long.

## Tone

Analytical, not encouraging. Expect 4–6/10 early — exam-level scenarios on
fundamentals-level material are genuinely hard, and the tracker is calibrated for
that. Do not congratulate; report, then say what tomorrow targets.
