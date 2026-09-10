#!/usr/bin/env python3
"""Spec-driven visual component library for digest topics.

The digest cannot use a fixed registry of diagrams: topics change every day. So
the agent emits a JSON spec per visual and this module renders it to standalone
HTML, which dashboard/render.py screenshots.

Six components, chosen so several visuals in one digest never look alike:

    compare    2-3 column card              GCP vs AWS, service A vs service B
    chain      nested hierarchy w/ marks    resource hierarchy, inheritance
    contrast   habit/reality pairs          the aws_traps entries
    sequence   numbered strip               IAM evaluation order, request path
    decision   branching tree               "which connectivity option"
    code       annotated snippet card       gcloud / Terraform with callouts

Every component draws a SENTINEL border, which render.py crops to. Cropping to
white would trim any light element sitting at the edge.

    .venv/bin/python dashboard/visuals.py <component>   # demo spec -> HTML
"""
from __future__ import annotations

import html
import json
import sys

# Palette, matching docs/house-style.md
INK = "#111418"
MUTED = "#5b6470"
LINE = "#d4d9e0"
ACCENT = "#1a73e8"
BAD = "#d93025"
GOOD = "#188038"
WASH = "#fbfcfd"

# Cropped away by render.py. Must not occur in normal content.
SENTINEL = "#ff00ff"

SECTION_COLOUR = {"1": "#1a73e8", "2": "#188038", "3": "#f29900",
                  "4": "#e8710a", "5": "#d93025"}

SHELL = """<!doctype html><meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; }}
  html {{ background: {sentinel}; }}
  body {{
    margin: 0; padding: 30px 34px; width: {width}px;
    background: #fff; border: 6px solid {sentinel};
    font: 15px/1.45 -apple-system, "Segoe UI", Inter, system-ui, sans-serif;
    color: {ink}; -webkit-font-smoothing: antialiased;
  }}
  h1 {{ font-size: 20px; margin: 0 0 3px; letter-spacing: -.015em; }}
  .sub {{ color: {muted}; font-size: 13.5px; margin: 0 0 22px; }}
  .mono {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12.5px; }}
  .foot {{ margin-top: 22px; padding-top: 12px; border-top: 1px solid {line};
           color: {muted}; font-size: 12.5px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  td, th {{ text-align: left; padding: 9px 13px; font-size: 14px;
            border-bottom: 1px solid {line}; vertical-align: top; }}
  th {{ font-size: 12px; text-transform: uppercase; letter-spacing: .05em;
        color: {muted}; font-weight: 620; border-bottom: 1.5px solid {line}; }}
</style>
<body>{body}</body>
"""


def esc(s) -> str:
    return html.escape(str(s), quote=False)


def _head(spec: dict) -> str:
    out = f"<h1>{esc(spec['title'])}</h1>"
    if spec.get("subtitle"):
        out += f'<p class="sub">{esc(spec["subtitle"])}</p>'
    else:
        out += '<div style="height:14px"></div>'
    return out


def _foot(spec: dict) -> str:
    if not spec.get("footnote"):
        return ""
    return f'<div class="foot">{esc(spec["footnote"])}</div>'


def _accent(spec: dict) -> str:
    return SECTION_COLOUR.get(str(spec.get("section", "")), ACCENT)


def compare(spec: dict) -> str:
    """Columns compared row by row. spec: columns[], rows[{label, cells[]}]."""
    cols = spec["columns"]
    accent = _accent(spec)
    head = "".join(f"<th>{esc(c)}</th>" for c in cols)
    body = ""
    for row in spec["rows"]:
        cells = ""
        for i, cell in enumerate(row["cells"]):
            weight = "620" if i == 0 else "400"
            colour = accent if i == 0 else INK
            cells += (f'<td style="font-weight:{weight};color:{colour}">'
                      f'{esc(cell)}</td>')
        body += (f'<tr><td style="color:{MUTED};font-weight:560">'
                 f'{esc(row["label"])}</td>{cells}</tr>')
    return (_head(spec) +
            f'<table><tr><th style="width:150px"></th>{head}</tr>{body}</table>' +
            _foot(spec))


def chain(spec: dict) -> str:
    """Nested hierarchy, each level optionally marked. spec: levels[{label, ident, mark, note}]."""
    marks = {"yes": ("&check;", GOOD), "no": ("&times;", BAD), "none": ("&middot;", MUTED)}
    out, indent = [], 0
    for lv in spec["levels"]:
        glyph, colour = marks.get(lv.get("mark", "none"), marks["none"])
        ident = (f'<div class="mono" style="color:{MUTED}">{esc(lv["ident"])}</div>'
                 if lv.get("ident") else "")
        note = (f'<div style="color:{MUTED};font-size:13.5px">{esc(lv["note"])}</div>'
                if lv.get("note") else "")
        out.append(f"""
        <div style="display:flex;align-items:center;gap:15px;margin-left:{indent}px">
          <div style="min-width:205px;border:1.5px solid {LINE};border-left:4px solid {colour};
                      border-radius:7px;padding:10px 14px;background:{WASH}">
            <div style="font-weight:640">{esc(lv["label"])}</div>{ident}
          </div>
          <div style="font-size:18px;color:{colour};font-weight:700;width:18px">{glyph}</div>
          {note}
        </div>""")
        indent += 32
    joiner = (f'<div style="height:9px;border-left:1.5px dashed {LINE};'
              f'margin:2px 0 2px 22px"></div>')
    return _head(spec) + joiner.join(out) + _foot(spec)


