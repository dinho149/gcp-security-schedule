---
name: sync-notion
description: Walk the Notion PCSE tree, ingest course transcripts and material, and regenerate knowledge/index.json, knowledge/coverage.md and knowledge/exemplars.json. Run on the first session of each day, or on demand after adding training material.
---

# sync-notion

Turns the Notion workspace into the index everything else is grounded against.
**This is the growth mechanism**: add a course to Notion and the next sync pulls
it into rotation with no code change.

## Skip the walk when the cache is fresh

Before walking anything, check `control.synced_on` on `🔧 Pipeline State`.
**If it is today, stop** — the walk has already happened.

`index.json` and `coverage.md` do not depend on this. `cloud-bootstrap` rebuilds
both from `sources.local.json` by script, with no Notion access; walking is only
how *new* material is discovered.

This skill is specified to run on the first session of each day. In the cloud
every run is a fresh sandbox, so every run *looks* like the first: without the
stamp, five routines a day means five full walks of the tree, five times the
latency and tokens, for an answer that cannot have changed.

`!sync` forces a walk regardless, which is what to use after adding material to
Notion mid-day.

## Walk

Start at `config.local.yaml` → `notion.root_page_id`
(*Professional Cloud Security Engineer*).

```
root
├── Exam Guide                 -> already transcribed to config/exam-blueprint.yaml
└── <course>                   -> one child page per course
    ├── Course Transcript      -> single page; H1 = module, H2 = section
    ├── Course Material        -> subpages, one per module
    └── Notebook LM            -> skip
```

**Walk children; do not pattern-match titles.** Course 1 names its material pages
`Module N: …`; course 2 uses free-form titles. Anything that assumes `Module N`
will silently miss material.

## Per section, record

- Exact heading text — **character for character**, because citations quote it
  and `validate.py` checks the match
- Parent page title and Notion URL
- Services mentioned (cross-check against `knowledge/aws-gcp-map.json`)
- Blueprint tags, by matching content against `config/exam-blueprint.yaml` topics
- `ingested: true` **only if the content was actually read**

A page you know exists but have not read is recorded with `ingested: false` and
no sections. The grounding gate refuses to cite it. Never guess at headings.

## Per page, keep the text you just read

You have to read a page in full to record its headings. **Keep the prose** —
write it to `knowledge/pages/<slug>.md` and record that path as `cache` on the
page entry. `<slug>` is the page title, lowercased, non-alphanumerics collapsed
to `-`.

This is the input the digest and quiz actually write from. Without it they
compose from a heading plus general GCP knowledge, which reads like a machine
wrote it and quietly weakens rule 2: the citation resolves, but the prose under
it was never sourced from the material. `docs/decisions.md` records how long that
went unnoticed.

The cache also makes `ingested: true` mean something checkable for the first
time — a page claiming it with no cached text is a claim with no evidence, and
`validate.py` warns about exactly that.

`knowledge/` is gitignored and structurally blocked by `leakcheck.py`, so course
transcripts cannot reach the public remote by this route.

## Per page, stamp the date it was read

When a page first flips to `ingested: true`, write `"ingested_on": "<today>"`
alongside it, and **never rewrite it afterwards**. It is what lets the readiness
estimate measure how fast you are actually getting through the course; without it
the coverage pace is unknowable and the estimate refuses to guess rather than
inventing one.

Pages ingested before the field existed keep `"ingested_on": null`, meaning
"before the measurement window" — they count toward the level of coverage but
contribute no rate. **Do not backfill a date you do not know.**

**Stamp new sections the same way.** A section added to a page that was already
ingested carries its own `"ingested_on"`, because the page's stamp is old. The
digest's `fresh` band reserves a slot for material ingested in the last few days,
and it reads the section stamp first, falling back to the page's. Without the
section stamp, material added to an existing module never reads as new and never
gets that slot.

`null` is the safe value in both places: it means "not fresh", so a stamp you are
unsure about costs one reserved slot rather than filling the digest with
arbitrary sections. This is the same reasoning that makes rewriting these stamps
from a fresh walk a bug — see `cloud-bootstrap`, which must never re-derive them.

On an un-ingested page you may also record `"expected_exam_tags"`: a planning-only
guess at what it will cover, used to answer "how much would reading this pull the
estimate in?". It is the same class of object as the add-next list in
`coverage.md` — **never citable and never teachable**, and coverage is computed
from `sections[].exam_tags` on ingested pages only, so rule 3 holds by
construction.

## Also harvest

- Every `## Section Quiz` (transcript) and `# Module quiz` (material) block into
  `knowledge/exemplars.json`. These are Google-authored, come with explanations,
  and calibrate difficulty.
- Note **coverage gaps** where the exam tests something the material only partly
  covers. Standing example: Module 3 teaches firewall targeting by network tag,
  but official sample Q6 keys on service-account targets.

  Record these as a `note` on the section. **They are planning signal only — never
  teaching content.** A gap says "this training has not reached here yet", and the
  learner is still working through the course. It will be covered in due course;
  getting there first is exactly the rushing they asked us not to do.

  Gaps surface in `knowledge/coverage.md` and `!status`. They must never appear in
  a digest or a quiz.

## Rebuild

```bash
.venv/bin/python scripts/build_index.py
.venv/bin/python scripts/build_coverage.py
.venv/bin/python scripts/validate.py
```

Then report what changed: new courses, newly covered subsections, and the
movement in reachable exam weight.

## AWS map

Re-parse the *AWS vs Azure vs GCP* page when it changes. A GCP service with an
empty AWS cell is **signal, not missing data** — VPC Service Controls has no AWS
equivalent, and that absence is exactly what a reader with an AWS background
needs told.

## Outputs are gitignored

`knowledge/` never gets committed — it derives from a private workspace and this
repository is public. Only the generators are committed.
