#!/usr/bin/env bash
# Install the pre-commit privacy gate.
#
#   ./scripts/install-hooks.sh
#
# This repository is PUBLIC. scripts/leakcheck.py is meant to run before every
# commit, but "meant to" is not enforcement -- a commit once landed with a
# failing gate simply because the check and the commit were separate commands.
# Git hooks are not versioned, so this installs it.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
hook="$root/.git/hooks/pre-commit"

cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
py="$root/.venv/bin/python"
[ -x "$py" ] || py=python3

if ! "$py" "$root/scripts/leakcheck.py"; then
  echo
  echo "pre-commit: privacy gate FAILED — commit aborted."
  echo "This repository is public. Fix the finding, or --no-verify if it is a"
  echo "false positive you have actually checked."
  exit 1
fi
HOOK

chmod +x "$hook"
echo "installed: .git/hooks/pre-commit -> leakcheck"
