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

### Enumerations are lists

Three or more parallel named items go **one per line**. Never inside a sentence.

This shipped on 11 Sep, and it is the shape to recognise:

> The six elements — security foundations, detection and response, automated
> defenses, platform controls, feedback loops, business context — are
> "explicitly not a sequence."

Six things the reader is meant to be able to recall, buried in a clause they
have to parse to count. The material itself lists them as six headings; the
digest flattened what the page had already structured.

- Two items are a sentence, or the ❌/✅ pair (§6.5).
- A list that is really a comparison is a table or a `compare` visual (§8).
- Where the cached page already breaks the items out, follow it — the structure
  is part of what §2 means by writing in the material's own terms.

`validate.py` fails on **five or more** short items run into a sentence, and
warns at three or four behind a stated count. The rule is written at three and
enforced at five because a gate that fails on the arguable case gets argued
with, and then ignored.

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

### Say where on the page, not just which page

A page is 200 lines. A citation that stops at the page leaves the reader
hunting, and they are reading this on a phone between meetings. Add one line
under the link naming the sub-heading to jump to and what to read when they get
there:

```
<https://app.notion.com/p/<page-id>|Module 3 → "01 — Virtual private cloud networking">
On the page: _Example: subnets spanning zones_ — the CIDR/zones table.
```

- The sub-heading is quoted **verbatim** from the cached page and _italicised_ —
  not `monospace`, which §5 reserves for things to recall exactly. A navigation
  aid is not an exam fact. Same reasoning as the no-backticks rule above.
- What to look for names a **concrete artifact** on the page — the table, the
  ⚠️ callout, the numbered list, a phrase to ⌘F — never a restatement of the
  topic you just wrote.
- One line, and it spends no emoji.
- **Omit it** when the section has no sub-headings. Five of the thirty ingested
  sections are flat; for those the page-level citation alone is correct.

`scripts/page_sections.py` lists a section's sub-headings, and `validate.py`
fails a locator that points at one the page does not have.

### A reference to a question is a link

Slack *does* expose per-message permalinks, and every quiz question is its own
top-level message. So "Q8", on its own, asks the reader to scroll back through a
day of channel history to find out what they are being corrected about:

```
<permalink|Q8 · 10 Sep> asked whether SAIF's six elements are a sequence.
You picked _"in order, gating deployment on each"_.
```

The recap is the load-bearing half and the link is the convenience — when the
question predates recorded timestamps, cite it as `Q8 · 10 Sep` unlinked rather
than dropping the reference. Never hand-assemble the URL: `scripts/slack_links.py`
builds it from the `message_ts` the ledger already carries.

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
