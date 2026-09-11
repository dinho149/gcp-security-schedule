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

## Repetition: topics may repeat, content may not

Asked what happens on a day with no new Notion material. The honest answer at the
time was: **you would get repeats, and the system would not know it.**

`digest.json` recorded `subsections_covered` but nothing ever read it back. The
only anti-repeat rule applied within a single day. `state.local/mastery.json` — the
file both prompts claimed to select from — did not exist. Nothing gave a question
an identity.

With 20 teachable sections and 4 topics a day, the all-new pool lasts ~5 days.

### The distinction

Repeating a **topic** is the point of spaced repetition. Repeating **content** is
waste. So the two sides get opposite treatment:

- **Quiz** — a question is fingerprinted (`sha256` of scenario + stem + *sorted*
  options, so reshuffling four options is the same question). Duplicates are
  rejected. The one exception: a question answered wrong returns verbatim exactly
  once, ≥3 days later. `quiz.mix.new` means a new *fingerprint*, so the quiz never
  exhausts.
- **Digest** — a section may be taught again, but only from an angle it has not
  had: `delta`, `trap`, `scenario`, `synthesis`, `remediation`. That makes
  "is there more to say?" arithmetic: `Σ (applicable − used)`.

### Weight per section, not novelty

§3.3 (SAIF) holds **9 of the 20** teachable sections but only 7.7% of reachable
exam weight. Ranking untaught sections by novelty would have spent the first two
days on SAIF while §1.4 Authorization waited. Phase A ranks by
*weight ÷ sections in that subsection*: §1.4 scores 5.0%/section, §3.3 scores
0.86%.

### Verified by simulation, not assertion

`scripts/simulate_days.py` drives selection forward with no new material:

```
days  1-5    phase A   breadth, heaviest weight first
days  6-15   phase C   second-pass angles (trap, then scenario)
days 16-19   phase D   synthesis across siblings
day  20      phase E   EXHAUSTED — 0 angles left
```

76 distinct (section, angle) pairs, **zero repeats**, and SAIF does not appear on
day one. So today's material yields ~19 days of non-repeating digests.

At exhaustion the digest says so and names what to add, heaviest first — §4.1 and
§4.2 Managing operations at 9.5% each, then §3.1, §3.2, §1.3. Total unreachable
weight: 39.4%.

### The ledger is derived, never authored

`scripts/build_ledger.py` rebuilds from `state.local/history/`, so it cannot drift
from what was actually posted and a deleted ledger costs nothing. Rebuild it
*before* validating, or the repetition checks compare against a stale picture.

One consequence worth knowing: because the ledger is built from posted history,
re-validating an already-posted quiz would flag every question as a duplicate of
itself. The check excludes the quiz's own date.

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

### Finding the browser is the renderer's job, not the bootstrap's

"Chrome 152 is already installed" was true of the laptop and false of the cloud
sandbox, so the first cloud digest posted text-only. The fallback worked exactly
as designed — and the design was still wrong in two ways.

**The probe was too narrow.** It was `which` over four names. A browser installed
off `PATH` — a puppeteer or playwright cache, `/opt`, `/snap` — reads as no
browser at all.

**Absence was treated as permanent.** The sandbox already runs `uv pip install`
on every run, so outbound network was never in question; fetching
`chrome-headless-shell` is the same class of operation as installing Pillow, not
a new capability. Ninety seconds against a digest that loses every diagram is not
a close call.

Resolution moved into `dashboard/ensure_chrome.py`, which `render.py` calls. That
makes it **lazy**, which is the part that matters: only the digest renders a PNG,
so only the digest waits for a browser. Doing it in `cloud-bootstrap` made the
quiz, grading and readiness routines — four of the five — pay for a capability
none of them use.

What `cloud-bootstrap` keeps is the *cache*, in `control.render_probe`: the
negative, so a barren sandbox stops re-paying, and the winning installer, so the
next run skips the route it already knows fails. Not the path — the sandbox is
discarded after each run, so tomorrow's path is a different one.

