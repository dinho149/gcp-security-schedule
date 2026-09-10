# Decisions and findings

Non-obvious things established by testing rather than assumption. Each one
changed the design.

---

## The Slack connector acts as the user, not as a bot

**Found:** 2026-09-10, by testing before relying on it.

Creating the channel returned `cant_invite_self` when inviting the learner —
which meant the caller *was* the learner. Confirmed directly by reacting to a
message and reading the attribution back:

```
slack_add_reaction(:one:)  ->  slack_get_reactions
:one: × 1 — <the learner's own account>
```

**Why it matters.** The original design had the agent pre-seed 1️⃣–4️⃣ on each
question so answering was a tap rather than an emoji hunt, with grading filtering
to the learner's user id. That cannot work: the seeds *are* the learner's
reactions. Grading would have read four answers on every question and had no way
to tell which was real.

**Decision.** The agent never adds reactions to quiz messages. Questions post
clean and the learner picks the emoji themselves; after the first quiz the number
emoji sit in Slack's frequently-used row, so the tap-cost is close to what
seeding would have bought.

The `slack.user_id` filter stays as defence in depth — the channel is public, so
another member could react.

**If tap-cost becomes annoying**, the real fix is a separate Slack app with its
own bot token doing the seeding. That is a different identity, so seeds become
distinguishable. It costs token management and a Slack app install, so it is not
worth it until the friction proves real.

---

## Digest visuals: headless Chrome, not the browser extension

The first digest shipped as one long message with a single diagram, because
producing that diagram took ~5 interactive browser-tool calls: write HTML, serve
it on localhost, navigate, screenshot, guess a crop region. Four visuals a day
would have been ~20 calls, and the digest is supposed to fire unattended at 07:15.

**Two things made the scripted version possible.**

The `file://` block that forced the localhost server was a *browser extension*
restriction, not a Chrome one. Headless Chrome opens local files directly, so no
server is needed.

Chrome 152 is already installed, so `--headless --screenshot` gave a scriptable
renderer with no new binary. Only Pillow was added, for cropping.

`dashboard/render.py` now renders a whole digest's visuals in one command, about
2s each.

### Cropping to a sentinel, not to white

Each component draws a magenta border that the cropper trims to. Cropping to white
would silently eat any light-coloured element sitting at the edge.

### The first clipping check was vacuous

It asserted a clean white margin on all four sides. That passes almost always,
because content rarely reaches the very edge — a deliberately clipped image passed
it. Replaced with a real check: if the content bounding box touches a canvas edge,
the page overflowed the render window and the run **fails** rather than posting a
truncated diagram. Verified against a spec built to overflow.

### Cropping in pure Python was the bottleneck

A per-pixel loop over ~8M pixels took ~4.5s per image. `ImageChops.difference`
against a solid sentinel plate does the same work natively: 28.7s → 14.1s for six
visuals, and the output is pixel-identical.

---

## Slack threads are flat, so questions are top-level messages

The plan had each question as a thread reply under a quiz parent, with its AWS
hint as a collapsed reply *under that question*. Slack does not nest: a reply to
a thread reply joins the same parent thread. The hint would have been visible
inline, losing the spoiler property that made it worth posting up front.

**Decision.** The quiz parent is one message; each question is its own top-level
message; each hint is a thread reply under its question. Threads collapse by
default, so the hint stays a deliberate click with no waiting, and reactions sit
on top-level messages where they are easy to see and easy to add.

Costs 11 messages a day in the channel. Worth it.

---

## Multi-select questions use four options, not five

**Found:** measuring all 20 official sample questions.

Third-party sources widely state that GCP multi-select questions offer five
options. The one multi-select in the official corpus offers **four** (A–D), with
the marker written lowercase as `(choose two)` at the end of the stem.

20/20 questions have exactly four options. `validate.py` enforces it.

---

## Near-variant distractors are a core technique, not a flaw

**Found:** same measurement.

The initial spec, drafted from third-party descriptions, said distractors should
be distinct strategies and that options differing by one word were a smell. The
real corpus does the opposite constantly:

- Storage Object Creator at the **project** level vs at the **bucket** level
- Service Account **User** vs Service Account **Admin**
- Org viewer + Project **owner** vs Org viewer + Project **viewer**

This is how the exam tests precision. `reference/question-spec.md` now *prefers*
it. Option length parallelism is enforced instead (spread ≤ 8 words, ratio ≤ 2.6),
since unequal length is the actual giveaway.

---

## Options are much shorter than reported

Measured: min 1 word, median 10.5, max 26. Many are bare noun phrases —
*"AES-256"*, *"VPC Service Controls"*, *"PCI DSS"*. Third-party guidance said
10–30 words of imperative action, which would produce visibly wrong questions.

---

## VPC Service Controls has no AWS equivalent — per Google

Google's own comparison table leaves the AWS cell **empty** for VPC Service
Controls. That is not missing data; it is the answer. For a reader coming from
AWS this is the single largest conceptual gap on the exam, and the digest should
say so plainly rather than inventing an analogy.

---

## A leak check that cries wolf gets ignored

The first `leakcheck.py` split profile phrases into individual words and searched
for each. It flagged "Engineer" in the exam title and "rules" in `.gitignore` —
four false positives on a clean tree.

A privacy gate is only useful if a failure means something. It now matches whole
phrases (≥ 12 chars) plus an explicit `sensitive_terms` list. Verified against
planted leaks: email, phone number, GitHub token, and an employer anchor phrase
are all caught, with zero false positives on the real tree.

---

## Gaps are planning signal, never teaching content

The first digest included a topic titled "A gap between your material and the
exam": Module 3 teaches firewall targeting by network tag, while official sample
question 6 keys on service-account targets. It cited the sample question honestly
and said the course did not cover it.

It should not have been there at all.

The original brief was explicit: *"if the courses do not match what is covered by
the exam yet, wait, don't rush as I am still working my way through the training —
it should cover only what is in the training."* Teaching a gap is precisely
running ahead. The learner reaches that material in due course and meets it
properly there, rather than as a spoiler.

**Root cause was a line I wrote in `.claude/skills/sync-notion/SKILL.md`:**
gaps should be recorded "— they are prime digest material." That single clause
turned a coverage-tracking feature into a teaching instruction.

### The fix, in three layers

1. **Wording.** sync-notion now says gaps are planning signal only. `CLAUDE.md`
   rule 3 covers teaching as well as quizzing. `prompts/digest.md` forbids
   teaching beyond the training and lists it as a failure mode.
2. **Mechanical.** `scripts/validate.py` gained `check_digest`: every topic must
   cite an ingested heading, its subsection must be covered, and a topic marked
   `beyond_material` is rejected outright.
3. **Where gaps do live.** `knowledge/coverage.md` and `!status`, as "not reached
   yet". Useful for planning what to study next; never rendered as a lesson.

### The limit of the mechanical check, stated honestly

`check_digest` catches a topic on an *uncovered subsection*, and one that
self-declares `beyond_material`. It cannot verify that a topic's prose stays
within what its cited section actually says — no check can entail that from text.
The retracted topic cited a covered heading; what exceeded the material was the
claim, not the citation.

So layer 2 is a backstop. Layer 1 — the prompt rules — is what actually carries
this, which is why the wording was fixed at the source rather than patched at the
point of use.

---

## The material has a real gap against the exam

Module 3 teaches firewall rule targeting via **network tags** only. Official
sample question 6 turns on targeting a **service account** instead — precisely
because tags can be attached by anyone who can manage a VM.

Recorded as a `note` on that section in `knowledge/index.json`. Gaps like this
are prime digest material: the exam tests them and the training does not cover
them.
