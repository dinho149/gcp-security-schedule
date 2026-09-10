#!/usr/bin/env python3
"""Render a digest diagram to standalone HTML, for screenshotting to PNG.

Slack cannot render SVG or style anything, so the only route to real imagery is
uploading a PNG. We build the diagram as HTML/SVG and screenshot it in a browser
rather than drawing a bitmap by hand, so it keeps real typography.

    .venv/bin/python dashboard/render_diagram.py hierarchy > /tmp/d.html

Diagrams are keyed by name so a digest can ask for the one it needs.
"""
from __future__ import annotations

import sys

# Section colours, matching docs/house-style.md
INK = "#111418"
MUTED = "#5b6470"
LINE = "#d4d9e0"
ACCENT = "#1a73e8"
BAD = "#d93025"
GOOD = "#188038"

SHELL = """<!doctype html><meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 34px 38px; width: 1000px; background: #fff;
    font: 15px/1.45 -apple-system, "Segoe UI", Inter, system-ui, sans-serif;
    color: {ink}; -webkit-font-smoothing: antialiased;
  }}
  h1 {{ font-size: 21px; margin: 0 0 4px; letter-spacing: -.015em; }}
  .sub {{ color: {muted}; font-size: 13.5px; margin: 0 0 24px; }}
  .mono {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12.5px; }}
  .foot {{ margin-top: 22px; padding-top: 13px; border-top: 1px solid {line};
           color: {muted}; font-size: 12.5px; }}
</style>
{body}
"""


def hierarchy() -> str:
    """Resource hierarchy, marking where a custom role may be DEFINED."""
    rows = [
        ("Organization", "org", True, "Custom roles CAN be defined here"),
        ("Folder", "folder", False, "Custom roles CANNOT be defined here"),
        ("Project", "project", True, "Custom roles CAN be defined here"),
        ("Resource", "resource", None, "Bindings attach here too"),
    ]
    boxes = []
    y = 0
    for label, ident, allowed, note in rows:
        if allowed is None:
            mark, colour = "·", MUTED
        elif allowed:
            mark, colour = "✓", GOOD
        else:
            mark, colour = "✗", BAD
        boxes.append(f"""
        <div style="display:flex;align-items:center;gap:16px;margin-left:{y}px">
          <div style="min-width:210px;border:1.5px solid {LINE};border-left:4px solid {colour};
                      border-radius:7px;padding:11px 15px;background:#fbfcfd">
            <div style="font-weight:640">{label}</div>
            <div class="mono" style="color:{MUTED}">{ident}</div>
          </div>
          <div style="font-size:19px;color:{colour};font-weight:700;width:20px">{mark}</div>
          <div style="color:{MUTED};font-size:13.5px">{note}</div>
        </div>""")
        y += 34
    joined = '<div style="height:10px;border-left:1.5px dashed %s;margin:2px 0 2px 22px"></div>' % LINE
    body = f"""<body>
      <h1>Where a custom role can be <em>defined</em></h1>
      <p class="sub">Policies inherit down every level. The place a role may be
         <em>created</em> does not follow that rule &mdash; folders are the exception.</p>
      {joined.join(boxes)}
      <div class="foot">
        Coming from AWS: you are used to defining a customer-managed policy anywhere
        and attaching it anywhere. In GCP, <span class="mono">where a role is defined</span>
        and <span class="mono">where it is granted</span> are separate questions, and only
        the second one follows the hierarchy.
      </div>
    </body>"""
    return SHELL.format(ink=INK, muted=MUTED, line=LINE, body=body)


def vpc_scope() -> str:
    """VPC global vs subnet regional — inverted from AWS."""
    def cloud(title, outer, inner_label, inners, accent):
        cells = "".join(
            f'<div style="border:1.5px solid {LINE};border-radius:6px;padding:9px 12px;'
            f'background:#fff;min-width:150px"><div class="mono" style="color:{MUTED}">'
            f'{inner_label}</div><div style="font-weight:600">{n}</div></div>'
            for n in inners)
        return f"""
        <div style="flex:1">
          <div style="font-weight:660;margin-bottom:9px">{title}</div>
          <div style="border:2px solid {accent};border-radius:10px;padding:14px;background:#fafbfc">
            <div class="mono" style="color:{accent};font-weight:660;margin-bottom:10px">{outer}</div>
            <div style="display:flex;gap:10px;flex-wrap:wrap">{cells}</div>
          </div>
        </div>"""

    body = f"""<body>
      <h1>VPC scope is inverted from AWS</h1>
      <p class="sub">One difference, and a lot of wrong answers downstream.</p>
      <div style="display:flex;gap:26px;align-items:flex-start">
        {cloud("Google Cloud", "VPC &mdash; GLOBAL", "region", ["europe-west2", "us-east1", "asia-east1"], ACCENT)}
        {cloud("AWS", "VPC &mdash; REGIONAL", "availability zone", ["eu-west-2a", "eu-west-2b"], MUTED)}
      </div>
      <div class="foot">
        A Google Cloud VPC spans every region at once; its subnets are
        <strong>regional</strong> and span the zones inside that region, so two instances in
        different zones can sit on the same subnet. In AWS the VPC is pinned to one region
        and each subnet to a single AZ.
      </div>
    </body>"""
    return SHELL.format(ink=INK, muted=MUTED, line=LINE, body=body)


DIAGRAMS = {"hierarchy": hierarchy, "vpc-scope": vpc_scope}


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in DIAGRAMS:
        print(f"usage: render_diagram.py <{'|'.join(DIAGRAMS)}>", file=sys.stderr)
        return 2
    print(DIAGRAMS[argv[0]]())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
