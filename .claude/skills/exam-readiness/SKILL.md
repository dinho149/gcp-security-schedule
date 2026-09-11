---
name: exam-readiness
description: Compute and post the exam readiness report to Slack — both headline numbers, the per-section breakdown, and a days-to-ready estimate — and republish the dashboard. Runs when readiness is due (weekly, or daily past the threshold), or on !readiness / !status.
---

# exam-readiness

Follow `prompts/readiness.md` for wording. This file covers mechanics.

The report answers one question — *would I pass, and when?* — and it has to
answer it twice, because there is only one honest way to say it:

| Number | Means | Ceiling |
|---|---|---|
| **True exam readiness** | of the whole exam, how much is solid | the coverage ceiling |
| **On covered material** | of what the training has taught, how much is solid | 100% |

**Never post the first without the second.** Alone, the second says "you are at
78%" about an exam that is 39% untested — `CLAUDE.md` rule 2, asserted about the
learner instead of about GCP.

## Build the numbers

```bash
.venv/bin/python scripts/build_ledger.py      # what has been taught and asked
.venv/bin/python scripts/build_mastery.py     # per-topic mastery, from results
.venv/bin/python scripts/build_readiness.py   # -> state.local/readiness.json
```

All three are **derived, never authored**: they rebuild from
`state.local/history/`, so they cannot drift from what was actually posted, and
deleting one costs nothing. Order matters — readiness reads mastery, mastery
reads outcomes.

You compute nothing yourself. Read `state.local/readiness.json` and report it.
If a number looks wrong, fix the script, not the message.

## Is it due?

```bash
.venv/bin/python scripts/due.py readiness      # exit 0 = run, 1 = skip; prints why
```

The rule it implements, from `config/schedule.yaml` → `readiness`:

- **Weekly** on `readiness.days`, at `at`, within `grace_minutes`.
- **Daily** on every run day once the covered score reaches `daily_from` — near
  the exam the number moves fast enough to watch; far from it a daily report is
  noise on an unchanged figure.
- Back to weekly only after it falls `daily_hysteresis` below that. Without the
  band a score sitting on the line flips cadence every day, which reads as
  instability in the score rather than in the rule.
- **Never twice in a day.** `state.local/history/<today>/readiness.json` existing
  is the guard, exactly as `digest.json` is for the digest.

It reads the *last* computed score, so deciding whether to run never depends on
the run it is deciding about.

## On demand

`!readiness` and `!status` skip the schedule, not the data check.

- Nothing graded since today's report → **reply in its thread** with what the
  numbers still are and when the next quiz changes them. A second identical
  top-level report is noise.
- A quiz graded since → a fresh top-level report, `"trigger": "on_demand"`.

`!status` is this command. It was in the table for a long time promising
"streak, per-section mastery, what is due, coverage", and every one of those is
a strict subset of this report — two commands rendering the same state is how a
report drifts from the number it reports.

## Post — parent, then one thread reply

Threads are flat (`docs/decisions.md`), so this is the whole hierarchy available,
and keeping the top level to one message leaves it collapsible.

1. **Parent** — both headlines, five section rows, the estimate, the evidence
   line. Skimmable in 60 seconds; that is the constraint.
2. **Thread reply** — the method, what is stale, and the two or three things
   that would actually move the number.

Slack has no table renderer, so pipes come out literal. Use the colour squares
and aligned rows. Bars are bare `▓░` and **not** in backticks — they are already
fixed-width, and `monospace` is reserved for things to recall exactly.

## Republish the dashboard

```bash
.venv/bin/python scripts/build_dashboard.py    # -> dashboard/readiness.generated.html
```

Publish it with the **Artifact** tool, passing `url` from `config.local.yaml` →
`dashboard.url` so every republish lands on the same bookmarkable page. On a
first publish, write the returned URL back into that file. Link it from the
parent message.

The page is private by default and its URL lives only in the gitignored config.
It carries a per-section competence profile — see `docs/privacy.md`.

## Record, prove, then post

Write `state.local/history/<date>/readiness.json` **before** posting:

```json
{
  "date": "2026-10-09", "trigger": "scheduled", "cadence": "weekly",
  "source": {"true": 0.48, "on_covered": 0.78, "reachable": 0.61,
             "too_early": false, "target": 0.75},
  "posted": {"headline_true": 48, "headline_covered": 78, "days_estimate": 24,
             "confidence": "medium", "too_early": false,
             "sections": {"1": 82, "2": 71, "3": 58, "4": null, "5": 64}},
  "slack": {"channel_id": "...", "parent_ts": null, "detail_ts": null}
}
```

```bash
.venv/bin/python scripts/validate.py state.local/history/<date>/readiness.json
```

**Post only when it exits zero**, the same rule the quiz follows. The gate does
not re-derive the arithmetic — that would be one script re-asserting another.
It checks the *transcription*: that both headlines are present, that each matches
what the script computed, that readiness never exceeds its ceiling, and that no
days estimate rides along with "still too early to decide". A report that drifts
from its own file looks exactly like a correct one to a reader, which is why it
is checked mechanically rather than by rereading.

Then post, and patch the `ts` values back in.

## No Notion write — but one marker

Unlike the digest and the quiz, readiness gets no Notion database. It is a pure
function of `📊 Quiz Results`, which is already the durable record — a second
copy would put another competence profile in the workspace and buy nothing a
rerun does not.

That still holds. But a cloud run discards `state.local/` when it ends, so append
**one line** to the `readiness` block on `🔧 Pipeline State`: date, `on_covered`,
the cadence just used, and `too_early`. Use `on_covered` as the key name, matching
what `due.py` reads out of `source` — a renamed key is a silently broken hysteresis
band. Not the report — the report is recomputed, and
`build_readiness.series()` replays mastery per graded day to do it.

Two things genuinely cannot be recomputed, and both are one number wide. `due.py`
applies a hysteresis band against the *last* report's score and whether it was
daily, so that a score sitting on the line does not flip the cadence every day —
which means it needs the previous decision, not the previous report. And the
marker is what stops a second run the same day posting the report again.

A line per run, no section breakdown. The moment it carries per-section numbers
it has become the second competence profile this section exists to refuse.
