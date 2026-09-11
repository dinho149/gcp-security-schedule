#!/usr/bin/env python3
"""Tests for the headless-Chrome resolver.

The failure that matters is a cloud digest silently losing its diagrams because
the probe did not look hard enough, so these check the search order and that
absence is reported with every location named. The install path is NOT exercised
by default -- it downloads ~100 MB -- and is gated behind an env var.

    .venv/bin/python -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

import ensure_chrome  # noqa: E402


def _fake_exe(tmp: Path, name: str) -> Path:
    p = tmp / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("#!/bin/sh\n")
    p.chmod(0o755)
    return p


class TestSearchOrder(unittest.TestCase):
    """Config beats PATH beats globs. First hit wins, and says how it won."""

    def test_configured_path_wins(self):
        with mock.patch.object(ensure_chrome, "_configured", return_value="/bin/sh"):
            r = ensure_chrome.resolve(verify=False)
        self.assertEqual(r.path, "/bin/sh")
        self.assertEqual(r.via, "config")

    def test_falls_through_a_configured_path_that_does_not_exist(self):
        """The stored macOS path is wrong in a Linux sandbox, not fatal."""
        with mock.patch.object(ensure_chrome, "_configured",
                               return_value="/nope/Google Chrome"), \
             mock.patch.object(ensure_chrome.shutil, "which",
                               side_effect=lambda n: "/usr/bin/chromium"
                               if n == "chromium" else None), \
             mock.patch.object(ensure_chrome, "_executable",
                               side_effect=lambda p: str(p) == "/usr/bin/chromium"):
            r = ensure_chrome.resolve(verify=False)
        self.assertEqual(r.via, "path")
        self.assertEqual(r.path, "/usr/bin/chromium")

    def test_finds_a_browser_off_path(self):
        """The bug this whole change exists for: installed, but not on PATH."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            shell = _fake_exe(Path(td), "puppeteer/chrome-headless-shell")
            with mock.patch.object(ensure_chrome, "_configured", return_value=None), \
                 mock.patch.object(ensure_chrome.shutil, "which", return_value=None), \
                 mock.patch.object(ensure_chrome, "SEARCH_GLOBS", (str(shell),)):
                r = ensure_chrome.resolve(verify=False)
            self.assertEqual(r.path, str(shell))
            self.assertEqual(r.via, "glob")

    def test_prefers_a_newer_revision(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            _fake_exe(Path(td), "chrome/108.0/chrome-headless-shell")
            newer = _fake_exe(Path(td), "chrome/121.0/chrome-headless-shell")
            with mock.patch.object(ensure_chrome, "_configured", return_value=None), \
                 mock.patch.object(ensure_chrome.shutil, "which", return_value=None), \
                 mock.patch.object(ensure_chrome, "SEARCH_GLOBS",
                                   (f"{td}/chrome/*/chrome-headless-shell",)):
                r = ensure_chrome.resolve(verify=False)
            self.assertEqual(r.path, str(newer))


class TestLiveness(unittest.TestCase):
    """Executable is not the same as runnable.

    A browser downloaded onto a minimal Linux image has its exec bit set and
    still dies with `error while loading shared libraries: libglib-2.0.so.0`.
    Accepting it makes render.py fail once per visual with "chrome wrote no
    file", which daily-digest reads as a clipping bug to fix rather than the
    missing renderer it is. Found in a Debian container.
    """

    def test_a_binary_that_will_not_start_is_not_accepted(self):
        with mock.patch.object(ensure_chrome, "_configured", return_value=None), \
             mock.patch.object(ensure_chrome.shutil, "which", return_value=None), \
             mock.patch.object(ensure_chrome, "SEARCH_GLOBS", ("/fake/headless_shell",)), \
             mock.patch.object(ensure_chrome, "_executable", return_value=True), \
             mock.patch.object(ensure_chrome, "_runnable", return_value=False), \
             self.assertRaises(RuntimeError) as cm:
            ensure_chrome.resolve()
        self.assertIn("will not start", str(cm.exception))

    def test_the_same_binary_is_accepted_when_it_starts(self):
        with mock.patch.object(ensure_chrome, "_configured", return_value=None), \
             mock.patch.object(ensure_chrome.shutil, "which", return_value=None), \
             mock.patch.object(ensure_chrome, "SEARCH_GLOBS", ("/fake/headless_shell",)), \
             mock.patch.object(ensure_chrome, "_executable", return_value=True), \
             mock.patch.object(ensure_chrome, "_runnable", return_value=True):
            self.assertEqual(ensure_chrome.resolve().via, "glob")

    def test_runnable_rejects_a_missing_library_on_stderr(self):
        """Some builds print the loader error and still exit 0."""
        broken = subprocess.CompletedProcess(
            [], 0, stdout="", stderr="error while loading shared libraries: libglib-2.0.so.0")
        with mock.patch.object(ensure_chrome.subprocess, "run", return_value=broken):
            self.assertFalse(ensure_chrome._runnable("/fake/chrome"))

    def test_runnable_accepts_a_real_version_banner(self):
        ok = subprocess.CompletedProcess([], 0, stdout="Chromium 153.0.8010.36\n", stderr="")
        with mock.patch.object(ensure_chrome.subprocess, "run", return_value=ok):
            self.assertTrue(ensure_chrome._runnable("/fake/chrome"))

    def test_runnable_survives_a_binary_that_cannot_exec(self):
        with mock.patch.object(ensure_chrome.subprocess, "run", side_effect=OSError):
            self.assertFalse(ensure_chrome._runnable("/fake/chrome"))


class TestAbsence(unittest.TestCase):
    """No browser is an environment fact, reported with what was tried."""

    def _barren(self):
        return (mock.patch.object(ensure_chrome, "_configured", return_value=None),
                mock.patch.object(ensure_chrome.shutil, "which", return_value=None),
                mock.patch.object(ensure_chrome, "SEARCH_GLOBS", ("/nope/chrome",)))

    def test_raises_and_names_every_location_tried(self):
        a, b, c = self._barren()
        with a, b, c, self.assertRaises(RuntimeError) as cm:
            ensure_chrome.resolve()
        msg = str(cm.exception)
        for name in ensure_chrome.BINARY_NAMES:
            self.assertIn(name, msg, f"{name} missing from the failure report")
        self.assertIn("/nope/chrome", msg)

    def test_does_not_install_unless_asked(self):
        a, b, c = self._barren()
        with a, b, c, \
             mock.patch.object(ensure_chrome, "_install_puppeteer") as pup, \
             mock.patch.object(ensure_chrome, "_install_playwright") as play:
            with self.assertRaises(RuntimeError):
                ensure_chrome.resolve(install=False)
        pup.assert_not_called()
        play.assert_not_called()

    def test_prefer_reorders_the_installers(self):
        """A cached probe should skip straight to the route that worked."""
        a, b, c = self._barren()
        with a, b, c, \
             mock.patch.object(ensure_chrome, "_install_puppeteer",
                               return_value=None) as pup, \
             mock.patch.object(ensure_chrome, "_install_playwright",
                               return_value="/tmp/chrome") as play:
            r = ensure_chrome.resolve(install=True, prefer="pip-playwright",
                                      verify=False)
        self.assertEqual(r.via, "pip-playwright")
        play.assert_called_once()
        # The preferred installer won, so the other must never have been tried.
        pup.assert_not_called()

    def test_cli_reports_failure_as_json(self):
        import io
        import json
        import contextlib
        a, b, c = self._barren()
        buf = io.StringIO()
        with a, b, c, contextlib.redirect_stdout(buf):
            rc = ensure_chrome.main(["--probe-only", "--json"])
        self.assertEqual(rc, 1)
        payload = json.loads(buf.getvalue())
        self.assertIsNone(payload["path"])
        self.assertEqual(payload["via"], "unavailable")
        self.assertIn("Tried:", payload["reason"])


class TestInstallDefault(unittest.TestCase):
    """Only a sandbox should ever pay for a download."""

    def test_config_wins_when_set(self):
        for configured in (True, False):
            with self.subTest(configured=configured), \
                 mock.patch.object(ensure_chrome, "_render_config",
                                   return_value={"install": configured}):
                self.assertIs(ensure_chrome.install_default(), configured)

    def test_defaults_off_on_a_laptop_and_on_in_a_sandbox(self):
        with mock.patch.object(ensure_chrome, "_render_config", return_value={}):
            with mock.patch.object(ensure_chrome.sys, "platform", "darwin"):
                self.assertFalse(ensure_chrome.install_default())
            with mock.patch.object(ensure_chrome.sys, "platform", "linux"):
                self.assertTrue(ensure_chrome.install_default())

    def test_a_non_bool_config_value_does_not_win(self):
        """A stray string must fall back, not read as truthy."""
        with mock.patch.object(ensure_chrome, "_render_config",
                               return_value={"install": "yes"}), \
             mock.patch.object(ensure_chrome.sys, "platform", "darwin"):
            self.assertFalse(ensure_chrome.install_default())


@unittest.skipUnless(os.environ.get("TEST_CHROME_INSTALL"),
                     "downloads ~100 MB; set TEST_CHROME_INSTALL=1 to run")
class TestInstall(unittest.TestCase):
    """Only meaningful in a sandbox with no browser. Never runs in CI."""

    def test_install_yields_a_working_binary(self):
        """SEARCH_GLOBS must be blanked, or a populated cache wins first.

        Without that the test passes via `glob` and never runs an installer at
        all -- which is exactly how it first "passed".
        """
        a = mock.patch.object(ensure_chrome, "_configured", return_value=None)
        b = mock.patch.object(ensure_chrome.shutil, "which",
                              side_effect=lambda n: None if n in
                              ensure_chrome.BINARY_NAMES else "/usr/bin/" + n)
        c = mock.patch.object(ensure_chrome, "SEARCH_GLOBS", ("/nonexistent/chrome",))
        with a, b, c:
            r = ensure_chrome.resolve(install=True)
        self.assertIn(r.via, ("npx-puppeteer", "pip-playwright"))
        self.assertTrue(ensure_chrome._executable(r.path))

    def test_install_never_writes_into_the_working_directory(self):
        """@puppeteer/browsers defaults to CWD -- 195 MB into a public repo."""
        a = mock.patch.object(ensure_chrome, "_configured", return_value=None)
        b = mock.patch.object(ensure_chrome.shutil, "which",
                              side_effect=lambda n: None if n in
                              ensure_chrome.BINARY_NAMES else "/usr/bin/" + n)
        c = mock.patch.object(ensure_chrome, "SEARCH_GLOBS", ("/nonexistent/chrome",))
        with a, b, c:
            r = ensure_chrome.resolve(install=True)
        self.assertFalse(Path(r.path).is_relative_to(ROOT),
                         f"installed inside the repo: {r.path}")
        self.assertTrue(Path(r.path).is_relative_to(ensure_chrome.CACHE_DIR))


if __name__ == "__main__":
    unittest.main(verbosity=2)
