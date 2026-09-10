#!/usr/bin/env python3
"""Render a digest's visual specs to PNGs, in one command.

    .venv/bin/python dashboard/render.py state.local/history/<date>/visuals.json

Input is {"visuals": [<spec>, ...]}; see dashboard/visuals.py for spec shapes.
Output is <spec-dir>/visuals/<slug>.png, one per spec.

Why headless Chrome: the visuals need real CSS layout and typography, and Chrome
is already installed. The earlier flow drove a live browser through the MCP
extension, which needed ~5 interactive calls per image and a browser session --
unworkable for something that fires unattended at 07:15.

Cropping is to the SENTINEL border each component draws, never to white: a
light-coloured element sitting at the edge would otherwise be trimmed away.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import visuals  # noqa: E402
from PIL import Image, ImageChops  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SCALE = 2          # retina; Slack displays these on high-DPI screens
PAD = 18           # breathing room left around the cropped content, in output px
RENDER_H = 2200    # tall canvas; the crop discards whatever is unused


def slug(text: str, fallback: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s[:48] or fallback


def chrome_path() -> str:
    cfg = ROOT / "config/config.local.yaml"
    if cfg.exists():
        try:
            import yaml
            data = yaml.safe_load(cfg.read_text()) or {}
            if p := (data.get("render") or {}).get("chrome_path"):
                return p
        except Exception:
            pass
    return DEFAULT_CHROME


def shoot(chrome: str, html: str, out: Path, width: int) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
        src = Path(f.name)
    try:
        proc = subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
             f"--force-device-scale-factor={SCALE}",
             "--default-background-color=ffffffff",
             f"--window-size={width},{RENDER_H}",
             f"--screenshot={out}", f"file://{src}"],
            capture_output=True, text=True, timeout=90,
        )
    finally:
        src.unlink(missing_ok=True)
    if not out.exists():
        raise RuntimeError(f"chrome wrote no file.\n{proc.stderr[-600:]}")


def crop_to_sentinel(path: Path) -> tuple[int, int]:
    """Trim to the sentinel border, then re-pad evenly. Returns final size.

    Uses ImageChops rather than a per-pixel loop: at 2x scale these canvases are
    ~8M pixels, and looping in Python took ~4.5s per image.
    """
    im = Image.open(path).convert("RGB")
    target = tuple(int(visuals.SENTINEL[i:i + 2], 16) for i in (1, 3, 5))

    # Content is anything that differs from the sentinel colour.
    sentinel_plate = Image.new("RGB", im.size, target)
    box = ImageChops.difference(im, sentinel_plate).convert("L").point(
        lambda v: 255 if v else 0).getbbox()
    if not box:
        raise RuntimeError(f"{path.name}: no content found inside sentinel border")

    # Clipping detection. Every side must have sentinel beyond the content; if the
    # bounding box reaches a canvas edge, the page overflowed the render window and
    # the visual is cut off. Better to fail loudly than to post a truncated diagram.
    touching = [side for side, hit in (
        ("left", box[0] == 0), ("top", box[1] == 0),
        ("right", box[2] == im.width), ("bottom", box[3] == im.height)) if hit]
    if touching:
        raise RuntimeError(
            f"{path.name}: content reaches the {', '.join(touching)} edge — the visual "
            f"overflowed the {im.width // SCALE}x{RENDER_H} canvas and would be clipped. "
            f"Increase RENDER_H, or set a wider 'width' on the spec.")

    im = im.crop(box)
    out = Image.new("RGB", (im.width + PAD * 2, im.height + PAD * 2), "white")
    out.paste(im, (PAD, PAD))
    out.save(path, optimize=True)
    return out.size


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec_file", help='JSON with {"visuals": [...]}')
    ap.add_argument("--out-dir", help="default: <spec-dir>/visuals")
    args = ap.parse_args(argv)

    spec_path = Path(args.spec_file)
    if not spec_path.exists():
        print(f"no such spec file: {spec_path}", file=sys.stderr)
        return 2

    data = json.loads(spec_path.read_text())
    specs = data.get("visuals", data if isinstance(data, list) else [])
    if not specs:
        print("spec file contains no visuals", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else spec_path.parent / "visuals"
    out_dir.mkdir(parents=True, exist_ok=True)
    chrome = chrome_path()
    if not Path(chrome).exists():
        print(f"chrome not found at {chrome}\n"
              f"set render.chrome_path in config/config.local.yaml", file=sys.stderr)
        return 2

    print(f"rendering {len(specs)} visual(s) with {Path(chrome).name}")
    failures = 0
    for i, spec in enumerate(specs, 1):
        name = spec.get("id") or slug(spec.get("title", ""), f"visual-{i}")
        out = out_dir / f"{name}.png"
        try:
            html = visuals.render(spec)
            width = spec.get("width") or visuals.DEFAULT_WIDTH[spec["component"]]
            shoot(chrome, html, out, width)
            w, h = crop_to_sentinel(out)
            kb = out.stat().st_size / 1024
            print(f"  ok   {name:<44} {w:>5}x{h:<5} {kb:>6.1f} KB")
        except Exception as e:
            failures += 1
            print(f"  FAIL {name:<44} {e}", file=sys.stderr)

    print(f"-> {out_dir}")
    if failures:
        print(f"{failures} visual(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
