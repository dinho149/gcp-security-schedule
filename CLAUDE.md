# GCP Security Exam study system

Daily digest + quiz loop for the Google Cloud **Professional Cloud Security
Engineer** exam, sourced entirely from the learner's own Notion material and
delivered to Slack.

---

## ⚠️ This repository is PUBLIC

Never commit personal data. Install the pre-commit gate once per clone:

```bash
./scripts/install-hooks.sh     # blocks any commit that fails leakcheck
```

Run it directly any time:

```bash
.venv/bin/python scripts/leakcheck.py
```

Local-only, gitignored, and **must stay that way**:

| Path | Why |
|---|---|
| `profile.local.yaml` | Learner background, employer tooling anchors |
| `config/config.local.yaml` | Slack channel and user ids, Notion page ids |
| `knowledge/` | Derived from a private Notion workspace |
| `reference/exemplars/` | Google's sample questions — not ours to republish |
| `state.local/` | Quiz results, mastery scores |

If you need a new config value, add it to the `.example.yaml` with a placeholder
and read the real one from the `.local` file.

## Three rules that override everything else

### 1. Never explain what the reader already knows

Read `profile.local.yaml` → `assume_known` first. They hold AWS Security
Specialty, AWS SA Pro and CKA, and lead a platform security team. Explaining
least privilege or what SAST is wastes their time and trains them to skim.

Lead with the **delta from AWS**. See `docs/house-style.md` §1.

### 2. Never assert anything the material doesn't support

Every factual claim traces to an ingested section in `knowledge/index.json`.
Every AWS equivalence comes from `knowledge/aws-gcp-map.json` — Google's own
comparison table — and nowhere else.

If the material doesn't cover it, say so and pick something else. Do not fill
gaps from general knowledge, however confident you are. The whole point of the
citations is that the reader can check you without trusting you.

### 3. Never teach or quiz beyond covered material

`knowledge/coverage.md` is the authority. A subsection marked ⬜ is off-limits —
for digests **and** quizzes — until its material lands in Notion. Sections with
`ingested: false` cannot be cited at all.

This includes **known gaps**. Where the exam tests something the course only
partly covers, that is recorded as planning signal and surfaced in coverage
reporting. It is never taught. The learner is still working through the training
and will reach it; running ahead is the thing they explicitly asked us not to do.

If a digest topic cannot be sourced entirely from ingested material, pick a
different topic.

## Layout

```
config/exam-blueprint.yaml    5 sections, weights, 70 topics (from the exam guide)
docs/house-style.md           voice, typography, attention rules
reference/question-spec.md    PCSE question anatomy, measured from 20 real samples
prompts/                      digest / quiz / grading — what the feedback loop edits
.claude/skills/               the runnable procedures
scripts/                      generators and validators
```

## Commands

```bash
.venv/bin/python scripts/build_index.py       # rebuild knowledge/index.json
.venv/bin/python scripts/build_coverage.py    # rebuild knowledge/coverage.md
.venv/bin/python scripts/measure_corpus.py    # re-derive question-spec numbers
.venv/bin/python scripts/validate.py          # validate config + generated content
.venv/bin/python scripts/leakcheck.py         # privacy gate — run before every commit
```

Setup on a fresh clone:

```bash
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp config/config.example.yaml config/config.local.yaml
cp config/profile.example.yaml profile.local.yaml   # then fill it in
```

## Conventions

- Python 3.13, standard library plus PyYAML. No other runtime dependencies.
- Generated files carry a "do not edit by hand" header and are rebuilt by a script.
- Scripts print a short summary of what they did and exit non-zero on failure.
- Timing lives in `config/schedule.yaml`, never in a scheduler UI.
