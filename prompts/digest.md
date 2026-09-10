# Digest prompt

Produce the daily digest. Posted **in full** to Slack before the quiz, and it is
explicitly the preparation for it: cover the topics the quiz will draw from.

## Inputs

| Source | Use |
|---|---|
| `profile.local.yaml` | **Read first.** Altitude, anchors, traps |
| `knowledge/coverage.md` | What is teachable |
| `knowledge/index.json` | Sections, headings, Notion URLs |
| `knowledge/aws-gcp-map.json` | The only source of AWS equivalences |
| `state.local/mastery.json` | Weakest and most-due topics |
| `docs/house-style.md` | Voice, typography, attention rules |

## Choosing today's topics — don't. Run the selector.

```bash
.venv/bin/python scripts/build_ledger.py          # what has already been said
.venv/bin/python scripts/select_topics.py --json  # what to say today
```

Topic choice is **not** a judgement call. The selector knows what has been taught
and from which angle; you do not. It returns the sections, the angle for each, and
the phase it is in.

Your job is to write the topics it hands you, at the angle it specifies.

### The angles

Each pass over a section must use an angle it has not had. This is what makes a
second pass worth reading rather than a re-run.

| Angle | Write |
|---|---|
| `delta` | How this differs from the AWS equivalent — or that it has none |
| `trap` | The precision distinction the exam tests: scope, level, which of two similar things |
| `scenario` | A design decision where this section determines the answer |
| `synthesis` | How it interacts with another already-taught section |
| `remediation` | Rebuild a concept answered wrong — approach from where the wrong answer suggests the model broke, do not just re-explain |

**A remediation pass is not a repeat of the delta pass.** If you cannot say
something genuinely new at the given angle, say so rather than padding — that is a
signal the selector should have moved on.

### When the selector returns nothing (phase E)

The material is exhausted: every section covered from every applicable angle.
**Do not invent a fifth way to explain the same thing.** Post the short honest
message instead:

- everything in the material has been covered at every applicable angle
- where they stand: reachable exam weight, weakest areas
- **what to add next** — `add_next` from the selector, heaviest exam weight first
- a link to the Notion PCSE page

The quiz still runs that day. Spaced repetition never exhausts.

## Structure — one message per topic

The digest is a **sequence of Slack messages**, not one long post. Same shape the
quiz uses, and for the same reason: threads collapse, so depth stays one click away.

```
parent      # ⚡ Digest · <date> · ⏱ <total>
            > <square> **Today:** <thesis, one line>
            _<why it matters for today's quiz>_
            **1.** <square> <topic> · ⏱ <n>s
            **2.** <square> <topic> · ⏱ <n>s   <- numbered agenda
            ...

topic 1..N  ## <square> <n> · <title>        ⏱ <n>s     (top-level message)
            <content — a different block shape per topic>
            📖 <Page> → "<exact heading>"
            └─ thread: visual(s), then the deep dive

closing     ## ✅ Before the quiz you can say…
            ☐ <checkable claim>
```

Each topic is self-contained: someone reading only that message should get the
whole point. No "as we saw above".

## Authoring visual specs

Emit `state.local/history/<date>/visuals.json` as `{"visuals": [<spec>, ...]}`,
then render it in one command (see the skill). Give each spec an `id` matching its
topic, e.g. `topic-2-vpc-scope`.

| Component | Use for |
|---|---|
| `compare` | GCP vs AWS, service A vs service B |
| `chain` | resource hierarchy, inheritance |
| `contrast` | an `aws_traps` entry — habit vs reality |
| `sequence` | evaluation order, request path |
| `decision` | "which option should you pick" |
| `code` | annotated `gcloud` / Terraform |

**One visual per topic minimum; two when the topic earns it** — typically a diagram
plus an annotated command. **Never two of the same component in one digest**: four
near-identical cards is the wall-of-text problem in picture form.

Set `section` on each spec ("1".."5") so its accent colour matches the topic's square.

If a topic cannot justify a visual, that is a signal the topic is too thin — merge
it or cut it, rather than inventing filler.

## Rules

- **Never define anything in `assume_known`.** This is the top rule. If a chunk
  could appear unchanged in a beginner's course, rewrite it.
- Open with a trap, contrast or mistake — **never a definition**.
- Every chunk: a ⏱ estimate, a distinct block shape, and a citation.
- `monospace` **only** for service names, roles, permissions, constraints, CLI.
- Use ❌ AWS habit / ✅ GCP reality for each service touched.
- Anchor to the reader's own systems using `anchors`, by name.
- AWS equivalences come from `aws-gcp-map.json` alone. **If a service has no AWS
  equivalent there, say so explicitly** — that absence is itself the lesson
  (VPC Service Controls is the standing example).
- Depth goes in the thread, never inline. Keep the main read under ~6 minutes.
- Cite only sections with `ingested: true`.
- **Never teach beyond the training.** Every topic must be fully sourced from
  ingested material. Do not teach a known gap, do not "flag what the exam also
  tests", do not preview what a later course will cover. The learner is working
  through the material in order and will get there. A topic that needs a source
  outside their notes is the wrong topic — pick another.

## Failure modes to avoid

| Symptom | Fix |
|---|---|
| Explains what IAM is | Assume it. Lead with how binding differs from attaching. |
| Generic "GCP ≈ AWS" table | Use the reader's own systems from `anchors`. |
| Four chunks all bulleted lists | Rotate: table, contrast pair, diagram, checklist. |
| A claim with no citation | Cut it or find the section. |
| Reads like documentation | It should read like a colleague who already knows what you know. |
| Teaches something the course hasn't reached | Cut it. It is coming in a later module; running ahead is not helping. |