**The cache has a 7-day expiry**, and that is load-bearing rather than tidy. The
sandbox image changes underneath us. A cached negative with no expiry is how
visuals stay off forever after one bad morning, with nothing in the record to
explain why.

### The installer defaults to the working directory, which is a public repo

`npx @puppeteer/browsers install` with no `--path` installs into the **current
working directory**. Run from the repo root — which is where every skill runs
things — that is 195 MB of Chrome sitting untracked in a public repository, one
`git add -A` away from being pushed.

Found by running the command rather than reasoning about it; the docs do not
mention the default. `ensure_chrome.py` now passes `--path` explicitly, a
regression test asserts the resolved binary is outside the repo, and
`.gitignore` carries `/chrome-headless-shell/` for the case where someone runs
the bare command by hand.

The parser learned something too. The output is `<name>@<version> <path>`, and
taking the last whitespace-separated token breaks on any install path containing
a space — `partition(" ")` from the left is correct.

### Sorting browser revisions as strings picks a build from 2022

Browser caches are keyed by revision — `131.0.6778.204` — and `sorted(reverse=True)`
puts `99.0.4844.51` first. A sandbox with two cached revisions would have rendered
with the older one indefinitely. Fixed by splitting digit runs and comparing them
numerically; verified against exactly that case.

### "One visual per topic" was asserted three times and enforced zero times

SKILL.md, house-style §8 and `prompts/digest.md` all state it. `validate.py`
checked only that two topics did not reuse a component, and only warned. So a
digest that dropped every diagram passed the gate, which is precisely what a
missing renderer produces.

`digest.json` now carries `visuals.state`, and `validate.py` holds both directions
to it: `rendered` requires every topic to have a visual, `unavailable` requires a
reason and forbids any topic claiming one. A text-only digest is now a recorded
fact with a cause attached, rather than something the reader has to infer from an
absence.

---

## Slack threads are flat, so questions are top-level messages

The plan had each question as a thread reply under a quiz parent, with its AWS
hint as a collapsed reply *under that question*. Slack does not nest: a reply to
a thread reply joins the same parent thread. The hint would have been visible
inline, losing the spoiler property that made it worth posting up front.

**Decision.** The quiz parent is one message; each question is its own top-level
message. Reactions then sit on top-level messages, where they are easy to see and
easy to add, and grading reads them from one place.

Costs 11 messages a day in the channel. Worth it.

**Superseded in part, 2026-09-11:** the hint reply this argument was built around
no longer exists — see below. Questions stay top-level anyway, now for the
reaction reason alone.

---

## An analogy that always fires teaches nothing

The hint under each question was **the AWS analogy only** (`prompts/hint.md`), and
it was written whether or not a counterpart existed. So a third of the time it
produced hedged filler — *"the two peering options have no clean AWS
counterpart"* — which asserts a fact nothing backs, on a service Google's own
comparison table does not list at all.

That table has three states, and only the first two were ever distinguished:

| `aws-gcp-map.json` | Count | Means |
|---|---|---|
| non-empty `aws` | 184 | There is a counterpart. Name it. |
| blank `aws` | 39 | **No counterpart, deliberately.** VPC Service Controls. Say so. |
| service absent | — | No source. **Say nothing.** |

Shared VPC, IAM, GKE and Dedicated Interconnect are all in the third row. The
retired hint spoke confidently about all of them.

**Decision.** No analogy thread and no 🔁 marker. An AWS counterpart is named
inline and in brackets — `Cloud Storage (≈ S3)` — only from the first row, said
in words for the second, and omitted entirely for the third. `house-style.md` §3.

`aws_equivalents` on each question and topic replaces the free-prose `aws_anchor`
field, so `validate.py` can check a claim against the table. Free prose could
assert anything and was checked against nothing.

