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

## 2. Voice — the material's, not the model's

The digest teaches a course the reader is **already taking**. It should sound like
that course, not like a summary written by someone who never watched it.

- **Write from the cached page text** (`knowledge/pages/<slug>.md`). It is the
  first input in `prompts/digest.md` and `prompts/quiz.md` for a reason:
  everything else — headings, service lists, blueprint tags — is *metadata about*
  the material, not the material. A topic written from a heading alone is the
  model's prose wearing a citation.
- **Carry the instructor's terms.** Where the page calls something "important VPC
  compatibilities" or walks a "decision tree", use their words, not a smoother
  synonym. The reader has heard those words; matching them makes a digest feel
  like revision rather than a fresh lecture.
- **Quote when their phrasing beats yours.** One short quoted line, attributed to
  the section, is worth more than a paraphrase.

### The tells

One construction dominates the current output: short declarative, pivot on an
em-dash or full stop, reversal.

> *"That's not a trick question — it's the default topology."*
> *"The one you'll reach for wrongly."*
> *"Your instinct is right about what these controls are for. It's wrong about
> where they live."*
> *"Coverage is a ceiling, not a discount."*

Once in a digest, that is voice. Four times, it is a tic, and it is the loudest
machine tell in the output. **At most one per message.**

Also cut:

- **Throat-clearing.** *"It's worth noting", "Importantly", "Keep in mind".*
- **Tricolons.** Three parallel clauses in a row is a cadence nobody speaks in.
- **Bolding an abstract noun and then explaining it.** Bold the word that decides
  the sentence, per §5.
- **Uniform sentence length.** Several 10-word sentences in a row is the most
  recognisable machine rhythm there is. Vary it or read it aloud.

This section is about cadence, never about level. §1 still governs.

## 3. AWS equivalences

Name an AWS counterpart **inline, in brackets, where the GCP service is first
named** — `Cloud Storage (≈ S3)` — and only where `knowledge/aws-gcp-map.json`
supports it. That file is Google's own comparison table and the single source
for this; nothing else may ground an equivalence.

| Map state | Write |
|---|---|
| `aws` non-empty | The bracket. Shortest recognisable AWS name; where the map lists several, pick the one the sentence is actually about. |
| `aws` blank | Say it in words, once, where it matters: *"VPC Service Controls has no AWS equivalent."* The absence is the lesson. |
| service absent from the map | **Nothing.** No source, so no assertion. |

That third row is the one that gets broken. Shared VPC, IAM, GKE and Dedicated
Interconnect are all absent from the map; writing *"the two peering options have
no clean AWS counterpart"* asserts a fact nothing backs. Silence is correct.

**No standalone analogy line, no analogy paragraph, no generic "GCP ≈ AWS"
table.** An analogy that fires whether or not a counterpart exists teaches
nothing, which is why the 🔁 marker was retired.

What this does **not** touch: the ❌/✅ habit-versus-reality pattern (§6) and the
`delta` digest angle. Those teach *behavioural* difference — where a role can be
defined, VPC scope being inverted — which is the highest-value content here.

## 4. Colour language

One mapping, used identically in Slack, Notion and the dashboard, so it's learned
by repetition:

`🟦 1 Access` · `🟩 2 Boundary` · `🟨 3 Data` · `🟧 4 Operations` · `🟥 5 Compliance`

## 5. Typography, emoji and rhythm

### Four typefaces, each with one job

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

### Emoji get the same discipline

They never did, and it showed: a digest topic carried six emoji across eight
lines, and the quiz parent carried fifteen. **An emoji earns its place only when
it encodes something the words do not.**

- **Budget: four per message.** The section square and the ⏱ are two of them.
  The ❌/✅ pair spends the other two, which is the point — it is the most
  load-bearing device in the system.
- **Load-bearing, always keep:** the section squares (§4 depends on them being
  learned), 1️⃣–4️⃣ on a quiz question, ❌/✅ where a genuine binary contrast exists.
- **Exempt from the budget:** 1️⃣–4️⃣ (they *are* the answer interface, not
  decoration) and ☐ (a list bullet that happens to live in a symbol block).
  Everything else counts, the section square included.
- Readiness reports are a different shape and §9 governs them; the budget is
  checked over digests and quizzes, which is where the crowding was.
- **Retired as decoration:** ⚡ 🧠 🎯 🔻 🧵 📖 🔁, and ⚠️ wherever it only adds
  urgency. ⚠️ survives only where it changes what the reader should do — the
  `(choose two)` marker, and the "our bar, not Google's" line.

### Vertical rhythm

Crammed text does not get read, and the spacing was previously ad hoc — one topic
had two blank lines before its ❌/✅ pair and none before its citation.

- **Exactly one blank line between blocks. Never two.** Slack's paragraph spacing
  is already generous; a double gap reads as a rendering bug.