def contrast(spec: dict) -> str:
    """habit/reality pairs. spec: rows[{habit, reality}]."""
    cards = []
    for row in spec["rows"]:
        cards.append(f"""
        <div style="display:flex;gap:14px;margin-bottom:13px">
          <div style="flex:1;border:1.5px solid {LINE};border-top:3px solid {BAD};
                      border-radius:8px;padding:12px 15px;background:{WASH}">
            <div style="color:{BAD};font-weight:660;font-size:12px;
                        text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px">
              &times; AWS habit</div>
            <div>{esc(row["habit"])}</div>
          </div>
          <div style="flex:1;border:1.5px solid {LINE};border-top:3px solid {GOOD};
                      border-radius:8px;padding:12px 15px;background:{WASH}">
            <div style="color:{GOOD};font-weight:660;font-size:12px;
                        text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px">
              &check; GCP reality</div>
            <div>{esc(row["reality"])}</div>
          </div>
        </div>""")
    return _head(spec) + "".join(cards) + _foot(spec)


def sequence(spec: dict) -> str:
    """Numbered left-to-right strip. spec: steps[{label, detail}]."""
    accent = _accent(spec)
    cells = []
    for i, step in enumerate(spec["steps"], 1):
        detail = (f'<div style="color:{MUTED};font-size:13px;margin-top:3px">'
                  f'{esc(step["detail"])}</div>' if step.get("detail") else "")
        cells.append(f"""
        <div style="flex:1;min-width:0;border:1.5px solid {LINE};border-radius:8px;
                    padding:13px 15px;background:{WASH}">
          <div style="display:inline-flex;align-items:center;justify-content:center;
                      width:22px;height:22px;border-radius:50%;background:{accent};
                      color:#fff;font-size:12.5px;font-weight:700;margin-bottom:7px">{i}</div>
          <div style="font-weight:620">{esc(step["label"])}</div>{detail}
        </div>""")
    arrow = (f'<div style="align-self:center;color:{LINE};font-size:20px;'
             f'padding:0 3px">&rarr;</div>')
    return (_head(spec) +
            f'<div style="display:flex;align-items:stretch">{arrow.join(cells)}</div>' +
            _foot(spec))


def decision(spec: dict) -> str:
    """Question with condition -> answer branches. spec: question, branches[{when, then}]."""
    accent = _accent(spec)
    rows = []
    for b in spec["branches"]:
        rows.append(f"""
        <div style="display:flex;align-items:stretch;gap:0;margin-bottom:9px">
          <div style="width:26px;border-left:2px solid {LINE};
                      border-bottom:2px solid {LINE};border-radius:0 0 0 8px;
                      margin:0 12px 11px 20px"></div>
          <div style="flex:1;display:flex;gap:12px;align-items:center">
            <div style="flex:1;border:1.5px solid {LINE};border-radius:7px;
                        padding:10px 14px;background:#fff;color:{MUTED}">
              {esc(b["when"])}</div>
            <div style="color:{LINE};font-size:17px">&rarr;</div>
            <div style="flex:1;border:1.5px solid {accent};border-radius:7px;
                        padding:10px 14px;background:{WASH};font-weight:620;
                        color:{accent}">{esc(b["then"])}</div>
          </div>
        </div>""")
    q = (f'<div style="border:2px solid {accent};border-radius:8px;padding:12px 16px;'
         f'background:{WASH};font-weight:640;margin-bottom:6px;display:inline-block">'
         f'{esc(spec["question"])}</div>')
    return _head(spec) + q + "".join(rows) + _foot(spec)


def code(spec: dict) -> str:
    """Annotated snippet. spec: lines[] or code, notes[{text}] optional."""
    accent = _accent(spec)
    lines = spec.get("lines") or spec.get("code", "").split("\n")
    rendered = ""
    for ln in lines:
        text, note = (ln["text"], ln.get("note")) if isinstance(ln, dict) else (ln, None)
        ann = (f'<span style="color:{accent};font-size:12px;margin-left:14px">'
               f'&larr; {esc(note)}</span>' if note else "")
        rendered += (f'<div style="padding:2px 0"><span class="mono">'
                     f'{esc(text)}</span>{ann}</div>')
    block = (f'<div style="border:1.5px solid {LINE};border-radius:8px;padding:14px 17px;'
             f'background:{WASH};overflow:hidden">{rendered}</div>')
    return _head(spec) + block + _foot(spec)


