---
name: daily-run
description: Tick orchestrator for the GCP study pipeline. Reads config/schedule.yaml and current state, then advances the pipeline one step if due, and handles any on-demand Slack commands first. Invoked by the scheduled task.
---

# daily-run

One scheduled task ticks; this decides what actually happens. **Timing lives in
`config/schedule.yaml`, never in a scheduler UI** — so retuning the day is a
one-line edit that takes effect on the next tick.

## Order

```
1. git pull                       pick up merged feedback PRs
2. build_ledger.py                what has already been taught and asked
3. on-demand commands             anything the learner asked for since last tick
4. sync-notion                    first tick of the day only
5. digest    if due & not posted     (selector may return "nothing new")
6. quiz      if due & digest posted & not posted
7. grade     if due, or ✅ on the quiz parent
8. feedback  any unprocessed intake
9. commit + push                  logic changes only; state stays local
```

Every step is **idempotent and order-guarded**. Re-running a tick must not
double-post. The quiz cannot precede the digest regardless of when ticks fire or
how the schedule is edited.

## Is a step due?

A step fires when `now >= <step>_at` and `now < <step>_at + grace_minutes`, on a
day listed in `days`, in `timezone` — and its output does not already exist in
`state.local/history/<today>/`.

If a step's window was missed entirely (laptop asleep, task paused), fire it on
the next tick anyway and note the delay. A late digest beats no digest.

## On-demand commands

Read the channel for messages since the last tick. Commands use `!` so ordinary
chat is never mistaken for one.

| Command | Action |
|---|---|
| `!digest` | Digest now. If today's already went out, advance to the next weakest topics rather than repeating. |
| `!digest <topic\|§>` | Digest scoped to a subsection or topic, resolved against `knowledge/index.json`. |
| `!quiz` | Extra practice set. Never replaces or suppresses the scheduled quiz. |
| `!quiz <topic\|§> [n]` | Scoped, and/or a different question count. |
| `!answers`, `!grade` | Grade the most recent ungraded quiz immediately. |
| `!status` | Streak, per-section mastery, what is due, coverage. |
| `!known <topic>` | Append to `assume_known`; never explain it again. |
| `!schedule <step> <HH:MM>` | Edit `config/schedule.yaml` and push. |
| `feedback: <text>` | Run `feedback-sdlc`. |

Reactions are also intake: ✅ on a quiz parent grades early, 💡 records hint use,
🥱 behaves as `!known` for that topic.

On-demand runs are recorded with `"trigger": "on_demand"` so ad-hoc practice
stays distinguishable from scheduled work in the history.

## Zero-latency path

A session is the instant route: open this repo and say "digest", "quiz me on
VPC Service Controls", "grade it". Same skills, same state, no tick to wait for.

## Before writing anything

```bash
.venv/bin/python scripts/build_ledger.py   # refresh what has been said
.venv/bin/python scripts/validate.py       # content + repetition gate
.venv/bin/python scripts/leakcheck.py      # privacy gate, before any commit
```

The ledger is derived from posted history, so rebuild it **before** validating —
otherwise the repetition checks compare against a stale picture.

Never commit `state.local/`, `knowledge/`, or `profile.local.yaml`. This
repository is public.
