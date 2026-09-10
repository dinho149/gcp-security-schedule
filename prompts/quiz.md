# Quiz prompt

Generate the daily quiz. **Read `reference/question-spec.md` in full first** —
it is measured from 20 real sample questions and overrides intuition.

## Inputs

`profile.local.yaml` · `knowledge/coverage.md` · `knowledge/index.json` ·
`knowledge/aws-gcp-map.json` · `reference/exemplars/official-samples.md` ·
`config/schedule.yaml` (quiz.mix, quiz.depth) · `state.local/mastery.json`

## Sampling

1. **Blueprint weights renormalised over covered subsections only.** Take these
   from the Summary table in `coverage.md` — do not recompute from the blueprint,
   which would include unreachable sections.
2. Composition from `schedule.yaml` → `quiz.mix`: new / review-due / previously-wrong.
3. Scenario depth from `quiz.depth`. The corpus skews deeper than intuition —
   roughly 1 bare, 6 mid, 3 deep per ten.
4. **Weight up `aws_traps`.** Weight down anything in `assume_known` — the exam
   still tests it, so do not exclude it, but the reader will clear it first time
   and mastery will deprioritise it anyway.

## Writing questions

Imitate the exemplars in `reference/exemplars/official-samples.md`. Imitate their
**shape**, never their content.

Non-negotiables from the spec:

- Exactly **4 options**, including for `(choose two)`.
- **Generic subjects only** — *"A customer…"*, *"Your team…"*, *"An organization…"*.
  Never a fictional company name; that is a third-party tell.
- Options **parallel in form**, similar in length. Word spread ≤ 8, ratio ≤ 2.6.
- Prefer **precision near-variants** as distractors — *project* vs *bucket* level,
  *User* vs *Admin* role. That is how the exam tests precision.
- Add *"You want to follow Google-recommended practices."* only when the managed /
  least-privilege choice genuinely is the discriminator.

## Repetition

Repeating a **topic** is the point of spaced repetition. Repeating a **question**
teaches the answer key instead of the concept.

- Every question carries a fingerprint (`scripts/build_ledger.py`), insensitive to
  formatting and to option order — reshuffling four options is the same question.
- **A previously-asked question is rejected**, with one exception.
- **The exception:** a question answered *wrong* may be re-asked **verbatim exactly
  once**, no sooner than 3 days later. Set `"is_retest": true`. After that the
  concept returns only as newly-written questions.
- `quiz.mix.new` means a **new fingerprint**, not a new section. A fresh question on
  an already-taught section is new. **The quiz therefore never exhausts**, even on a
  day the digest has nothing new to say.

`scripts/validate.py` enforces all of this. A duplicate fails the run.

## Grounding — non-negotiable

Every question must carry `source.notion_url` and an exact `source.heading` from
`knowledge/index.json`. Every service in `services[]` must appear in
`aws-gcp-map.json`. **Do not invent service names, role IDs or permission
strings.** If the material will not support a question, write a different one.

## Self-critique before posting

1. Generate the set.
2. Score each question against `reference/question-spec.md` §2 and the exemplars.
3. Revise what fails.
4. Run `.venv/bin/python scripts/validate.py <quiz.json>`.
5. **Only post once it exits zero.** A failing question is regenerated, not posted.

## Slack rendering

Parent message, then one threaded reply per question.

**Never add reactions to quiz messages.** The connector posts as the learner, so
any reaction it adds is indistinguishable from an answer. Question messages go
out clean.

```
<square> Q<n> · §<blueprint> <subsection title>        ⏱ <n>s

> <scenario, with the deciding constraint bolded>

<stem>

1️⃣  <option A>
2️⃣  <option B>
3️⃣  <option C>
4️⃣  <option D>

📖 <Page> → "<heading>"
```

Post the AWS analogy **immediately as a threaded reply** — collapsed by default,
so it is a spoiler the reader opens deliberately, with no waiting. A 💡 reaction
records that they used it, which weights the topic for review.
