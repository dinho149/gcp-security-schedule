#!/usr/bin/env python3
"""Render the readiness dashboard — dashboard/readiness.generated.html.

The bookmarkable half of the readiness report. Slack carries the headline; this
carries what a chat message cannot: the trend, every subsection with the
evidence behind it, and the shape of what is left.

One design decision does the arguing. The headline readiness bar and every
section bar sit on the same 0-100 exam-weight axis, with unreachable weight drawn
as hatching, so "capped by coverage" becomes something you can see rather than
something the page asserts. The on-covered figure is deliberately the one bar on a
different denominator, and the page says so rather than quietly rescaling it.

Colours come from dashboard/visuals.py so the dashboard, the digest visuals and
the Slack colour squares stay one language.

    .venv/bin/python scripts/build_dashboard.py [--out PATH]
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

from visuals import SECTION_COLOUR  # noqa: E402  one palette, not two

READINESS = ROOT / "state.local/readiness.json"
OUT = ROOT / "dashboard/readiness.generated.html"

SQUARE = {"1": "🟦", "2": "🟩", "3": "🟨", "4": "🟧", "5": "🟥"}


def e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def pct(x, digits=0) -> str:
    return "—" if x is None else f"{x * 100:.{digits}f}%"


def bar(points: float, reachable: float, total: float, colour: str) -> str:
    """One row on the shared exam-weight axis: earned, reachable, unreachable."""
    earned = max(0.0, min(points, total)) / total * 100
    reach = max(0.0, min(reachable, total)) / total * 100
    return (f'<div class="bar" role="img" aria-label="{earned:.0f} of {reach:.0f} '
            f'reachable percent earned">'
            f'<div class="bar-reach" style="width:{reach:.3f}%"></div>'
            f'<div class="bar-fill" style="width:{earned:.3f}%;background:{colour}"></div>'
            f"</div>")


def trend_svg(trend: list[dict], target: float) -> str:
    """True readiness over time against the target line."""
    if len(trend) < 2:
        return ('<p class="empty">No trend yet — it needs two graded quizzes to '
                "have a shape. Every point on it will be a day you were measured, "
                "not a day that passed.</p>")

    w, h, pad = 640, 200, 34
    ys = [p["true"] for p in trend] + [target]
    top = max(ys) * 1.15 or 1
    xs = [datetime.date.fromisoformat(p["date"]).toordinal() for p in trend]
    span = (xs[-1] - xs[0]) or 1

    def px(i):
        return pad + (xs[i] - xs[0]) / span * (w - pad * 2)

    def py(v):
        return h - pad - (v / top) * (h - pad * 2)

    pts = " ".join(f"{px(i):.1f},{py(p['true']):.1f}" for i, p in enumerate(trend))
    area = f"{px(0):.1f},{h - pad:.1f} {pts} {px(len(trend) - 1):.1f},{h - pad:.1f}"
    ty = py(target)
    last = trend[-1]

    return f"""<svg viewBox="0 0 {w} {h}" class="trend" role="img"
     aria-label="True exam readiness over time against the target">
  <line x1="{pad}" y1="{h - pad}" x2="{w - pad}" y2="{h - pad}" class="axis"/>
  <line x1="{pad}" y1="{ty:.1f}" x2="{w - pad}" y2="{ty:.1f}" class="target"/>
  <text x="{w - pad}" y="{ty - 7:.1f}" class="tick" text-anchor="end">
    our bar {target * 100:.0f}%</text>
  <polygon points="{area}" class="area"/>
  <polyline points="{pts}" class="line"/>
  <circle cx="{px(len(trend) - 1):.1f}" cy="{py(last['true']):.1f}" r="4.5" class="dot"/>
  <text x="{px(len(trend) - 1):.1f}" y="{py(last['true']) - 12:.1f}" class="tick"
        text-anchor="end">{last['true'] * 100:.0f}%</text>
  <text x="{pad}" y="{h - 12}" class="tick">{e(trend[0]['date'])}</text>
  <text x="{w - pad}" y="{h - 12}" class="tick" text-anchor="end">{e(last['date'])}</text>
