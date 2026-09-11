---
name: daily-run
description: Orchestrator for the GCP study pipeline. Reads config/schedule.yaml and current state, then advances the pipeline if a step is due, handling any on-demand Slack commands first. Run at the start of a session; nothing fires it automatically.
---

# daily-run

**Scheduled cloud routines drive this.** Five weekday routines call `cloud-run`,
which hydrates state from Notion, runs this skill, and writes state back. The
laptop is no longer required, and no longer the runner — see `docs/decisions.md`.

This reverses a decision that stood until 2026-09-11. The old reasoning was that
everything this needs — `config/config.local.yaml`, `profile.local.yaml`,
`knowledge/`, `state.local/` — is gitignored and stays on the laptop, so a cloud
runner would have nothing to read. What changed is not the privacy design, which
is intact: it is that a cloud session keeps the claude.ai Slack and Notion
connectors, and `docs/privacy.md` already made Notion the durable record. So the
state a run needs can be rehydrated from the place it was already being mirrored
to. Nothing new is committed; `leakcheck.py` is unchanged.

**This skill itself is unchanged by that.** Its due-logic already assumed an
unreliable clock, which is exactly what a routine is.

**Timing still lives in `config/schedule.yaml`, never in a scheduler UI.** It
decides what is *due* when a session runs, which is what makes retuning the day a
one-line edit.

## Order

```
1. git pull                       pick up merged feedback PRs
2. build_ledger.py                what has already been taught and asked
3. on-demand commands             anything asked for since the last run
4. sync-notion                    first run of the day only
5. digest    if due & not posted     (selector may return "nothing new")
6. quiz      if due & digest posted & not posted
7. grade     if due, or ✅ on the quiz parent
8. readiness if due & not posted     (weekly; daily past the threshold)
9. feedback  any unprocessed intake
10. last_run.json                 the watermark, always
11. commit + push                 logic changes only; state stays local
```

Every step is **idempotent and order-guarded**. Re-running must not double-post.
The quiz cannot precede the digest regardless of when a session opens or how the
schedule is edited.

Readiness sits after grading because the day's results are the point of it, and
before feedback because `feedback-sdlc` can merge a PR editing
`prompts/readiness.md` mid-run — a report composed half either side of that is a
bug nobody would ever find. It does **not** wait for grading to have run: mastery
is derived from history, so it reports on whatever results exist. A report that
waits for a perfect input is a report that never posts.

Readiness is also the only step with a cadence of its own — weekly, unless the
score has crossed `readiness.daily_from`. `scripts/due.py` owns that decision so
it can be tested; the hysteresis band in particular reads fine as prose and is
easy to get wrong in practice.

## Is a step due?

**A step fires when its time has passed today and its output is not already in
`state.local/history/<today>/`**, on a day listed in `days`, in `timezone`.

That is the whole rule. Sessions open when the learner opens them, so most runs
land well outside any `grace_minutes` window — under the tick this repo used to
describe, a missed window was the exception; now it is the norm. Gating on the
window would mean a session at 14:00 silently skipping the 12:30 quiz.

`grace_minutes` survives only to label the post: inside the window it is on time,
outside it the message notes the delay. A late digest beats no digest.

## On-demand commands

Read the channel with `slack_read_channel(channel_id, oldest=<watermark>)`, where
the watermark is `state.local/last_run.json` → `ts`. Commands use `!` so ordinary
chat is never mistaken for one.

**Write the watermark at the end of every run**, as
`{"ts": "<newest message ts seen>", "at": "<iso8601>"}`. Without it a session
rescans the whole channel and re-fires a `!quiz` from three days ago. On the first
run, with no file, take only the current day.

