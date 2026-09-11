#!/usr/bin/env python3
"""Fail if anything personal, employer-specific or third-party is tracked by git.

THIS REPOSITORY IS PUBLIC. This is the highest-consequence check in the suite,
so it runs on every PR — including the ones the feedback loop auto-merges.

Two layers:

  Structural (always, including CI where profile.local.yaml is absent)
    - no *.local.* files tracked
    - no state.local/, knowledge/, reference/exemplars/ tracked
    - no generic secrets (API keys, tokens, private keys, emails, phone numbers)

  Content (only when profile.local.yaml is present, i.e. locally / pre-push)
    - none of the *values* from the local profile appear in tracked files
    - derived from the profile itself, so the sensitive strings are never
      hard-coded into this committed script

    .venv/bin/python scripts/leakcheck.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_PATHS = [
    (re.compile(r"\.local\.(yaml|json|md)$"), "*.local.* files hold personal config"),
    (re.compile(r"^state\.local/"), "quiz results and mastery scores"),
    (re.compile(r"^knowledge/"), "derived from a private Notion workspace"),
    (re.compile(r"^reference/exemplars/"), "Google's sample questions — not ours to republish"),
    (re.compile(r"^profile\."), "learner profile"),
]

GENERIC_SECRETS = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "email address"),
    (re.compile(r"\b(?:\+44|0)7\d{9}\b"), "UK mobile number"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (re.compile(r"\bsecret_[A-Za-z0-9]{32,}"), "Notion integration token"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key"),
    # A 32-hex Notion page id identifies a page in a private workspace. Harmless
    # on its own -- the page is still ACL'd -- but it describes private structure,
    # and .gitignore excludes knowledge/ for exactly that reason. Committed code
    # must read ids from the gitignored ingestion map, never hard-code them.
    (re.compile(r"\b[0-9a-f]{32}\b"), "Notion page id"),
    # Slack workspace object ids -- users (U), channels (C), groups (G), DMs (D).
    # There were patterns for Slack *tokens* but none for these, so a real user
    # id sat in a tracked skill file on a public remote from 3f52aa2 until it was
    # found by an audit rather than by this gate. An id grants nothing without
    # workspace access, but it names a real person's account: same boundary as
    # the Notion page ids above, and the same rule -- read them from the
    # gitignored config, never write them into committed prose.
    # The negative lookbehind keeps Python's own escapes out of it: "\\U0001F300"
    # in a character class is U, 0, then seven uppercase hex, and matched every
    # time. A gate that cries wolf gets ignored -- see docs/decisions.md. A real
    # id is never written behind a backslash.
    (re.compile(r"(?<!\\)\b[UCGD]0[A-Z0-9]{7,}\b"), "Slack workspace id"),
]

# Placeholder ids in *.example.* files are documentation, not real pages or
# accounts. Applies to every id-shaped pattern, not just Notion's.
ID_ALLOW_PATHS = re.compile(r"(^|/)[^/]*\.example\.[a-z]+$|^docs/|^reference/question-spec\.md$")
ID_LABELS = {"Notion page id", "Slack workspace id"}

# Emails that are fine in a public repo: the git noreply address, documentation
# placeholders, and Google service-account addresses (which are resource
# identifiers in examples, not contact details).
EMAIL_ALLOW = re.compile(
    r"users\.noreply\.github\.com$"
    r"|@company\.com\b"
    r"|@example\.(com|org)\b"
    r"|\.iam\.gserviceaccount\.com\b"
    r"|@(proj|project|my-project)\."
)

MIN_PHRASE = 12  # shorter phrases produce false positives, not signal


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [ln for ln in out.splitlines() if ln.strip()]


def profile_needles() -> list[tuple[str, str]]:
    """Sensitive strings to search for, derived from the gitignored local profile.

    Whole phrases only, plus explicitly declared sensitive terms. An earlier
    version also split phrases into individual words; that flagged "Engineer" in
    the exam title and "rules" in .gitignore. A check that cries wolf gets
    ignored, which is worse than no check at all.
    """
    profile = ROOT / "profile.local.yaml"
    if not profile.exists():
        return []
    try:
        import yaml
    except ModuleNotFoundError:
        return []

    data = yaml.safe_load(profile.read_text()) or {}
    needles: list[tuple[str, str]] = []

    # Explicitly declared — matched regardless of length.
    for term in data.get("sensitive_terms") or []:
        needles.append((str(term), "sensitive_terms"))

    ident = data.get("identity", {})
    for key in ("name", "role", "context"):
        val = str(ident.get(key, ""))
        if len(val) >= MIN_PHRASE:
            needles.append((val, f"identity.{key}"))

    # Anchor VALUES are employer-specific narrative. Anchor KEYS are public
    # GCP service names and must NOT be flagged.
    for gcp, anchor in (data.get("anchors") or {}).items():
        val = str(anchor)
        if len(val) >= MIN_PHRASE:
            needles.append((val, f"anchors[{gcp}]"))

    return sorted(set(needles), key=lambda x: -len(x[0]))


def main() -> int:
    failures: list[str] = []
    files = tracked_files()

    for path in files:
        for pattern, why in FORBIDDEN_PATHS:
            if pattern.search(path):
                failures.append(f"TRACKED FILE  {path}\n              -> {why}")

    needles = profile_needles()
    content_mode = "content+structural" if needles else "structural only (no local profile)"

    for path in files:
        f = ROOT / path
        if not f.is_file():
            continue
        try:
            text = f.read_text()
        except (UnicodeDecodeError, OSError):
            continue

        for pattern, label in GENERIC_SECRETS:
            for m in pattern.finditer(text):
                if label == "email address" and EMAIL_ALLOW.search(m.group(0)):
                    continue
                if label in ID_LABELS and ID_ALLOW_PATHS.search(path):
                    continue
                line = text[: m.start()].count("\n") + 1
                failures.append(f"SECRET        {path}:{line}\n              -> {label}")

        low = text.lower()
        seen: set[str] = set()
        for needle, origin in needles:
            idx = low.find(needle.lower())
            if idx != -1 and origin not in seen:
                seen.add(origin)
                line = text[:idx].count("\n") + 1
                failures.append(
                    f"PROFILE LEAK  {path}:{line}\n"
                    f"              -> value from {origin} appears in a tracked file"
                )

    print(f"leakcheck: {len(files)} tracked files, mode = {content_mode}")
    if failures:
        print(f"\n{len(failures)} problem(s):\n", file=sys.stderr)
        for f in failures:
            print(f"  {f}\n", file=sys.stderr)
        print("This repository is PUBLIC. Fix before pushing.", file=sys.stderr)
        return 1
    print("leakcheck: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