💡 retired with the thread it reported on. `build_mastery.py` still halves credit
for `hint_used`, because one historical result carries a true and deleting the
logic would silently rewrite what that record means.

---

## The tick was never built

`schedule.yaml` set `tick_minutes: 15`. `daily-run/SKILL.md` said "invoked by the
scheduled task". `validate.py` range-checked the number. **Nothing ever fired
it** — no cron, no launchd agent, no GitHub Actions schedule, no cloud routine.

Found 2026-09-11, when the learner asked why pressing ✅ on the quiz parent did
nothing. It had been sitting unread since the day before, next to a 💡 on Q5.

Every reaction-driven and `!`-driven behaviour in this repo was documented and
unreachable. The two days of history exist because sessions were run by hand.

**A cloud runner cannot fix it.** `config/config.local.yaml`, `profile.local.yaml`,
`knowledge/` and `state.local/` are gitignored and stay on the laptop, which is
the whole privacy design. A routine would clone the repo and find no channel id,
no profile, no material, no mastery scores.

**Decision.** Session-driven, stated as the design rather than left implied.
`tick_minutes` is gone. The due-ness rule inverted with it: under a 15-minute tick
a missed `grace_minutes` window was the exception, so gating on the window was
safe. Sessions open when the learner opens them, so the window is now missed
almost every time — a session at 14:00 would have silently skipped the 12:30
quiz. A step now fires when its time has passed today and its output is absent,
and `grace_minutes` only labels the post on-time or late.

`state.local/last_run.json` is the watermark, so a session reads the channel from
where the last one stopped instead of re-firing a `!quiz` from three days ago.

The pinned `#gcp-security-exam` message says all of this out loud, because the
honest version — *"nothing here is live"* — is more useful than a promise of a
reply that never comes.

**Superseded the same day** by the entry below. The claim that a cloud runner
*cannot* fix it was wrong, and wrong in an interesting way.

---

## A cloud runner can fix it — connectors are the reason

**Found:** 2026-09-11, asking what it would take to drive this from a phone.

The entry above asserts that a cloud runner would clone the repo and find no
channel id, no profile, no material, no mastery scores. Every clause of that is
true. The conclusion drawn from it was not.

**What was missed:** two facts already in this repo, never put together.

1. `docs/privacy.md` already names Notion the durable record — *"Because results
   cannot be committed, the Notion databases hold the durable record.
   `state.local/` is a fast local cache that can be rebuilt."* If it can be
   rebuilt, it can be rebuilt in a sandbox.
2. `sync-notion` already regenerates the whole of `knowledge/` from Notion. The
   growth mechanism was also, unnoticed, a rehydration mechanism.

So a cloud run does not need the laptop's files. It needs Notion — which it has,
because **a Claude Code cloud session runs as the logged-in account and keeps the
claude.ai connectors.**

**The part worth remembering, because it is counter-intuitive.** The obvious
"proper" answer — a container on GCP, Cloud Run and Scheduler, state in a bucket
— *cannot do this at all*, and the blocker has nothing to do with GCP. Anthropic
documents that `claude setup-token` "can only make model requests, so it can't
establish Remote Control sessions or fetch claude.ai connectors", and API-key
auth is the same. Slack and Notion here are account connectors with no bot token
anywhere, so a container would first have to replace the entire I/O layer: a
Slack app, a Notion integration, and new client code across six skills. Weeks of
work to reach somewhere strictly worse.

The managed option is the capable one and the self-hosted option is the
constrained one, which is the reverse of the usual shape. That is why the
research went the wrong way for an hour before the question "could I just use the
Claude mobile app?" turned it around.

**Decision.** Five weekday routines call `cloud-run`: hydrate from Notion, run
`daily-run` unchanged, dehydrate. `!` commands become real triggers on an hourly
drain — within the hour, honestly stated, not "live". The laptop stops being the
runner and becomes the place logic is edited.

