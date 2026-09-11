# Privacy

**This repository is public.** `dinho149/gcp-security-schedule` is readable by
anyone. Every design decision below follows from that.

## What is committed

Logic only — skills, prompts, house style, question spec, blueprint, scripts,
tests, CI. This is the surface the feedback loop edits, so the SDLC loop works
exactly as intended.

## What never is

| Path | Contains |
|---|---|
| `profile.local.yaml` | Background, certifications, employer tooling anchors |
| `config/config.local.yaml` | Slack channel and user ids, Notion page ids |
| `knowledge/` | Derived from a private Notion workspace, including `sources.local.json` — the ingestion map of page ids, course titles and headings |
| `reference/exemplars/` | Google's sample questions — not ours to republish |
| `state.local/` | Quiz results, scores, weak areas — plus `mastery.json` and `readiness.json`, a per-section competence profile and the most inference-rich files in the system |

## The readiness dashboard leaves the machine

`exam-readiness` publishes `dashboard/readiness.generated.html` as an Artifact and
republishes it to the same URL every run. That page carries a per-section
competence profile: what is weak, what has never been tested, how long until
ready.

This is the first time results go anywhere but Notion, so it is a deliberate
decision rather than a side effect. Artifacts are private by default, the URL
lives only in the gitignored `config/config.local.yaml`, and the generated HTML is
covered by `.gitignore`'s existing `dashboard/*.generated.html`. Nothing about it
is committed.

Readiness gets **no** Notion database, unlike the digest and the quiz. It is a
pure function of `📊 Quiz Results`, which is already durable — a mirror would put
a second competence profile in the workspace and buy nothing a rerun does not.

## The Slack user id incident

Found 2026-09-10: `.claude/skills/daily-quiz/SKILL.md` carried the learner's real
Slack user id in prose, tracked and pushed to a public remote in `3f52aa2`.
`leakcheck.py` matched Slack *tokens* but not workspace object ids.

Redacted, and the pattern added. Low actual consequence — an id grants nothing
without workspace access — but it is the same boundary as the Notion page ids one
section down, and it was caught by an audit rather than by the gate that exists to
catch it. **The id stays in git history**, which is the difference between this and
the Notion-id case: that one was fixed before the first public push.

## Consequence: Notion is the source of truth for state

Because results cannot be committed, the Notion databases (`📊 Quiz Results`,
`📖 Daily Digests`) hold the durable record. `state.local/` is a fast local cache
that can be rebuilt.

The cost is real: **no version-controlled history of results, and no diff of how
the profile evolved.** That was the accepted trade for keeping the repo public.

## Runs happen in the cloud now

From 2026-09-11 the pipeline is driven by scheduled Claude Code routines rather
than by a session on the laptop (`docs/decisions.md`). Each run is an ephemeral
Anthropic-managed sandbox that rehydrates state from Notion, works, writes state
back, and is discarded.

**What did not change, and is the whole reason this was acceptable:**

- Nothing new is committed. `.gitignore` and `leakcheck.py` are untouched, and
  the structural rules still fail the build on `state.local/`, `knowledge/`,
  `reference/exemplars/`, `profile.*` or any `*.local.*` file being tracked.
- The repo stays public and still carries logic only.
- Personal data does not go to GitHub. It moves between Notion — where it already
  was — and a sandbox that holds it only for the length of a run.

**What did change, stated plainly:**

- The gitignored files are reconstructed outside this machine, once per run. They
  were previously read only here.
- More of the local state is now mirrored into Notion than before: the `state`
  toggles carrying `digest.json` / `quiz.json` / `results.json`, the
  `🔧 Pipeline State` page, and `👤 Learner Profile`. That is a genuine
  widening of what the workspace holds, in exchange for the laptop no longer
  being required.
- Routines auto-approve every tool from every connector they include, writes as
  well as reads, with no prompt. **Scope them to Slack and Notion only** — a
  routine that carries Drive or Gmail is granting unattended write access to
  mailboxes it has no use for.

**Readiness stays out of Notion**, as the section below requires. What is stored
is one line per run — date, covered score, cadence — because `due.py` needs the
previous cadence decision to apply its hysteresis band, and because a marker is
what stops a second run re-posting the same day. No per-section breakdown: the
moment it carries one it has become the second competence profile the no-database
rule exists to refuse.

`reference/exemplars/official-samples.md` moves to a private Notion page for the
same reason it was never committed — copyright, not privacy. That rule is
unaffected by where runs happen.

## Committed code must not hard-code Notion ids

`scripts/build_index.py` originally embedded the ingestion map directly — 18 page
ids plus every course, module and section title. It was caught in the final audit
before the first public push.

Low actual risk: a page id grants nothing without permissions, and the module
titles come from a public Google Cloud course. But it contradicted the boundary
above, and git history on a public repo is permanent — so it was fixed *before*
publishing rather than after.

The map now lives in the gitignored `knowledge/sources.local.json`, with
`config/sources.example.json` documenting the shape. `leakcheck.py` fails on any
32-hex Notion id in a tracked file, excluding `*.example.*` and docs where such
ids are placeholders.

`config/exam-blueprint.yaml` now cites Google's public exam guide rather than a
private Notion mirror of it — more correct as well as more shareable.

## Enforcement

`scripts/leakcheck.py`, run locally before every commit and first in CI.

- **Structural** (always): no `*.local.*`, `state.local/`, `knowledge/` or
  `reference/exemplars/` tracked; no generic secrets — emails, phone numbers,
  AWS keys, GitHub/Slack tokens, private keys, Notion page ids, Slack workspace
  ids.
- **Content** (when the profile is present): none of the profile's own values
  appear in tracked files. The needles are read from the gitignored profile at
  runtime, so the sensitive strings are never hard-coded into the committed script.

In CI the profile is absent, so only the structural layer runs. The content layer
is a local pre-push check by design.

An earlier version also split profile phrases into single words. It flagged
"Engineer" in the exam title and "rules" in `.gitignore`. A check that cries wolf
gets ignored, so it now matches whole phrases plus an explicit `sensitive_terms`
list.

## Commit identity

`user.email` is set repo-locally to the GitHub `users.noreply.github.com` address
so a personal email is not published in the commit history.

## If you make the repo private

Delete these from `.gitignore`:

```
knowledge/
state.local/
```

Everything else works unchanged, and you regain version-controlled history of
results and profile evolution. `profile.local.yaml` and
`reference/exemplars/` should arguably stay ignored regardless — one holds
personal data with no reason to be versioned, the other is not ours to publish.
