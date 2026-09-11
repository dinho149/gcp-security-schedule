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
            r = ensure_chrome.resolve()
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
            r = ensure_chrome.resolve()
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
                r = ensure_chrome.resolve()
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
                r = ensure_chrome.resolve()
            self.assertEqual(r.path, str(newer))


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
            r = ensure_chrome.resolve(install=True, prefer="pip-playwright")
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
