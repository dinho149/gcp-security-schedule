#!/usr/bin/env python3
"""Tests for the digest visual component library.

Rendering runs daily and unattended, so the failure mode that matters is a
visual that silently comes out clipped, empty, or with an unresolved template
placeholder in it. These check for exactly that.

Chrome-dependent tests skip automatically when Chrome is absent (e.g. in CI).

    .venv/bin/python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

import visuals  # noqa: E402


class TestComponentHtml(unittest.TestCase):
    """Every component renders self-contained, fully-substituted HTML."""

    def test_all_components_have_a_demo(self):
        self.assertEqual(set(visuals.COMPONENTS), set(visuals.DEMOS),
                         "every component needs a demo spec, they are the fixtures")

    def test_all_components_have_a_default_width(self):
        self.assertEqual(set(visuals.COMPONENTS), set(visuals.DEFAULT_WIDTH))

    def test_renders_without_unsubstituted_placeholders(self):
        for name, spec in visuals.DEMOS.items():
            with self.subTest(component=name):
                html = visuals.render(spec)
                # A stray {foo} means a .format() field was missed.
                leftovers = re.findall(r"\{[a-z_]+\}", html)
                self.assertEqual(leftovers, [], f"unsubstituted: {leftovers}")

    def test_renders_standalone_document(self):
        for name, spec in visuals.DEMOS.items():
            with self.subTest(component=name):
                html = visuals.render(spec)
                self.assertTrue(html.startswith("<!doctype html>"))
                self.assertIn("<body>", html)
                # No external requests: rendering must not depend on the network.
                self.assertNotIn("http://", html.replace("http://www.w3.org", ""))
                self.assertNotIn("<script", html)

    def test_draws_the_sentinel_border(self):
        """render.py crops to this. Without it a light element gets trimmed."""
        for name, spec in visuals.DEMOS.items():
            with self.subTest(component=name):
                self.assertIn(visuals.SENTINEL, visuals.render(spec))

    def test_escapes_content(self):
        spec = dict(visuals.DEMOS["compare"])
        spec["title"] = "IAM & <script>alert(1)</script>"
        html = visuals.render(spec)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_rejects_unknown_component(self):
        with self.assertRaises(ValueError):
            visuals.render({"component": "sankey", "title": "x"})

    def test_rejects_missing_title(self):
        with self.assertRaises(ValueError):
            visuals.render({"component": "compare", "columns": [], "rows": []})

    def test_demo_specs_are_valid_json(self):
        payload = json.dumps({"visuals": list(visuals.DEMOS.values())})
        self.assertEqual(len(json.loads(payload)["visuals"]), len(visuals.DEMOS))


def chrome_available() -> bool:
    sys.path.insert(0, str(ROOT / "dashboard"))
    import render
    return Path(render.chrome_path()).exists()


@unittest.skipUnless(chrome_available(), "Chrome not installed (expected in CI)")
class TestRenderPipeline(unittest.TestCase):
    """End-to-end: spec -> PNG. Slow (~2s per visual), so one representative case."""

    def test_renders_and_crops_evenly(self):
        import render
        from PIL import Image

        spec = visuals.DEMOS["contrast"]
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "specs.json"
            out.write_text(json.dumps({"visuals": [spec]}))
            rc = render.main([str(out), "--out-dir", td])
            self.assertEqual(rc, 0)

            pngs = list(Path(td).glob("*.png"))
            self.assertEqual(len(pngs), 1)
            png = pngs[0]
            self.assertGreater(png.stat().st_size, 5_000, "suspiciously small PNG")

            im = Image.open(png).convert("RGB")
            self.assertGreater(im.width, 400)
            self.assertGreater(im.height, 200)

            # The sentinel must be fully cropped away.
            target = tuple(int(visuals.SENTINEL[i:i + 2], 16) for i in (1, 3, 5))
            present = {c for _, c in im.getcolors(maxcolors=1 << 24)}
            self.assertNotIn(target, present, "sentinel colour survived the crop")

    def test_detects_clipping(self):
        """A visual too tall for the canvas must fail, not post truncated.

        An earlier version checked for a clean white margin instead. That was
        vacuous: content rarely reaches the very edge, so a clipped image passed.
        Overflow is detectable because the sentinel border goes missing on the
        side that overflowed.
        """
        import render

        rows = [{"habit": f"Habit {i} written long enough to wrap onto several lines",
                 "reality": f"Reality {i} written long enough to wrap onto several lines"}
                for i in range(24)]
        spec = {"component": "contrast", "title": "Overflowing", "rows": rows}

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "specs.json"
            out.write_text(json.dumps({"visuals": [spec]}))
            rc = render.main([str(out), "--out-dir", td])
            self.assertEqual(rc, 1, "an overflowing visual must fail the run")


if __name__ == "__main__":
    unittest.main(verbosity=2)
