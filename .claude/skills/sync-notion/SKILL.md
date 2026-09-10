---
name: sync-notion
description: Walk the Notion PCSE tree, ingest course transcripts and material, and regenerate knowledge/index.json, knowledge/coverage.md and knowledge/exemplars.json. Run on the first tick of each day, or on demand after adding training material.
---

# sync-notion

Turns the Notion workspace into the index everything else is grounded against.
**This is the growth mechanism**: add a course to Notion and the next sync pulls
it into rotation with no code change.

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

## Also harvest

- Every `## Section Quiz` (transcript) and `# Module quiz` (material) block into
  `knowledge/exemplars.json`. These are Google-authored, come with explanations,
  and calibrate difficulty.
- Note **coverage gaps** where the exam tests something the material only partly
  covers. Standing example: Module 3 teaches firewall targeting by network tag,
  but official sample Q6 keys on service-account targets. Record these as a
  `note` on the section — they are prime digest material.

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
