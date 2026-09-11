---
name: cloud-run
description: Entrypoint for a scheduled cloud routine. Hydrates state from Notion, runs daily-run, writes state back, and reports any failure to Slack. This is what the routines invoke; on the laptop, run daily-run directly instead.
---

# cloud-run

The routine entrypoint. Everything a scheduled run does, in the order it does it:

```
1. cloud-bootstrap  hydrate      state from Notion; honours the pause flag
2. daily-run                     unchanged — decides what is due and does it
3. cloud-bootstrap  dehydrate    changed state back to Notion
4. on any failure                post it to Slack
```

`daily-run` is not modified for the cloud. Its rule — *a step fires when its time
has passed today and its output is not already in `state.local/history/<today>/`*
— already assumes an unreliable clock, which is exactly what a routine is. Five
routines a day all calling this is not five decisions; it is the same decision
asked five times, and answered idempotently.

## Failure must be loud

**Wrap the whole run. If any step raises, post to Slack before exiting**, naming
the step, the error, and what state was left behind:

```
⚠️ Cloud run failed at <step> — <error>
Nothing was posted. State in Notion is unchanged. Next run: <time>.
```

This is not defensive decoration. Routines send no completion notification, and
the last time this pipeline had a scheduled trigger it *silently did nothing for
a day* and was found only when the learner asked why ✅ had done nothing
(`docs/decisions.md`, "The tick was never built"). A cloud runner that dies
quietly is strictly worse than no cloud runner, because it also looks fine.

If Slack itself is what failed, there is nowhere to report to — exit non-zero and
let the routine's own run history carry it.

## Pause

`hydrate` reads the `control` block first. If `paused` is true it handles
`!resume` and `!ping` and nothing else — post nothing, write nothing, exit clean.

**`!resume` must stay reachable while paused**, because it is itself an on-demand
command handled by `daily-run`, which runs inside the step the pause stops.
A pause that also disables its own release can only be undone from a session,
which defeats the point of driving this from a phone.

`!pause` exists so a week off does not generate five days of unanswered quizzes
that then drag the mastery scores down for having been skipped.

`!resume` clears it. `!ping` reports it, so a forgotten pause is visible rather
than looking like a broken pipeline.

## Which routine is which

All five routines invoke this skill with no arguments and let the due-logic
choose. The times exist to bound latency, not to select the step:

| Routine | Weekday time | What normally fires |
|---|---|---|
| digest | 07:15 | digest |
| quiz | 12:30 | quiz |
| grade | 20:45 | grading |
| readiness | 21:15 | readiness, on its own cadence |
| drain | hourly | on-demand `!` commands and ✅ reactions |

The drain is separate because routine cron granularity bottoms out at one hour,
so the scheduled steps cannot be expressed as a single frequent tick. It also
means a `!quiz` typed on a train is answered within the hour without anyone
opening anything.

**For an instant answer, open a cloud session from the phone** and say
"daily-run". Same repo, same connectors, no waiting for the next drain.

## Connectors

Scope the routine to **Slack and Notion only**. A routine auto-approves every
tool from every connector it includes, writes as well as reads, with no prompt —
so the ones it does not need should not be there.

## Time

The sandbox is UTC; `config/schedule.yaml` is `Europe/London`. Every due-ness
comparison goes through the configured timezone, never the container's clock.
This matters twice a year and is invisible the rest of the time: in BST a 07:15
London digest is a 06:15 UTC routine.