</svg>"""


def render(r: dict) -> str:
    h_, est, cov = r["headline"], r["estimate"], r["coverage"]
    ev = r["evidence"]
    target = est.get("target", 0.75)
    unreachable = round((1 - h_["reachable"]) * 100, 1)

    section_rows = "\n".join(
        f"""<tr>
      <th scope="row"><span class="sq">{SQUARE.get(s['id'], '')}</span>
        <span class="sname">{e(s['title'])}</span>
        <span class="smeta">{s['subsections_with_material']}/{s['subsections_total']}
          subsections · {s['weight']}% of the exam</span></th>
      <td class="num">{pct(s['on_covered'])}</td>
      <td class="num">{s['points']:.1f}<span class="of">/{s['weight']}</span></td>
      <td class="barcell">{bar(s['points'], s['reachable_points'], s['weight'],
                               SECTION_COLOUR.get(s['id'], '#5b6470'))}</td>
    </tr>"""
        for s in r["sections"])

    sub_rows = "\n".join(
        f"""<tr>
      <th scope="row"><span class="sq">{SQUARE.get(sid.split('.')[0], '')}</span>
        <span class="mono">{e(sid)}</span></th>
      <td class="num">{v['weight']:.1f}%</td>
      <td class="num">{v['readiness'] * 100:.0f}%</td>
      <td class="num">{v['taught']}/{v['sections_with_material']}</td>
      <td class="num">{v['attempts']}</td>
      <td><span class="tag t-{e(v['evidence'].split()[0])}">{e(v['evidence'])}</span></td>
    </tr>"""
        for sid, v in sorted(r["subsections"].items()))

    if est["too_early"]:
        checks = "\n".join(
            f'<li class="{"ok" if c["ok"] else "waiting"}">'
            f'<span class="mark">{"✅" if c["ok"] else "⬜"}</span>'
            f'{e(c["name"])}<span class="detail">{e(c["detail"])}</span></li>'
            for c in est["checks"])
        estimate_block = f"""<div class="estimate early">
      <p class="ehead">Still too early to decide</p>
      <p class="ewhy">{e(est.get('reason', ''))}</p>
      <ul class="checks">{checks}</ul>
    </div>"""
    else:
        estimate_block = f"""<div class="estimate">
      <p class="ehead">~{est['days']} days</p>
      <p class="ewhy">confidence {e(est['confidence'])} · ready around
        {e(est.get('ready_on', ''))}</p>
      <p class="ewhy">Mastery pace puts it at {est.get('days_mastery', '—')} days;
        finishing the course puts it at {est.get('days_coverage', '—')}. The longer
        of the two is the honest answer — you cannot prove readiness on material
        you have not unlocked.</p>
    </div>"""

    leverage = "\n".join(
        f"""<li><span class="mono">{e(l['subsection'])}</span>
        <span class="lgain">+{l['gain']:.1f} pts available</span>
        <span class="detail">{l['weight']:.1f}% of the exam, currently
          {l['readiness'] * 100:.0f}% — {e(l['evidence'])}</span></li>"""
        for l in r["leverage"])

    caveat_items = "\n".join(
        f'<li class="c-{e(c["severity"])}">{e(c["text"])}</li>' for c in r["caveats"])

    blind = r["coverage"]["blind_spots"]
    blind_block = (
        "<p class=\"empty\">None — everything taught has been quizzed at least once.</p>"
        if not blind else
        "<ul class=\"plain\">" + "".join(
            f'<li><span class="mono">{e(k.split("::")[-1])}</span>'
            f'<span class="detail">{e(k.split("::")[0])}</span></li>'
            for k in blind) + "</ul>")

    return f"""<title>PCSE Readiness</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<style>
  :root {{
    --bg:#fafbfd; --panel:#ffffff; --ink:#111418; --muted:#5b6470;
    --line:#d4d9e0; --wash:#f2f5f9; --accent:#1a73e8;
    --good:#188038; --warn:#b06000; --hatch:#c9d1da;
    --shadow:0 1px 2px rgba(17,20,24,.05), 0 8px 24px -18px rgba(17,20,24,.35);
    --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
    --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, system-ui, sans-serif;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#14171c; --panel:#1b1f26; --ink:#e8ecf1; --muted:#98a2b0;
      --line:#2b323c; --wash:#20252d; --accent:#7aa9f7;
      --good:#5bb974; --warn:#e8a33d; --hatch:#39424e;
      --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -18px rgba(0,0,0,.8);
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#14171c; --panel:#1b1f26; --ink:#e8ecf1; --muted:#98a2b0;
    --line:#2b323c; --wash:#20252d; --accent:#7aa9f7;
    --good:#5bb974; --warn:#e8a33d; --hatch:#39424e;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -18px rgba(0,0,0,.8);
  }}
  * {{ box-sizing:border-box; }}
  body {{ background:var(--bg); color:var(--ink); font-family:var(--sans);
         font-size:15px; line-height:1.5; margin:0;
         padding-block:36px; padding-left:20px; padding-right:20px;
         -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:900px; margin:0 auto; display:flex; flex-direction:column; gap:26px; }}
  h1 {{ font-size:21px; margin:0; letter-spacing:-.02em; text-wrap:balance; }}
  h2 {{ font-size:12px; margin:0 0 14px; text-transform:uppercase;
        letter-spacing:.09em; color:var(--muted); font-weight:600; }}
  .eyebrow {{ font-size:12.5px; color:var(--muted); margin:0 0 4px;
              letter-spacing:.04em; }}
  .panel {{ background:var(--panel); border:1px solid var(--line);
            border-radius:10px; padding:22px 24px; box-shadow:var(--shadow); }}
  .num, .mono, td.num {{ font-family:var(--mono); font-variant-numeric:tabular-nums; }}

  /* ── the two headline numbers, on one shared axis ── */
  .heads {{ display:grid; grid-template-columns:1fr 1fr; gap:22px; }}
  .head .label {{ font-size:12.5px; color:var(--muted); letter-spacing:.03em; }}
  .head .value {{ font-family:var(--mono); font-variant-numeric:tabular-nums;
                  font-size:44px; line-height:1.05; letter-spacing:-.03em;
                  margin:2px 0 8px; }}
  .head .note {{ font-size:12.5px; color:var(--muted); }}
  .axis-note {{ margin:18px 0 0; font-size:13.5px; color:var(--muted); }}
  .axis-note strong {{ color:var(--ink); font-weight:600; }}

  .bar {{ position:relative; height:11px; border-radius:3px; overflow:hidden;
          background:repeating-linear-gradient(135deg, var(--wash) 0 5px,
                     var(--hatch) 5px 6px); }}
  .bar-reach {{ position:absolute; inset:0 auto 0 0; background:var(--wash); }}
  .bar-fill {{ position:absolute; inset:0 auto 0 0; border-radius:3px; }}
  .bigbar {{ height:15px; }}

  table {{ border-collapse:collapse; width:100%; }}
  th, td {{ text-align:left; padding:11px 10px; border-bottom:1px solid var(--line);
            vertical-align:middle; font-weight:400; }}
  thead th {{ font-size:11.5px; text-transform:uppercase; letter-spacing:.07em;
              color:var(--muted); padding-bottom:7px; }}
  tbody tr:last-child th, tbody tr:last-child td {{ border-bottom:0; }}
  td.num, th.num {{ text-align:right; white-space:nowrap; }}
  .of {{ color:var(--muted); font-size:12px; }}
  .sq {{ margin-right:7px; }}
  .sname {{ font-weight:600; }}
  .smeta {{ display:block; font-size:12px; color:var(--muted); margin-left:24px; }}
  .barcell {{ width:34%; min-width:120px; }}
  .scroll {{ overflow-x:auto; }}
  .scroll table {{ min-width:520px; }}

  .tag {{ font-size:11.5px; padding:2px 8px; border-radius:99px;
          border:1px solid var(--line); color:var(--muted); white-space:nowrap; }}
  .tag.t-graded {{ color:var(--good); border-color:currentColor; }}
  .tag.t-prior {{ color:var(--warn); border-color:currentColor; }}

  .estimate {{ display:flex; flex-direction:column; gap:6px; }}
  .ehead {{ font-family:var(--mono); font-size:30px; letter-spacing:-.02em;
            margin:0; }}
  .estimate.early .ehead {{ font-size:19px; font-family:var(--sans);
                            font-weight:600; }}
  .ewhy {{ margin:0; font-size:13.5px; color:var(--muted); max-width:62ch; }}
  .checks {{ list-style:none; padding:0; margin:12px 0 0; display:grid; gap:5px; }}
  .checks li {{ display:flex; gap:9px; align-items:baseline; font-size:13.5px; }}
  .checks .mark {{ font-size:11px; }}
  .checks .waiting {{ color:var(--muted); }}
  .detail, .checks .detail {{ color:var(--muted); font-size:12.5px;
                              font-family:var(--mono); margin-left:auto;
                              padding-left:12px; }}
  ul.plain {{ list-style:none; padding:0; margin:0; display:grid; gap:9px; }}
  ul.plain li {{ display:flex; gap:10px; align-items:baseline; flex-wrap:wrap;
                 font-size:13.5px; }}
  .lgain {{ color:var(--accent); font-family:var(--mono); font-size:13px; }}
  .empty {{ color:var(--muted); font-size:13.5px; margin:0; max-width:62ch; }}

  .trend {{ width:100%; height:auto; display:block; }}
  .trend .axis {{ stroke:var(--line); stroke-width:1; }}
  .trend .target {{ stroke:var(--accent); stroke-width:1; stroke-dasharray:4 4; }}
  .trend .line {{ fill:none; stroke:var(--accent); stroke-width:2.5;
                  stroke-linejoin:round; stroke-linecap:round; }}
  .trend .area {{ fill:var(--accent); opacity:.11; stroke:none; }}
  .trend .dot {{ fill:var(--accent); stroke:var(--panel); stroke-width:2.5; }}
  .trend .tick {{ fill:var(--muted); font-size:11px; font-family:var(--mono); }}

  .caveats {{ list-style:none; padding:0; margin:0; display:grid; gap:10px; }}
  .caveats li {{ font-size:13px; color:var(--muted); padding-left:13px;
                 border-left:2px solid var(--line); max-width:70ch; }}
  .caveats li.c-high {{ border-left-color:var(--warn); color:var(--ink); }}
  footer {{ color:var(--muted); font-size:12.5px; text-align:center;
            padding-top:4px; }}
  @media (max-width:640px) {{
    .heads {{ grid-template-columns:1fr; }}
    .head .value {{ font-size:36px; }}
    .detail {{ margin-left:0; padding-left:0; }}
  }}
  @media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; }} }}
