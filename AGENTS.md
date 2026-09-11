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
| `knowledge/` | Derived from a private Notion workspace (incl. `sources.local.json`) |
| `reference/exemplars/` | Google's sample questions — not ours to republish |
| `state.local/` | Quiz results, mastery and readiness scores — a per-section competence profile |

If you need a new config value, add it to the `.example.yaml` with a placeholder
and read the real one from the `.local` file.

**Never hard-code Notion page ids in committed code.** The ingestion map lives in
the gitignored `knowledge/sources.local.json`; `config/sources.example.json` shows
the shape. `leakcheck.py` fails the build on a 32-hex id in a tracked file.

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

This applies to **reporting**, too. A readiness score computed only over covered
material is a claim about 61% of the exam; posting it without its ceiling asserts
something the material does not support. Both numbers, always — `exam-readiness`
and `validate.check_readiness` enforce it.

## How this is driven

**Scheduled cloud routines.** Five weekday routines call `cloud-run`, which
rehydrates state from Notion, runs `daily-run`, and writes state back. Slack `!`
commands and reactions are **real triggers**, picked up by the hourly drain —
within the hour, not instantly. The laptop does not need to be on.

`config/schedule.yaml` still decides what is *due*; a step whose time has passed
today and whose output is missing fires, however late. That rule did not change
and did not need to: it always assumed an unreliable clock.

```
from the phone:   type !digest in Slack, or open a session and say "digest"
```

Routine setup, the one-time Notion migration and the failure playbook live in
`docs/cloud-routines.md`.

The pinned message in `#gcp-security-exam` lists the commands;
`.agents/skills/daily-run/SKILL.md` holds the canonical copy and `!help` reprints
it — keep the three identical.

### Why a cloud runner is possible now

Until 2026-09-11 this section said the opposite, and the reasoning was sound at
the time: everything the pipeline reads is gitignored and stays on this machine,
so a cloud runner would have nothing to read.

Two things make it work, and neither is a weakening of the privacy design:

1. **A cloud session keeps the claude.ai connectors.** Slack and Notion are
   reached through the account, not a token — which is also why a container on
   GCP or anywhere else *cannot* do this. `claude setup-token` and API keys make
   model requests and cannot fetch connectors.
2. **Notion was already the durable record** (`docs/privacy.md`). State the
   pipeline needs is rehydrated from the place it was already being mirrored to.

Still true, and load-bearing: **nothing private is committed.** `leakcheck.py` is
unchanged, `.gitignore` is unchanged, and the repo stays public. What changed is
where a *run* happens, not what git holds.

**The laptop is no longer the runner.** It is for editing logic, which travels
through git as it always has. `scripts/runner_guard.py` refuses a local run whose
state is behind the cloud's watermark — two runners on one state is how a day
gets double-posted.

## Layout

```
config/exam-blueprint.yaml    5 sections, weights, 70 topics (from the exam guide)
docs/house-style.md           voice, typography, attention rules
docs/cloud-routines.md        the five routines, and how to set them up
reference/question-spec.md    PCSE question anatomy, measured from 20 real samples
prompts/                      digest / quiz / grading — what the feedback loop edits
.agents/skills/               the runnable procedures
scripts/                      generators and validators
```

## Commands

```bash
.venv/bin/python scripts/build_index.py       # rebuild knowledge/index.json
.venv/bin/python scripts/build_coverage.py    # rebuild knowledge/coverage.md
.venv/bin/python scripts/measure_corpus.py    # re-derive question-spec numbers
.venv/bin/python scripts/build_mastery.py     # rebuild state.local/mastery.json
.venv/bin/python scripts/build_readiness.py   # rebuild state.local/readiness.json
.venv/bin/python scripts/build_dashboard.py   # render the readiness dashboard
.venv/bin/python scripts/validate.py          # validate config + generated content
.venv/bin/python scripts/leakcheck.py         # privacy gate — run before every commit
.venv/bin/python scripts/runner_guard.py --notion-ts <ts>   # safe to run locally?
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