**What did not change, and is the reason this is acceptable:** nothing private is
committed. `leakcheck.py` and `.gitignore` are untouched, the repo stays public,
and state moves between Notion and an ephemeral sandbox — never into git. The
privacy boundary held; only the assumption about *where a run happens* was wrong.

**What it cost.** State that existed only on disk had to get a durable home, and
one piece of it was load-bearing: `slack.parent_ts` and the per-question
`message_ts` live nowhere but `quiz.json`. A cloud run could have posted a quiz
it was then permanently unable to grade, because the reactions sit on messages it
has no handle for. The `📊 Quiz Results` row is now created by `daily-quiz` at
post time rather than by `grade-quiz` at grading time — a lifecycle change forced
entirely by that one field.

`sources.local.json` was the second: its `ingested_on` stamps are written once
and never rewritten, and re-deriving them from a fresh walk would silently reset
every one to today, making the coverage pace unknowable while looking fine.

---

## The prose was never sourced

Every digest topic and every quiz question was composed from **a heading and a
service list**. `select_topics.py` returns `{page, heading, notion_url,
blueprint, services}`; the input tables in `prompts/digest.md` and
`prompts/quiz.md` listed `index.json`, `coverage.md`, `aws-gcp-map.json` and
`mastery.json`. Not one of them holds a sentence of the course. `sync-notion`
read each page in full to record its headings, then discarded the text.

So the citation resolved to a real ingested heading while the prose beneath it
came from the model's own knowledge of GCP. Found 2026-09-11 via a complaint
about *voice* — the output "reads very AI generated" — which turned out to be the
visible symptom of a grounding gap.

This is the limit the `check_digest` entry above already concedes: it "cannot
verify that a topic's prose stays within what its cited section actually says".
True, and unfixable by another check. It is very fixable by reading the page.

**Decision.** `sync-notion` writes what it reads to `knowledge/pages/<slug>.md`
and records the path as `cache`. That text is the **first** input to both prompts,
and the write path falls back to fetching the page when a cache is missing.
`validate.py` warns when a page claims `ingested: true` with no cached text —
which is the first time that flag has meant something checkable.

It tightens rules 2 and 3 rather than loosening them: it is harder to run ahead of
the material while looking at it. And it is the only real fix for voice, because
carrying the instructor's own terms is not something a prompt can fake.

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

## The leak gate caught Python, twice removed

Adding an emoji regex to `validate.py` failed `leakcheck.py` on
`[\U0001F300-\U0001FAFF]`: `U0` followed by seven uppercase hex is exactly the
Slack workspace id shape added after a real id reached the public remote.

The entry above says a gate that cries wolf gets ignored. Two changes, because
either alone would leave the trap set: the escapes are written lowercase, and the
pattern gained `(?<!\\)` so a Python escape can never match it again. Verified
both ways — a real id is still caught, the escape is not.

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

Recorded as a `note` on that section in `knowledge/index.json`.

**Corrected 2026-09-10:** this entry used to end "gaps like this are prime digest
material: the exam tests them and the training does not cover them" — the exact
sentence the *"Gaps are planning signal, never teaching content"* entry above
identifies as the root cause of the retracted topic. It survived the fix in
`sync-notion` but not here, so the document argued both sides for a while. A gap
is planning signal: it surfaces in coverage reporting and in the readiness
report's "where study pays most", and it is never taught until the material
lands.

---

## Readiness is two numbers, because either one alone is a lie

A score over answered questions reads ~78% while 39.3% of the exam has never been
tested at all. A single blended number hides which half is lagging.

So the report always carries both — *on covered material* and *true exam
readiness* — with `true = on_covered × reachable` as an exact identity. The gap
between them **is** the remaining course, which makes it the most actionable line
in the report rather than a footnote.

`validate.check_readiness` rejects a report that posts one without the other.

---

## The mastery prior is the guess rate, and teaching cannot beat it

