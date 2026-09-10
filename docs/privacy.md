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
| `knowledge/` | Derived from a private Notion workspace |
| `reference/exemplars/` | Google's sample questions — not ours to republish |
| `state.local/` | Quiz results, scores, weak areas |

## Consequence: Notion is the source of truth for state

Because results cannot be committed, the Notion databases (`📊 Quiz Results`,
`📖 Daily Digests`) hold the durable record. `state.local/` is a fast local cache
that can be rebuilt.

The cost is real: **no version-controlled history of results, and no diff of how
the profile evolved.** That was the accepted trade for keeping the repo public.

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
