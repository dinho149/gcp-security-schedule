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
| `state.local/` | Quiz results, scores, weak areas |

## Consequence: Notion is the source of truth for state

Because results cannot be committed, the Notion databases (`📊 Quiz Results`,
`📖 Daily Digests`) hold the durable record. `state.local/` is a fast local cache
that can be rebuilt.

The cost is real: **no version-controlled history of results, and no diff of how
the profile evolved.** That was the accepted trade for keeping the repo public.

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
  AWS keys, GitHub/Slack tokens, private keys.
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
