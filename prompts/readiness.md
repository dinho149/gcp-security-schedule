# Readiness prompt

Report how ready the learner is for the exam, per section and overall, and how
long the gap is likely to take. Or say plainly that it is too early to tell.

You compute nothing. `scripts/build_readiness.py` has already done the
arithmetic; read `state.local/readiness.json` and report what it says. If a
number looks wrong, fix the script, not the message.

## Two numbers, never one

| Number | Reads | Ceiling |
|---|---|---|
| **True exam readiness** | of the whole exam, how much is solid | the coverage ceiling |
| **On covered material** | of what the training has taught, how much is solid | 100% |

**Never post one without the other.** On its own, the second is a claim about
61% of the exam wearing the clothes of a claim about the exam — which is
`CLAUDE.md` rule 2, pointed at the learner instead of at GCP. The gap between
them is the remaining course, and saying so is the whole job.

`validate.py` rejects a report that posts one headline, and rejects a headline
that disagrees with the file it came from.

## Parent message

```
📈 *Exam readiness* · <Day DD Mon> · ⏱ 60s

*True exam readiness*   <n>%  ▓▓▓▓▓░░░░░   ceiling <n>%
*On covered material*   <n>%  ▓▓▓▓▓▓▓▓░░   our bar <n>

<one line: coverage is a ceiling, not a discount, and what it costs>

🟦 *1 Access*        <n>%  ·  <n>/<n> subsections  ·  <n>% of the exam
🟩 *2 Boundary*      …
🟨 *3 Data*          …
🟧 *4 Operations*     —   ·  0/2              ·  19%   ⬜ nothing ingested
🟥 *5 Compliance*    …

🔻 <weakest reachable section, with the evidence count behind it>

🎯 *Ready in ~<n> days* · confidence *<low|medium|high>*
_<the two or three drivers, from estimate.days_mastery / days_coverage / leverage>_
⚠️ Our <n>% bar, not Google's — no pass mark is published for this exam.

_<n> quiz days · <n> graded questions · <coverage date> · 📈 <dashboard url>_
```

Numbers come from `headline`, `sections`, `estimate` and `evidence`. Section rows
stay in blueprint order so the shape of the report is learned rather than read.

## The "too early" variant

Replace **only** the estimate block. Every coverage number still posts —
coverage is knowable from day one and does not need a quiz to be true.

```
🎯 *Still too early to decide.*
_<estimate.reason>. <what is missing, from estimate.checks>._
_At one quiz a weekday, that lands <date>._
```

Do not soften it into a guess, and do not offer a range instead. "Still too early
to decide" is a fixed phrase; `validate.py` rejects a days estimate posted
alongside it.

## Thread reply

One reply, carrying what the parent cannot:

1. **Method** — what the score is and what it is not. Lead with the caveat whose
   `severity` is `high`, in your own words, not pasted.
2. **What would move it**, highest return first, from `leverage` — each with the
   exam weight it unlocks.
3. **Blind spots and due for review** — taught but never quizzed, and anything
   whose `next_due` has passed.
4. **Staleness** — when mastery and coverage were last rebuilt.

## Voice

Analytical. The same calibration as grading: **do not congratulate, and do not
soften a weak section.** A readiness report that reads as encouragement is
useless, because the one thing it exists to do is tell the learner something they
would rather not hear.

Report, then name what moves the number.

- Confidence is exactly one of `low`, `medium`, `high` — never a phrase.
- Three kinds of dash, never one: *too few to score* (measured, thin), *not yet
  asked* (unmeasured), *no material ingested* (unmeasurable). Collapsing them is
  the most likely way this report lies.
- Round to whole percent. The exam is 50–60 questions with unknown per-section
  sampling; a decimal place claims precision that is not there.
- Say "our <n>% bar", never "the pass mark". Google publishes neither.

## Worked example numbers are fabricated

Any example in this file uses invented figures, and must keep doing so.
`leakcheck.py` derives its needles from `profile.local.yaml` — it cannot tell a
real score from an invented one, so this is a rule the gate will not catch for
you.
