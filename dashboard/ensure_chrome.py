#!/usr/bin/env python3
"""Find a headless-Chrome binary for the digest renderer, on any machine.

    .venv/bin/python dashboard/ensure_chrome.py [--probe-only|--install] [--json]

Prints the resolved path on stdout and exits 0; exits 1 with a reason naming
every location tried.

Why this is a script and not two lines in render.py: the laptop has Chrome at a
known macOS path, and the cloud sandbox has no browser on PATH at all. The old
probe was a bare `which` over four names in cloud-bootstrap's prose, which asked
only "is a browser already here?" and answered it badly -- it misses a browser
sitting in a puppeteer cache, under /opt, or in /snap, and it treats absence as
permanent when a 90-second download would fix it.

Resolution is LAZY -- render.py calls it, so only the digest pays. The quiz,
grading and readiness routines never render a PNG and must never wait for a
browser to download.

A sandbox is discarded after each run, so an installed binary does not persist.
That is a per-digest-run cost by design, not a bug to cache around: what is worth
caching is the *negative* and the *winning method*, which cloud-bootstrap keeps in
Notion's `control.render_probe`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Names a packaged browser goes by, best first. chrome-headless-shell is the
# screenshot-only build -- the only thing render.py actually drives.
BINARY_NAMES = ("chrome-headless-shell", "chromium", "chromium-browser",
                "google-chrome", "google-chrome-stable")

# Places a browser lives when it is not on PATH. Globs are expanded in order and
# each match sorted, so a newer pinned revision wins over an older one.
SEARCH_GLOBS = (
    "~/.cache/puppeteer/chrome-headless-shell/*/*/chrome-headless-shell",
    "~/.cache/puppeteer/chrome/*/*/chrome",
    "~/.cache/ms-playwright/chromium_headless_shell-*/chrome-linux/headless_shell",
    "~/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
    "/opt/google/chrome/chrome",
    "/usr/lib/chromium/chromium",
    "/usr/lib/chromium-browser/chromium-browser",
    "/snap/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)

INSTALL_TIMEOUT = 300  # a cold fetch is ~200 MB; the 07:15 digest can afford it

# Where a fetched browser goes. Never the working directory -- see
# _install_puppeteer. Honours XDG so a sandbox can redirect it.
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "puppeteer"


class Resolved:
    """What the resolver found, and how. `via` is what cloud-bootstrap caches."""

    def __init__(self, path: str, via: str, tried: list[str]):
        self.path, self.via, self.tried = path, via, tried

    def as_dict(self) -> dict:
        return {"path": self.path, "via": self.via, "tried": self.tried}


def _render_config() -> dict:
    cfg = ROOT / "config/config.local.yaml"
    if not cfg.exists():
        return {}
    try:
        import yaml
        data = yaml.safe_load(cfg.read_text()) or {}
        return (data.get("render") or {})
    except Exception:
        return {}


def _configured() -> str | None:
    return _render_config().get("chrome_path") or None


def install_default() -> bool:
    """Whether to download a browser when none is found.

    `render.install` in config wins if set. Otherwise: on everywhere but macOS,
    where a laptop already has Chrome and the fetch would be dead weight.
    """
    configured = _render_config().get("install")
    if isinstance(configured, bool):
        return configured
    return sys.platform != "darwin"


def _executable(p: str | Path) -> bool:
    p = Path(p)
    return p.is_file() and os.access(p, os.X_OK)


def _newest_first(paths):
    """Sort by version, digit-runs numerically.

    Browser caches are keyed by revision (`131.0.6778.204`), and a plain string
    sort puts 99.x above 131.x -- picking a years-old build over the one just
    installed.
    """
    def key(p: Path):
        return [int(t) if t.isdigit() else t
                for t in re.split(r"(\d+)", str(p))]
    return sorted(paths, key=key, reverse=True)


def _from_globs() -> tuple[str | None, list[str]]:
    tried = []
    for pattern in SEARCH_GLOBS:
        tried.append(pattern)
        if pattern.startswith("~"):
            base, _, tail = pattern.partition("/")
            matches = _newest_first(Path(base).expanduser().glob(tail))
        elif "*" in pattern:
            matches = _newest_first(Path("/").glob(pattern.lstrip("/")))
        else:
            matches = [Path(pattern)]
        for m in matches:
            if _executable(m):
                return str(m), tried
    return None, tried


def _runnable(path: str) -> bool:
    """Does this binary actually start?

    `_executable` only asks whether the file bit is set. A downloaded browser on
    a minimal Linux image is executable and still dead:

        error while loading shared libraries: libglib-2.0.so.0

    Without this check `resolve()` returns that path, reports success, and
    render.py then fails once per visual with "chrome wrote no file" -- which
    daily-digest reads as a clipping bug (exit 1, fix your specs) rather than
    the missing renderer it is (exit 2, post text-only). Measured in a Debian
    container, not hypothesised.
    """
    try:
        p = subprocess.run([path, "--version"], capture_output=True,
                           text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return p.returncode == 0 and "error while loading shared libraries" not in (
        (p.stderr or "") + (p.stdout or ""))


def _run(cmd: list[str]) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=INSTALL_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None


def _ok(proc: subprocess.CompletedProcess | None) -> bool:
    """A CompletedProcess is truthy even when the command failed."""
    return proc is not None and proc.returncode == 0


def _install_puppeteer() -> str | None:
    """Fetch chrome-headless-shell. Prints `chrome-headless-shell@<rev> <path>`.

    `--path` is not optional. Without it @puppeteer/browsers installs into the
    CURRENT WORKING DIRECTORY -- which, for a run started at the repo root, means
    195 MB of browser dropped into a public git repo as untracked files. Measured,
    not guessed.
    """
    if not shutil.which("npx"):
        return None
    proc = _run(["npx", "-y", "@puppeteer/browsers", "install",
                 "chrome-headless-shell@stable", "--path", str(CACHE_DIR)])
    if not _ok(proc):
        return None
    # Format is `<name>@<version> <path>`. Split once from the left rather than
    # taking the last token: an install path may legitimately contain spaces.
    for line in reversed((proc.stdout or "").strip().splitlines()):
        _, _, candidate = line.strip().partition(" ")
        if candidate and _executable(candidate):
            return candidate
    return None


def _install_playwright() -> str | None:
    """Fallback when the sandbox has Python but no node."""
    if not _ok(_run([sys.executable, "-m", "pip", "install", "--quiet", "playwright"])):
        return None
    # --with-deps apt-installs the shared libraries the browser needs. It wants
    # root, which a sandbox has and a laptop does not, so fall back to the plain
    # install rather than failing outright.
    for args in (["install", "--with-deps", "chromium-headless-shell"],
                 ["install", "chromium-headless-shell"],
                 ["install", "chromium"]):
        if _ok(_run([sys.executable, "-m", "playwright", *args])):
            found, _ = _from_globs()
            if found:
                return found
    return None


def resolve(install: bool = False, prefer: str | None = None,
            verify: bool = True) -> Resolved:
    """First hit wins. Raises RuntimeError naming everything tried.

    A candidate must both exist and *start*; see `_runnable`. A browser that
    cannot load its shared libraries is not a browser, and saying so here is
    what keeps the digest's text-only fallback reachable.
    """
    tried: list[str] = []

    def accept(path: str, via: str) -> Resolved | None:
        if verify and not _runnable(path):
            tried.append(f"  ^ found but will not start (missing libraries?)")
            return None
        return Resolved(path, via, tried)

    if (p := _configured()):
        tried.append(f"config render.chrome_path ({p})")
        if _executable(p) and (r := accept(p, "config")):
            return r

    for name in BINARY_NAMES:
        tried.append(f"PATH: {name}")
        if (p := shutil.which(name)) and (r := accept(p, "path")):
            return r

    found, glob_tried = _from_globs()
    tried += glob_tried
    if found and (r := accept(found, "glob")):
        return r

    if install:
        # `prefer` lets cloud-bootstrap skip straight to the installer that won
        # last time instead of re-walking a route it already knows fails.
        installers = [("npx-puppeteer", _install_puppeteer),
                      ("pip-playwright", _install_playwright)]
        if prefer:
            installers.sort(key=lambda kv: kv[0] != prefer)
        for via, fn in installers:
            tried.append(f"install: {via}")
            if (p := fn()) and (r := accept(p, via)):
                return r

    raise RuntimeError(
        "no headless-Chrome binary found. Tried:\n  " + "\n  ".join(tried)
        + ("" if install else "\n  (install not attempted; pass --install)"))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--install", action="store_true",
                   help="download a browser if none is present (~100 MB)")
    g.add_argument("--probe-only", action="store_true",
                   help="never download; just report what is here")
    ap.add_argument("--prefer", help="installer to try first (from a cached probe)")
    ap.add_argument("--json", action="store_true", help="machine-readable result")
    args = ap.parse_args(argv)

    try:
        r = resolve(install=args.install, prefer=args.prefer)
    except RuntimeError as e:
        if args.json:
            print(json.dumps({"path": None, "via": "unavailable",
                              "reason": str(e)}))
        else:
            print(e, file=sys.stderr)
        return 1

    print(json.dumps(r.as_dict()) if args.json else r.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