- Blank line after the header line, and before the citation.
- Option lists: a blank line before and after; the options themselves single-spaced.
- Keep lines under ~90 characters so nothing wraps mid-thought on a laptop.
- **~12 lines per message.** Past that it is two topics, or the overflow belongs
  in the thread — which §6.7 already says.

## 6. Attention rules

1. **⏱ cost on the header line, once per message** (`⏱ 90s`). The reader always
   knows what they're committing to. It does **not** repeat in the agenda: a
   four-topic digest used to print it nine times.
2. **Never 3+ sentences without a visual break** — table, rule, callout, diagram, code block.
3. **Shape rotation.** No two consecutive chunks use the same block type.
4. **Hook first, never a definition.** Open with a trap, a contrast, or a mistake worth making.
5. **❌/✅ pattern** for every service: *AWS habit* vs *GCP reality*.
6. **TL;DR at top, checklist at bottom.** Both must stand alone.
7. **Progressive disclosure** — depth goes in Slack threads and Notion toggles, never inline.
8. **Every chunk ends with its Notion citation.** No exceptions.
9. **~6 minute ceiling.** Estimate and trim.

## 7. Citations

Format: the page title and the exact heading, **as a link** to the Notion page.
In Slack that is `<url|text>`, and the whole string is the label:

```
<https://app.notion.com/p/<page-id>|Module 2 → "03 — IAM roles">
```

Linking it is the step every prompt used to skip, leaving the reader with a
citation they could read but not follow. `scripts/build_coverage.py` renders the
markdown equivalent — same shape, `[label](url)`.

No 📖 marker: a link is already visually distinct, so the emoji was spending
budget (§5) on a signal the colour was giving for free. No backticks around the
heading either — `monospace` means "recall this exactly", and a heading is a
navigation aid, not an exam fact.

The Notion API does not expose heading block IDs, so we link to the page and quote
the heading verbatim — it's ⌘F-able. The heading text must match
`knowledge/index.json` character for character; validate.py checks this.

Never cite a section whose `ingested` flag is false.

## 8. Visuals

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

## 9. Reporting numbers

Grading and readiness report on the **reader**, not on GCP, so different rules
apply.

- **Two numbers or none.** A score over covered material and a score over the
  whole exam always appear together, with the ceiling named. Either alone is a
  claim the material does not support.
- **Bars are not `monospace`.** `▓▓▓▓▓▓▓▓░░` is already fixed-width; backticks
  around it spend the exam-recall signal on decoration.
- **No pipe tables in Slack.** They render literal. The tables in §6 survive only
  because the digest is mirrored to Notion; a report is not.
- **Confidence is one of three words** — low, medium, high. When the data is too
  thin for any of them the fixed phrase is *"still too early to decide"*,
  followed by what it is waiting for and when that arrives at the current pace.
- **Three kinds of dash, never one.** *Too few to score*, *not yet asked* and *no
  material ingested* are different facts. Collapsing them is the most likely way
  a report lies.
- **Per-section rows in blueprint order**, each led by its colour square, so the
  shape of the report is learned rather than read.
- **Cite the inputs, not Notion.** §7 requires a citation on anything that
  teaches; a report teaches nothing, and cites its own evidence instead —
  `<n> quiz days · <n> graded questions · coverage as of <date>`.
- **Never congratulate.** Report, then name what moves the number.

## 10. Worked example

Four emoji in the topic message — square, ⏱, ❌, ✅ — one blank line between
blocks, and a citation you can click.

```
Digest · Wed 10 Sep · ⏱ 6 min

> 🟦 **Today:** the two IAM controls that don't behave like their AWS analogues.

_Get these and today's quiz is an 8/10._

**1.** 🟦 Org policies are not SCPs
**2.** 🟦 Where custom roles can live
```

```
🟦 1 · Org policies are not SCPs · ⏱ 90s

The instinct is to reach for an org policy constraint when you want to stop
someone calling an API. That's the wrong tool.

| | Blocks | Lives on |
|---|---|---|
| `constraints/*` (org policy) | resource **configuration** | org / folder / project |
| IAM **deny policy** | the **API call** | principal + resource |

❌ **AWS habit** — SCP at the OU to deny an action
✅ **GCP reality** — IAM deny policy; org policy won't do it

Deny is evaluated **before** allow. Same order as an explicit Deny in AWS,
different object entirely.

<https://app.notion.com/p/<page-id>|Module 2 → "02 — Identity and Access Management (IAM)">
```

```
✅ Before the quiz you can say…

☐ which control stops an API call, and which stops a configuration
☐ where a custom role can and cannot be created
☐ what deny policies are evaluated against, and when
```

Note what it does **not** do: define IAM, explain least privilege, introduce what
a policy is, or reach for an AWS analogy that `aws-gcp-map.json` does not carry.
