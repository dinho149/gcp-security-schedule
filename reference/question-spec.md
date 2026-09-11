# PCSE question specification

Every generated question must conform. `scripts/validate.py` enforces the
mechanical rules; `prompts/quiz.md` carries the judgement ones.

**This spec is empirical.** Every number below was measured from the 20 official
sample questions in `reference/exemplars/official-samples.md`, not inferred from
third-party descriptions — several of which turned out to be wrong. If the corpus
grows, re-run `scripts/measure_corpus.py` and update these numbers rather than
arguing from memory.

---

## 1. Anatomy

```
[scenario]   0-4 sentences of context carrying the deciding constraint
[stem]       1 interrogative sentence
[options]    exactly 4, labelled A-D
```

**The scenario is material-anchored.** Every entity and situation in it comes
from the cited section — its own worked examples, terms and numbers. Generic
subjects are the exception and are attested throughout the corpus (§3). Framing
that carries no deciding constraint and appears nowhere in the material — an
industry, a product launch, a compliance stake, a programme — is invention, and
it is what makes a correctly sourced question read as though it came from
somewhere other than the course. `prompts/quiz.md` carries the reference set of
failures.

## 2. Hard rules (mechanically enforced)

| Rule | Value | Evidence |
|---|---|---|
| Option count | **exactly 4** | 20/20 questions |
| Multi-select option count | **also 4** | the one multi-select uses A-D |
| Multi-select marker | `(choose two)`, lowercase, end of stem | verbatim from corpus |
| Scenario + stem sentences | 1-5, target median 3 | min 1, max 5, median 3 |
| Option length | 1-26 words, median ~10 | mean 10.7 |
| Within-question word spread | **<= 8** (max-min) | p90 = 8, only one outlier at 12 |
| Within-question length ratio | **<= 2.6** (max/min) | observed max 2.60 |
| Fictional company names | **banned** | 0/20 use one |
| "All/None of the above" | **banned** | 0/20 |
| Negatively-phrased stems | **banned** | 0/20 |

## 3. Subjects — generic only

Real corpus uses: *"A customer…"*, *"Your company…"*, *"Your team…"*,
*"An organization…"*, *"You…"*, *"A cloud customer…"*, *"A retail company…"*,
*"Developers in an organization…"*, *"Your customer…"*.

**Never invent a brand name.** Fictional companies are a reliable tell that a
question came from a third-party dump rather than Google.

## 4. Stem forms

Use one of these shapes (all attested in the corpus):

- `What should you do?`
- `What action should you take?`
- `What should your team do to meet this requirement?`
- `What action should the customer take to meet these requirements?`
- `How should you grant access?`
- `Which solution should you use to meet these requirements?`
- `Which solution should be used to resolve this concern?`
- `Which Google Cloud solution should be used to meet these requirements?`
- `Which action should you take to meet the customer's requirements?`
- `Which two … ? (choose two)`
- A bare-recall form: `Which encryption algorithm is used with …?`

Stems may be extended with a purpose clause — *"What should you do **to ensure that
the container images used for new deployments contain the latest security patches**?"*

## 5. The "Google-recommended practices" tell

The phrase *"You want to follow Google-recommended practices."* appears in the corpus
and signals that the **most managed / most native / least-privilege** option wins.
Use it when that is genuinely the discriminator; do not sprinkle it.

## 6. Distractor construction

Two legitimate techniques, both attested. **Prefer the first** — it is how the exam
tests precision, and it was the single biggest correction to our initial assumptions.

### 6a. Precision near-variants (preferred)

Options share a frame and differ by one decisive detail:

- *Storage Object Creator at the **project** level* vs *at the **bucket** level* (Q5)
- *Service Account **User*** vs *Service Account **Admin*** (Q3)
- *Org viewer + Project **owner*** vs *Org viewer + Project **viewer*** (Q14)
- *target a **network tag*** vs *target a **service account*** (Q6)

### 6b. Distinct strategies

Each option is a different service that could plausibly address the problem; a
constraint in the scenario discriminates. (Q8: IAP vs Cloud VPN vs ACL vs firewall.)

**Parallelism is mandatory either way.** Within one question, options are all noun
phrases or all imperative sentences — never mixed. Corpus first words are dominated
by `Create` (19), `Use` (8), `Configure` (5), `Set` (4); bare noun-phrase questions
use them consistently across all four.

## 7. Difficulty

**Exam-level scenarios on covered content.** Only concepts the ingested Notion
material teaches, asked the way Google asks them.

**Mix scenario depth across a 10-question set** to match the measured corpus
distribution (1 bare / 12 mid / 7 deep out of 20), which scales to roughly:

| Depth | Sentences | Per 10 questions |
|---|---|---|
| bare recall | 0-1 | ~1 |
| mid | 2-3 | ~6 |
| deep | 4-5 | ~3 |

Do not make every question a heavy scenario — but note the corpus skews *deeper*
than intuition suggests: over a third are 4-5 sentences.

## 8. Grounding (the anti-hallucination gate)

A question is rejected and regenerated unless:

1. Every GCP service, role, permission and constraint named resolves to
   `knowledge/index.json` or `knowledge/aws-gcp-map.json`.
2. `source.page` and `source.heading` are **one real citation** — that heading on
   that page, not two halves that each resolve somewhere.
3. `source.anchor` is a span of **at least 10 words**, found **verbatim in the
   cited section's body** of the cached page. Markup is normalised (emphasis,
   table pipes, bullets, dash and quote variants, line wrapping, case); nothing
   word-level is. A paraphrase fails.
4. The cited section holds at least `quiz.min_source_ratio` times the words of
   the question written from it (scenario + stem + options).
5. The tagged blueprint subsection is marked covered in `knowledge/coverage.md`.
6. A `source.locator`, where given, names a sub-heading the page actually has.
7. All rules in §2 pass.

**Where the numbers come from.** Ten words: §2 measures the corpus option median
at ~10, so an anchor shorter than one option is a term rather than a claim, and
would match the page while asserting nothing. The ratio lives in
`config/schedule.yaml` with its own measured basis, and caps scenario *depth* by
material without needing a per-depth table — a 16-word section carries no
question, a 51-word one carries bare recall and nothing larger.

No invented service names. No invented role IDs. No plausible-sounding permission
strings. If the material does not support a question, generate a different one —
and if that leaves fewer than ten, post short and say which sections could not
carry one. Never refill the slot from an easier section.

### What this gate does not entail, stated plainly

It proves the anchor exists in the section cited. It cannot prove the keyed
answer *follows* from it, and it cannot prove the scenario stayed
material-anchored: a question can carry a real anchor and still wrap it in an
invented product launch. §1 and `prompts/quiz.md` carry that, as the wording
layer — the same division `docs/decisions.md` settled for teaching beyond the
material, where the prompt rule is load-bearing and the check is the backstop.

What the anchor changes is that invention becomes **visible**. The grading reply
quotes the line back, so the reader compares the question against the course
themselves rather than trusting that we did.