COMPONENTS = {
    "compare": compare, "chain": chain, "contrast": contrast,
    "sequence": sequence, "decision": decision, "code": code,
}

DEFAULT_WIDTH = {"compare": 900, "chain": 980, "contrast": 900,
                 "sequence": 980, "decision": 940, "code": 860}


def render(spec: dict) -> str:
    """Spec -> standalone HTML."""
    name = spec.get("component")
    if name not in COMPONENTS:
        raise ValueError(f"unknown component {name!r}; "
                         f"expected one of {', '.join(sorted(COMPONENTS))}")
    if not spec.get("title"):
        raise ValueError(f"{name}: spec needs a title")
    width = spec.get("width") or DEFAULT_WIDTH[name]
    return SHELL.format(sentinel=SENTINEL, ink=INK, muted=MUTED,
                        line=LINE, width=width, body=COMPONENTS[name](spec))


DEMOS = {
    "compare": {
        "component": "compare", "section": "2",
        "title": "VPC scope is inverted from AWS",
        "subtitle": "One difference, and a lot of wrong answers downstream.",
        "columns": ["Google Cloud", "AWS"],
        "rows": [
            {"label": "VPC", "cells": ["Global", "Regional"]},
            {"label": "Subnet", "cells": ["Regional — spans zones", "Zonal — one AZ"]},
            {"label": "Consequence", "cells": ["Two zones can share a subnet",
                                               "A subnet never spans AZs"]},
        ],
        "footnote": "Instances in different zones sitting on one subnet is the default "
                    "topology, not a trick.",
    },
    "chain": {
        "component": "chain", "section": "1",
        "title": "Where a custom role can be defined",
        "subtitle": "Policies inherit down every level. Role definition does not.",
        "levels": [
            {"label": "Organization", "ident": "org", "mark": "yes", "note": "CAN define here"},
            {"label": "Folder", "ident": "folder", "mark": "no", "note": "CANNOT define here"},
            {"label": "Project", "ident": "project", "mark": "yes", "note": "CAN define here"},
            {"label": "Resource", "ident": "resource", "mark": "none", "note": "Bindings attach here"},
        ],
        "footnote": "Where a role is defined and where it is granted are separate "
                    "questions. Only the second follows the hierarchy.",
    },
    "contrast": {
        "component": "contrast", "section": "1",
        "title": "Two controls that look like SCPs and are not",
        "rows": [
            {"habit": "Deny an API action with an SCP at the OU",
             "reality": "Organization policy constrains resource configuration, not API calls"},
            {"habit": "Reach for a policy boundary to stop a principal",
             "reality": "IAM deny policy — evaluated before allow, and inherited"},
        ],
        "footnote": "The SCP analogue is the IAM deny policy, not the org policy constraint.",
    },
    "sequence": {
        "component": "sequence", "section": "1",
        "title": "How an IAM decision is reached",
        "steps": [
            {"label": "Deny policies", "detail": "Checked first, inherited"},
            {"label": "Allow policies", "detail": "Role bindings on the resource"},
            {"label": "Inheritance", "detail": "Org → folder → project"},
            {"label": "Decision", "detail": "Any deny wins"},
        ],
        "footnote": "Deny is evaluated before allow — same order as an explicit Deny in "
                    "AWS, a different object entirely.",
    },
    "decision": {
        "component": "decision", "section": "2",
        "title": "Choosing a connectivity option",
        "question": "Do you need private connectivity with an SLA?",
        "branches": [
            {"when": "Yes, and you can place equipment in a Google PoP",
             "then": "Dedicated Interconnect"},
            {"when": "Yes, but via a service provider", "then": "Partner Interconnect"},
            {"when": "No SLA needed, internet link is adequate", "then": "Cloud VPN"},
            {"when": "No private addressing needed", "then": "Public IP"},
        ],
        "footnote": "Direct and Carrier Peering carry no SLA — that wording in a stem is "
                    "usually the discriminator.",
    },
    "code": {
        "component": "code", "section": "1",
        "title": "Granting on the resource, not the project",
        "lines": [
            {"text": "gcloud storage buckets add-iam-policy-binding gs://reports \\"},
            {"text": "  --member=serviceAccount:app@proj.iam.gserviceaccount.com \\",
             "note": "the workload identity"},
            {"text": "  --role=roles/storage.objectCreator", "note": "write only, no read"},
        ],
        "footnote": "Binding on the bucket keeps the grant to the one resource that needs it.",
    },
}


def main(argv: list[str]) -> int:
    if len(argv) == 1 and argv[0] == "--demo-specs":
        print(json.dumps({"visuals": list(DEMOS.values())}, indent=2))
        return 0
    if len(argv) != 1 or argv[0] not in COMPONENTS:
        print(f"usage: visuals.py <{'|'.join(COMPONENTS)}> | --demo-specs", file=sys.stderr)
        return 2
    print(render(DEMOS[argv[0]]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