Every question has exactly four options — measured across all 20 official samples
and enforced by `validate.OPTIONS_EXACT`. So an unproven topic starts at **0.25**,
where blind guessing lands, not at zero.

Teaching raises the prior to at most **0.50** (`p₀ = 0.25 + 0.25 × taught`). The
property that buys is worth stating plainly: **a fully-taught, never-quizzed exam
is structurally capped at 50% readiness.** That is the honest answer to "am I
fooling myself by reading digests?"

Teaching is a prior, not a gate. The first quiz asked a §3.3 question and §3.3 had
never appeared in a digest; gating on taught would have scored a correct answer
there as zero. Proof beats teaching; teaching only fills the gap where proof is
absent.

Shrinkage uses `k = 4`, the smallest integer where one lucky correct answer on an
untaught subsection reads 0.40 — below "proven". At `k = 2` it reads 0.50, which
already looks like knowledge.

---

## The 75% target is ours, not Google's

Google publishes **no pass mark** for the Professional Cloud Security Engineer
exam; the official guide states question count and duration only. Asserting one
would violate rule 2 as directly as inventing a GCP fact.

So `readiness.target` lives in `config/schedule.yaml` with a required
`target_basis` string saying where it came from, and `validate.py` rejects a
target without one. It is deliberately **not** in `config/exam-blueprint.yaml`,
whose entire warrant is being a verbatim transcription of the exam guide — a
number of ours sitting in that file would be indistinguishable from one of
Google's within a week.

The report says "our 75% bar", never "the pass mark".

---

## Three ledger bugs, all found by building the thing that reads it

Readiness was the first consumer to care whether the ledger was *right* rather
than merely well-formed. All three had shipped silently.

**A missing angle claimed `delta`.** `topic.get("angle", "delta")` — and no digest
had ever recorded an angle, so all four taught sections read `angles_used:
["delta"]`. Selection believed the AWS-delta pass, the highest-value first pass
for this reader, was spent everywhere it wasn't. Fixed in three layers:
`daily-digest` records it, `validate.check_digest` rejects a topic without it, and
`build_ledger` records the pass without claiming an angle when one is absent.

**Two shapes for "withdrawn", one honoured.** `build_ledger` checked
`topic["retracted"]`; the 2026-09-11 digest recorded `retractions: [{topic: 4,
ts: …}]` at top level. Latent rather than active — that topic was *replaced*
rather than left in `topics[]`, so nothing was actually miscounted — but it would
inflate coverage the first time a topic was pulled without replacement.

The fix matches on **`ts`, never the topic number.** The first attempt keyed on
the number and immediately dropped a legitimately taught section, because a
withdrawn topic is normally replaced and the replacement reuses the number. That
is the same error as counting the retraction, pointing the other way.

**On-demand quizzes were invisible.** `schedule.yaml` sets
`on_demand.counts_toward_mastery: true`, but only the bare `quiz.json` was
globbed, so a second quiz in a day could not be recorded and ad-hoc practice moved
nothing. On-demand sets are now `quiz-<HHMM>.json` / `results-<HHMM>.json`.

---

## A real Slack user id was public for a month

Found 2026-09-10 while auditing what the readiness feature would expose:
`.claude/skills/daily-quiz/SKILL.md` contained the learner's actual Slack user id
in prose, committed in `3f52aa2` and live on `origin/main` of a public repo.

`leakcheck.py` had patterns for Slack *tokens* but none for workspace object ids,
so it passed the gate every time. An id grants nothing without workspace access,
but it names a real account — the same boundary as the Notion page ids, and the
same rule: read them from the gitignored config, never write them into committed
prose.

Redacted, and `[UCGD]0[A-Z0-9]{7,}` added to `GENERIC_SECRETS`, sharing the
`ID_ALLOW_PATHS` skip so the `U0XXXXXXXXX` placeholders in `config.example.yaml`
do not trip it.

