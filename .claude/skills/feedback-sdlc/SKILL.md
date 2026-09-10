---
name: feedback-sdlc
description: Turn Slack feedback into a validated GitHub issue and PR, auto-merging only trivial prompt or docs changes. Handles the 🥱 too-basic signal by editing the local profile instead. Runs on feedback intake.
---

# feedback-sdlc

Rules live in `docs/feedback-sdlc.md`. This file is the procedure.

## 1. Classify

| Signal | Route |
|---|---|
| 🥱 or `!known <topic>` | Append to `profile.local.yaml` → `assume_known.retired`. **No PR** — that file is gitignored. Confirm in-thread and stop. |
| `feedback:` or 🛠 | Continue below |

## 2. Validate before acting

Reply in-thread with the interpretation and the concrete change proposed. If the
feedback could mean two different changes, **ask** — a wrong guess costs a PR
and erodes trust in the loop.

Feedback about *content being wrong* is different from *style*: check it against
`knowledge/index.json` first. If the material genuinely says what the digest
said, reply with the citation rather than opening a PR.

## 3. Issue then PR

```bash
gh issue create --label feedback --title "<short>" --body "<verbatim + permalink + proposal>"
git checkout -b feedback/<issue>-<slug>
# edit prompts/** or docs/**
.venv/bin/python scripts/validate.py
.venv/bin/python scripts/leakcheck.py
gh pr create --title "<short>" --body "Closes #<issue>"
```

**Never paste the learner's message into a tracked file.** The issue body is on
GitHub, which is fine; a tracked file is not. Run `leakcheck.py` before pushing —
Slack feedback can easily contain employer detail.

## 4. Auto-merge check

Apply `docs/feedback-sdlc.md` → *the trivial rule*, all conditions. Print which
condition failed if declining, so the decision is auditable.

Never auto-merge a change to `scripts/`, `tests/`, `reference/question-spec.md`,
`config/`, `.claude/skills/` or `.gitignore` — those are what make auto-merge
safe in the first place.

## 5. Reply

Issue link, PR link, and whether it merged or awaits review. If it awaits review,
say which condition held it back.

## 6. Live

The next tick's `git pull` picks it up. Mark the intake processed so it is not
handled twice.
