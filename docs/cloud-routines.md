# Running this from a phone

Five scheduled Claude Code routines drive the pipeline. They live in your Claude
account, not in this repo — nothing here can create them, which is why this file
exists.

Background and the reasoning behind the switch: `docs/decisions.md`, *"A cloud
runner can fix it — connectors are the reason"*.

---

## One-time setup

### 1. Create the Notion state pages

Under the same root as `📊 Quiz Results` and `📖 Daily Digests`:

| Page | Holds |
|---|---|
| `🔧 Pipeline State` | `config`, `watermark`, `sources`, `control` and `readiness` blocks |
| `👤 Learner Profile` | `profile.local.yaml` |
| `📚 Exam Samples` | `reference/exemplars/official-samples.md` |

Exact layout and block names: `.claude/skills/cloud-bootstrap/SKILL.md`.

**The titles are the bootstrap.** A run finds `🔧 Pipeline State` by searching for
it by name, which is what avoids needing a page id in an environment variable. So
there must be exactly one page with that title — a duplicate is a split-brain
state store, and `cloud-bootstrap` stops rather than guessing between them.

### 2. Migrate the current local state

From a session on the laptop, once:

- Copy `config/config.local.yaml` and `profile.local.yaml` into their pages.
- Copy `knowledge/sources.local.json` into `sources`, **`ingested_on` stamps
  intact**. Do not regenerate it — those stamps are written once and never
  rewritten, and a fresh walk would reset every one to today.
- **Backfill `message_ts` for any quiz that is still ungraded.** Put the verbatim
  `state.local/history/<date>/quiz.json` into a `state` toggle on that day's
  `📊 Quiz Results` row. Without it the first cloud run inherits a quiz it can
  never grade, because the reactions sit on messages it has no handle for.
- Backfill `digest.json` and `results.json` the same way for the days already in
  `state.local/history/`.
- Seed `control` as `{"paused": false, "force_full": false}`.

### 3. Prove the sandbox before trusting it

Open a cloud session from the phone against this repo and check the three things
the docs do not promise:

```bash
which chromium chromium-browser google-chrome chrome-headless-shell
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m unittest discover -s tests
```

Then publish an Artifact and republish it, confirming the URL is stable — that is
how the readiness dashboard keeps one bookmarkable address.

If no browser exists, nothing here breaks: digests post text-only and say so.
Better to know before the first 07:15.

### 4. Create the routines

At `claude.ai/code/routines` — this works in mobile Safari, though the mobile app
itself has no routine-creation screen. Each one is the same:

- **Repository**: this repo
- **Prompt**: `/cloud-run`
- **Connectors**: **Slack and Notion only** — see the warning below
- **Schedule**: weekdays, at the times below

| Routine | London | Fires |
|---|---|---|
| `gcp-digest` | 07:15 | the digest |
| `gcp-quiz` | 12:30 | the quiz |
| `gcp-grade` | 20:45 | grading |
| `gcp-readiness` | 21:15 | readiness, on its own cadence |
| `gcp-drain` | hourly, 08:00–22:00 | `!` commands and ✅ reactions |

Routine times are entered in local time and stored as UTC, so **the London times
above shift by an hour at the BST boundary if the form pins UTC** — check each
March and October, or accept that a digest lands at 06:15 or 08:15 for a fortnight.
`config/schedule.yaml` is unaffected: it is timezone-aware and remains the rule
for what is *due*.

### 5. Repost the pinned Slack message

The pinned message in `#gcp-security-exam` still says *"Nothing here is live."*
That is now false. The replacement text is in `daily-run/SKILL.md`; `!help`
reprints it, and the two must stay identical.

---

## Why Slack and Notion only

A routine **auto-approves every tool from every connector it includes**, writes as
well as reads, with no prompt at any point. A routine carrying Drive or Gmail is
granting an unattended agent write access to a mailbox for no reason.

This is the one genuinely new trust decision in the switch. It is worth making on
purpose rather than by accepting a default that includes everything connected.

---

## When something goes wrong

`cloud-run` posts failures to Slack, naming the step and what state was left
behind. That is deliberate and not decoration: the last scheduled trigger this
pipeline had **silently did nothing for a day** and was noticed only when a ✅ went
unanswered. A runner that dies quietly is worse than no runner, because it also
looks fine.

| Symptom | Check |
|---|---|
| Nothing posted, no error | `!ping` — a forgotten `!pause` looks exactly like a dead pipeline |
| Quiz posted but never graded | `state` toggle missing on that `📊 Quiz Results` row |
| Digest repeated material | hydration read stale or partial history; check the `state` toggles exist for recent days |
| Every run re-walks Notion | `control.synced_on` is not being written by `dehydrate` |

Run nothing from the laptop while diagnosing without checking first:

```bash
.venv/bin/python scripts/runner_guard.py --notion-ts <watermark from Notion>
```

Two runners on one state is how a day gets double-posted.

---

## On-demand, from anywhere

- **Within the hour**: type `!digest`, `!quiz`, `!ask …` in Slack. The drain picks
  it up. The laptop does not need to be on.
- **Instantly**: open a Claude Code session from the phone's Code tab and say
  "digest" or "grade it". Same repo, same connectors, no waiting.

`!pause` before a holiday. Left running, the pipeline posts five unanswered
quizzes a week, and unanswered scores as skipped — which drags mastery down for
material never actually seen.
