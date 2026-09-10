# Feedback loop

Slack feedback → validated → GitHub issue → PR → merged → live on the next tick.

The point is that the system improves without you opening an editor, while
staying reviewable and revertable.

---

## Intake

| Signal | Meaning |
|---|---|
| `feedback: <text>` | General feedback |
| 🛠 on any agent message | Feedback about that specific output |
| 🥱 on a chunk or question | *Too basic — never explain this again* |

## Flow

1. **Restate.** Reply in-thread with the interpretation and the concrete change
   proposed. Ambiguous feedback gets a question, not a guess.
2. **Issue.** Label `feedback`. Body carries the verbatim words, the Slack
   permalink, and the proposed change.
3. **PR.** Branch `feedback/<issue>-<slug>`, edit, open a PR closing the issue.
4. **Merge.** Auto-merge if trivial (below), otherwise wait for review.
5. **Reply.** Post issue and PR links, and say whether it auto-merged.

Because every tick begins with `git pull`, a merged change is live immediately.

## 🥱 is different

`assume_known` lives in `profile.local.yaml`, which is **gitignored** — this
repository is public. So 🥱 and `!known` edit that file directly and open no PR.
Confirm in-thread; there is nothing to review.

## Auto-merge — the trivial rule

A PR may auto-merge **only if every condition holds**:

- Touches **only** `prompts/**` or `docs/**`
- ≤ 30 changed lines
- No changes to `scripts/`, `config/`, `tests/`, `.github/`, `.claude/skills/`,
  `reference/question-spec.md`, or `.gitignore`
- Adds no new file
- CI green — **including the privacy gate**
- The issue is labelled `feedback`, not `bug` or `security`

Anything else waits for review. When in doubt, do not auto-merge: the cost of
waiting is a few hours, the cost of a bad unreviewed merge is a system that
silently generates worse questions.

Set `github.auto_merge_trivial: false` in `config.local.yaml` to disable entirely.

## Why the exclusions

| Excluded | Because |
|---|---|
| `scripts/`, `tests/` | The validator and its tests are what make auto-merge safe. Never let the loop weaken its own gate. |
| `reference/question-spec.md` | Measured from real exam questions. Changing it should require re-measuring, not an opinion. |
| `.gitignore` | It is the privacy boundary of a public repository. |
| `config/` | Schedule and identifiers affect behaviour beyond wording. |
| New files | A new file is a new idea, and ideas get read first. |

## Reverting

Every change is one PR closing one issue, so `git revert` plus a Slack note is
the whole rollback. If a digest gets worse after a merge, revert first and
discuss after.
