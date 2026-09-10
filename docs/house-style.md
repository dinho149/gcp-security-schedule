# House style

Governs every digest, quiz and results message. `scripts/validate.py` enforces
what can be checked mechanically; the rest is judgement carried by `prompts/`.

This exists because the reader has a short attention span and a demanding day job.
A digest that doesn't get read is worth nothing, however accurate it is.

---

## 1. Altitude — the rule that matters most

The reader holds AWS Security Specialty, AWS SA Pro and CKA, and leads a platform
security team. **Explaining a concept they already own is the worst failure this
system can make** — worse than being wrong, because it wastes their time and
teaches them to skim.

- Read `profile.local.yaml` → `assume_known` before writing. Never define anything on it.
- Lead with the **delta from AWS**, never with the concept.
- Where AWS intuition actively misleads, say so explicitly — that's `aws_traps`,
  and it's the highest-value content in the system.
- Anchor GCP services to systems the reader built themselves (`anchors`), by name.
- Show `gcloud` and Terraform freely. Do not explain what IaC is.

If a chunk could appear unchanged in a beginner's course, it's wrong.

## 2. Colour language

One mapping, used identically in Slack, Notion and the dashboard, so it's learned
by repetition:

`🟦 1 Access` · `🟩 2 Boundary` · `🟨 3 Data` · `🟧 4 Operations` · `🟥 5 Compliance`

## 3. Typography — Slack has four typefaces, each with one job

Slack gives regular, **bold**, _italic_ and `monospace`. Assign each a fixed role;
never decorate.

| Face | Job | Never |
|---|---|---|
| `monospace` | Service names, roles, permissions, constraints, CLI — anything to recall **exactly** | Emphasis |
| **bold** | The single load-bearing word in a bullet | Whole sentences |
| _italic_ | Asides and the "why it matters" line | Key terms |
| `#` headers, `>` quotes, `---` | Structural rhythm | Decoration |

`monospace` becomes the visual signal for *"this is a thing you must get exactly
right in the exam"*. That only works if it is never used for anything else.

## 4. Attention rules

1. **⏱ cost on every chunk** (`⏱ 90s`). The reader always knows what they're committing to.
2. **Never 3+ sentences without a visual break** — table, rule, callout, diagram, code block.
3. **Shape rotation.** No two consecutive chunks use the same block type.
4. **Hook first, never a definition.** Open with a trap, a contrast, or a mistake worth making.
5. **❌/✅ pattern** for every service: *AWS habit* vs *GCP reality*.
6. **TL;DR at top, checklist at bottom.** Both must stand alone.
7. **Progressive disclosure** — depth goes in Slack threads and Notion toggles, never inline.
8. **Every chunk ends with its Notion citation.** No exceptions.
9. **~6 minute ceiling.** Estimate and trim.

## 5. Citations

Format: `📖 <Page title> → "<exact heading>"` linked to the Notion page URL.

The Notion API does not expose heading block IDs, so we link to the page and quote
the heading verbatim — it's ⌘F-able. The heading text must match
`knowledge/index.json` character for character; validate.py checks this.

Never cite a section whose `ingested` flag is false.

## 6. Visuals

The digest posts as **one message per topic**, each with its visual(s) in its own
thread. Threads collapse, so a visual is available instantly but never in the way.

Six components live in `dashboard/visuals.py`; `dashboard/render.py` turns a spec
file into PNGs in one command.

| Component | Shape | Use for |
|---|---|---|
| `compare` | 2–3 column card | GCP vs AWS, service A vs B |
| `chain` | nested hierarchy with marks | hierarchy, inheritance |
| `contrast` | ❌ habit / ✅ reality | an `aws_traps` entry |
| `sequence` | numbered strip | evaluation order, request path |
| `decision` | branching tree | "which option" |
| `code` | annotated snippet | `gcloud` / Terraform |

**Rules**

- One visual per topic minimum; two when the topic earns it.
- **Never two of the same component in one digest.** Four lookalike cards is the
  wall-of-text problem in picture form.
- Set `section` on the spec so its accent matches the topic's colour square.
- A topic that cannot justify a visual is too thin — merge or cut it.
- The renderer refuses to emit a clipped image. Fix the spec rather than shipping
  a truncated one.

## 7. Worked example

```
# ⚡ Digest · Wed 10 Sep · ⏱ 6 min
> 🟦 **Today:** the two IAM controls that don't behave like their AWS analogues.
_Get these and today's quiz is an 8/10._
───────────────────────────────
## 🟦 1 · Org policies are not SCPs         ⏱ 90s
The instinct is to reach for an org policy constraint when you want to stop
someone calling an API. That's the wrong tool.

| | Blocks | Lives on |
|---|---|---|
| `constraints/*` (org policy) | resource **configuration** | org / folder / project |
| IAM **deny policy** | the **API call** | principal + resource |

❌ **AWS habit** — SCP at the OU to deny an action
✅ **GCP reality** — IAM deny policy; org policy won't do it

🎯 Deny is evaluated **before** allow. Same order as an explicit Deny in AWS,
   different object entirely.

📖 Module 2 → "02 — Identity and Access Management (IAM)"
───────────────────────────────
## 🟦 2 · Where custom roles can live       ⏱ 45s
Org **or** project. _Never_ folder — even though folders inherit everything else.

📖 Module 2 → "03 — IAM roles"
───────────────────────────────
        [ diagram: org ▶ folder ▶ project ▶ resource ]
───────────────────────────────
## ✅ Before the quiz you can say…
☐ which control stops an API call, and which stops a configuration
☐ where a custom role can and cannot be created
☐ what deny policies are evaluated against, and when

🧵 _Thread: deep dives, plus the anchor to your own PAM rollout_
```

Note what it does **not** do: define IAM, explain least privilege, or introduce
what a policy is.