The id remains in git history. History on a public repo is permanent, which this
document already says about Notion ids — the difference is that one was caught
*before* the first push and this one after.

---

## The readiness gate checks the transcription, not the arithmetic

`check_mastery` does not exist and should not. It would be one script
re-asserting what another just computed — the tautological gate this repo already
shipped once, in the clipping check that "passed almost always".

`check_readiness` checks the one part that is model-generated: the posted message
and the block transcribing numbers into prose. The failures with teeth are
quoting the covered score as the exam score, and printing a days estimate
alongside "still too early to decide". Both are cheap to check and impossible to
catch by rereading, because a drifted report looks exactly like a correct one.

---

## No readiness PNG in v1

The six components in `dashboard/visuals.py` are teaching shapes — none carries a
scalar or a trend, and `tests/test_visuals.py` requires a demo spec and default
width for every component, so a seventh is a render function plus three test
surfaces. A picture of five numbers that mrkdwn already shows is not worth a
Chrome dependency in an unattended 21:15 job.

The trend lives on the dashboard instead, as inline SVG. Revisit at six weekly
data points, when a sparkline in the message itself becomes the first thing
mrkdwn genuinely cannot say.

---

## The digest mix is a quota, not a priority order

**Found:** 2026-09-11, by reading a digest that had gone out that morning.

Three of its four topics were remediation on the previous night's misses. That
was not bad luck: `remediation` had `priority: 0`, and the selector ran the
remediation phase first and **unbounded** up to `topics_per_digest`. A quiz with
four misses would have produced a digest with no new material in it at all — and
since every digest feeds the next quiz, a bad day could keep the system circling
two headings indefinitely.

Priority order was the wrong shape for the problem. Misses are the most valuable
thing to revisit *and* the easiest thing to over-serve, and an ordering has no
way to express "most valuable, up to a point". A quota does:

```
fresh 0-1 · remediation 0-2 · new 1+ · review 0+ · synthesis 0-1
```

`fresh` and `remediation` have **hard** ceilings — a fifth miss defers to
tomorrow rather than being absorbed — because both are self-replenishing and
would otherwise crowd everything else out forever. What does not fit is reported
in `deferred` rather than dropped, and a floor that cannot be met is reported in
`unfilled_floors` rather than padded around. "There is no new ground left" is
something the digest should say, not something it should hide by finding a
fourth way to explain the same section.

Two details that only showed up in testing:

- **`fresh` had to overlap `new`, not partition it.** With a strict partition, a
  large sync makes every section fresh, `new` empties, its floor cannot be met,
  and the digest collapses to the single topic the fresh cap allows. Bands
  overlap; only the picks are exclusive.
- **`new` ranks sections with a pending miss last.** Otherwise the `new` floor
  takes the heaviest untaught section, which is often one carrying a miss, and
  the remediation band loses the topic whose question most needed linking.

`select_topics.py` also reads `state.local/mastery.json` for the first time. The
spaced repetition the system already computed drove the quiz and never the
digest, so "what do I need reminding on?" had no answer on this side at all. A
section whose `next_due` is in the future is not eligible however long ago it was
taught — the learner has demonstrably retained it, and staleness alone cannot
tell that from neglect.

---

## The style gate had never run over a digest

**Found:** 2026-09-11, while working out how a run-on list reached Slack.

`validate.check_style` reads `state.local/history/<date>/digest.md`. Nothing had
ever written one. `daily-digest/SKILL.md` had said so in plain text — "This was
specified and never actually done" — for long enough that it read as a known
limitation rather than an open bug. The no-argument glob matched zero files, the
loop body never executed, and `validate.py` reported success.

So the emoji budget, the blank-line rule, the line length and the message length
were all unchecked over every digest ever posted. Two failures shipped the same
morning: SAIF's six core elements run into one sentence, and a bare "Q8".

