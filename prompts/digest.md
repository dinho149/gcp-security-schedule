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

## Choosing today's topics

1. Start from the weakest / most-due entries in `mastery.json`.
2. **Weight up anything in `profile.local.yaml` → `aws_traps`.** Those are the
   marks actually at risk. A trap that has never appeared should outrank a
   topic already scoring well.
3. Restrict to subsections marked ✅ in `coverage.md`.
4. Pick 3–4 that hang together. A digest with a thesis beats a digest with
   coverage.

## Structure

```
# ⚡ Digest · <date> · ⏱ <n> min
> <square> **Today:** <the thesis, one line>
_<why it matters for today's quiz>_
───────────────────────────────
## <square> 1 · <title>        ⏱ <n>s
<content — different block shape each chunk>
📖 <Page> → "<exact heading>"
───────────────────────────────
        [ diagram ]
───────────────────────────────
## ✅ Before the quiz you can say…
☐ <checkable claim>
🧵 _Thread: <what is in the thread>_
```

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

## Failure modes to avoid

| Symptom | Fix |
|---|---|
| Explains what IAM is | Assume it. Lead with how binding differs from attaching. |
| Generic "GCP ≈ AWS" table | Use the reader's own systems from `anchors`. |
| Four chunks all bulleted lists | Rotate: table, contrast pair, diagram, checklist. |
| A claim with no citation | Cut it or find the section. |
| Reads like documentation | It should read like a colleague who already knows what you know. |
