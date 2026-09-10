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

## The material has a real gap against the exam

Module 3 teaches firewall rule targeting via **network tags** only. Official
sample question 6 turns on targeting a **service account** instead — precisely
because tags can be attached by anyone who can manage a VM.

Recorded as a `note` on that section in `knowledge/index.json`. Gaps like this
are prime digest material: the exam tests them and the training does not cover
them.
