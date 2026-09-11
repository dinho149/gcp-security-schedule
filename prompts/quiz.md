# Quiz prompt

Generate the daily quiz. **Read `reference/question-spec.md` in full first** —
it is measured from 20 real sample questions and overrides intuition.

## Inputs

| Source | Use |
|---|---|
| `knowledge/pages/<slug>.md` | **The material itself. Read the pages you are asking about before writing a question.** |
| `profile.local.yaml` | Altitude, anchors, traps |
| `reference/exemplars/official-samples.md` | The shape to imitate |
| `knowledge/coverage.md` | What is askable |
| `knowledge/index.json` | Sections, headings, Notion URLs, the `cache` path |
| `knowledge/aws-gcp-map.json` | The only source of AWS equivalences |
| `config/schedule.yaml` | `quiz.mix`, `quiz.depth` |
| `state.local/mastery.json` | Weakest and most-due topics |

If a page has no cached text yet, fetch it from its `notion_url` and write the
cache before writing questions. A question built from a heading and general GCP
knowledge is ungrounded even when its citation resolves.

## Sampling

1. **Blueprint weights renormalised over covered subsections only.** Take these
   from the Summary table in `coverage.md` — do not recompute from the blueprint,
   which would include unreachable sections.
2. Composition from `schedule.yaml` → `quiz.mix`: new / review-due / previously-wrong.
3. Scenario depth from `quiz.depth`. The corpus skews deeper than intuition —
   roughly 1 bare, 6 mid, 3 deep per ten. **Depth is capped by the material**,
   not chosen freely: before assigning a deep slot, ask how much the section has.

   ```bash
   .venv/bin/python scripts/page_sections.py --page knowledge/<cache> --words
   ```

   A section must hold `quiz.min_source_ratio` times the words of the question
   written from it. A 16-word section carries no question at all; a 51-word one
   carries a bare-recall question and nothing larger. Deep slots go to the
   sections the course actually covers properly.
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
`knowledge/index.json`, and the two must be the same citation — that heading on
that page. Every service in `services[]` must appear in `aws-gcp-map.json`. **Do
not invent service names, role IDs or permission strings.** If the material will
not support a question, write a different one.

### Anchor every question to a line of the material

`source.anchor` is the span of the cited section the **keyed answer** rests on,
quoted verbatim. `validate.py` checks it against the cached page, normalising
markup and nothing else — a paraphrase fails, which is the point.

It is **never posted with the question**; on a near-verbatim question it would
hand over the answer. `grade-quiz` reveals it. Pick a span that is a claim, not a
term: ten words minimum, and prefer one without emoji, which would spend budget
in the grading reply.

If you cannot quote a line the answer rests on, you do not have a question —
you have a fact you believe. Write a different question.

### Scenarios are material-anchored

A scenario may use only entities and situations **the cited section itself
uses** — its own worked examples, its own terms, its own numbers. Generic
subjects stay: *"Your team…"*, *"An organization…"*, *"A customer…"* are attested
across the corpus and invent nothing.

What is banned is decoration — framing that carries no deciding constraint and
appears nowhere in the material. The 2026-09-11 quiz is the reference set of
failures, and every one of them sat on a correctly sourced fact:

| Written | Wrong because |
|---|---|
| *"A mobile game studio… launch day for a new title"* | an invented industry and product |
| *"The service also processes payment data"* | an invented compliance stake |
| *"An organization runs regular red-team exercises… testers keep finding"* | an invented programme |

The facts under all three were in the material. The framing was not, and the
reader cannot tell those apart — which is why the whole quiz read as though it
came from somewhere other than the course.

Say the same thing with the section's own furniture, or say less. A question the
course could plausibly have asked is worth more than a polished one it could not.

AWS equivalences follow `docs/house-style.md` §3: inline and in brackets where
the map has a counterpart, said in words where the map's cell is blank, and
**silent** where the service is absent from the map.

## Self-critique before posting

1. Generate the set.
2. Score each question against `reference/question-spec.md` §2 and the exemplars.
3. Revise what fails.
4. Run `.venv/bin/python scripts/validate.py <quiz.json>`.
5. **Only post once it exits zero.** A failing question is regenerated, not posted.

### When the material will not support ten

Rewrite a failing question once. If it still cannot be anchored, **drop it**.

**Never refill the slot from an easier section.** Keeping the count at ten is the
obvious move and it is the one thing this must not do — it is how a quiz ends up
asking about material the course has not covered properly. Record
`short_reason` naming the sections that could not carry a question; `validate.py`
fails a short quiz that does not say why. The parent message says it too:

```
7 questions today — three §3.3 sections hold too little material to ask about
honestly.
```

## Slack rendering

Parent message, then **one top-level message per question**. Threads are flat in
Slack, and there is no longer anything to collapse under a question — the AWS
analogy reply was retired (`docs/decisions.md`).

**Never add reactions to quiz messages.** The connector posts as the learner, so
any reaction it adds is indistinguishable from an answer. Question messages go
out clean.

Four emoji per message, one blank line between blocks, per `docs/house-style.md`
§5. The option emoji are exempt from the budget.

```
<square> Q<n> · §<blueprint> <subsection title> · ⏱ <n>s

> <scenario, with the deciding constraint bolded>

_<stem>_

1️⃣  <option A>
2️⃣  <option B>
3️⃣  <option C>
4️⃣  <option D>

<notion_url|<Page> → "<heading>">
On the page: _<sub-heading>_ — <the table / bullet / callout to read>
```

The locator line is `docs/house-style.md` §7 and it is why the reader can check
you: a page is 200 lines, and a citation that stops at the page leaves them
hunting. Pick the sub-heading from the page you already have open:

```bash
.venv/bin/python scripts/page_sections.py --page knowledge/<cache> --heading "<heading>"
```

`validate.py` rejects a sub-heading the page does not have. Omit the line for a
flat section rather than inventing one — it spends no emoji either way.

Record `slack.parent_ts` on the quiz. Grading needs it to find a ✅, and it is
the only handle on the parent message once the run ends.

### The parent message must not promise a live reply

A ✅ on the parent is read by the **next scheduled run** — the hourly drain, or
the grade routine. Within the hour, not immediately, and the footer says exactly
that rather than rounding it up:

```
React ✅ on this message when you are done. It is picked up within the hour —
for an instant grade, open a session and say "grade it".
```

🥱 on a question still means *too basic*, and routes to `feedback-sdlc`.