| Command | Action |
|---|---|
| `!digest` | Digest now. If today's already went out, advance to the next weakest topics rather than repeating. |
| `!digest <topic\|§>` | Digest scoped to a subsection or topic, resolved against `knowledge/index.json`. |
| `!quiz` | Extra practice set. Never replaces or suppresses the scheduled quiz. |
| `!quiz <topic\|§> [n]` | Scoped, and/or a different question count. |
| `!answers`, `!grade` | Grade the most recent ungraded quiz immediately. |
| `!readiness`, `!status` | Readiness report now — both headline numbers, per-section mastery, coverage, the days estimate. |
| `!known <topic>` | Append to `assume_known`; never explain it again. |
| `!schedule <step> <HH:MM>` | Edit `config/schedule.yaml` and push. |
| `!sync` | Force a Notion re-walk now, ignoring the knowledge cache. |
| `!ask <question>` | Answer a free-form question in-thread, under rules 1–3 like everything else: grounded in ingested material, cited, and refused rather than guessed if the material does not cover it. |
| `!ping` | Last run, next scheduled run, and whether the pipeline is paused. |
| `!pause` / `!resume` | Set or clear `paused` on `🔧 Pipeline State`. Every routine honours it. |
| `!run` | Force a full pass on the next drain, ignoring what looks already done. |
| `!help` | Reprint the pinned command list below. |
| `feedback: <text>` | Run `feedback-sdlc`. |

Reactions are also intake: ✅ on a quiz parent grades it (found via
`quiz.json` → `slack.parent_ts`), 🥱 behaves as `!known` for that topic. 💡 is
retired — it reported on an AWS-analogy thread that no longer exists.

### Control commands

`!pause`, `!resume`, `!ping` and `!run` act on the `control` block of
`🔧 Pipeline State`, so they take effect on the *next* routine rather than the
current one.

**`!resume` and `!ping` are still handled while paused** — `cloud-bootstrap`
scans for those two before it honours the flag. Everything else waits. Without
that exception the release for a pause would sit behind the pause.

**`!pause` is not a bug workaround, it is for a week off.** Left running through
a holiday the pipeline posts five unanswered quizzes, and unanswered is scored as
skipped, which drags mastery down for material never actually seen. `!ping`
reports the paused state precisely so a forgotten `!pause` is legible as a choice
rather than as a dead pipeline.

**`!run` forces one full pass**, ignoring the "already done today" guard. It is
the escape hatch for a step that recorded itself as done and did not post — so it
can double-post by design, and should be offered only when something is visibly
missing, never as a routine retry.

`!ask` answers in-thread from ingested material only. It is subject to rules 1–3
exactly like a digest: no explaining what `assume_known` already covers, no claim
the material does not support, nothing from a ⬜ subsection. **If the material
does not cover it, say so and stop.** It is the command most likely to tempt a
general-knowledge answer, because a question asked directly feels like it
deserves one.

On-demand runs are recorded with `"trigger": "on_demand"` so ad-hoc practice
stays distinguishable from scheduled work in the history.

## The pinned help message

`#gcp-security-exam` carries this as a pinned message, and `!help` reprints it
verbatim. Keep the two identical — if the command table above changes, repost it.

```
How to drive this channel

!digest              digest now
!digest <topic|§>    digest scoped to one subsection
!quiz [topic] [n]    extra practice set
!answers / !grade    grade the latest quiz
!status              readiness report
!ask <question>      answered from the material, cited
!known <topic>       never explain it again
!schedule <step> <HH:MM>
!sync                re-read Notion now
!ping                last run, next run, paused?
!pause / !resume     stop and restart the schedule
feedback: <text>     files an issue and a PR
!help                this message

Reactions: 1️⃣–4️⃣ answer a question · ✅ on a quiz parent grades it ·
🥱 marks a question too basic.

Commands are picked up by the next run — hourly on weekdays, so within the hour.
The laptop does not need to be on. For an instant answer, open a Claude Code
session from your phone and say "digest" or "grade it".
```

## Latency, stated honestly

A `!` command is now a real trigger, not a note to self. The hourly weekday drain
picks it up, so the honest promise is **within the hour** — not instant.

Say that, and do not round it up to "live". The instant route still exists and is
now also on the phone: open a Claude Code session against this repo and say
"digest", "quiz me on VPC Service Controls", "grade it". Same connectors, same
state, no waiting for the next drain.

Outside the drain's weekday hours a command waits for the next one. `!ping`
answers "did it get picked up?" without guessing.

## Before writing anything

```bash
.venv/bin/python scripts/build_ledger.py   # refresh what has been said
.venv/bin/python scripts/build_mastery.py  # refresh what is actually known
.venv/bin/python scripts/validate.py       # content + repetition gate
.venv/bin/python scripts/leakcheck.py      # privacy gate, before any commit
```

The ledger is derived from posted history, so rebuild it **before** validating —
otherwise the repetition checks compare against a stale picture.

Never commit `state.local/`, `knowledge/`, or `profile.local.yaml`. This
repository is public.