Caching the posted text is now a **gate** in the Post sequence, ahead of the
Notion mirror, and a `digest.json` with no sibling `digest.md` is an error from
2026-09-12 on. Dated, because the two existing history entries have no cache and
never will: without the cutover `validate.py` would go red on its own state and
stay red, which is how a gate gets disabled.

The delimiter changed at the same time. `_messages()` split on `---`, but house
style §5 lists a horizontal rule as in-message typography — the first digest to
use one would have been cut into two pseudo-messages, each with its own emoji
budget, so the check would have *passed* a message that broke the rule the budget
exists to enforce. The separator is now `---8<---`, which nothing else means.

---

## Enumerations, and why the gate fires at five

**Found:** 2026-09-11, writing the check for the six-elements failure.

The obvious heuristic — a comma run ending in "and" or "or" — does not match the
sentence that prompted it:

> The six elements — security foundations, detection and response, automated
> defenses, platform controls, feedback loops, business context — are …

There is no terminal conjunction, and one item ("detection and response")
contains the word the pattern keys on. The signal that actually works is a run of
short comma-separated noun phrases inside one clause, with the line split on
dashes and colons first so the surrounding prose is not counted as an item.

House style asks for a list at **three** items. The gate fails at **five**, and
warns at three or four behind a stated count. The gap is deliberate: four items
behind a count is sometimes a chain that reads correctly inline ("Four levels,
bottom up: resources, projects, folders, the organization node"), and a gate that
fails on the arguable case gets argued with and then switched off. Five short
items run into a sentence has no defence.

---

## A citation points at a place, not just a page

**Found:** 2026-09-11, from the reader's own feedback on the links.

The page-level citation was working — it was the most useful thing in the digest
— but `Module 3 → "01 — Virtual private cloud networking"` is a 200-line page,
and the reader still had to hunt. §7 already records why there is no deep link:
the Notion API does not expose heading block ids.

But the sub-headings were always available. The cached page text carries them,
and the digest already opens that text for every section it teaches. So the
locator is authored from the page in hand and checked against it, rather than
precomputed into the index — which also sidesteps the fact that a cloud run
hydrates only the pages it cites, so an index-wide table of sub-headings would be
empty there.

The parse is **level-relative**. Heading depth is not consistent across the
material: the module pages put index headings at `#` with `##` children, while
`introduction-to-security-in-the-world-of-ai-review` uses `##` with `###`. A
parser fixed at `##` returns nothing for that page — and the failure is silent,
because "no sub-headings" is a legitimate answer for the five ingested sections
that genuinely have none.

---

## Q8 was always linkable

**Found:** 2026-09-11, checking what the quiz already records.

Every quiz question is posted as its own top-level Slack message — a decision
made for a different reason (threads are flat, so a hint could not be collapsed
under a question that was itself a reply) — and `message_ts` has been recorded
per question since the first quiz. Slack exposes per-message permalinks. The link
was constructible from day one and nothing built one, so a remediation topic said
"Q8" and left the reader to scroll back through a day of channel history.

The ts → permalink transform lives in `scripts/slack_links.py` rather than in the
prompt: dropping the dot and prefixing `p` is exactly the kind of rule that gets
subtly wrong in a way nobody notices until a link lands on nothing. It returns
`None` rather than a half-formed URL.

The recap is the load-bearing half, not the link. History written before
`message_ts` existed still gets "Q8 · 10 Sep" plus what the reader picked;
`validate.py` warns there rather than failing, so old records stay valid.

---

## The facts were sourced; the framing was not

**Found:** 2026-09-11, from the reader's own complaint about a quiz — *"the
content of the quiz is not what's in the course"*, alongside *"it gives me a link
but not where to search where this exists."*

Checked before believing it, and the complaint was half wrong in an instructive
way. **Every one of the ten questions' facts was in the cached material**, several
near-verbatim: Q6's no-pre-warming claim, Q7's Partner Interconnect conditions,
Q2's Editor/Viewer split, Q10's perfect forward secrecy. The grounding gate had
not been bypassed.

What was invented was the **framing wrapped around each fact** — a mobile game
studio, a service that also processes payment data, an organisation running
regular red-team exercises. None of it in the material, none of it carrying the
deciding constraint. Decoration.

**The two complaints are one problem.** The reader could not separate the sourced
half from the decoration, because the citation stopped at a 200-line page. Given
no way to check, invented framing is indistinguishable from invented content —
and the rational response to a source you cannot verify is to distrust all of it.
That is a stronger argument for followable citations than "it saves scrolling",
which is how the digest's version of this was justified a day earlier.

### Three things that let it happen

**The quiz never adopted the locator.** House style §7 gained *"say where on the
page"* that morning, with a working helper, and `check_digest` enforced it.
`check_quiz` never read `source.locator`. A rule written once for one caller
reads as a rule about that caller.

**`check_quiz`'s grounding was referential, not semantic.** A non-empty URL, a
heading in a global flat set, services in the AWS map. A question composed
entirely from general GCP knowledge satisfies all three perfectly — which is what
the *"The prose was never sourced"* entry above said, and the fix there was to put
the page text in front of the model without ever checking that it was used. It
also never read `blueprint` at all, so a question on an **uncovered** subsection
validated clean, against rule 3.

**Thin material was quizzable and nothing noticed.** The AI-review page is 419
words and backs five of the nine sections that make §3.3 covered; its thinnest
tagged section holds **sixteen words**. Asking for a 4-5 sentence scenario there
does not risk invention, it *requires* it. The depth mix asked for three deep
questions a day with no idea what could support one.

### The anchor, and why a paraphrase must fail

Each question now quotes the span its keyed answer rests on, checked verbatim
against the body of the section it cites. Normalisation is deliberately
asymmetric: it folds emphasis markers, table pipes, bullets, dash and quote
variants, line wrapping and case — every one of which differs between how a line
sits on the page and how it gets quoted — and folds **nothing word-level**. No
stemming, no synonyms, no edit distance. A single substituted word fails, because
a paraphrase passing is the exact thing being tested for.

**Where the digest warns, the quiz errors.** A cited page with no cached text is
a hard failure. The locator is decoration on a citation that was already grounded;
the anchor *is* the grounding. `daily-quiz` fetches and caches every page it asks
about, so an absent cache at validate time means the page was never opened. A
gate that degrades to a warning in the cloud is the *"style gate had never run"*
failure with a new name, and that one hid two shipped defects for the system's
whole life.

### A question may not outgrow its source

The thin-material rule is a ratio, not a table: the cited section must hold
`min_source_ratio` times the words of the question written from it. Measured over
the twenty questions posted to date, the leanest sits at 1.98x, so 1.5 fails none
of the system's own history while excluding what cannot be sourced.

The property worth having is that **depth caps itself**. A 16-word section
affords no four-option question at all; a 51-word one affords bare recall and
nothing larger. No per-depth floors to tune, and no way to ask for a deep
scenario from a section that has not got one in it.

### The limit, stated rather than papered over

The gate proves the anchor exists in the section cited. It **cannot** prove the
keyed answer follows from it, and it cannot prove the scenario stayed
material-anchored — a question can carry a real anchor and a fabricated game
studio. That is layer 1's job (`prompts/quiz.md`, `question-spec.md` §1), the same
division the *"Gaps are planning signal"* entry settled: the prompt rule is
load-bearing, the check is the backstop.

What changed is that invention became **visible**. The grading reply quotes the
line back, so the reader checks the question against their own course instead of
trusting that we did. That was always the point of the citations.

**Rejected:** a mechanical "every noun in the scenario must appear in the
material" check. It fires on *"Your team"*, *"an on-call group"*, *"several
projects"* — generic subjects the measured corpus uses everywhere. A gate that
cries wolf gets argued with and then switched off, which this document already
says twice.