</style>

<div class="wrap">
  <header>
    <p class="eyebrow">Professional Cloud Security Engineer</p>
    <h1>Exam readiness · {e(r['as_of'])}</h1>
  </header>

  <section class="panel">
    <div class="heads">
      <div class="head">
        <div class="label">True exam readiness</div>
        <div class="value">{pct(h_['true'])}</div>
        {bar(h_['true'] * 100, h_['reachable'] * 100, 100, 'var(--accent)')}
        <div class="note">of the whole exam</div>
      </div>
      <div class="head">
        <div class="label">On covered material</div>
        <div class="value">{pct(h_['on_covered'])}</div>
        {bar((h_['on_covered'] or 0) * 100, 100, 100, 'var(--good)')}
        <div class="note">of the {pct(h_['reachable'])} you have unlocked</div>
      </div>
    </div>
    <p class="axis-note">The left bar and every section bar below sit on the same
      0–100 exam-weight axis, so their lengths are directly comparable; hatching is
      weight with no ingested material behind it. The right bar is the same
      achievement measured against a smaller denominator — only what you have
      unlocked. <strong>{unreachable}%</strong> of the exam is currently outside it.
      That is a ceiling, not a discount: it cannot be earned however well the
      quizzes go, which is why the right number always reads higher.</p>
  </section>

  <section class="panel">
    <h2>How long</h2>
    {estimate_block}
  </section>

  <section class="panel">
    <h2>By exam section</h2>
    <div class="scroll"><table>
      <thead><tr><th scope="col">Section</th><th scope="col" class="num">Covered</th>
        <th scope="col" class="num">Points</th><th scope="col">Earned / reachable</th></tr></thead>
      <tbody>{section_rows}</tbody>
    </table></div>
  </section>

  <section class="panel">
    <h2>Trend</h2>
    {trend_svg(r['trend'], target)}
  </section>

  <section class="panel">
    <h2>Where study pays most</h2>
    <ul class="plain">{leverage}</ul>
  </section>

  <section class="panel">
    <h2>Coverage</h2>
    <div class="scroll"><table>
      <tbody>
        <tr><th scope="row">Course pages ingested</th>
          <td class="num">{cov['course_pages_ingested']}/{cov['course_pages_total']}</td></tr>
        <tr><th scope="row">Sections taught</th>
          <td class="num">{cov['sections_taught']}/{cov['sections_teachable']}</td></tr>
        <tr><th scope="row">Taught sections quizzed</th>
          <td class="num">{cov['sections_quizzed']}/{cov['sections_taught']}</td></tr>
        <tr><th scope="row">Angles of new material remaining</th>
          <td class="num">{e(cov['angles_remaining'])}</td></tr>
      </tbody>
    </table></div>
  </section>

  <section class="panel">
    <h2>Blind spots — taught, never quizzed</h2>
    {blind_block}
  </section>

  <section class="panel">
    <h2>Every subsection</h2>
    <div class="scroll"><table>
      <thead><tr><th scope="col">§</th><th scope="col" class="num">Weight</th>
        <th scope="col" class="num">Ready</th><th scope="col" class="num">Taught</th>
        <th scope="col" class="num">Asked</th><th scope="col">Evidence</th></tr></thead>
      <tbody>{sub_rows}</tbody>
    </table></div>
  </section>

  <section class="panel">
    <h2>What these numbers are not</h2>
    <ul class="caveats">{caveat_items}</ul>
  </section>

  <footer>{ev['graded_quizzes']} graded quiz(zes) · {ev['answered']} answered ·
    {ev['skipped']} skipped · target {target * 100:.0f}% is ours, not Google's</footer>
</div>
"""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    if not READINESS.exists():
        print("no state.local/readiness.json — run build_readiness.py first",
              file=sys.stderr)
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(json.loads(READINESS.read_text())))
    print(f"dashboard: {out.stat().st_size // 1024}KB")
    print(f"-> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
